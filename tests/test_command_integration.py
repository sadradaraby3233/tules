"""End-to-end command tests: every registered action plus important failure edges."""

import json

import pytest

from tules.commands import web
from tules.registry import REGISTRY


def run_ok(agent, payload):
	result = agent.run(payload)
	assert result.success, (payload, result.message, result.details)
	return result


def test_every_registered_command_has_an_end_to_end_success_path(agent, monkeypatch):
	root = agent.root

	def fake_web_request(url, timeout, max_bytes):
		if "google.com/search" in url:
			body = b'<a href="/url?q=https%3A%2F%2Fexample.com%2F">Example</a>'
			return body, url, "text/html", 200
		return b"<html><title>Example</title><body>page</body></html>", url, "text/html", 200

	monkeypatch.setattr(web, "_request", fake_web_request)
	(root / "other.py").write_text("import sample\n\ndef greet():\n\treturn sample.greet('x')\n")
	(root / "book.ipynb").write_text(
		json.dumps(
			{
				"cells": [
					{"id": "cell-a", "cell_type": "markdown", "metadata": {}, "source": ["old"]}
				],
				"metadata": {},
				"nbformat": 4,
				"nbformat_minor": 5,
			}
		)
	)

	# Read-only operations and project inspection.
	payloads = {
		"read_file": {"action": "read_file", "file": "notes.md"},
		"read": {"action": "read", "file_path": "notes.md", "offset": 1, "limit": 2},
		"view": {"action": "view", "file": "notes.md", "start_line": 1, "end_line": 2},
		"list_files": {"action": "list_files", "pattern": "sample"},
		"glob": {"action": "glob", "pattern": "**/*.py"},
		"search": {"action": "search", "search": "greet"},
		"search_regex": {"action": "search_regex", "search": r"def\s+greet"},
		"search_fuzzy": {"action": "search_fuzzy", "search": "def greet(name):", "threshold": 0.8},
		"grep": {"action": "grep", "pattern": "greet", "output_mode": "content"},
		"analyze": {"action": "analyze", "file": "sample.py"},
		"extract_symbols": {"action": "extract_symbols", "file": "sample.py"},
		"review": {"action": "review", "file": "sample.py"},
		"check_duplicates": {"action": "check_duplicates"},
		"impact_check": {"action": "impact_check", "file": "sample.py"},
		"diff_preview": {
			"action": "diff_preview",
			"file": "notes.md",
			"search": "alpha",
			"replace_with": "ALPHA",
		},
		"validate_batch": {
			"action": "validate_batch",
			"commands": [{"action": "read_file", "file": "notes.md"}],
		},
		"list_actions": {"action": "list_actions"},
		"memory": {"action": "memory", "action_type": "read"},
		"run": {"action": "run", "command": "printf integration-ok"},
		"bash": {"action": "bash", "command": "printf bash-ok", "description": "smoke test"},
		"web_search": {"action": "web_search", "query": "example"},
		"web_fetch": {"action": "web_fetch", "url": "https://example.com"},
		"download_url": {
			"action": "download_url",
			"url": "https://example.com/file.html",
			"file": "downloaded.html",
		},
	}
	for payload in payloads.values():
		run_ok(agent, payload)
	powershell_result = agent.run({"action": "powershell", "command": "Write-Output 'ok'"})
	if not powershell_result.success:
		assert "not installed" in powershell_result.message.lower()

	# Mutations use separate files so every command gets a genuine successful write.
	mutations = {
		"str_replace": ("str.txt", "one\n", {"old_str": "one", "new_str": "two"}),
		"edit": (
			"edit.txt",
			"one\n",
			{"file_path": "edit.txt", "old_string": "one", "new_string": "two"},
		),
		"replace": ("replace.txt", "one\n", {"search": "one", "replace_with": "two"}),
		"search_and_replace_all": (
			"all.txt",
			"one one\n",
			{"search": "one", "replace_with": "two"},
		),
		"surgical_replace": ("surgical.txt", "  one\n", {"search": "one", "replace_with": "two"}),
		"context_replace": (
			"context.txt",
			"before\none\nafter\n",
			{"search": "one", "replace_with": "two"},
		),
		"replace_by_line": (
			"lines.txt",
			"one\ntwo\n",
			{"line_start": 1, "line_end": 1, "replace_with": "ONE"},
		),
		"insert": ("insert.txt", "one\n", {"line_start": 1, "content": "two"}),
		"delete": ("delete.txt", "one\ntwo\n", {"line_start": 1, "line_end": 1}),
	}
	for action, (filename, initial, fields) in mutations.items():
		(root / filename).write_text(initial)
		payload = {"action": action, "file": filename, **fields}
		run_ok(agent, payload)

	(root / "smart.txt").write_text("one\none\n")
	ambiguous = agent.run(
		{"action": "smart_replace", "file": "smart.txt", "search": "one", "replace_with": "two"}
	)
	assert not ambiguous.success
	run_ok(
		agent,
		{
			"action": "confirm_smart_replace",
			"file": "smart.txt",
			"search": "one",
			"replace_with": "two",
			"match_id": 1,
		},
	)

	run_ok(agent, {"action": "create_file", "file": "created.txt", "content": "created\n"})
	run_ok(agent, {"action": "write", "file_path": "written.txt", "content": "written\n"})
	(root / "remove.txt").write_text("remove\n")
	run_ok(agent, {"action": "delete_file", "file": "remove.txt"})
	(root / "undo.txt").write_text("before\n")
	run_ok(
		agent,
		{"action": "str_replace", "file": "undo.txt", "old_str": "before", "new_str": "after"},
	)
	run_ok(agent, {"action": "undo", "file": "undo.txt"})
	run_ok(
		agent,
		{
			"action": "notebook_edit",
			"notebook_path": "book.ipynb",
			"cell_id": "cell-a",
			"new_source": "new",
		},
	)

	covered = (
		set(payloads)
		| set(mutations)
		| {
			"powershell",
			"create_file",
			"write",
			"delete_file",
			"undo",
			"notebook_edit",
		}
	)
	assert not set(REGISTRY) - covered, (
		f"Commands without an integration path: {set(REGISTRY) - covered}"
	)


@pytest.mark.parametrize(
	"payload,message",
	[
		({"action": "read", "file_path": "notes.md", "offset": 0}, "positive"),
		({"action": "read", "file_path": "missing.md"}, "not found"),
		({"action": "glob", "pattern": "*", "path": "notes.md"}, "not a directory"),
		({"action": "grep", "pattern": "["}, "invalid regex"),
		({"action": "grep", "pattern": "x", "output_mode": "wrong"}, "output_mode"),
		(
			{"action": "str_replace", "file": "notes.md", "old_str": "missing", "new_str": "x"},
			"no_confident_match",
		),
		(
			{
				"action": "replace_by_line",
				"file": "notes.md",
				"line_start": 99,
				"line_end": 99,
				"replace_with": "x",
			},
			"past the end",
		),
		({"action": "create_file", "file": "notes.md"}, "already exists"),
		({"action": "delete_file", "file": "missing.md"}, "not found"),
		({"action": "undo", "file": "notes.md"}, "no backup"),
		({"action": "run", "command": "exit 7"}, "exit code 7"),
	],
)
def test_command_failure_edges_are_structured(agent, payload, message):
	result = agent.run(payload)
	assert not result.success
	assert message in result.message.lower()


def test_path_escape_is_rejected_through_read_write_search_and_edit(agent):
	for payload in [
		{"action": "read_file", "file": "../outside.txt"},
		{"action": "write", "file_path": "../outside.txt", "content": "x"},
		{"action": "grep", "pattern": "x", "path": ".."},
		{"action": "edit", "file_path": "../outside.txt", "old_string": "", "new_string": "x"},
	]:
		result = agent.run(payload)
		assert not result.success
		assert "escape" in result.message.lower()


def test_python_syntax_guard_covers_edit_write_create_and_line_operations(agent):
	for payload in [
		{
			"action": "str_replace",
			"file": "sample.py",
			"old_str": "def greet(name):",
			"new_str": "def greet(name:",
		},
		{"action": "write", "file_path": "sample.py", "content": "def broken("},
		{"action": "create_file", "file": "broken.py", "content": "def broken("},
		{
			"action": "replace_by_line",
			"file": "sample.py",
			"line_start": 4,
			"line_end": 4,
			"replace_with": "def broken(",
		},
	]:
		before = (agent.root / "sample.py").read_text()
		result = agent.run(payload)
		assert not result.success
		assert "syntax" in result.message.lower()
		assert (agent.root / "sample.py").read_text() == before


def test_grep_filters_modes_context_and_pagination_in_real_workspace(agent):
	(agent.root / "nested").mkdir()
	(agent.root / "nested" / "a.py").write_text("before\nNeedle\nafter\nNeedle\n")
	(agent.root / "nested" / "a.js").write_text("Needle\n")

	content = run_ok(
		agent,
		{
			"action": "grep",
			"pattern": "needle",
			"path": "nested",
			"type": "py",
			"-i": True,
			"output_mode": "content",
			"-C": 1,
			"head_limit": 2,
		},
	)
	assert content.details["num_matches"] == 2
	assert content.details["num_lines"] == 2
	assert content.details["truncated"] is True
	page = run_ok(
		agent,
		{
			"action": "grep",
			"pattern": "Needle",
			"path": "nested",
			"glob": "*.py",
			"output_mode": "content",
			"head_limit": 2,
			"offset": 2,
		},
	)
	assert page.details["applied_offset"] == 2
	counts = run_ok(
		agent, {"action": "grep", "pattern": "Needle", "path": "nested", "output_mode": "count"}
	)
	assert counts.details["num_files"] == 2
	assert counts.details["num_matches"] == 3


def test_notebook_all_modes_and_invalid_edges(agent):
	path = agent.root / "edge.ipynb"
	path.write_text(
		json.dumps(
			{
				"cells": [{"id": "a", "cell_type": "markdown", "metadata": {}, "source": ["a"]}],
				"metadata": {},
				"nbformat": 4,
				"nbformat_minor": 5,
			}
		)
	)
	inserted = run_ok(
		agent,
		{
			"action": "notebook_edit",
			"notebook_path": "edge.ipynb",
			"cell_id": "a",
			"new_source": "print(1)",
			"cell_type": "code",
			"edit_mode": "insert",
		},
	)
	cell_id = inserted.details["cell_id"]
	run_ok(
		agent,
		{
			"action": "notebook_edit",
			"notebook_path": "edge.ipynb",
			"cell_id": cell_id,
			"new_source": "",
			"edit_mode": "delete",
		},
	)
	for payload in [
		{"action": "notebook_edit", "notebook_path": "edge.txt", "new_source": "x"},
		{
			"action": "notebook_edit",
			"notebook_path": "edge.ipynb",
			"cell_id": "missing",
			"new_source": "x",
		},
		{
			"action": "notebook_edit",
			"notebook_path": "edge.ipynb",
			"new_source": "x",
			"edit_mode": "insert",
		},
	]:
		assert not agent.run(payload).success


def test_shell_disabled_timeout_and_output_clipping(workspace):
	from tules.agent import Agent

	disabled = Agent(str(workspace.root), allow_shell=False)
	assert "disabled" in disabled.run({"action": "run", "command": "echo no"}).message.lower()
	timed = Agent(str(workspace.root), shell_timeout=1)
	assert "timed out" in timed.run({"action": "run", "command": "sleep 2"}).message.lower()
	result = run_ok(timed, {"action": "run", "command": "python -c \"print('x'*40000)\""})
	assert len(result.details["stdout"]) == 30_000
	assert result.details["truncated"] is True


def test_empty_no_match_and_no_issue_results_are_successful(agent):
	assert (
		run_ok(agent, {"action": "search", "search": "definitely absent"}).details["matches"] == []
	)
	assert run_ok(agent, {"action": "glob", "pattern": "**/*.never"}).details["filenames"] == []
	assert (
		run_ok(agent, {"action": "grep", "pattern": "definitely absent"}).details["num_matches"]
		== 0
	)
	(agent.root / "clean.py").write_text("x = 1\n")
	assert run_ok(agent, {"action": "review", "file": "clean.py"}).details["issues"] == []
	assert run_ok(agent, {"action": "impact_check", "file": "clean.py"}).details["dependents"] == []
