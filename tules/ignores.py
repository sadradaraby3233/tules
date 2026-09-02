"""A useful subset of .gitignore, so search does not surface files you exclude.

Ignored files are usually ignored for a reason: build output is noise, and a
local env file is a secret. Without this, a single `search` can copy either into
a chat window.

This reads the workspace's own `.gitignore` files. It is not git: it supports
directory (`build/`), root-anchored (`/dist`), suffix (`*.log`), path
(`src/**/tmp`), and negation (`!keep.log`) patterns, but not the full
specification. It never hides a file the caller asked for by name — it only
narrows traversal — so a mistake here costs recall, not access.
"""

import fnmatch
from pathlib import Path
from typing import List, Optional, Tuple

IGNORE_FILE = ".gitignore"
MAX_PATTERNS = 500


class Ignores:
	"""The ignore rules found in a workspace, compiled once per session."""

	def __init__(self, rules: Optional[List[Tuple[str, bool, bool]]] = None):
		self.rules = rules or []

	@classmethod
	def read(cls, root: Path) -> "Ignores":
		"""Collect rules from the root .gitignore and any in its immediate subtrees."""
		rules: List[Tuple[str, bool, bool]] = []
		for path in cls._ignore_files(root):
			prefix = path.parent.relative_to(root).as_posix()
			prefix = "" if prefix == "." else f"{prefix}/"
			try:
				body = path.read_text(encoding="utf-8", errors="replace")
			except OSError:
				continue
			for line in body.splitlines():
				rule = cls._parse(line, prefix)
				if rule:
					rules.append(rule)
				if len(rules) >= MAX_PATTERNS:
					return cls(rules)
		return cls(rules)

	@staticmethod
	def _ignore_files(root: Path) -> List[Path]:
		found = [root / IGNORE_FILE]
		with_nested = sorted(root.glob(f"*/{IGNORE_FILE}")) + sorted(
			root.glob(f"*/*/{IGNORE_FILE}")
		)
		return [path for path in found + with_nested if path.is_file()]

	@staticmethod
	def _parse(line: str, prefix: str) -> Optional[Tuple[str, bool, bool]]:
		"""Turn one .gitignore line into (pattern, is_negation, directory_only)."""
		text = line.strip()
		if not text or text.startswith("#"):
			return None
		negated = text.startswith("!")
		if negated:
			text = text[1:]
		directory_only = text.endswith("/")
		text = text.strip("/")
		if not text:
			return None
		return (f"{prefix}{text}" if "/" in text or prefix else text, negated, directory_only)

	def ignored(self, relpath: str) -> bool:
		"""True when the last matching rule says to ignore this workspace-relative path."""
		if not self.rules:
			return False
		verdict = False
		for pattern, negated, directory_only in self.rules:
			if self._matches(pattern, relpath, directory_only):
				verdict = not negated
		return verdict

	@staticmethod
	def _matches(pattern: str, relpath: str, directory_only: bool) -> bool:
		segments = relpath.split("/")
		if "/" in pattern:
			if fnmatch.fnmatch(relpath, pattern) or fnmatch.fnmatch(relpath, f"{pattern}/*"):
				return True
			return fnmatch.fnmatch(relpath, f"{pattern}/**")
		# A bare pattern matches at any depth, as a file or as a containing directory.
		targets = segments[:-1] if directory_only else segments
		return any(fnmatch.fnmatch(segment, pattern) for segment in targets)
