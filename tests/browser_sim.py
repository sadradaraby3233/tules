"""A simulated AI chat website for end-to-end tests of the browser automation.

``FakePage`` subclasses the real ``BrowserPage`` and replaces only the
DevTools boundary, so the production submission, verification, completion,
selector-derivation, and teach logic all run unchanged against a fake DOM.
The fake site streams scripted replies (which contain real TULES command
blocks), shows a Copy button that writes to a fake clipboard, and can be
configured to misbehave in every way the loop must survive.
"""

import re
from typing import Dict, List, Optional

from tules.browser.page import (
	ActivityView,
	BrowserPage,
	BoxText,
	Clock,
	PageState,
	SubmissionView,
)
from tules.browser.selectors import Element

SIMPLE_PART = re.compile(
	r"^(?P<tag>[a-z][a-z0-9]*)?(?:#(?P<id>[\w-]+))?(?P<classes>(?:\.[\w-]+)*)"
	r"(?:\[(?P<attr>[\w-]+)(?:(?P<op>\*?=)(?P<value>[^\]]*?))?(?P<flag> i)?\])?"
	r"(?::nth-of-type\((?P<nth>\d+)\))?$"
)


class FakeEl:
	"""One fake DOM node: just enough for selector matching and describing."""

	def __init__(
		self,
		tag: str,
		id: str = "",
		classes: Optional[List[str]] = None,
		attrs: Optional[Dict[str, str]] = None,
		text: str = "",
		editable: bool = False,
		kind: str = "",
		visible: bool = True,
	):
		self.tag = tag
		self.id = id
		self.classes = list(classes or [])
		self.attrs = dict(attrs or {})
		self.text = text
		self.editable = editable
		self.kind = kind
		self.visible = visible
		self.parent: Optional["FakeEl"] = None
		self.children: List["FakeEl"] = []

	def add(self, child: "FakeEl") -> "FakeEl":
		child.parent = self
		self.children.append(child)
		return child

	@property
	def current_text(self) -> str:
		return self.text

	def attr(self, name: str) -> str:
		return self.attrs.get(name, "")

	def describe(self) -> str:
		return f"<{self.tag} id={self.id}>".replace(" id= >", ">")


def walk(node: FakeEl):
	for child in node.children:
		yield child
		yield from walk(child)


def _match_simple(el: FakeEl, part: str) -> bool:
	match = SIMPLE_PART.match(part)
	if not match:
		return False
	if match.group("tag") and el.tag != match.group("tag"):
		return False
	if match.group("id") and el.id != match.group("id"):
		return False
	for name in [c[1:] for c in re.findall(r"\.[\w-]+", match.group("classes") or "")]:
		if name not in el.classes:
			return False
	attr = match.group("attr")
	if attr:
		op = match.group("op")
		value = match.group("value") or ""
		if value.startswith('"') and value.endswith('"'):
			value = value[1:-1]
		actual = el.attr(attr)
		if op == "=" and actual != value:
			return False
		if op == "*=":
			needle = value.rstrip(" i").strip('"') if match.group("flag") else value.strip('"')
			hay = actual.lower() if match.group("flag") else actual
			if (needle.lower() if match.group("flag") else needle) not in hay:
				return False
	if match.group("nth"):
		parent = el.parent
		if parent is None:
			return False
		same_tag = [sibling for sibling in parent.children if sibling.tag == el.tag]
		nth = int(match.group("nth"))
		if len(same_tag) < nth or same_tag[nth - 1] is not el:
			return False
	return True


def split_selector(selector: str) -> List[str]:
	"""Split on whitespace outside brackets, so `[attr*="x" i]` stays whole."""
	parts: List[str] = []
	depth = 0
	current = ""
	for char in selector:
		if char == "[":
			depth += 1
		elif char == "]":
			depth -= 1
		if char.isspace() and depth == 0:
			if current:
				parts.append(current)
			current = ""
			continue
		current += char
	if current:
		parts.append(current)
	return parts


def query_all(root: FakeEl, selector: str) -> List[FakeEl]:
	"""A tiny CSS-subset engine: descendants, tag/#id/.class/[attr]/:nth-of-type."""
	parts = split_selector(selector)
	if not parts:
		return []
	return [el for el in walk(root) if _match_chain(el, parts)]


def _match_chain(el: FakeEl, parts: List[str]) -> bool:
	if not _match_simple(el, parts[-1]):
		return False
	if len(parts) == 1:
		return True
	parent = el.parent
	while parent is not None:
		if _match_chain(parent, parts[:-1]):
			return True
		parent = parent.parent
	return False


class FakeClipboard:
	"""The system clipboard stand-in; the fake site's Copy button writes here."""

	def __init__(self):
		self.contents = ""

	def read(self) -> str:
		return self.contents

	def write(self, text: str) -> bool:
		self.contents = text
		return True


class FakeClock(Clock):
	"""Virtual time: sleep() advances instantly so tests never really wait."""

	def __init__(self, start: float = 10_000.0):
		self.t = start

	def now(self) -> float:
		return self.t

	def sleep(self, seconds: float) -> None:
		self.t += seconds


class FakeSite:
	"""The website behavior: composer, scripted streaming replies, Copy."""

	def __init__(
		self,
		clipboard: FakeClipboard,
		replies: List[str],
		copy_works: bool = True,
		copy_ready_early: bool = False,
		enter_submits: bool = True,
		rate: float = 40.0,
		latency: float = 0.0,
		hide_input: bool = False,
		hide_copy: bool = False,
	):
		self.clipboard = clipboard
		self.replies = list(replies)
		self.copy_works = copy_works
		self.copy_ready_early = copy_ready_early
		self.enter_submits = enter_submits
		self.rate = rate
		self.latency = latency
		self.hide_input = hide_input
		self.hide_copy = hide_copy
		self.teach_input_target: Optional[FakeEl] = None
		self.root = FakeEl("html")
		self.body = self.root.add(FakeEl("body"))
		self.chat = self.body.add(FakeEl("div", id="chat"))
		self.composer = self.body.add(FakeEl("div", id="composer"))
		self.input = self.composer.add(
			FakeEl(
				"textarea",
				id="prompt-input",
				kind="textarea",
				editable=True,
				attrs={"placeholder": "Message the AI"},
			)
		)
		self.decoy_input = self.composer.add(
			FakeEl("input", id="search", kind="text", attrs={"placeholder": "Search chats"})
		)
		self.send_button = self.composer.add(
			FakeEl("button", id="send-btn", attrs={"aria-label": "Send message"})
		)
		self.box = ""
		self.pending = None  # dict(target, produced, started, segments)
		self.focused: Optional[FakeEl] = None
		self.copy_clicks = 0
		self.send_clicks = 0
		self.teach_target_input: Optional[FakeEl] = None
		self.teach_target_copy: Optional[FakeEl] = None
		self.teach_delay = 0.0
		self._teach_armed: Dict[str, float] = {}

	# --- site behavior ------------------------------------------------------

	def submit(self) -> bool:
		if not self.box.strip():
			return False
		user_text = self.box
		self.box = ""
		self.chat.add(
			FakeEl(
				"div",
				classes=["msg-user"],
				attrs={"data-message-author-role": "user"},
				text=user_text,
			)
		)
		reply = self.replies.pop(0) if self.replies else "All done, nothing more to run."
		assistant_attrs = {"data-message-author-role": "assistant"}
		message = self.chat.add(FakeEl("div", classes=["msg-assistant"], attrs=assistant_attrs))
		self.pending = {
			"el": message,
			"target": reply,
			"produced": 0,
			"started": None,
		}
		if self.copy_ready_early:
			self._add_toolbar(message)
		return True

	def _add_toolbar(self, message: FakeEl) -> FakeEl:
		toolbar = message.add(FakeEl("div", classes=["toolbar"]))
		toolbar.add(FakeEl("button", classes=["link-btn"], attrs={"aria-label": "Copy link"}))
		toolbar.add(FakeEl("button", classes=["copy-btn"], attrs={"aria-label": "Copy"}))
		toolbar.add(FakeEl("button", classes=["code-btn"], attrs={"aria-label": "Copy code"}))
		return toolbar

	def advance(self, now: float) -> None:
		"""Streaming progress as a function of (virtual) time."""
		pending = self.pending
		if pending is None:
			return
		if pending["started"] is None:
			pending["started"] = now + self.latency
		start = pending["started"]
		if now < start:
			return
		produced = int((now - start) * self.rate)
		pending["produced"] = min(len(pending["target"]), produced)
		if pending["produced"] >= len(pending["target"]):
			message = pending["el"]
			message.text = pending["target"]
			if not self.copy_ready_early:
				self._add_toolbar(message)
			self.pending = None

	@property
	def generating(self) -> bool:
		return self.pending is not None

	def copy_last_response(self) -> bool:
		self.copy_clicks += 1
		if not self.copy_works:
			return False
		messages = [
			el for el in walk(self.body) if el.attr("data-message-author-role") == "assistant"
		]
		if not messages:
			return False
		self.clipboard.write(messages[-1].current_text)
		return True

	# --- teach simulation ---------------------------------------------------

	def arm_teach(self, kind: str, now: float) -> None:
		self._teach_armed[kind] = now

	def teach_result(self, kind: str, now: float):
		"""The user's answer to a teach prompt, after a short human-like delay.

		Copy teaching is dynamic: the user clicks the Copy button of the latest
		response, and their click copies it, exactly as on a real site.
		"""
		armed = self._teach_armed.get(kind)
		if armed is None or now - armed < self.teach_delay:
			return None
		if kind == "input":
			return self.teach_input_target
		messages = [
			el for el in walk(self.body) if el.attr("data-message-author-role") == "assistant"
		]
		if not messages:
			return None
		for el in walk(messages[-1]):
			if el.attr("aria-label") == "Copy":
				self.copy_last_response()
				return el
		return None


class FakePage(BrowserPage):
	"""BrowserPage over a FakeSite: production logic, simulated DevTools."""

	def __init__(self, site: FakeSite, clipboard: FakeClipboard, clock: FakeClock, url: str = ""):
		super().__init__(FakeConnection(site, clock), clock=clock)
		self.site = site
		self.clipboard = clipboard
		self.clock = clock
		self.url = url or "https://fake-chat.example/chat"
		self._els: List[FakeEl] = []
		self.clicks: List[str] = []

	# --- refs ---------------------------------------------------------------

	def ref(self, el: FakeEl) -> int:
		self._els.append(el)
		return len(self._els) - 1

	def deref(self, element: Element) -> Optional[FakeEl]:
		if 0 <= element.ref < len(self._els):
			return self._els[element.ref]
		return None

	# --- probes -------------------------------------------------------------

	def state(self) -> PageState:
		self.site.advance(self.clock.now())
		inputs = [] if self.site.hide_input else [self.describe(self.site.input, "textarea")]
		if not self.site.hide_input and self.site.decoy_input.visible:
			inputs.append(self.describe(self.site.decoy_input, "text"))
		copies = (
			[]
			if self.site.hide_copy
			else [
				self.describe(el, "")
				for el in walk(self.site.body)
				if el.tag == "button" and el.visible
			]
		)
		response = ActivityView(
			generating=self.site.generating,
			response_selector=None,
			response_count=len(
				[
					el
					for el in walk(self.site.body)
					if el.attr("data-message-author-role") == "assistant"
				]
			),
			response_len=len(self.last_response_text()),
		)
		active = None
		if self.site.focused is not None:
			active = self.describe(self.site.focused, getattr(self.site.focused, "kind", ""))
		return PageState(
			url=self.url,
			title="Fake chat",
			inputs=inputs,
			copies=copies,
			response=response,
			generating=self.site.generating,
			active=active,
		)

	def last_response_text(self) -> str:
		messages = [
			el for el in walk(self.site.body) if el.attr("data-message-author-role") == "assistant"
		]
		if self.site.pending is not None:
			return self.site.pending["target"][: self.site.pending["produced"]]
		return messages[-1].text if messages else ""

	def describe(self, el: FakeEl, kind: str) -> Element:
		return Element(
			ref=self.ref(el),
			tag=el.tag,
			id=el.id,
			classes=list(el.classes),
			placeholder=el.attr("placeholder"),
			aria=el.attr("aria-label"),
			title=el.attr("title"),
			testid=el.attr("data-testid"),
			name=el.attr("name"),
			role=el.attr("role"),
			kind=kind or el.kind,
			text=el.current_text[-300:],
			visible=el.visible,
			connected=True,
			editable=el.editable,
			rect={"x": 0, "y": 0, "w": 320, "h": 60},
		)

	def element_by_selector(self, selector: str) -> Optional[Element]:
		self.site.advance(self.clock.now())
		try:
			found = query_all(self.site.body, selector)
		except re.error:
			return None
		found = [el for el in found if el.visible]
		if not found:
			return None
		el = found[-1]
		return self.describe(el, getattr(el, "kind", ""))

	# --- box ----------------------------------------------------------------

	def clear_box(self, element: Element) -> bool:
		el = self.deref(element)
		if el is None:
			return False
		self.site.box = ""
		self.site.focused = el
		return True

	def type_text(self, text: str) -> None:
		self.site.box += text

	def box_text(self, element: Element) -> Optional[BoxText]:
		el = self.deref(element)
		if el is None:
			return None
		text = self.site.box
		return BoxText(len=len(text), head=text[:150], tail=text[-150:])

	def press_enter(self) -> None:
		if self.site.enter_submits:
			self.site.submit()

	def submission_view(self, element: Element, response_selector: str) -> SubmissionView:
		count = len(
			[
				el
				for el in walk(self.site.body)
				if el.attr("data-message-author-role") == "assistant"
			]
		)
		return SubmissionView(
			box_len=len(self.site.box.strip()),
			response_count=count,
			generating=self.site.generating,
		)

	# --- clicking -----------------------------------------------------------

	def click(self, element: Element) -> None:
		el = self.deref(element)
		if el is None:
			return
		self.clicks.append(el.id or el.attr("aria-label") or el.tag)
		if el is self.site.send_button:
			self.site.send_clicks += 1
			self.site.submit()
		elif el.attr("aria-label") == "Copy" or "copy-btn" in el.classes:
			self.site.copy_last_response()

	# --- teaching -----------------------------------------------------------

	def arm_teach(self, kind: str) -> None:
		self.site.arm_teach(kind, self.clock.now())

	def teach_result(self, kind: str) -> Optional[Element]:
		target = self.site.teach_result(kind, self.clock.now())
		if target is None:
			return None
		kind_field = target.kind or "textarea" if kind == "input" else ""
		return self.describe(target, kind_field)

	def reset_teach(self, kind: str) -> None:
		self.site._teach_armed.pop(kind, None)

	# --- selector learning --------------------------------------------------

	def verify_candidates(self, element: Element, selectors: List[str]) -> Optional[str]:
		el = self.deref(element)
		if el is None:
			return None
		for selector in selectors:
			try:
				found = query_all(self.site.body, selector)
			except re.error:
				continue
			if el in found:
				return selector
		return None


class FakeConnection:
	"""Present only to satisfy BrowserPage's constructor; never used."""

	def __init__(self, site: FakeSite, clock: FakeClock):
		self.site = site
		self.clock = clock

	def evaluate(self, expression, timeout=None):
		raise AssertionError("FakePage must not touch the DevTools connection")

	def insert_text(self, text):
		raise AssertionError("FakePage must not touch the DevTools connection")

	def press_enter(self):
		raise AssertionError("FakePage must not touch the DevTools connection")

	def click_at(self, x, y):
		raise AssertionError("FakePage must not touch the DevTools connection")

	def close(self):
		pass
