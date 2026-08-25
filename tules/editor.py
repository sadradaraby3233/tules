"""Every mutation of a workspace file goes through this class."""

import ast
import re
from difflib import SequenceMatcher, unified_diff
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


class Editor:
	"""Applies replacements, always backing up and never leaving broken Python."""

	def __init__(self, workspace: Workspace):
		self.workspace = workspace

	# Universal string replacement -------------------------------------------------

	def replace_best(
		self,
		relpath: str,
		search: str,
		replace: str,
		reason: str,
		context_before: Sequence[str] = (),
		context_after: Sequence[str] = (),
		threshold: float = 0.85,
		replace_all: bool = False,
		match_id: Optional[int] = None,
	) -> Result:
		"""Universally locate and replace text, from safest to most forgiving.

		The cascade is exact, normalized quotes, whitespace-insensitive lines,
		tokens, Python AST, then confidence-gated contextual similarity. Ambiguous
		matches are never guessed unless context or an explicit match ID resolves them.
		"""
		document = self._open(relpath, search)
		text = document.text

		# Exact and typography-normalized substring matching.
		actual = search
		level = "exact"
		if search not in text:
			normal_text = normalize_quotes(text)
			normal_search = normalize_quotes(search)
			offset = normal_text.find(normal_search)
			if offset >= 0:
				actual = text[offset : offset + len(search)]
				level = "normalized_quotes"
		if actual in text:
			offsets = self._offsets(text, actual)
			if replace_all:
				styled = preserve_quote_style(search, actual, replace)
				return self._apply(
					document,
					apply_substring(text, actual, styled, True),
					reason,
					match_level=level,
					occurrences=len(offsets),
					replace_all=True,
				)
			if match_id is not None:
				return self._replace_occurrence(relpath, actual, replace, match_id, reason)
			if len(offsets) == 1:
				styled = preserve_quote_style(search, actual, replace)
				return self._apply(
					document,
					apply_substring(text, actual, styled, False),
					reason,
					match_level=level,
					occurrences=1,
				)
			if context_before or context_after:
				chosen, confidence = self._choose_context_offset(
					document, offsets, actual, context_before, context_after
				)
				if chosen is not None and confidence >= threshold:
					styled = preserve_quote_style(search, actual, replace)
					end = chosen + len(actual)
					if not styled and not actual.endswith("\n") and text[end : end + 1] == "\n":
						end += 1
					updated = text[:chosen] + styled + text[end:]
					line = text.count("\n", 0, chosen) + 1
					return self._apply(
						document,
						updated,
						reason,
						match_level="context",
						confidence=round(confidence, 4),
						matched_lines=str(line),
						occurrences=1,
					)

			raise MatchError(
				f"AMBIGUOUS: {len(offsets)} exact matches. Add context_before/context_after, "
				"set replace_all, or pass match_id.",
				occurrences=len(offsets),
				candidates=self._occurrence_candidates(relpath, actual),
			)

		# Whole-line whitespace matching, requiring a unique candidate.
		wanted = [line.strip() for line in search.split("\n") if line.strip()]
		lines = document.lines
		blocks = []
		if wanted:
			for index in range(len(lines) - len(wanted) + 1):
				if [line.strip() for line in lines[index : index + len(wanted)]] == wanted:
					blocks.append((index, index + len(wanted)))
		if len(blocks) == 1:
			first, last = blocks[0]
			return self._replace_span(
				document, first, last, search, replace, reason, "whitespace", 1.0
			)
		if len(blocks) > 1:
			raise MatchError(
				f"AMBIGUOUS: {len(blocks)} whitespace matches. Add context.",
				occurrences=len(blocks),
				lines=[first + 1 for first, _ in blocks],
			)

		matches = self._token_matches(text, search)
		if len(matches) == 1:
			span = matches[0]
			return self._apply(
				document,
				text[: span.start()] + replace + text[span.end() :],
				reason,
				match_level="tokens",
				occurrences=1,
			)
		if len(matches) > 1:
			raise MatchError(
				f"AMBIGUOUS: {len(matches)} token matches. Add context.", occurrences=len(matches)
			)

		segment = self._definition_source(document, search)
		if segment:
			return self._apply(
				document,
				text.replace(segment, replace, 1),
				reason,
				match_level="ast",
				occurrences=1,
			)

		return self._replace_located(
			document,
			search,
			replace,
			context_before,
			context_after,
			threshold,
			reason,
			"context" if context_before or context_after else "fuzzy",
		)

	def _choose_context_offset(
		self,
		document: Document,
		offsets: Sequence[int],
		actual: str,
		context_before: Sequence[str],
		context_after: Sequence[str],
	):
		"""Score exact duplicate occurrences only by their requested surroundings."""
		before = as_lines(context_before)
		after = as_lines(context_after)
		lines = document.lines
		scored = []
		for offset in offsets:
			first = document.text.count("\n", 0, offset)
			last = first + actual.count("\n") + 1
			parts = []
			if before:
				candidate = lines[max(0, first - len(before)) : first]
				parts.append(SequenceMatcher(None, "\n".join(before), "\n".join(candidate)).ratio())
			if after:
				candidate = lines[last : last + len(after)]
				parts.append(SequenceMatcher(None, "\n".join(after), "\n".join(candidate)).ratio())
			scored.append((sum(parts) / len(parts) if parts else 0.0, offset))
		scored.sort(reverse=True)
		if not scored or (len(scored) > 1 and scored[0][0] == scored[1][0]):
			return None, scored[0][0] if scored else 0.0
		return scored[0][1], scored[0][0]

	def _replace_located(
		self,
		document: Document,
		search: str,
		replace: str,
		context_before: Sequence[str],
		context_after: Sequence[str],
		threshold: float,
		reason: str,
		level: str,
	) -> Result:
		first, last, confidence = locate_block(
			document.lines, search.split("\n"), as_lines(context_before), as_lines(context_after)
		)
		required = self._required_confidence(search.split("\n"), threshold)
		if first < 0 or confidence < required:
			raise MatchError(
				f"NO_CONFIDENT_MATCH: best {confidence:.0%}, need {required:.0%}",
				confidence=round(confidence, 4),
				closest_match=describe_closest(document.text, search),
				hint="Read the file and provide exact text or stronger context.",
			)
		return self._replace_span(document, first, last, search, replace, reason, level, confidence)

	def _replace_span(
		self,
		document: Document,
		first: int,
		last: int,
		search: str,
		replace: str,
		reason: str,
		level: str,
		confidence: float,
	) -> Result:
		lines = document.lines
		file_indent = common_indent(lines[first:last])
		search_indent = common_indent(search.split("\n"))
		body = reindent(replace.split("\n"), search_indent, file_indent)
		body = adapt_indent_style(body, lines[first:last], file_indent)
		updated = "\n".join(lines[:first] + body + lines[last:])
		details = {
			"match_level": level,
			"confidence": round(confidence, 4),
			"matched_lines": f"{first + 1}-{last}",
			"occurrences": 1,
		}
		if file_indent != search_indent:
			details["indent_adjusted"] = f"{search_indent!r} -> {file_indent!r}"
		return self._apply(document, updated, reason, **details)

	def _occurrence_candidates(self, relpath: str, search: str) -> List[Dict[str, Any]]:
		document = self._open(relpath, search)
		lines = document.lines
		found: List[Dict[str, Any]] = []
		for offset in self._offsets(document.text, search):
			number = document.text.count("\n", 0, offset) + 1
			found.append(
				{
					"id": len(found),
					"line": number,
					"context": "\n".join(lines[max(0, number - 4) : min(len(lines), number + 3)]),
				}
			)
		return found

	def _replace_occurrence(
		self, relpath: str, search: str, replace: str, index: int, reason: str
	) -> Result:
		document = self._open(relpath, search)
		offsets = self._offsets(document.text, search)
		if index < 0 or index >= len(offsets):
			raise MatchError(f"Match id {index} not found", occurrences=len(offsets))
		offset = offsets[index]
		text = document.text[:offset] + replace + document.text[offset + len(search) :]
		return self._apply(document, text, reason, match_id=index)

	# Explicit line operations -----------------------------------------------------

	def replace_lines(
		self, relpath: str, first: int, last: int, replace: str, reason: str
	) -> Result:
		document = self._open(relpath)
		lines = document.lines
		self._check_range(first, last, len(lines))
		body = replace.split("\n") if replace else []
		text = "\n".join(lines[: first - 1] + body + lines[min(last, len(lines)) :])
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
		text = "\n".join(lines[: first - 1] + lines[min(last, len(lines)) :])
		return self._apply(document, text, reason, deleted_lines=f"{first}-{min(last, len(lines))}")

	# Preview and file lifecycle ---------------------------------------------------

	def preview(self, relpath: str, search: str, replace: str) -> Result:
		document = self._open(relpath, search)
		if search not in document.text:
			raise MatchError(
				"NOT_FOUND: search string is absent from the file",
				closest_match=describe_closest(document.text, search),
			)
		updated = document.text.replace(search, replace, 1)
		diff = list(
			unified_diff(
				document.text.split("\n"),
				updated.split("\n"),
				fromfile=f"a/{document.relpath}",
				tofile=f"b/{document.relpath}",
				lineterm="",
				n=3,
			)
		)
		body = "\n".join(diff[:DIFF_LINES])
		if len(diff) > DIFF_LINES:
			body += f"\n... ({len(diff) - DIFF_LINES} more lines)"
		return Result.ok(f"Diff preview for {relpath}", diff=body, diff_lines=len(diff))

	def write_file(self, relpath: str, content: str) -> Result:
		"""Create or replace a complete file through the standard mutation guards."""
		path = self.workspace.resolve(relpath)
		self._guard_syntax(path.suffix, content, relpath)
		if not path.exists():
			self.workspace.write(path, content)
			return Result.ok(
				f"Created {self.workspace.relativize(path)}",
				type="create",
				content=content,
				original_file=None,
			)
		document = self.workspace.load(relpath)
		if document.text == content:
			raise TulesError("NO_CHANGE: content is identical to the existing file")
		backup = self.workspace.save(document, content)
		return Result.ok(
			f"Updated {document.relpath}",
			type="update",
			content=content,
			original_file=document.text,
			backup=self.workspace.relativize(backup),
		)

	def create(self, relpath: str, content: str) -> Result:
		path = self.workspace.resolve(relpath)
		if path.exists():
			raise WorkspaceError(f"File already exists: {relpath}")
		self._guard_syntax(path.suffix, content, relpath)
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

	# Shared mutation safeguards ---------------------------------------------------

	def _open(self, relpath: str, search: Optional[str] = None) -> Document:
		if search is not None and not search.strip():
			raise TulesError("Empty search string")
		return self.workspace.load(relpath)

	def _apply(self, document: Document, text: str, reason: str, **details: Any) -> Result:
		if text == document.text:
			raise TulesError("NO_CHANGE: the replacement is identical to the original")
		self._guard_syntax(document.path.suffix, text, document.relpath, include_context=True)
		backup = self.workspace.save(document, text)
		return Result.ok(
			f"Edited {document.relpath}",
			backup=self.workspace.relativize(backup),
			reason=reason,
			**details,
		)

	def _guard_syntax(
		self, suffix: str, content: str, relpath: str, include_context: bool = False
	) -> None:
		if suffix != ".py":
			return
		problem = check_syntax(content, relpath)
		if not problem:
			return
		details = {"error": problem}
		if include_context:
			details["blast_radius"] = quote_error_region(content, problem)
		raise SyntaxGuardError("SYNTAX_ERROR_PREVENTED", **details)

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


# Pure replacement helpers ------------------------------------------------------


def apply_substring(content: str, old: str, new: str, replace_all: bool) -> str:
	"""Apply a substring edit and avoid leaving a blank line after full-line deletion."""
	needle = old
	if not new and not old.endswith("\n") and old + "\n" in content:
		needle += "\n"
	return content.replace(needle, new, -1 if replace_all else 1)


def adapt_indent_style(body: List[str], matched: Sequence[str], base: str) -> List[str]:
	"""Translate model indentation to the local block's tab/space convention."""
	indents = [line[: len(line) - len(line.lstrip(" \t"))] for line in matched if line.strip()]
	uses_tabs = any("\t" in indent for indent in indents)
	if uses_tabs:
		converted = []
		for line in body:
			prefix = line[: len(line) - len(line.lstrip(" \t"))]
			rest = line[len(prefix) :]
			relative = prefix[len(base) :] if prefix.startswith(base) else prefix
			relative = relative.replace("    ", "\t")
			converted.append(base + relative + rest)
		return converted
	space_widths = [len(indent.expandtabs(4)) - len(base.expandtabs(4)) for indent in indents]
	unit = min((width for width in space_widths if width > 0), default=4)
	converted = []
	for line in body:
		prefix = line[: len(line) - len(line.lstrip(" \t"))]
		rest = line[len(prefix) :]
		relative = prefix[len(base) :] if prefix.startswith(base) else prefix
		converted.append(base + relative.replace("\t", " " * unit) + rest)
	return converted


def normalize_quotes(value: str) -> str:
	return value.translate(
		str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})
	)


def preserve_quote_style(search: str, actual: str, replacement: str) -> str:
	"""Preserve curly typography when a match required quote normalization."""
	if search == actual:
		return replacement
	if "\u201c" in actual or "\u201d" in actual:
		opened = True
		out = []
		for char in replacement:
			if char == '"':
				out.append("\u201c" if opened else "\u201d")
				opened = not opened
			else:
				out.append(char)
		replacement = "".join(out)
	if "\u2018" in actual or "\u2019" in actual:
		replacement = replacement.replace("'", "\u2019")
	return replacement


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
