"""Pulling a command payload out of whatever a chat model put on the clipboard."""

import json
import re
from typing import Any, List, Optional

from .errors import TulesError

BLOCK = re.compile(r"(?is)edit:\s*(.*?)\s*endedit")
FENCE_OPEN = re.compile(r"^```[A-Za-z0-9_+-]*\s*")
FENCE_CLOSE = re.compile(r"\s*```$")
TRAILING_COMMA = re.compile(r",\s*([}\]])")
BRACKETS = (("{", "}"), ("[", "]"))


def find_block(text: str) -> Optional[str]:
	"""Return the payload between the edit: and endedit markers."""
	match = BLOCK.search(text or "")
	if not match:
		return None
	payload = match.group(1).strip()
	payload = FENCE_OPEN.sub("", payload)
	payload = FENCE_CLOSE.sub("", payload)
	return payload.strip().strip("`").strip()


def carve_json(text: str) -> Optional[str]:
	"""Return the first balanced JSON object or array, ignoring braces in strings."""
	for opening, closing in BRACKETS:
		start = text.find(opening)
		if start == -1:
			continue
		depth = 0
		in_string = False
		escaped = False
		for index in range(start, len(text)):
			char = text[index]
			if escaped:
				escaped = False
			elif char == "\\" and in_string:
				escaped = True
			elif char == '"':
				in_string = not in_string
			elif in_string:
				continue
			elif char == opening:
				depth += 1
			elif char == closing:
				depth -= 1
				if depth == 0:
					return text[start:index + 1]
	return None


def repair(text: str) -> str:
	"""Escape raw control characters inside strings and drop trailing commas."""
	text = TRAILING_COMMA.sub(r"\1", text)
	escapes = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}
	out = []
	in_string = False
	escaped = False
	for char in text:
		if escaped:
			out.append(char)
			escaped = False
			continue
		if char == "\\" and in_string:
			out.append(char)
			escaped = True
			continue
		if char == '"':
			in_string = not in_string
			out.append(char)
			continue
		out.append(escapes[char] if in_string and char in escapes else char)
	return "".join(out)


def decode(payload: str) -> List[Any]:
	"""Parse a payload into a list of commands, repairing common model mistakes."""
	for candidate in _candidates(payload):
		try:
			parsed = json.loads(candidate)
		except json.JSONDecodeError:
			continue
		if isinstance(parsed, dict):
			return [parsed]
		if isinstance(parsed, list):
			return parsed
		raise TulesError(f"Payload must be an object or array, got {type(parsed).__name__}")
	raise TulesError("Invalid JSON payload, even after repair", payload=payload[:300])


def _candidates(payload: str) -> List[str]:
	found = [payload]
	carved = carve_json(payload)
	if carved and carved != payload:
		found.append(carved)
	found.extend(repair(item) for item in list(found))
	return found
