"""Filesystem access confined to a single project root."""

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional, Set

from .errors import WorkspaceError

BACKUP_DIR = ".tules_backups"
STATE_DIR = ".tules"

TEXT_SUFFIXES: Set[str] = {
	".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".c", ".h", ".hpp",
	".cs", ".html", ".css", ".scss", ".json", ".xml", ".yaml", ".yml", ".toml",
	".ini", ".cfg", ".md", ".rst", ".txt", ".sql", ".sh", ".bash", ".rb", ".go",
	".rs", ".swift", ".kt", ".php", ".lua", ".nvgt",
}

SKIPPED_DIRS: Set[str] = {
	"__pycache__", ".git", ".hg", ".svn", "node_modules", "venv", ".venv", "env",
	"dist", "build", ".idea", ".vscode", ".mypy_cache", ".pytest_cache", ".tox",
	"target", "bin", "obj", "site-packages", BACKUP_DIR, STATE_DIR,
}

MAX_TEXT_BYTES = 4 * 1024 * 1024
BACKUP_STAMP = "%Y%m%d_%H%M%S"


@dataclass
class Document:
	"""A text file loaded with its line endings normalized to ``\n``."""

	path: Path
	relpath: str
	text: str
	newline: str

	@property
	def lines(self):
		return self.text.split("\n")


class Workspace:
	"""Resolves, reads, writes and backs up files below a fixed root."""

	def __init__(self, root: str = "."):
		self.root = Path(root).expanduser().resolve()
		if not self.root.is_dir():
			raise WorkspaceError(f"Not a directory: {self.root}")
		self.backup_root = self.root / BACKUP_DIR
		self.state_root = self.root / STATE_DIR

	def resolve(self, relpath: str) -> Path:
		if not relpath:
			raise WorkspaceError("Missing file path")
		candidate = (self.root / relpath).expanduser()
		try:
			resolved = candidate.resolve()
		except OSError as exc:
			raise WorkspaceError(f"Invalid path {relpath!r}: {exc}") from exc
		if resolved != self.root and self.root not in resolved.parents:
			raise WorkspaceError(f"Path escapes the workspace: {relpath}")
		return resolved

	def require(self, relpath: str) -> Path:
		path = self.resolve(relpath)
		if not path.exists():
			raise WorkspaceError(f"File not found: {relpath}")
		if not path.is_file():
			raise WorkspaceError(f"Not a file: {relpath}")
		return path

	def relativize(self, path: Path) -> str:
		try:
			return path.relative_to(self.root).as_posix()
		except ValueError:
			return str(path)

	def includes(self, path: Path) -> bool:
		if path.suffix.lower() not in TEXT_SUFFIXES:
			return False
		try:
			parts = path.relative_to(self.root).parts
		except ValueError:
			return False
		if any(part in SKIPPED_DIRS for part in parts[:-1]):
			return False
		try:
			return path.is_file() and path.stat().st_size <= MAX_TEXT_BYTES
		except OSError:
			return False

	def walk(self, suffix: Optional[str] = None) -> Iterator[Path]:
		pattern = f"*{suffix}" if suffix else "*"
		for path in self.root.rglob(pattern):
			if self.includes(path):
				yield path

	def load(self, relpath: str, strict: bool = True) -> Document:
		path = self.require(relpath)
		return self.load_path(path, strict=strict)

	def load_path(self, path: Path, strict: bool = True) -> Document:
		try:
			raw = path.read_bytes()
		except OSError as exc:
			raise WorkspaceError(f"Cannot read {self.relativize(path)}: {exc}") from exc
		try:
			text = raw.decode("utf-8", errors="strict" if strict else "replace")
		except UnicodeDecodeError as exc:
			raise WorkspaceError(f"Not UTF-8 text: {self.relativize(path)}") from exc
		newline = "\r\n" if b"\r\n" in raw else "\n"
		return Document(
			path=path,
			relpath=self.relativize(path),
			text=text.replace("\r\n", "\n"),
			newline=newline,
		)

	def save(self, document: Document, text: str) -> Path:
		backup = self.back_up(document.path)
		self.write(document.path, text, document.newline)
		return backup

	def write(self, path: Path, text: str, newline: str = "\n") -> None:
		path.parent.mkdir(parents=True, exist_ok=True)
		try:
			path.write_bytes(text.replace("\n", newline).encode("utf-8"))
		except OSError as exc:
			raise WorkspaceError(f"Cannot write {self.relativize(path)}: {exc}") from exc

	def back_up(self, path: Path) -> Path:
		stamp = datetime.now().strftime(BACKUP_STAMP)
		target = self.backup_root / path.parent.relative_to(self.root)
		target.mkdir(parents=True, exist_ok=True)
		backup = target / f"{path.stem}_{stamp}{path.suffix}"
		shutil.copy2(path, backup)
		return backup

	def backups_of(self, path: Path) -> list:
		folder = self.backup_root / path.parent.relative_to(self.root)
		if not folder.is_dir():
			return []
		pattern = re.compile(rf"^{re.escape(path.stem)}_\d{{8}}_\d{{6}}$")
		found = [
			item for item in folder.iterdir()
			if item.is_file() and item.suffix == path.suffix and pattern.match(item.stem)
		]
		return sorted(found, key=lambda f: f.name, reverse=True)

	def restore(self, path: Path) -> Path:
		backups = self.backups_of(path)
		if not backups:
			raise WorkspaceError(f"No backup found for {self.relativize(path)}")
		latest = backups[0]
		path.parent.mkdir(parents=True, exist_ok=True)
		shutil.copy2(latest, path)
		return latest

	def state_file(self, name: str) -> Path:
		self.state_root.mkdir(exist_ok=True)
		return self.state_root / name
