"""One attached AI chat tab: what TULES sees, fills, clicks, and waits for.

``BrowserPage`` turns the raw DevTools connection into the small vocabulary the
automation loop needs: a page state probe, element lookup by saved selector,
fill-and-submit with verification, a verified click, and teaching hooks. The
completion detection (``CompletionWatcher``) is separate and clock-injected so
streaming, stalls, and slow responses are all covered by tests.

Element references: page scripts keep located elements in the page's
``window.__tules.els`` array and hand back indexes. Probes append, so a
reference stays valid for the session; every use still re-checks
``isConnected`` and reports ``stale`` rather than guessing.
"""

import json as json_module
import time
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from . import js
from .cdp import BrowserError, CDPConnection
from .profiles import normalize_host
from .selectors import Element, choose_copy, choose_input, choose_input_from, derive_candidates

DEFAULT_RESPONSE_SELECTORS = [
	'[data-message-author-role="assistant"]',
	'[data-testid="assistant-message"]',
	'[data-testid*="assistant"]',
	'[class*="assistant-message"]',
	".font-claude-message",
	".model-response-text",
	".message-content",
	".markdown",
	"article",
]

DEFAULT_GENERATING_SELECTORS = [
	'button[aria-label*="stop" i]',
	'[aria-label*="stop generating" i]',
	'[data-testid*="stop-button" i]',
	'[data-testid*="stop_response" i]',
	".result-streaming",
	'[data-is-streaming="true"]',
	'[class*="streaming" i]',
	'[class*="thinking-indicator"]',
	'[class*="typing-indicator"]',
]

SEND_SELECTORS = [
	'button[aria-label*="send" i]',
	'[data-testid*="send" i]',
	'button[aria-label*="submit" i]',
	'button[type="submit"]',
]

SUBMIT_NO_BUTTON = (
	"the message is still in the edit box and no send button could be confidently identified"
)


class Clock:
	"""Real time; the tests substitute a fake clock."""

	def now(self) -> float:
		return time.time()

	def sleep(self, seconds: float) -> None:
		time.sleep(seconds)


@dataclass
class ActivityView:
	"""What the completion detector needs to know right now."""

	generating: bool = False
	response_selector: Optional[str] = None
	response_count: int = 0
	response_len: int = 0


@dataclass
class PageState:
	url: str = ""
	title: str = ""
	inputs: List[Element] = field(default_factory=list)
	copies: List[Element] = field(default_factory=list)
	response: ActivityView = field(default_factory=ActivityView)
	generating: bool = False
	active: Optional[Element] = None

	@property
	def host(self) -> str:
		return normalize_host(self.url)


@dataclass
class BoxText:
	len: int = 0
	head: str = ""
	tail: str = ""


@dataclass
class SubmissionView:
	box_len: int = -1
	response_count: int = 0
	generating: bool = False


@dataclass
class SubmitOutcome:
	ok: bool
	detail: str = ""


class BrowserPage:
	"""The loop's view of the tab. Refs are valid until the next ``state()``."""

	def __init__(
		self,
		conn: CDPConnection,
		response_selectors: Optional[List[str]] = None,
		generating_selectors: Optional[List[str]] = None,
		clock: Optional[Clock] = None,
	):
		self.conn = conn
		self.response_selectors = (response_selectors or []) + DEFAULT_RESPONSE_SELECTORS
		self.generating_selectors = (generating_selectors or []) + DEFAULT_GENERATING_SELECTORS
		self.clock = clock or Clock()

	# --- probes -------------------------------------------------------------

	def state(self) -> PageState:
		expr = js.PROBE.replace("%RESPONSE_SELECTORS%", json_module.dumps(self.response_selectors))
		expr = expr.replace("%GENERATING_SELECTORS%", json_module.dumps(self.generating_selectors))
		raw = self.conn.evaluate(expr) or {}
		response_raw = raw.get("response") or {}
		return PageState(
			url=str(raw.get("url", "")),
			title=str(raw.get("title", "")),
			inputs=[item for item in (Element.from_js(d) for d in raw.get("inputs", [])) if item],
			copies=[item for item in (Element.from_js(d) for d in raw.get("copies", [])) if item],
			response=ActivityView(
				generating=bool(raw.get("generating")),
				response_selector=response_raw.get("selector"),
				response_count=int(response_raw.get("count", 0)),
				response_len=int(response_raw.get("len", 0)),
			),
			generating=bool(raw.get("generating")),
			active=Element.from_js(raw.get("active")),
		)

	def element_by_selector(self, selector: str) -> Optional[Element]:
		"""Resolve a saved selector to the last visible match (chats render the
		latest message last, so the last Copy button is the one we want)."""
		expr = js.ELEMENT_BY_SELECTOR.replace("%SELECTOR_JSON%", json_module.dumps(selector))
		raw = self.conn.evaluate(expr) or {}
		if raw.get("error") or not raw.get("visible_found"):
			return None
		return Element.from_js(raw.get("element"))

	def focused_input(self, state: PageState) -> Optional[Element]:
		active = state.active
		if active is None or not active.visible:
			return None
		if active.tag in ("textarea",) or active.editable or active.kind == "contenteditable":
			return active
		if active.tag == "input" and active.kind in ("", "text", "search"):
			return active
		return None

	# --- filling and submitting --------------------------------------------

	def clear_box(self, element: Element) -> bool:
		raw = self.conn.evaluate(js.CLEAR_BOX.replace("%REF%", str(element.ref))) or {}
		return bool(raw.get("ok"))

	def type_text(self, text: str) -> None:
		self.conn.insert_text(text)

	def box_text(self, element: Element) -> Optional[BoxText]:
		raw = self.conn.evaluate(js.BOX_TEXT.replace("%REF%", str(element.ref)))
		if not isinstance(raw, dict):
			return None
		return BoxText(
			len=int(raw.get("len", 0)),
			head=str(raw.get("head", "")),
			tail=str(raw.get("tail", "")),
		)

	def text_matches(self, element: Element, expected: str) -> bool:
		view = self.box_text(element)
		if view is None:
			return False
		return (
			view.len == len(expected)
			and view.head == expected[:150]
			and (view.tail == expected[-150:] if len(expected) > 150 else True)
		)

	def press_enter(self) -> None:
		self.conn.press_enter()

	def submission_view(self, element: Element, response_selector: str) -> SubmissionView:
		expr = js.SUBMISSION_VIEW.replace("%REF%", str(element.ref))
		selector = response_selector or "body"
		expr = expr.replace("%RESPONSE_SELECTOR_JSON%", json_module.dumps(selector))
		expr = expr.replace("%STOP_SELECTOR_JSON%", json_module.dumps(self.generating_selectors[0]))
		raw = self.conn.evaluate(expr) or {}
		return SubmissionView(
			box_len=int(raw.get("box_len", -1)),
			response_count=int(raw.get("response_count", 0)),
			generating=bool(raw.get("generating")),
		)

	def submit_message(
		self,
		element: Element,
		text: str,
		send_selector: str = "",
		response_selector: str = "",
		before_count: int = -1,
		verify_seconds: float = 4.0,
	) -> SubmitOutcome:
		"""Fill the edit box with ``text``, press Enter, and prove it submitted.

		Nothing is left to chance: after typing we read the box back, after
		Enter we look for evidence of submission, and only a confidently
		identified send button may be clicked as a fallback.
		"""
		if not self.clear_box(element):
			return SubmitOutcome(False, "the edit box disappeared before it could be filled")
		self.type_text(text)
		if not self.text_matches(element, text):
			return SubmitOutcome(False, "the text did not land in the edit box as typed")
		self.press_enter()
		if self._evidence(element, response_selector, text, before_count, verify_seconds):
			return SubmitOutcome(True)
		if self._click_send_button(send_selector) is None:
			return SubmitOutcome(False, SUBMIT_NO_BUTTON)
		if self._evidence(element, response_selector, text, before_count, verify_seconds):
			return SubmitOutcome(True)
		return SubmitOutcome(False, "even the send button did not submit the message")

	def _evidence(
		self,
		element: Element,
		response_selector: str,
		text: str,
		before_count: int,
		verify_seconds: float,
	) -> bool:
		deadline = self.clock.now() + verify_seconds
		while True:
			view = self.submission_view(element, response_selector)
			emptied = 0 <= view.box_len < max(1, len(text) // 2)
			grew = before_count >= 0 and view.response_count > before_count
			if emptied or grew or view.generating:
				return True
			if self.clock.now() >= deadline:
				return False
			self.clock.sleep(0.4)

	def _click_send_button(self, send_selector: str) -> Optional[str]:
		for selector in ([send_selector] if send_selector else []) + SEND_SELECTORS:
			if not selector:
				continue
			element = self.element_by_selector(selector)
			if element is None:
				continue
			width = float(element.rect.get("w", 0))
			height = float(element.rect.get("h", 0))
			if width < 4 or height < 4:
				continue
			self.click(element)
			return selector
		return None

	# --- clicking -----------------------------------------------------------

	def click(self, element: Element) -> None:
		"""Click only at the fresh rectangle of a confidently identified element."""
		rect = element.rect or {}
		width = float(rect.get("w", 0))
		height = float(rect.get("h", 0))
		if width < 4 or height < 4:
			raise BrowserError("refusing to click: the element has no usable on-screen rectangle")
		self.conn.click_at(
			float(rect.get("x", 0)) + width / 2,
			float(rect.get("y", 0)) + height / 2,
		)

	# --- teaching -----------------------------------------------------------

	def arm_teach(self, kind: str) -> None:
		arm = js.TEACH_INPUT_ARM if kind == "input" else js.TEACH_COPY_ARM
		self.conn.evaluate(arm)

	def teach_result(self, kind: str) -> Optional[Element]:
		name = "taughtInput" if kind == "input" else "taughtCopy"
		raw = self.conn.evaluate(js.TEACH_RESULT.replace("%NAME%", name))
		return Element.from_js(raw if isinstance(raw, dict) else None)

	def reset_teach(self, kind: str) -> None:
		name = "taughtInput" if kind == "input" else "taughtCopy"
		flag = "teachFocus" if kind == "input" else "teachClick"
		expr = f"window.__tules && (window.__tules.{name} = null, window.__tules.{flag} = false)"
		self.conn.evaluate(expr)

	# --- selector learning --------------------------------------------------

	def verify_candidates(self, element: Element, selectors: List[str]) -> Optional[str]:
		"""The first selector that resolves to a set containing the element."""
		for selector in selectors:
			expr = js.VERIFY_CANDIDATE.replace("%SELECTOR_JSON%", json_module.dumps(selector))
			expr = expr.replace("%REF%", str(element.ref))
			raw = self.conn.evaluate(expr) or {}
			if raw.get("hit") and int(raw.get("found", 0)) >= 1:
				return selector
		return None

	def best_selector_for(
		self,
		element: Element,
		structural_path: Optional[List[dict]] = None,
	) -> Optional[str]:
		candidates = derive_candidates(element, structural_path)
		return self.verify_candidates(element, candidates)

	# --- finding ------------------------------------------------------------

	def find_input(self, state: PageState) -> Optional[Element]:
		return choose_input(state.inputs)

	def find_input_with_focus(self, state: PageState) -> Optional[Element]:
		return choose_input_from(state.inputs, self.focused_input(state))

	def find_copy(self, state: PageState) -> Optional[Element]:
		return choose_copy(state.copies)


class PageClipboard:
	"""Clipboard read/write that lives inside the page.

	The production loop uses the system clipboard via ``tules.clipboard``; this
	adapter is for sessions where no system clipboard can observe the browser
	(headless, remote) and by the smoke test. It exposes the same read/write
	interface the rest of TULES already codes against.
	"""

	def __init__(self, conn: CDPConnection):
		self.conn = conn

	def read(self) -> str:
		raw = self.conn.evaluate(js.PAGE_READ_CLIPBOARD)
		if isinstance(raw, dict) and raw.get("ok"):
			return str(raw.get("text", ""))
		return ""

	def write(self, text: str) -> bool:
		raw = self.conn.evaluate(js.PAGE_WRITE_CLIPBOARD.replace("%TEXT%", json_module.dumps(text)))
		return bool(isinstance(raw, dict) and raw.get("ok"))


class LazyClipboard:
	"""Picks the real clipboard backend on first use, after the page connects.

	Lets ``--auto`` pass the system clipboard by default but the in-page
	clipboard (``--page-clipboard``) for headless browsers, without deciding
	before the connection exists.
	"""

	def __init__(self, factory: Callable[[], Any]):
		self._factory = factory
		self._impl: Any = None

	def _get(self):
		if self._impl is None:
			self._impl = self._factory()
		return self._impl

	def read(self) -> str:
		return self._get().read()

	def write(self, text: str) -> bool:
		return self._get().write(text)


@dataclass
class CompletionConfig:
	poll_seconds: float = 0.5
	stability_seconds: float = 2.5
	min_wait_seconds: float = 1.0
	timeout_seconds: float = 600.0
	max_errors: int = 8
	progress_every: float = 30.0


@dataclass
class CompletionOutcome:
	complete: bool
	reason: str
	elapsed: float = 0.0
	response_len: int = 0
	generating: bool = False
	selector: Optional[str] = None


class CompletionWatcher:
	"""Decides when the AI has finished generating, from polled activity views.

	A response counts as complete when its tracked text has stopped growing for
	``stability_seconds`` while no generating indicator (stop button, streaming
	class, busy flag) is present. Growth or an indicator resets the stability
	window, so slow and long responses are simply waited out, and the Copy
	button appearing early cannot fool it: the copy button is not part of the
	signal at all.
	"""

	def __init__(
		self,
		config: CompletionConfig,
		clock: Clock,
		source: Callable[[], ActivityView],
		on_progress: Optional[Callable[[str], None]] = None,
	):
		self.config = config
		self.clock = clock
		self.source = source
		self.on_progress = on_progress

	def wait(self) -> CompletionOutcome:
		cfg = self.config
		start = self.clock.now()
		stable_since = start
		last_len = -1
		errors = 0
		last_progress = start
		while True:
			now = self.clock.now()
			try:
				view = self.source()
				errors = 0
			except BrowserError:
				errors += 1
				if errors >= cfg.max_errors:
					elapsed = self.clock.now() - start
					return CompletionOutcome(False, "lost contact with the page", elapsed)
				self.clock.sleep(cfg.poll_seconds)
				continue
			if view.generating:
				stable_since = now
			if view.response_len != last_len:
				last_len = view.response_len
				stable_since = now
			settled = now - stable_since >= cfg.stability_seconds
			settled = settled and now - start >= cfg.min_wait_seconds
			if settled and not view.generating and last_len > 0:
				return CompletionOutcome(
					True,
					"response is stable, no generating indicator",
					now - start,
					last_len,
					False,
					view.response_selector,
				)
			if now - start >= cfg.timeout_seconds:
				detail = "still generating" if view.generating else "no finished response detected"
				if not view.generating and last_len == 0:
					detail = "the page never exposed a growing response to track"
					detail += " (the site may need training)"
				return CompletionOutcome(
					False, detail, now - start, last_len, view.generating, view.response_selector
				)
			if self.on_progress and now - last_progress >= cfg.progress_every:
				last_progress = now
				self.on_progress(
					f"waiting for the AI: {int(now - start)} s elapsed,"
					f" response at {last_len} characters"
				)
			self.clock.sleep(cfg.poll_seconds)
