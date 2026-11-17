"""Pulling a command payload out of whatever a chat model put on the clipboard."""

import json
import re
from typing import Any, List, Optional

from .errors import TulesError

FENCE_OPEN = re.compile(r"^```[A-Za-z0-9_+-]*\s*")
FENCE_CLOSE = re.compile(r"\s*```$")
CLOSE_AFTER_WHITESPACE = re.compile(r"\s*[}\]]")


def find_block(text: str) -> Optional[str]:
	"""Return the payload between the edit: and endedit markers."""
	# Markers inside JSON strings are content, not the end of the envelope.
	start = re.search(r"(?i)edit:\s*", text or "")
	if not start:
		return None
	in_string = escaped = False
	end = start.end()
	while end < len(text):
		char = text[end]
		if escaped:
			escaped = False
		elif in_string and char == "\\":
			escaped = True
		elif char == '"':
			in_string = not in_string
		elif not in_string and text[end : end + 7].lower() == "endedit":
			payload = text[start.end() : end].strip()
			payload = FENCE_OPEN.sub("", payload)
			payload = FENCE_CLOSE.sub("", payload)
			return payload.strip().strip("`").strip()
		end += 1
	return None


def carve_json(text: str) -> Optional[str]:
	"""Return the first balanced JSON object or array, ignoring braces in strings."""
	start = next((i for i, char in enumerate(text) if char in "{["), -1)
	if start < 0:
		return None
	stack = []
	in_string = escaped = False
	for index in range(start, len(text)):
		char = text[index]
		if escaped:
			escaped = False
		elif in_string and char == "\\":
			escaped = True
		elif char == '"':
			in_string = not in_string
		elif not in_string:
			if char in "{[":
				stack.append(char)
			elif char in "}]":
				if not stack or stack.pop() != ("{" if char == "}" else "["):
					return None
				if not stack:
					return text[start : index + 1]
	return None


def repair(text: str) -> str:
	"""Escape raw control characters inside strings and drop trailing commas."""
	escapes = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}
	out = []
	in_string = False
	escaped = False
	for index, char in enumerate(text):
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
		if not in_string and char == "," and CLOSE_AFTER_WHITESPACE.match(text, index + 1):
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
