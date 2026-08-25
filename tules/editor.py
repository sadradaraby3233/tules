"""Every mutation of a workspace file goes through this class."""

import ast
import json
import re
from difflib import unified_diff
from typing import Any, Dict, List, Optional, Sequence

from .errors import MatchError, SyntaxGuardError, TulesError, WorkspaceError
from .matching import common_indent, describe_closest, locate_block, reindent
from .models import Result
from .workspace import Document, Workspace

BLAST_RADIUS_LINES = 10
DIFF_LINES = 60
SHORT_BLOCK_CONFIDENCE = {1: 0.95, 3: 0.90}


def check_syntax(text: str, filename: str = "<edit>") -> Optional[str]:
	"""Return a description of the syntax error, or None when the code parses."""
	try:
		compile(text, filename, "exec")
	except SyntaxError as exc:
		return f"SyntaxError at line {exc.lineno}, offset {exc.offset}: {exc.msg}"
	except ValueError as exc:
		return f"Invalid source: {exc}"
	return None


def check_json(text: str) -> Optional[str]:
	"""Return a description of the JSON error, or None when the text parses."""
	try:
		json.loads(text)
	except json.JSONDecodeError as exc:
		return f"JSONDecodeError at line {exc.lineno}, column {exc.colno}: {exc.msg}"
	return None


def guard_source(text: str, filename: str, suffix: str) -> Optional[str]:
	"""Refuse an edit that would make a file we understand unparseable."""
	if suffix == ".py":
		return check_syntax(text, filename)
	if suffix == ".json":
		return check_json(text)
	return None


class Editor:
	"""Applies replacements, always backing up and never leaving broken Python."""

	def __init__(self, workspace: Workspace):
		self.workspace = workspace

	def replace_first(self, relpath: str, search: str, replace: str, reason: str) -> Result:
		document = self._open(relpath, search)
		if search not in document.text:
			raise MatchError(
				"NOT_FOUND: search string is absent from the file",
				closest_match=describe_closest(document.text, search),
			)
		return self._apply(document, document.text.replace(search, replace, 1), reason)

	def replace_unique(self, relpath: str, search: str, replace: str, reason: str) -> Result:
		document = self._open(relpath, search)
		count = document.text.count(search)
		if count == 0:
			raise MatchError(
				"NOT_FOUND: old_str is absent. Use the view action to copy the exact text.",
				closest_match=describe_closest(document.text, search),
			)
		if count > 1:
			raise MatchError(
				f"NOT_UNIQUE: old_str occurs {count} times. Add context or use replace_by_line.",
				occurrences=count,
			)
		return self._apply(document, document.text.replace(search, replace, 1), reason)

	def replace_all(self, relpath: str, search: str, replace: str, reason: str) -> Result:
		document = self._open(relpath, search)
		count = document.text.count(search)
		if count == 0:
			raise MatchError("NOT_FOUND: search string is absent from the file")
		return self._apply(
			document, document.text.replace(search, replace), reason, occurrences=count)

	def find_occurrences(self, relpath: str, search: str) -> List[Dict[str, Any]]:
		document = self._open(relpath, search)
		lines = document.lines
		found: List[Dict[str, Any]] = []
		for offset in self._offsets(document.text, search):
			number = document.text.count("\n", 0, offset) + 1
			found.append({
				"id": len(found),
				"line": number,
				"context": "\n".join(lines[max(0, number - 4):min(len(lines), number + 3)]),
			})
		return found

	def replace_occurrence(self, relpath: str, search: str, replace: str, index: int,
			reason: str) -> Result:
		document = self._open(relpath, search)
		offsets = self._offsets(document.text, search)
		if index < 0 or index >= len(offsets):
			raise MatchError(f"Match id {index} not found", occurrences=len(offsets))
		offset = offsets[index]
		text = document.text[:offset] + replace + document.text[offset + len(search):]
		return self._apply(document, text, reason, match_id=index)

	def replace_lines(self, relpath: str, first: int, last: int, replace: str,
			reason: str) -> Result:
		document = self._open(relpath)
		lines = document.lines
		self._check_range(first, last, len(lines))
		body = replace.split("\n") if replace else []
		text = "\n".join(lines[:first - 1] + body + lines[min(last, len(lines)):])
		span = f"{first}-{min(last, len(lines))}"
		return self._apply(document, text, reason, replaced_lines=span)

	def insert_lines(self, relpath: str, line: int, content: str, reason: str) -> Result:
		document = self._open(relpath)
		lines = document.lines
		position = max(0, min(line, len(lines)))
		text = "\n".join(lines[:position] + content.split("\n") + lines[position:])
		return self._apply(document, text, reason, inserted_at=position + 1)

	def delete_lines(self, relpath: str, first: int, last: int, reason: str) -> Result:
		document = self._open(relpath)
		lines = document.lines
		self._check_range(first, last, len(lines))
		text = "\n".join(lines[:first - 1] + lines[min(last, len(lines)):])
		return self._apply(document, text, reason, deleted_lines=f"{first}-{min(last, len(lines))}")

	def replace_flexible(self, relpath: str, search: str, replace: str, reason: str) -> Result:
		"""Exact, then whitespace agnostic, then token based, then AST based."""
		document = self._open(relpath, search)
		text = document.text
		if search in text:
			return self._apply(
				document, text.replace(search, replace, 1), reason, match_level="exact")

		stripped = [line.strip() for line in search.split("\n") if line.strip()]
		lines = document.lines
		for index in range(len(lines) - len(stripped) + 1):
			if [line.strip() for line in lines[index:index + len(stripped)]] == stripped:
				block = "\n".join(lines[index:index + len(stripped)])
				return self._apply(
					document, text.replace(block, replace, 1), reason, match_level="whitespace")

		matches = self._token_matches(text, search)
		if len(matches) > 1:
			raise MatchError(
				f"AMBIGUOUS: {len(matches)} token matches. Add context or use replace_by_line.",
				first_match_line=text.count("\n", 0, matches[0].start()) + 1,
			)
		if len(matches) == 1:
			span = matches[0]
			return self._apply(
				document, text[:span.start()] + replace + text[span.end():], reason,
				match_level="tokens")

		segment = self._definition_source(document, search)
		if segment:
			return self._apply(
				document, text.replace(segment, replace, 1), reason, match_level="ast")

		raise MatchError(
			"SEARCH_FAILED: could not locate the search block",
			closest_match=describe_closest(text, search),
		)

	def replace_in_context(self, relpath: str, search: str, replace: str,
			context_before: Sequence[str] = (), context_after: Sequence[str] = (),
			threshold: float = 0.85, reason: str = "Context-aware replace") -> Result:
		"""Locate the block by similarity, anchored on the surrounding lines."""
		document = self._open(relpath, search)
		if search in document.text:
			return self._apply(
				document, document.text.replace(search, replace, 1), reason,
				confidence=1.0, match_level="exact")

		lines = document.lines
		search_lines = search.split("\n")
		first, last, confidence = locate_block(
			lines, search_lines, as_lines(context_before), as_lines(context_after))
		if first < 0:
			raise MatchError(
				"NO_MATCH: search block not found anywhere in the file",
				closest_match=describe_closest(document.text, search),
			)

		required = self._required_confidence(search_lines, threshold)
		if confidence < required:
			raise MatchError(
				f"LOW_CONFIDENCE: {confidence:.0%} (need {required:.0%})"
				f" at lines {first + 1}-{last}",
				confidence=round(confidence, 4),
				matched_block="\n".join(lines[first:last]),
				closest_match=describe_closest(document.text, search),
				hint="Add context_before/context_after or lower confidence_threshold.",
			)

		file_indent = common_indent(lines[first:last])
		search_indent = common_indent(search_lines)
		body = reindent(replace.split("\n"), search_indent, file_indent)
		text = "\n".join(lines[:first] + body + lines[last:])
		details: Dict[str, Any] = {
			"confidence": round(confidence, 4),
			"matched_lines": f"{first + 1}-{last}",
			"match_level": "context" if (context_before or context_after) else "fuzzy",
		}
		if file_indent != search_indent:
			details["indent_adjusted"] = f"{search_indent!r} -> {file_indent!r}"
		return self._apply(document, text, reason, **details)

	def preview(self, relpath: str, search: str, replace: str) -> Result:
		document = self._open(relpath, search)
		if search not in document.text:
			raise MatchError(
				"NOT_FOUND: search string is absent from the file",
				closest_match=describe_closest(document.text, search),
			)
		updated = document.text.replace(search, replace, 1)
		diff = list(unified_diff(
			document.text.split("\n"), updated.split("\n"),
			fromfile=f"a/{document.relpath}", tofile=f"b/{document.relpath}",
			lineterm="", n=3))
		body = "\n".join(diff[:DIFF_LINES])
		if len(diff) > DIFF_LINES:
			body += f"\n... ({len(diff) - DIFF_LINES} more lines)"
		return Result.ok(f"Diff preview for {relpath}", diff=body, diff_lines=len(diff))

	def create(self, relpath: str, content: str) -> Result:
		path = self.workspace.resolve(relpath)
		if path.exists():
			raise WorkspaceError(f"File already exists: {relpath}")
		problem = guard_source(content, relpath, path.suffix.lower())
		if problem:
			raise SyntaxGuardError("SYNTAX_ERROR_PREVENTED", error=problem)
		self.workspace.write(path, content)
		return Result.ok(f"Created {relpath}", lines=content.count("\n") + 1)

	def remove(self, relpath: str) -> Result:
		path = self.workspace.require(relpath)
		backup = self.workspace.back_up(path)
		path.unlink()
		return Result.ok(f"Deleted {relpath}", backup=self.workspace.relativize(backup))

	def restore(self, relpath: str) -> Result:
		path = self.workspace.resolve(relpath)
		backup = self.workspace.restore(path)
		return Result.ok(f"Reverted {relpath} to {backup.name}")

	def _open(self, relpath: str, search: Optional[str] = None) -> Document:
		if search is not None and not search.strip():
			raise TulesError("Empty search string")
		return self.workspace.load(relpath)

	def _apply(self, document: Document, text: str, reason: str, **details: Any) -> Result:
		if text == document.text:
			raise TulesError("NO_CHANGE: the replacement is identical to the original")
		problem = guard_source(text, document.relpath, document.path.suffix.lower())
		if problem:
			raise SyntaxGuardError(
				"SYNTAX_ERROR_PREVENTED",
				error=problem,
				blast_radius=quote_error_region(text, problem),
			)
		backup = self.workspace.save(document, text)
		return Result.ok(
			f"Edited {document.relpath}",
			backup=self.workspace.relativize(backup),
			reason=reason,
			**details,
		)

	def _check_range(self, first: int, last: int, total: int) -> None:
		if first < 1 or last < first:
			raise TulesError(f"Invalid line range {first}-{last}")
		if first > total:
			raise TulesError(f"line_start {first} is past the end of the file ({total} lines)")

	def _offsets(self, text: str, needle: str) -> List[int]:
		offsets = []
		cursor = text.find(needle)
		while cursor != -1:
			offsets.append(cursor)
			cursor = text.find(needle, cursor + len(needle))
		return offsets

	def _required_confidence(self, search_lines: Sequence[str], threshold: float) -> float:
		filled = sum(1 for line in search_lines if line.strip())
		for size, minimum in sorted(SHORT_BLOCK_CONFIDENCE.items()):
			if filled <= size:
				return max(threshold, minimum)
		return threshold

	def _token_matches(self, text: str, search: str) -> List[Any]:
		tokens = re.findall(r"\S+", search)
		if not tokens:
			return []
		body = r"\s*".join(re.escape(token) for token in tokens)
		return list(re.finditer(r"(?m)^[ \t]*" + body + r"[ \t]*$", text))

	def _definition_source(self, document: Document, search: str) -> Optional[str]:
		if document.path.suffix != ".py":
			return None
		name = re.search(r"(?:def|class)\s+([A-Za-z_]\w*)", search)
		if not name:
			return None
		try:
			tree = ast.parse(document.text)
		except SyntaxError:
			return None
		definitions = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
		for node in ast.walk(tree):
			if isinstance(node, definitions) and node.name == name.group(1):
				segment = ast.get_source_segment(document.text, node)
				if segment and segment in document.text:
					return segment
		return None


def as_lines(value: Any) -> List[str]:
	if not value:
		return []
	if isinstance(value, str):
		return value.split("\n")
	return [str(item) for item in value]


def quote_error_region(text: str, problem: str) -> str:
	"""Show the lines around a reported syntax error so the caller can self-correct."""
	number = re.search(r"line (\d+)", problem)
	if not number:
		return ""
	center = int(number.group(1))
	lines = text.split("\n")
	start = max(0, center - BLAST_RADIUS_LINES)
	stop = min(len(lines), center + BLAST_RADIUS_LINES)
	return "\n".join(f"{index + 1:4d} | {lines[index]}" for index in range(start, stop))
