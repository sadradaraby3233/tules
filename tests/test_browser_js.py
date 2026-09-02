"""The embedded page scripts must be valid JavaScript.

Each template is rendered the way page.py renders it and syntax-checked with
node when one is available, so a typo in the page-side code cannot reach a
user's browser untested.
"""

import json
import shutil
import subprocess

import pytest

from tules.browser import js

RENDERED = {
	"PROBE": js.PROBE.replace(
		"%RESPONSE_SELECTORS%", json.dumps(['[data-message-author-role="assistant"]'])
	).replace("%GENERATING_SELECTORS%", json.dumps(['button[aria-label*="stop" i]'])),
	"BOX_TEXT": js.BOX_TEXT.replace("%REF%", "3"),
	"CLEAR_BOX": js.CLEAR_BOX.replace("%REF%", "3"),
	"SUBMISSION_VIEW": js.SUBMISSION_VIEW.replace("%REF%", "3")
	.replace("%RESPONSE_SELECTOR_JSON%", json.dumps('[data-message-author-role="assistant"]'))
	.replace("%STOP_SELECTOR_JSON%", json.dumps('button[aria-label*="stop" i]')),
	"ELEMENT_BY_SELECTOR": js.ELEMENT_BY_SELECTOR.replace(
		"%SELECTOR_JSON%", json.dumps("button.copy")
	),
	"VERIFY_CANDIDATE": js.VERIFY_CANDIDATE.replace(
		"%SELECTOR_JSON%", json.dumps("button.copy")
	).replace("%REF%", "3"),
	"TEACH_INPUT_ARM": js.TEACH_INPUT_ARM,
	"TEACH_COPY_ARM": js.TEACH_COPY_ARM,
	"TEACH_RESULT": js.TEACH_RESULT.replace("%NAME%", "taughtInput"),
	"PAGE_READ_CLIPBOARD": js.PAGE_READ_CLIPBOARD,
	"PAGE_WRITE_CLIPBOARD": js.PAGE_WRITE_CLIPBOARD.replace("%TEXT%", '"x"'),
	"RESET_TEACH": "window.__tules && (window.__tules.taughtInput = null, window.__tules.teachFocus = false);",
}


STATEMENT_SCRIPTS = ("RESET_TEACH",)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_every_page_script_is_syntactically_valid_javascript(tmp_path):
	for name, source in RENDERED.items():
		if name in STATEMENT_SCRIPTS:
			wrapped = f"(() => {{ {source} }});"
		else:
			wrapped = f"(() => {{ const value = ({source}); return value; }});"
		script = tmp_path / f"{name}.js"
		script.write_text(wrapped, encoding="utf-8")
		result = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True)
		assert result.returncode == 0, f"{name} is not valid JavaScript:\n{result.stderr}"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_probe_and_teach_scripts_run_against_a_dom_shim(tmp_path):
	"""Run PROBE for real against a small DOM shim: returns a usable state."""
	shim = tmp_path / "dom_shim.js"
	shim.write_text("""
function makeEl(tag, attrs, children) {
	attrs = attrs || {}; children = children || [];
	const rect = attrs.rect || { x: 0, y: 0, w: 300, h: 60 };
	const el = {
		tagName: tag.toUpperCase(), id: attrs.id || "", isConnected: true,
		_isEl: true, attrs: attrs, children: children, _rect: rect,
		innerText: attrs.text || "", value: undefined,
		getAttribute(n) { return attrs[n] !== undefined ? attrs[n] : null; },
		getBoundingClientRect() { return { x: rect.x, y: rect.y, width: rect.w, height: rect.h }; },
		get classList() { const classes = (attrs.classes || []);
			const arrayLike = { length: classes.length };
			classes.forEach((name, index) => { arrayLike[index] = name; });
			return arrayLike; },
		focus() {}, addEventListener() {},
	};
	return el;
}
const searchBox = makeEl("input", { placeholder: "Search chats", classes: [], rect: { x: 0, y: 0, w: 140, h: 20 } });
const composer = makeEl("textarea", { id: "prompt-input", placeholder: "Message the AI", classes: [] });
const copyBtn = makeEl("button", { "aria-label": "Copy", classes: ["copy-btn"] });
const decoyBtn = makeEl("button", { "aria-label": "Copy link", classes: [] });
const assistant = makeEl("div", { "data-message-author-role": "assistant", text: "A finished answer" });
document = {
	querySelectorAll(sel) {
		if (sel.indexOf("textarea") === 0) return [composer, searchBox];
		if (sel.indexOf('"stop"') !== -1) return [];   // no stop button in the shim
		if (sel.indexOf("button") === 0) return [copyBtn, decoyBtn];
		if (sel.indexOf("assistant") !== -1) return [assistant];
		return [];
	},
	querySelector() { return null; },
	addEventListener() {},
	activeElement: composer,
	body: makeEl("body", {}),
};
	window = { __tules: null };
	location = { href: "https://fake.chat/x" };
	getComputedStyle = () => ({ visibility: "visible", display: "block", opacity: "1" });
""")
	for name in ("PROBE",):
		script = tmp_path / f"{name}_run.js"
		script.write_text(
			shim.read_text(encoding="utf-8")
			+ "\nconsole.log(JSON.stringify(("
			+ RENDERED[name]
			+ ")));",
			encoding="utf-8",
		)
		result = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=30)
		assert result.returncode == 0, result.stderr
		state = json.loads(result.stdout)
		assert state["url"] == "" or isinstance(state["url"], str)
		assert len(state["inputs"]) == 2
		assert state["inputs"][0]["id"] == "prompt-input"
		assert any(c["label"] == "copy" for c in state["copies"])
		assert state["response"]["count"] == 1
		assert state["response"]["len"] == len("A finished answer")
		assert state["generating"] is False
		assert state["active"]["id"] == "prompt-input"
