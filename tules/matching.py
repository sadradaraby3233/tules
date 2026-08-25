"""Whitespace and unicode tolerant location of a block of lines inside a file."""

import unicodedata
from difflib import SequenceMatcher
from typing import List, Sequence, Tuple

QUOTE_REPLACEMENTS = {
	"\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
	"\u201c": '"', "\u201d": '"', "\u201e": '"', "\u2032": "'", "\u2033": '"',
}
INVISIBLE = ("\u200b", "\u200c", "\u200d", "\ufeff")
TAB_WIDTH = 4
CONTEXT_CONFIDENCE = 0.6

Located = Tuple[int, int, float]


def normalize(text: str) -> str:
	"""Collapse the differences a language model routinely introduces."""
	text = text.replace("\r\n", "\n").replace("\r", "\n")
	text = unicodedata.normalize("NFC", text)
	for source, target in QUOTE_REPLACEMENTS.items():
		text = text.replace(source, target)
	for char in INVISIBLE:
		text = text.replace(char, "")
	text = text.replace("\u00a0", " ").replace("\t", " " * TAB_WIDTH)
	return "\n".join(line.rstrip() for line in text.split("\n"))


def common_indent(lines: Sequence[str]) -> str:
	"""Return the shortest leading whitespace shared by the non-empty lines."""
	indents = [line[: len(line) - len(line.lstrip())] for line in lines if line.strip()]
	return min(indents, key=len) if indents else ""


def reindent(lines: Sequence[str], source: str, target: str) -> List[str]:
	"""Shift lines from one base indent to another, keeping relative depth."""
	if source == target:
		return list(lines)
	shifted = []
	for line in lines:
		if not line.strip():
			shifted.append("")
			continue
		body = line.lstrip()
		indent = line[: len(line) - len(body)]
		if indent.startswith(source):
			shifted.append(target + indent[len(source):] + body)
		else:
			shifted.append(target + body)
	return shifted


def _content_lines(lines: Sequence[str]) -> List[Tuple[int, str]]:
	normalized = ((index, normalize(line)) for index, line in enumerate(lines))
	return [(index, line) for index, line in normalized if line.strip()]


def _similarity(window: Sequence[Tuple[int, str]], wanted: Sequence[str]) -> float:
	total = sum(SequenceMatcher(None, window[i][1], wanted[i]).ratio() for i in range(len(wanted)))
	return total / len(wanted)


def _best_window(haystack: List[Tuple[int, str]], wanted: List[str],
		start: int, stop: int) -> Tuple[float, int]:
	best_score, best_index = 0.0, -1
	for index in range(start, min(stop, len(haystack) - len(wanted) + 1)):
		score = _similarity(haystack[index:index + len(wanted)], wanted)
		if score > best_score:
			best_score, best_index = score, index
	return best_score, best_index


def _anchor(haystack: List[Tuple[int, str]], anchor_lines: List[str], start: int) -> int:
	for index in range(start, len(haystack) - len(anchor_lines) + 1):
		window = haystack[index:index + len(anchor_lines)]
		if [line for _, line in window] == anchor_lines:
			return index
	return -1


def locate_block(
	file_lines: Sequence[str],
	search_lines: Sequence[str],
	context_before: Sequence[str] = (),
	context_after: Sequence[str] = (),
) -> Located:
	"""Return ``(start, end, confidence)`` as 0-based, end-exclusive line indices.

	Blank lines are ignored on both sides, so the result maps back onto the
	original file even when the search block spaces itself differently.
	"""
	haystack = _content_lines(file_lines)
	needle = _content_lines(search_lines)
	if not needle or len(needle) > len(haystack):
		return (-1, -1, 0.0)
	wanted = [line for _, line in needle]
	span = len(wanted)

	def bounds(index: int, score: float) -> Located:
		return (haystack[index][0], haystack[index + span - 1][0] + 1, score)

	for index in range(len(haystack) - span + 1):
		if all(haystack[index + offset][1] == wanted[offset] for offset in range(span)):
			return bounds(index, 1.0)

	before = [line for _, line in _content_lines(context_before or ())]
	after = [line for _, line in _content_lines(context_after or ())]
	if before or after:
		start = 0
		if before:
			found = _anchor(haystack, before, 0)
			start = found + len(before) if found >= 0 else 0
		stop = len(haystack)
		if after:
			found = _anchor(haystack, after, start)
			if found >= 0:
				stop = found
		score, index = _best_window(haystack, wanted, start, max(start + 1, stop - span + 1))
		if index >= 0 and score >= CONTEXT_CONFIDENCE:
			return bounds(index, score)

	score, index = _best_window(haystack, wanted, 0, len(haystack))
	return bounds(index, score) if index >= 0 else (-1, -1, 0.0)


def describe_closest(file_text: str, search: str, context: int = 3) -> str:
	"""Render the region that most resembles the search block, with line numbers."""
	file_lines = file_text.split("\n")
	search_lines = [line for line in search.split("\n") if line.strip()]
	if not search_lines:
		return "(empty search)"
	span = len(search_lines)
	best_score, best_index = 0.0, 0
	for index in range(max(1, len(file_lines) - span + 1)):
		window = file_lines[index:index + span]
		score = sum(
			SequenceMatcher(None, normalize(wanted), normalize(actual)).ratio()
			for wanted, actual in zip(search_lines, window)
		) / max(1, len(window))
		if score > best_score:
			best_score, best_index = score, index
	start = max(0, best_index - context)
	stop = min(len(file_lines), best_index + span + context)
	body = [
		f"{'>>>' if best_index <= number < best_index + span else '   '}"
		f" {number + 1:4d} | {file_lines[number]}"
		for number in range(start, stop)
	]
	header = f"Closest match ({best_score:.0%}) at lines {best_index + 1}-{best_index + span}:"
	return "\n".join([header, *body])
