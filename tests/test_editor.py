import pytest

from tules.editor import Editor, check_json, check_syntax
from tules.errors import MatchError, SyntaxGuardError, TulesError, WorkspaceError


@pytest.fixture
def editor(workspace) -> Editor:
	return Editor(workspace)


def read(workspace, name="sample.py") -> str:
	return (workspace.root / name).read_text(encoding="utf-8")


def test_replace_unique_edits_and_backs_up(editor, workspace):
	result = editor.replace_unique("sample.py", "hello", "hi", "test")
	assert result.success
	assert "hi {name}" in read(workspace)
	assert workspace.backups_of(workspace.root / "sample.py")


def test_replace_unique_refuses_several_matches(editor, workspace):
	(workspace.root / "twice.py").write_text("a = 1\na = 1\n", encoding="utf-8")
	with pytest.raises(MatchError) as caught:
		editor.replace_unique("twice.py", "a = 1", "a = 2", "test")
	assert "NOT_UNIQUE" in caught.value.message


def test_missing_search_reports_the_closest_match(editor):
	with pytest.raises(MatchError) as caught:
		editor.replace_unique("sample.py", "def greet(nam):", "x", "test")
	assert "closest_match" in caught.value.details


def test_syntax_guard_blocks_a_broken_edit(editor, workspace):
	with pytest.raises(SyntaxGuardError) as caught:
		editor.replace_unique("sample.py", "def greet(name):", "def greet(name:", "test")
	assert caught.value.details["error"].startswith("SyntaxError")
	assert "def greet(name):" in read(workspace)


def test_identical_replacement_is_rejected(editor):
	with pytest.raises(TulesError) as caught:
		editor.replace_unique("sample.py", "hello", "hello", "test")
	assert "NO_CHANGE" in caught.value.message


def test_replace_flexible_matches_across_indentation(editor, workspace):
	result = editor.replace_flexible(
		"sample.py",
		"def build(self):\n\t\t\t\treturn greet(\"widget\")",
		"\tdef build(self):\n\t\treturn greet(\"gadget\")",
		"test",
	)
	assert result.details["match_level"] == "whitespace"
	assert "gadget" in read(workspace)


def test_replace_flexible_falls_back_to_the_ast(editor, workspace):
	replacement = "def greet(name):\n\treturn name.upper()"
	result = editor.replace_flexible("sample.py", "def greet(name): ...", replacement, "test")
	assert result.details["match_level"] == "ast"
	assert "name.upper()" in read(workspace)


def test_replace_in_context_tolerates_smart_quotes(editor, workspace):
	result = editor.replace_in_context(
		"sample.py", "\t\treturn greet(“widget”)", "\t\treturn greet(\"gadget\")",
		threshold=0.6)
	assert result.success
	assert "gadget" in read(workspace)


def test_replace_in_context_refuses_a_weak_match(editor):
	with pytest.raises(MatchError) as caught:
		editor.replace_in_context("sample.py", "totally different line here", "x = 1")
	assert "LOW_CONFIDENCE" in caught.value.message
	assert "closest_match" in caught.value.details


def test_replace_in_context_reindents_the_replacement(editor, workspace):
	result = editor.replace_in_context(
		"sample.py",
		"def build(self):\n        return greet(\"widget\")",
		"def build(self):\n\treturn greet(\"gadget\")",
		threshold=0.6,
	)
	assert result.details["indent_adjusted"]
	assert "\tdef build(self):\n\t\treturn greet(\"gadget\")" in read(workspace)


def test_replace_lines_swaps_an_inclusive_range(editor, workspace):
	editor.replace_lines("notes.md", 2, 3, "gamma", "test")
	assert read(workspace, "notes.md") == "# notes\ngamma\n"


def test_replace_lines_validates_the_range(editor):
	with pytest.raises(TulesError):
		editor.replace_lines("notes.md", 5, 2, "x", "test")


def test_delete_and_insert_lines(editor, workspace):
	editor.delete_lines("notes.md", 2, 2, "test")
	assert read(workspace, "notes.md") == "# notes\nbeta\n"
	editor.insert_lines("notes.md", 1, "alpha", "test")
	assert read(workspace, "notes.md") == "# notes\nalpha\nbeta\n"


def test_find_occurrences_numbers_every_match(editor, workspace):
	(workspace.root / "twice.py").write_text("a = 1\nb = 2\na = 1\n", encoding="utf-8")
	found = editor.find_occurrences("twice.py", "a = 1")
	assert [item["id"] for item in found] == [0, 1]
	assert [item["line"] for item in found] == [1, 3]


def test_replace_occurrence_targets_the_chosen_match(editor, workspace):
	(workspace.root / "twice.py").write_text("a = 1\nb = 2\na = 1\n", encoding="utf-8")
	editor.replace_occurrence("twice.py", "a = 1", "a = 9", 1, "test")
	assert read(workspace, "twice.py") == "a = 1\nb = 2\na = 9\n"


def test_create_refuses_to_overwrite(editor):
	with pytest.raises(WorkspaceError):
		editor.create("sample.py", "x = 1")


def test_create_refuses_broken_python(editor):
	with pytest.raises(SyntaxGuardError):
		editor.create("new.py", "def broken(")


def test_remove_backs_the_file_up_first(editor, workspace):
	editor.remove("notes.md")
	assert not (workspace.root / "notes.md").exists()
	assert workspace.backups_of(workspace.root / "notes.md")


def test_preview_does_not_touch_the_file(editor, workspace):
	before = read(workspace)
	result = editor.preview("sample.py", "hello", "hi")
	assert "-\treturn f\"hello {name}\"" in result.details["diff"]
	assert read(workspace) == before


def test_check_syntax_accepts_valid_code():
	assert check_syntax("x = 1\n") is None
	assert "SyntaxError" in check_syntax("x = (\n")


def test_check_json_accepts_valid_and_rejects_broken():
	assert check_json('{"a": 1}') is None
	assert "JSONDecodeError" in check_json('{"a": 1,}')


def test_json_syntax_guard_blocks_a_broken_edit(editor, workspace):
	(workspace.root / "config.json").write_text('{"a": 1, "b": 2}\n', encoding="utf-8")
	with pytest.raises(SyntaxGuardError) as caught:
		editor.replace_unique("config.json", '"b": 2', '"b": 2,', "test")
	assert caught.value.details["error"].startswith("JSONDecodeError")
	assert read(workspace, "config.json") == '{"a": 1, "b": 2}\n'


def test_create_refuses_broken_json(editor):
	with pytest.raises(SyntaxGuardError):
		editor.create("bad.json", '{"a": 1,}')
