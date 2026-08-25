import pytest

from tules.errors import WorkspaceError
from tules.workspace import Workspace


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


def test_walk_skips_the_backup_directory(workspace):
	workspace.back_up(workspace.root / "sample.py")
	names = {path.name for path in workspace.walk()}
	assert names == {"sample.py", "notes.md"}


def test_backups_are_pruned_to_the_retention_limit(tmp_path):
	space = Workspace(str(tmp_path), max_backups=3)
	target = tmp_path / "sample.py"
	for value in range(6):
		target.write_text(f"x = {value}\n", encoding="utf-8")
		backup = space.back_up(target)
		# Force distinct timestamps so each copy lands under its own name.
		backup.rename(backup.with_name(f"sample_2026010{value}_000000.py"))
	assert len(space.backups_of(target)) == 3


def test_pruning_keeps_the_newest_backups(tmp_path):
	space = Workspace(str(tmp_path), max_backups=2)
	target = tmp_path / "sample.py"
	for value in range(4):
		target.write_text(f"x = {value}\n", encoding="utf-8")
		backup = space.back_up(target)
		backup.rename(backup.with_name(f"sample_2026010{value}_000000.py"))
	kept = sorted(item.name for item in space.backups_of(target))
	assert kept == ["sample_20260102_000000.py", "sample_20260103_000000.py"]


def test_max_backups_zero_disables_pruning(tmp_path):
	space = Workspace(str(tmp_path), max_backups=0)
	target = tmp_path / "sample.py"
	for value in range(4):
		target.write_text(f"x = {value}\n", encoding="utf-8")
		backup = space.back_up(target)
		backup.rename(backup.with_name(f"sample_2026010{value}_000000.py"))
	assert len(space.backups_of(target)) == 4
