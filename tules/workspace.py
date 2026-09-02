"""Filesystem access confined to a single project root."""

import os
import re
from contextlib import suppress
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional, Set

from .errors import WorkspaceError
from .ignores import Ignores

BACKUP_DIR = ".tules_backups"
STATE_DIR = ".tules"

TEXT_SUFFIXES: Set[str] = {
	".py",
	".js",
	".ts",
	".jsx",
	".tsx",
	".java",
	".cpp",
	".c",
	".h",
	".hpp",
	".cs",
	".html",
	".css",
	".scss",
	".json",
	".xml",
	".yaml",
	".yml",
	".toml",
	".ini",
	".cfg",
	".md",
	".rst",
	".txt",
	".sql",
	".sh",
	".bash",
	".rb",
	".go",
	".rs",
	".swift",
	".kt",
	".php",
	".lua",
	".nvgt",
}

SKIPPED_DIRS: Set[str] = {
	"__pycache__",
	".git",
	".hg",
	".svn",
	"node_modules",
	"venv",
	".venv",
	"env",
	"dist",
	"build",
	".idea",
	".vscode",
	".mypy_cache",
	".pytest_cache",
	".tox",
	"target",
	"bin",
	"obj",
	"site-packages",
	BACKUP_DIR,
	STATE_DIR,
}

MAX_TEXT_BYTES = 4 * 1024 * 1024
BACKUP_STAMP = "%Y%m%d_%H%M%S"
MAX_BACKUPS_PER_FILE = 10


@dataclass
class Document:
	"""A text file loaded with its line endings normalized to ``\n``."""

	path: Path
	relpath: str
	text: str
	newline: str

	@property
	def lines(self) -> List[str]:
		return self.text.split("\n")


class Workspace:
	"""Resolves, reads, writes and backs up files below a fixed root."""

	def __init__(
		self,
		root: str = ".",
		max_backups: int = MAX_BACKUPS_PER_FILE,
		respect_ignores: bool = True,
	):
		self.root = Path(root).expanduser().resolve()
		if not self.root.is_dir():
			raise WorkspaceError(f"Not a directory: {self.root}")
		self.backup_root = self.root / BACKUP_DIR
		self.state_root = self.root / STATE_DIR
		self.max_backups = max_backups
		self.ignores = Ignores.read(self.root) if respect_ignores else Ignores()

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
		if self.ignores.ignored("/".join(parts)):
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
		"""Atomically write UTF-8 text, leaving the old file intact on failure."""
		self.write_bytes(path, text.replace("\n", newline).encode("utf-8"))

	def write_bytes(self, path: Path, data: bytes) -> None:
		"""Atomically write arbitrary bytes and preserve existing permissions."""
		path.parent.mkdir(parents=True, exist_ok=True)
		temporary: Optional[Path] = None
		try:
			with tempfile.NamedTemporaryFile(
				dir=path.parent, prefix=f".{path.name}.", delete=False
			) as handle:
				temporary = Path(handle.name)
				handle.write(data)
				handle.flush()
				os.fsync(handle.fileno())
			if path.exists():
				shutil.copymode(path, temporary)
			os.replace(temporary, path)
		except OSError as exc:
			if temporary is not None:
				with suppress(OSError):
					temporary.unlink(missing_ok=True)
			raise WorkspaceError(f"Cannot write {self.relativize(path)}: {exc}") from exc

	def back_up(self, path: Path) -> Path:
		"""Copy a file to a unique timestamped backup, even after rapid edits."""
		stamp = datetime.now().strftime(BACKUP_STAMP)
		target = self.backup_root / path.parent.relative_to(self.root)
		target.mkdir(parents=True, exist_ok=True)
		backup = target / f"{path.stem}_{stamp}{path.suffix}"
		if backup.exists() or self._stamp_counters(path, stamp):
			# Never reuse a name pruned earlier this second: the counter walks
			# forward past every backup this stamp has already produced, so the
			# newest copy can never sort behind (and be pruned ahead of) an
			# older one.
			counter = max(self._stamp_counters(path, stamp), default=0) + 1
			backup = target / f"{path.stem}_{stamp}_{counter}{path.suffix}"
			while backup.exists():
				counter += 1
				backup = target / f"{path.stem}_{stamp}_{counter}{path.suffix}"
		shutil.copy2(path, backup)
		self._prune_backups(path)
		return backup

	def _stamp_counters(self, path: Path, stamp: str) -> List[int]:
		"""Counters already used by this file's backups stamped ``stamp``."""
		folder = self.backup_root / path.parent.relative_to(self.root)
		if not folder.is_dir():
			return []
		pattern = re.compile(rf"^{re.escape(path.stem)}_{stamp}(?:_(\d+))?$")
		counters = []
		for item in folder.iterdir():
			match = pattern.match(item.stem)
			if item.is_file() and item.suffix == path.suffix and match:
				counters.append(int(match.group(1) or 0))
		return counters

	def _prune_backups(self, path: Path) -> None:
		"""Keep only the newest ``max_backups`` copies of a file; delete the rest."""
		if self.max_backups <= 0:
			return
		for stale in self.backups_of(path)[self.max_backups :]:
			with suppress(OSError):
				stale.unlink()

	def backups_of(self, path: Path) -> List[Path]:
		folder = self.backup_root / path.parent.relative_to(self.root)
		if not folder.is_dir():
			return []
		stamp = re.compile(rf"^{re.escape(path.stem)}_(\d{{8}}_\d{{6}})(?:_(\d+))?$")
		found = []
		for item in folder.iterdir():
			if not item.is_file() or item.suffix != path.suffix:
				continue
			match = stamp.match(item.stem)
			if match:
				# Sort by the creation stamp in the name, not mtime: rapid edits
				# share file metadata with their source, and a copy2 backup can
				# otherwise sort behind older ones. The counter breaks ties, so a
				# second rollover mid-run never demotes the newest backup.
				order = (match.group(1), int(match.group(2) or 0), item.name)
				found.append((order, item))
		return [item for _, item in sorted(found, key=lambda pair: pair[0], reverse=True)]

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
