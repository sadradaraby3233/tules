import pytest

from tules.errors import WorkspaceError


def test_resolve_rejects_paths_outside_the_root(workspace):
	with pytest.raises(WorkspaceError):
		workspace.resolve("../escape.py")


def test_resolve_rejects_absolute_paths_elsewhere(workspace, tmp_path):
	with pytest.raises(WorkspaceError):
		workspace.resolve(str(tmp_path.parent / "other.py"))


def test_require_reports_a_missing_file(workspace):
	with pytest.raises(WorkspaceError):
		workspace.require("nope.py")


def test_load_normalizes_line_endings_and_remembers_them(workspace):
	path = workspace.root / "crlf.py"
	path.write_bytes(b"a = 1\r\nb = 2\r\n")
	document = workspace.load("crlf.py")
	assert "\r" not in document.text
	assert document.newline == "\r\n"


def test_save_restores_the_original_line_endings(workspace):
	path = workspace.root / "crlf.py"
	path.write_bytes(b"a = 1\r\nb = 2\r\n")
	document = workspace.load("crlf.py")
	workspace.save(document, document.text.replace("1", "3"))
	assert path.read_bytes() == b"a = 3\r\nb = 2\r\n"


def test_backups_only_match_the_same_file(workspace):
	(workspace.root / "sample_helper.py").write_text("x = 1\n", encoding="utf-8")
	workspace.back_up(workspace.root / "sample_helper.py")
	assert workspace.backups_of(workspace.root / "sample.py") == []


def test_restore_brings_back_the_previous_content(workspace):
	document = workspace.load("sample.py")
	workspace.save(document, "broken = True\n")
	workspace.restore(document.path)
	assert document.path.read_text(encoding="utf-8") == document.text


def test_rapid_backups_are_unique_and_restore_the_latest_version(workspace):
	path = workspace.root / "notes.md"
	first = workspace.load("notes.md")
	workspace.save(first, "second\n")
	second = workspace.load("notes.md")
	workspace.save(second, "third\n")

	backups = workspace.backups_of(path)
	assert len(backups) == 2
	assert len({backup.name for backup in backups}) == 2
	workspace.restore(path)
	assert path.read_text(encoding="utf-8") == "second\n"


def test_atomic_write_preserves_existing_permissions(workspace):
	path = workspace.root / "notes.md"
	path.chmod(0o640)
	workspace.write(path, "replacement\n")
	assert path.read_text(encoding="utf-8") == "replacement\n"
	assert path.stat().st_mode & 0o777 == 0o640
	assert not list(workspace.root.glob(".notes.md.*"))


def test_walk_skips_the_backup_directory(workspace):
	workspace.back_up(workspace.root / "sample.py")
	names = {path.name for path in workspace.walk()}
	assert names == {"sample.py", "notes.md"}
