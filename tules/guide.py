"""The small bootstrap prompt, and the per-action usage TULES serves on demand.

The full manual is too large to paste into a chat window. Instead the model gets a
short prompt that teaches the envelope and one escape hatch, then asks TULES for the
usage of each action as it needs it.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .registry import ALIASES, REGISTRY

BOOTSTRAP = """TULES - you are the brain, TULES is the hands on a real local codebase.

To act, put ONE block in your reply (a JSON object, or an array to batch):

edit:
{"action":"view","file":"src/app.py"}
endedit

The user runs it and pastes back:
STATUS: SUCCESS|FAILED / MESSAGE / DETAILS / WARNINGS.

You do NOT know the command set. Ask TULES:
  {"action":"help"}                  -> every action, one line each
  {"action":"help","name":"replace"} -> that action's arguments + example
A wrong call fails harmlessly and replies with the correct usage.

Results are windowed. `truncated: true` means you have NOT seen it all, and the
`next` field is the command to read the rest.

Rules:
- Read or search before editing. Never edit text you have not seen.
- Only STATUS: SUCCESS means it worked.
- Verify after editing: re-read, review, or run the tests.
- Valid JSON: escape backslashes, newlines as \\n. One edit: block per reply.

First move:

edit:
[{"action":"help"},{"action":"analyze"}]
endedit
"""

# Groups keep the on-demand index short; every action must appear in exactly one.
GROUPS: List[Tuple[str, Tuple[str, ...]]] = [
	("READ", ("read_file", "view", "read", "glob", "list_files")),
	("SEARCH", ("search", "search_regex", "search_fuzzy", "grep")),
	(
		"EDIT",
		(
			"replace",
			"replace_by_line",
			"insert",
			"delete",
			"write",
			"create_file",
			"delete_file",
			"undo",
		),
	),
	(
		"CHECK",
		(
			"analyze",
			"extract_symbols",
			"review",
			"check_duplicates",
			"impact_check",
			"diff_preview",
			"validate_batch",
		),
	),
	("RUN", ("bash", "powershell", "run")),
	("WEB", ("web_search", "web_fetch", "download_url")),
	("OTHER", ("memory", "notebook_edit", "list_actions")),
]


@dataclass(frozen=True)
class Usage:
	"""What one action needs, what it accepts, and one copyable example."""

	required: Tuple[str, ...] = ()
	optional: Tuple[str, ...] = ()
	example: str = ""
	note: str = ""


USAGE: Dict[str, Usage] = {
	"analyze": Usage(
		optional=("file",),
		example='{"action":"analyze"}',
		note="omit 'file' for a whole-project survey",
	),
	"bash": Usage(
		required=("command",),
		optional=("timeout", "description"),
		example='{"action":"bash","command":"python -m pytest -q"}',
		note="timeout 1-600 seconds; output is clipped to 30,000 characters",
	),
	"check_duplicates": Usage(
		optional=("file",),
		example='{"action":"check_duplicates"}',
	),
	"create_file": Usage(
		required=("file",),
		optional=("content",),
		example='{"action":"create_file","file":"src/new.py","content":"x = 1\\n"}',
		note="fails if the file already exists; use 'write' to overwrite",
	),
	"delete": Usage(
		required=("file", "line_start", "line_end"),
		optional=("reason",),
		example='{"action":"delete","file":"src/app.py","line_start":10,"line_end":12}',
		note="the range is inclusive and 1-based",
	),
	"delete_file": Usage(
		required=("file",),
		example='{"action":"delete_file","file":"src/old.py"}',
		note="backs the file up first, so 'undo' can restore it",
	),
	"diff_preview": Usage(
		required=("file", "search"),
		optional=("replace_with",),
		example='{"action":"diff_preview","file":"src/app.py","search":"old","replace_with":"new"}',
		note="writes nothing; use it when unsure an edit will land correctly",
	),
	"download_url": Usage(
		required=("url",),
		optional=("file", "max_bytes", "overwrite", "timeout"),
		example='{"action":"download_url","url":"https://example.com/a.json","file":"data/a.json"}',
	),
	"extract_symbols": Usage(
		required=("file",),
		example='{"action":"extract_symbols","file":"src/app.py"}',
	),
	"glob": Usage(
		required=("pattern",),
		optional=("path",),
		example='{"action":"glob","pattern":"**/*.py"}',
		note="newest files first",
	),
	"grep": Usage(
		required=("pattern",),
		optional=("path", "output_mode", "glob", "type", "-i", "context", "head_limit", "offset"),
		example='{"action":"grep","pattern":"def run\\\\(","output_mode":"content","context":2}',
		note="output_mode: files_with_matches (default), content, or count",
	),
	"impact_check": Usage(
		required=("file",),
		example='{"action":"impact_check","file":"src/app.py"}',
		note="run this before renaming or deleting anything",
	),
	"insert": Usage(
		required=("file", "content"),
		optional=("line_start", "reason"),
		example='{"action":"insert","file":"src/app.py","line_start":10,"content":"import os"}',
		note="inserts after line_start; 0 puts the content at the top",
	),
	"list_actions": Usage(
		optional=("name", "limit"),
		example='{"action":"list_actions","name":"replace"}',
		note="also reachable as 'help'; pass 'name' for one action's full usage",
	),
	"list_files": Usage(
		optional=("pattern",),
		example='{"action":"list_files","pattern":"test"}',
		note="'pattern' is a name fragment, not a glob; use 'glob' for globs",
	),
	"memory": Usage(
		optional=("action_type", "target", "content"),
		example='{"action":"memory","action_type":"write","target":"todo","content":"fix parser"}',
		note="action_type: read (default), write, or list; target names the file",
	),
	"notebook_edit": Usage(
		required=("notebook_path",),
		optional=("cell_id", "edit_mode", "cell_type", "new_source"),
		example='{"action":"notebook_edit","notebook_path":"a.ipynb","cell_id":"c1",'
		'"new_source":"print(1)"}',
		note="edit_mode: replace (default), insert, or delete",
	),
	"powershell": Usage(
		required=("command",),
		optional=("timeout", "description"),
		example='{"action":"powershell","command":"Get-ChildItem"}',
		note="timeout 1-600 seconds; output is clipped to 30,000 characters",
	),
	"read": Usage(
		required=("file_path",),
		optional=("offset", "limit"),
		example='{"action":"read","file_path":"src/app.py","offset":1,"limit":200}',
		note="numbered window; 'offset' is a 1-based line number",
	),
	"read_file": Usage(
		required=("file",),
		optional=("start_line", "end_line"),
		example='{"action":"read_file","file":"pyproject.toml"}',
		note="raw text, no line numbers; use 'view' when you need to quote lines back",
	),
	"replace": Usage(
		required=("file", "old_string", "new_string"),
		optional=(
			"context_before",
			"context_after",
			"match_id",
			"replace_all",
			"confidence_threshold",
			"reason",
		),
		example='{"action":"replace","file":"src/app.py","old_string":"def run(",'
		'"new_string":"def start("}',
		note="one universal engine: exact, then unique, then context-anchored, then fuzzy. "
		"On NOT_UNIQUE add context_before/context_after or match_id, never replace_all blindly",
	),
	"replace_by_line": Usage(
		required=("file", "line_start", "line_end"),
		optional=("replace_with", "reason"),
		example='{"action":"replace_by_line","file":"src/app.py","line_start":4,"line_end":6,'
		'"replace_with":"pass"}',
		note="the range is inclusive; re-read first, line numbers move after every edit",
	),
	"review": Usage(
		required=("file",),
		example='{"action":"review","file":"src/app.py"}',
	),
	"run": Usage(
		required=("command",),
		optional=("timeout",),
		example='{"action":"run","command":"python -m pytest -q"}',
		note="kept for compatibility; prefer 'bash' or 'powershell'",
	),
	"search": Usage(
		required=("search",),
		optional=("case_sensitive", "whole_word"),
		example='{"action":"search","search":"Widget"}',
	),
	"search_fuzzy": Usage(
		required=("search",),
		optional=("threshold",),
		example='{"action":"search_fuzzy","search":"def run(self)","threshold":0.8}',
	),
	"search_regex": Usage(
		required=("search",),
		example='{"action":"search_regex","search":"class \\\\w+Error"}',
		note="escape backslashes for JSON: \\\\b not \\b",
	),
	"undo": Usage(
		required=("file",),
		example='{"action":"undo","file":"src/app.py"}',
		note="restores the most recent backup of that file",
	),
	"validate_batch": Usage(
		required=("commands",),
		example='{"action":"validate_batch","commands":[{"action":"replace","file":"a.py",'
		'"old_string":"x","new_string":"y"}]}',
		note="dry run: checks each command would land before you send it for real",
	),
	"view": Usage(
		required=("file",),
		optional=("start_line", "end_line"),
		example='{"action":"view","file":"src/app.py","start_line":1,"end_line":200}',
		note="line-numbered, so you can quote exact text back into a replace",
	),
	"web_fetch": Usage(
		required=("url",),
		optional=("mode", "max_bytes", "start_line", "end_line", "tag", "id", "class"),
		example='{"action":"web_fetch","url":"https://example.com","mode":"text"}',
		note="mode: text (default), html, links, or elements",
	),
	"web_search": Usage(
		required=("query",),
		optional=("limit", "offset", "language"),
		example='{"action":"web_search","query":"python asyncio timeout"}',
	),
	"write": Usage(
		required=("file_path", "content"),
		example='{"action":"write","file_path":"src/app.py","content":"x = 1\\n"}',
		note="overwrites the whole file after backing it up; prefer 'replace' for edits",
	),
}


def index() -> str:
	"""One compact line per group: the whole command set in well under 1,000 characters."""
	lines = []
	for label, names in GROUPS:
		entries = [f"{name}({','.join(USAGE[name].required)})" for name in names]
		lines.append(f"{label:<7} {' '.join(entries)}")
	lines.append("")
	lines.append('Ask {"action":"help","name":"<action>"} for arguments and an example.')
	return "\n".join(lines)


def detail(name: str) -> str:
	"""The full usage of one action: summary, arguments, caveat, and a copyable example."""
	usage = USAGE[name]
	lines = [f"{name} - {REGISTRY[name].summary}"]
	if usage.required:
		lines.append(f"  required: {', '.join(usage.required)}")
	if usage.optional:
		lines.append(f"  optional: {', '.join(usage.optional)}")
	if usage.note:
		lines.append(f"  note: {usage.note}")
	lines.append(f"  example: {usage.example}")
	return "\n".join(lines)


def resolve(name: str) -> Optional[str]:
	"""Map a requested help topic onto a canonical action name, tolerating aliases."""
	wanted = name.strip().lower()
	target = wanted if wanted in USAGE else ALIASES.get(wanted, "")
	return target if target in USAGE else None
