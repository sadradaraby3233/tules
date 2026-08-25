"""Text, regex, fuzzy and filename search across the workspace."""

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, List, Sequence

from .errors import TulesError, WorkspaceError
from .models import SearchResult
from .workspace import Workspace

CONTEXT_LINES = 2
DEFAULT_LIMIT = 200

LineMatcher = Callable[[str], bool]


class Searcher:
	"""Walks the workspace once per query and yields located lines."""

	def __init__(self, workspace: Workspace):
		self.workspace = workspace

	def find_text(self, pattern: str, case_sensitive: bool = False, whole_word: bool = False,
			limit: int = DEFAULT_LIMIT) -> List[SearchResult]:
		if not pattern:
			raise TulesError("Missing 'search' pattern")
		if whole_word:
			flags = 0 if case_sensitive else re.IGNORECASE
			expression = re.compile(rf"\b{re.escape(pattern)}\b", flags)
			return self._scan(lambda line: expression.search(line) is not None, "exact", limit)
		if case_sensitive:
			return self._scan(lambda line: pattern in line, "exact", limit)
		needle = pattern.lower()
		return self._scan(lambda line: needle in line.lower(), "exact", limit)

	def find_regex(self, pattern: str, limit: int = DEFAULT_LIMIT) -> List[SearchResult]:
		try:
			expression = re.compile(pattern)
		except re.error as exc:
			raise TulesError(f"Invalid regex: {exc}") from exc
		return self._scan(lambda line: expression.search(line) is not None, "regex", limit)

	def find_similar(self, pattern: str, threshold: float = 0.8,
			limit: int = DEFAULT_LIMIT) -> List[SearchResult]:
		if not pattern:
			raise TulesError("Missing 'search' pattern")
		matcher = SequenceMatcher(None, pattern, "")

		def similar(line: str) -> bool:
			matcher.set_seq2(line.strip())
			return matcher.ratio() >= threshold

		return self._scan(similar, "fuzzy", limit)

	def find_files(self, pattern: str, limit: int = DEFAULT_LIMIT) -> List[str]:
		needle = (pattern or "").lower().strip("*")
		found = []
		for path in self.workspace.walk():
			if needle in path.name.lower():
				found.append(self.workspace.relativize(path))
				if len(found) >= limit:
					break
		return found

	def _scan(self, matches: LineMatcher, kind: str, limit: int) -> List[SearchResult]:
		results: List[SearchResult] = []
		for path in self.workspace.walk():
			try:
				lines = self.workspace.load_path(path, strict=False).lines
			except WorkspaceError:
				continue
			for number, line in enumerate(lines, 1):
				if not matches(line):
					continue
				results.append(self._locate(path, number, lines, kind))
				if len(results) >= limit:
					return results
		return results

	def _locate(self, path: Path, number: int, lines: Sequence[str], kind: str) -> SearchResult:
		start = max(0, number - 1 - CONTEXT_LINES)
		stop = min(len(lines), number + CONTEXT_LINES)
		return SearchResult(
			file=self.workspace.relativize(path),
			line=number,
			text=lines[number - 1].rstrip(),
			context_before="\n".join(lines[start:number - 1]),
			context_after="\n".join(lines[number:stop]),
			kind=kind,
		)
