"""A best-effort delimiter check for the brace languages TULES cannot parse.

Python and JSON get a real parser before a write is committed. For the brace
languages there is no parser here, so this module does the one structural check
that catches the common damage: an edit that leaves brackets unbalanced.

It is deliberately conservative. The original file is the control: a file is only
refused when it was balanced before the edit and is not afterwards. If this
scanner cannot lex a file — a raw string, an unterminated block comment, a
regular expression literal it mistakes for code — the original will not look
balanced either, and the check stays out of the way rather than blocking a valid
edit. It reports structural damage; it does not certify that code compiles.
"""

from typing import Dict, Optional, Set

OPENERS: Dict[str, str] = {"(": ")", "[": "]", "{": "}"}
CLOSERS: Dict[str, str] = {close: open_ for open_, close in OPENERS.items()}

# Families that use // and /* */ comments and the same three bracket pairs.
BRACE_SUFFIXES: Set[str] = {
	".js",
	".jsx",
	".mjs",
	".cjs",
	".ts",
	".tsx",
	".java",
	".cs",
	".kt",
	".scala",
	".c",
	".h",
	".cpp",
	".hpp",
	".cc",
	".go",
	".rs",
	".php",
	".swift",
}
# Languages whose backtick spans a multi-line string rather than being punctuation.
BACKTICK_SUFFIXES: Set[str] = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go"}
# Constructs this scanner knowingly cannot lex; seeing one means it declines to judge.
UNLEXABLE = ('r#"', 'R"(', "'''", '"""')


def supported(suffix: str) -> bool:
	return suffix.lower() in BRACE_SUFFIXES


def balanced(text: str, suffix: str) -> Optional[bool]:
	"""True/False when the brackets can be judged, or None when they cannot."""
	suffix = suffix.lower()
	if suffix not in BRACE_SUFFIXES:
		return None
	if any(marker in text for marker in UNLEXABLE):
		return None
	quotes = {'"', "'"}
	if suffix in BACKTICK_SUFFIXES:
		quotes.add("`")
	stack = []
	index, length = 0, len(text)
	while index < length:
		char = text[index]
		if (char == "/" and index + 1 < length and text[index + 1] == "/") or (
			char == "#" and suffix == ".php"
		):
			index = _end_of_line(text, index)
		elif char == "/" and index + 1 < length and text[index + 1] == "*":
			closed = text.find("*/", index + 2)
			if closed < 0:
				return None
			index = closed + 2
		elif char in quotes:
			moved = _skip_string(text, index, char)
			if moved is None:
				return None
			index = moved
		elif char in OPENERS:
			stack.append(char)
			index += 1
		elif char in CLOSERS:
			if not stack or stack.pop() != CLOSERS[char]:
				return False
			index += 1
		else:
			index += 1
	return not stack


def describe(text: str, suffix: str) -> str:
	"""Name the unclosed or mismatched bracket, so the model can see what it broke."""
	counts = dict.fromkeys(OPENERS, 0)
	for opener in OPENERS:
		counts[opener] = text.count(opener) - text.count(OPENERS[opener])
	unbalanced = [f"{key}{OPENERS[key]}: {value:+d}" for key, value in counts.items() if value]
	if not unbalanced:
		return "brackets are mismatched or closed in the wrong order"
	return f"unbalanced brackets ({', '.join(unbalanced)})"


def _end_of_line(text: str, index: int) -> int:
	newline = text.find("\n", index)
	return len(text) if newline < 0 else newline + 1


def _skip_string(text: str, index: int, quote: str) -> Optional[int]:
	"""Step past a string literal, or return None when it does not terminate cleanly."""
	cursor = index + 1
	while cursor < len(text):
		char = text[cursor]
		if char == "\\":
			cursor += 2
			continue
		if char == quote:
			return cursor + 1
		if char == "\n" and quote != "`":
			return None
		cursor += 1
	return None
