"""The brace-language write guard, and keeping ignored files out of search."""

import pytest

from tules import structure
from tules.agent import Agent

BALANCED_JS = "function run() {\n  return 1;\n}\n"


@pytest.fixture()
def project(tmp_path):
	(tmp_path / "app.js").write_text(BALANCED_JS, encoding="utf-8")
	return Agent(str(tmp_path))


# --- The structural guard ---------------------------------------------------


@pytest.mark.parametrize(
	("name", "body", "old", "new"),
	[
		("app.js", BALANCED_JS, "return 1;", "if (x) { return 1;"),
		("app.ts", "function f(): number {\n  return g(1);\n}\n", "g(1);", "g((1;"),
		("main.go", "package main\n\nfunc main() {\n\tp(1)\n}\n", "p(1)", "if true {\n\tp(1)"),
		("m.rs", 'fn main() {\n    p("hi");\n}\n', 'p("hi");', 'if x { p("hi");'),
		("A.java", "class A {\n  void r() {\n    x();\n  }\n}\n", "x();", "if (y) { x();"),
	],
)
def test_an_edit_that_unbalances_a_brace_language_is_refused(tmp_path, name, body, old, new):
	agent = Agent(str(tmp_path))
	(tmp_path / name).write_text(body, encoding="utf-8")
	result = agent.run({"action": "replace", "file": name, "old_string": old, "new_string": new})
	assert not result.success
	assert result.message == "SYNTAX_ERROR_PREVENTED"
	assert (tmp_path / name).read_text(encoding="utf-8") == body


def test_a_balanced_edit_is_still_applied(project):
	result = project.run(
		{
			"action": "replace",
			"file": "app.js",
			"old_string": "return 1;",
			"new_string": "return 2;",
		}
	)
	assert result.success
	assert "return 2;" in (project.root / "app.js").read_text(encoding="utf-8")


def test_a_file_the_scanner_cannot_lex_is_never_blocked(tmp_path):
	"""A regex literal defeats the scanner, so the original is the control and it stands aside."""
	agent = Agent(str(tmp_path))
	body = "const re = /\\{/;\nfunction f() {\n  return 1;\n}\n"
	(tmp_path / "r.js").write_text(body, encoding="utf-8")
	result = agent.run(
		{"action": "replace", "file": "r.js", "old_string": "return 1;", "new_string": "return 2;"}
	)
	assert result.success


def test_an_already_broken_file_can_still_be_repaired(tmp_path):
	"""The guard compares against the original, so it never traps you in a broken file."""
	agent = Agent(str(tmp_path))
	(tmp_path / "b.js").write_text("function f() {\n  return 1;\n", encoding="utf-8")
	result = agent.run(
		{
			"action": "replace",
			"file": "b.js",
			"old_string": "  return 1;\n",
			"new_string": "  return 1;\n}\n",
		}
	)
	assert result.success


def test_languages_without_a_guard_are_left_alone(tmp_path):
	agent = Agent(str(tmp_path))
	(tmp_path / "n.md").write_text("# hi\n\ntext\n", encoding="utf-8")
	result = agent.run(
		{"action": "replace", "file": "n.md", "old_string": "text", "new_string": "text {{{"}
	)
	assert result.success


def test_the_scanner_reports_what_it_can_and_cannot_judge():
	assert structure.balanced(BALANCED_JS, ".js") is True
	assert structure.balanced("function f() {\n", ".js") is False
	assert structure.balanced("x = 1\n", ".py") is None
	assert structure.balanced('let s = r#"{"#;\n', ".rs") is None
	assert structure.balanced("/* never closed\n", ".js") is None
	assert structure.balanced("// { in a comment\nlet a = 1;\n", ".js") is True
	assert structure.balanced('let a = "{";\n', ".js") is True
	assert structure.balanced("let a = (1];\n", ".js") is False


# --- Ignored files ----------------------------------------------------------


@pytest.fixture()
def ignoring(tmp_path):
	(tmp_path / ".gitignore").write_text("secrets/\n*.log\n!keep.log\n", encoding="utf-8")
	for rel, body in {
		"app.py": "TOKEN_MARK = 1\n",
		"secrets/keys.py": "TOKEN_MARK = 'sk-live'\n",
		"debug.log": "TOKEN_MARK\n",
		"keep.log": "TOKEN_MARK\n",
		"src/main.py": "TOKEN_MARK = 2\n",
	}.items():
		path = tmp_path / rel
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(body, encoding="utf-8")
	return tmp_path


def test_search_skips_ignored_files(ignoring):
	agent = Agent(str(ignoring))
	found = {
		match["file"]
		for match in agent.run({"action": "search", "search": "TOKEN"}).details["matches"]
	}
	assert found == {"app.py", "src/main.py"}


def test_grep_and_glob_skip_ignored_files_but_honour_negation(ignoring):
	agent = Agent(str(ignoring))
	names = set(agent.run({"action": "grep", "pattern": "TOKEN"}).details["filenames"])
	assert "secrets/keys.py" not in names and "debug.log" not in names
	assert "keep.log" in names
	assert "secrets/keys.py" not in set(
		agent.run({"action": "glob", "pattern": "**/*"}).details["files"]
	)


def test_an_ignored_file_named_directly_is_still_readable(ignoring):
	"""Ignoring narrows what search surfaces; it must never deny access."""
	result = Agent(str(ignoring)).run({"action": "read_file", "file": "secrets/keys.py"})
	assert result.success
	assert "sk-live" in result.details["content"]


def test_all_files_mode_restores_the_old_behaviour(ignoring):
	agent = Agent(str(ignoring), respect_ignores=False)
	found = {
		match["file"]
		for match in agent.run({"action": "search", "search": "TOKEN"}).details["matches"]
	}
	assert "secrets/keys.py" in found


def test_a_project_without_a_gitignore_is_unaffected(tmp_path):
	(tmp_path / "a.py").write_text("MARK = 1\n", encoding="utf-8")
	agent = Agent(str(tmp_path))
	assert agent.run({"action": "search", "search": "MARK"}).details["matches"]
