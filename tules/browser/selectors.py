"""Pure element recognition: turning DOM descriptors into reliable CSS selectors.

Everything here is deliberately free of I/O so it can be tested without a
browser. The browser layer hands over plain dictionaries (as returned by
``Runtime.evaluate`` with ``returnByValue``) and gets back scored candidates
and an ordered list of selectors to verify against the live DOM.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Words that make a visible textbox look like the chat message box.
INPUT_HINTS = ("message", "prompt", "chat", "ask", "reply", "say")
# Labels that mean a Copy button but copy something other than the AI response.
COPY_EXCLUSIONS = ("copy link", "copy url", "copy address", "copy email", "copy path")
HASHY = re.compile(r"(?=.*[a-z])(?=.*[A-Z0-9])[A-Za-z0-9_-]{12,}|[a-z0-9]{7}[0-9a-f]{6,}")


@dataclass
class Element:
	"""One candidate element as reported by the page probe."""

	ref: int = -1
	tag: str = ""
	id: str = ""
	name: str = ""
	classes: List[str] = field(default_factory=list)
	placeholder: str = ""
	aria: str = ""
	title: str = ""
	testid: str = ""
	role: str = ""
	label: str = ""
	kind: str = ""
	text: str = ""
	visible: bool = True
	connected: bool = True
	rect: Dict[str, float] = field(default_factory=dict)
	editable: bool = False

	@classmethod
	def from_js(cls, data: Optional[Dict[str, Any]]) -> Optional["Element"]:
		if not isinstance(data, dict):
			return None
		rect = data.get("rect")
		return cls(
			ref=int(data.get("ref", -1)),
			tag=str(data.get("tag", "")),
			id=str(data.get("id", "")),
			name=str(data.get("name", "")),
			classes=[str(c) for c in data.get("classes", []) if c],
			placeholder=str(data.get("placeholder", "")),
			aria=str(data.get("aria", "")),
			title=str(data.get("title", "")),
			testid=str(data.get("testid", "")),
			role=str(data.get("role", "")),
			label=str(data.get("label", "")).strip().lower(),
			kind=str(data.get("kind", "")),
			text=str(data.get("text", "")),
			visible=bool(data.get("visible", True)),
			connected=bool(data.get("connected", True)),
			rect=rect if isinstance(rect, dict) else {},
			editable=bool(data.get("editable", False)),
		)

	def matches(self, other: "Element") -> bool:
		"""Same element as far as the descriptor can tell (used after teaching)."""
		return (
			self.tag == other.tag
			and self.id == other.id
			and self.testid == other.testid
			and self.aria == other.aria
			and self.placeholder == other.placeholder
		)

	def describe(self) -> str:
		parts = [f"<{self.tag}"]
		if self.id:
			parts.append(f"id={self.id}")
		if self.testid:
			parts.append(f"data-testid={self.testid}")
		if self.aria:
			parts.append(f"aria-label={self.aria!r}")
		if self.placeholder:
			parts.append(f"placeholder={self.placeholder!r}")
		return " ".join(parts) + ">"


def _escape(value: str) -> str:
	return value.replace("\\", "\\\\").replace('"', '\\"')


def _css_ident(value: str) -> str:
	return re.sub(r"([^A-Za-z0-9_-])", lambda m: f"\\{m.group(1)}", value)


def _stable_id(value: str) -> bool:
	"""Reject generated ids like 'radix-:r1a:' or long digit soup."""
	if not value or len(value) > 64:
		return False
	if re.search(r"\d{5,}", value):
		return False
	return ":" not in value and "/" not in value


def _usable_classes(classes: List[str]) -> List[str]:
	keep = []
	for name in classes:
		if HASHY.search(name):
			continue
		if name.startswith(("is-", "has-", "js-")) or len(name) > 40:
			continue
		keep.append(name)
		if len(keep) == 3:
			break
	return keep


def _structural_selector(path: List[Dict[str, Any]], tag: str, nth: int) -> str:
	"""Anchor on the nearest stable ancestor, then walk nth-of-type down."""
	parts: List[str] = []
	for level in path:
		name = level.get("tag", "div")
		if level.get("id") and _stable_id(level["id"]):
			parts.append(f"#{_css_ident(level['id'])}")
			parts = [parts[-1]]
			continue
		if level.get("testid"):
			parts.append(f'[data-testid="{_escape(level["testid"])}"]')
			parts = [parts[-1]]
			continue
		parts.append(f"{name}:nth-of-type({level.get('nth', 1)})")
	parts.append(f"{tag}:nth-of-type({nth})" if nth > 1 else tag)
	return " ".join(parts)


def derive_candidates(
	element: Element,
	structural_path: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
	"""Selectors for an element, ordered from most to least trustworthy.

	The caller verifies each against the live DOM and keeps the first that
	resolves to exactly the taught element, so a wrong guess never ships.
	"""
	tag = element.tag or "*"
	out: List[str] = []
	if element.id and _stable_id(element.id):
		out.append(f"#{_css_ident(element.id)}")
	if element.testid:
		out.append(f'[data-testid="{_escape(element.testid)}"]')
	if element.name:
		out.append(f'{tag}[name="{_escape(element.name)}"]')
	if element.aria:
		out.append(f'{tag}[aria-label="{_escape(element.aria)}"]')
	if element.placeholder:
		out.append(f'{tag}[placeholder="{_escape(element.placeholder)}"]')
	classes = _usable_classes(element.classes)
	if classes:
		out.append(tag + "".join(f".{_css_ident(c)}" for c in classes))
	if structural_path:
		out.append(_structural_selector(structural_path, tag, 1))
	return out


def score_input(element: Element) -> Optional[int]:
	"""Confidence that a visible editable element is the chat message box."""
	if not element.visible or not element.connected:
		return None
	tag = element.tag
	if tag == "input":
		if element.kind not in ("text", "", "search"):
			return None
		base = 1
	elif tag == "textarea" or element.editable or element.kind == "contenteditable":
		base = 4
	else:
		base = 1
	height = float(element.rect.get("h", 0))
	if 0 < height < 14:
		return None
	score = base
	if height >= 40:
		score += 2
	haystack = f"{element.placeholder} {element.aria} {element.testid} {element.name}".lower()
	score += min(2, sum(2 for word in INPUT_HINTS if word in haystack))
	return score


def choose_input(candidates: List[Element]) -> Optional[Element]:
	"""Pick the message box among candidates; None means 'do not guess'."""
	scored = [(score_input(item), index, item) for index, item in enumerate(candidates)]
	scored = [item for item in scored if item[0] is not None]
	if not scored:
		return None
	scored.sort(key=lambda item: (-item[0], item[1]))
	best_score, _, best = scored[0]
	if len(scored) > 1 and best_score - scored[1][0] < 2:
		return None  # Two plausible boxes: never guess between them.
	return best


def choose_input_from(candidates: List[Element], focused: Optional[Element]) -> Optional[Element]:
	"""The user's focused element wins outright; otherwise score the field."""
	if focused is not None and score_input(focused) is not None:
		return focused
	return choose_input(candidates)


def copy_score(element: Element) -> Optional[int]:
	"""Confidence that a visible button is the AI response's Copy button."""
	if not element.visible or not element.connected:
		return None
	buttonish = element.tag == "button" or element.role == "button"
	if not buttonish and "button" not in " ".join(element.classes):
		return None
	label = element.label
	if not label:
		label = f"{element.aria} {element.testid} {element.title} {element.text}".lower()
	label = label.strip()
	for excluded in COPY_EXCLUSIONS:
		if excluded in label:
			return None
	if label == "copy":
		return 10
	if "copy" in label and "code" not in label:
		return 5
	if any("copy" in name for name in element.classes):
		return 2
	return None


def choose_copy(candidates: List[Element]) -> Optional[Element]:
	"""Pick the Copy button. Equal scores resolve to the LAST match, because a
	conversation renders one Copy per message and the last one belongs to the
	latest reply."""
	scored = [(copy_score(item), index, item) for index, item in enumerate(candidates)]
	scored = [item for item in scored if item[0] is not None]
	if not scored:
		return None
	best = max(item[0] for item in scored)
	tied = [item for item in scored if item[0] == best]
	tied.sort(key=lambda item: item[1])
	return tied[-1][2]
