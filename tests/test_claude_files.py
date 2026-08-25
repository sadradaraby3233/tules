import json


def test_read_uses_claude_offset_limit_and_line_numbers(agent):
	result = agent.run({"action": "Read", "file_path": "notes.md", "offset": 2, "limit": 1})
	assert result.success
	assert result.details["content"] == "     2→alpha"
	assert result.details["truncated"] is True


def test_edit_is_unique_by_default_and_supports_replace_all(agent):
	path = agent.root / "many.txt"
	path.write_text("one\none\n", encoding="utf-8")
	failed = agent.run(
		{"action": "Edit", "file_path": "many.txt", "old_string": "one", "new_string": "two"}
	)
	assert not failed.success and failed.details["occurrences"] == 2
	result = agent.run(
		{
			"action": "Edit",
			"file_path": "many.txt",
			"old_string": "one",
			"new_string": "two",
			"replace_all": True,
		}
	)
	assert result.success
	assert path.read_text() == "two\ntwo\n"


def test_edit_normalizes_curly_quotes(agent):
	path = agent.root / "quotes.md"
	path.write_text("Say “hello” now\n", encoding="utf-8")
	result = agent.run(
		{
			"action": "edit",
			"file_path": "quotes.md",
			"old_string": 'Say "hello" now',
			"new_string": "Done",
		}
	)
	assert result.success
	assert result.details["match_level"] == "normalized_quotes"


def test_write_creates_and_overwrites_with_backup(agent):
	assert (
		agent.run({"action": "write", "file_path": "new.txt", "content": "first\n"}).details["type"]
		== "create"
	)
	result = agent.run({"action": "write", "file_path": "new.txt", "content": "second\n"})
	assert result.details["type"] == "update"
	assert "backup" in result.details


def test_glob_supports_recursive_patterns(agent):
	(agent.root / "src").mkdir()
	(agent.root / "src" / "a.py").write_text("x = 1\n")
	result = agent.run({"action": "glob", "pattern": "**/*.py"})
	assert "src/a.py" in result.details["filenames"]


def test_grep_modes_filters_context_and_pagination(agent):
	result = agent.run(
		{"action": "grep", "pattern": "greet", "glob": "*.py", "output_mode": "content", "-C": 1}
	)
	assert result.success
	assert "sample.py:4:def greet" in result.details["content"]
	counts = agent.run({"action": "grep", "pattern": "greet", "output_mode": "count"})
	assert counts.details["num_matches"] == 2
	assert "sample.py:2" in counts.details["content"]


def test_notebook_edit_replaces_inserts_and_deletes(agent):
	path = agent.root / "book.ipynb"
	path.write_text(
		json.dumps(
			{
				"cells": [{"id": "a", "cell_type": "markdown", "metadata": {}, "source": ["old"]}],
				"metadata": {},
				"nbformat": 4,
				"nbformat_minor": 5,
			}
		)
	)
	result = agent.run(
		{
			"action": "notebook_edit",
			"notebook_path": "book.ipynb",
			"cell_id": "a",
			"new_source": "new",
		}
	)
	assert result.success
	assert json.loads(path.read_text())["cells"][0]["source"] == ["new"]
	inserted = agent.run(
		{
			"action": "notebook_edit",
			"notebook_path": "book.ipynb",
			"cell_id": "a",
			"new_source": "print(1)",
			"cell_type": "code",
			"edit_mode": "insert",
		}
	)
	cell_id = inserted.details["cell_id"]
	assert agent.run(
		{
			"action": "notebook_edit",
			"notebook_path": "book.ipynb",
			"cell_id": cell_id,
			"new_source": "",
			"edit_mode": "delete",
		}
	).success
