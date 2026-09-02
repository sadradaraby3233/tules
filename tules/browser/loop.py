"""The Ctrl+F12 automation loop: edit box, Enter, wait, Copy, clipboard, repeat.

The loop drives exactly the manual workflow it automates, reusing the existing
agent and clipboard machinery unchanged:

    agent message -> edit box -> Enter -> wait for completion -> Copy button
    -> system clipboard -> existing command processing -> reply on clipboard
    -> edit box -> Enter -> ...

Session resume modes, so a hotkey press never repeats work already done:

``fresh``     paste the agent bootstrap (plus ``--task``) and start the cycle.
``awaiting``  the AI spoke last; resume by waiting for its next finished
              response and copying it.
``resend``    a message is waiting to be pasted; re-paste it and continue.

Every failure pauses with a clear message and a beep instead of guessing, and
the pause leaves the session in the mode that resumes from the failed step.
"""

import sys
import time
from typing import Callable, Optional, Tuple

from ..agent import Agent
from ..clipboard import Clipboard, beep
from ..guide import BOOTSTRAP
from ..monitor import is_reply, run_payload
from ..protocol import find_block
from .cdp import BrowserError, BrowserUnavailable
from .page import (
	ActivityView,
	BrowserPage,
	Clock,
	CompletionConfig,
	CompletionOutcome,
	CompletionWatcher,
	PageState,
)
from .profiles import ProfileStore, SiteProfile, valid_selector
from .selectors import Element
from .teach import Teacher, TeachingTimeout, known_site_defaults

MODE_FRESH = "fresh"
MODE_AWAITING = "awaiting"
MODE_RESEND = "resend"

CLIPBOARD_WAIT_SECONDS = 12.0
RESUME_HINT = "Press the hotkey (or Enter in the terminal) to continue from here."
STALE_SITE_HINT = " - the site may have changed. Trying automatic detection."
BOX_NOT_EMPTY = (
	"the AI edit box already contains text. Submit or clear it yourself first,"
	" so your words are not overwritten."
)
WRONG_COPY = (
	"the clipboard holds a TULES reply, not an AI response - the wrong Copy"
	" button may have been identified. Bring the correct response into view and try again."
)
NOTHING_COPIED = (
	"the Copy button did not put anything new on the clipboard."
	" Check that the finished response has a working Copy button, then try again."
)


class AutomationPaused(Exception):
	"""The loop stopped and needs the user; carries the resume mode."""

	def __init__(self, message: str, mode: str):
		super().__init__(message)
		self.message = message
		self.mode = mode


class Reporter:
	"""Timestamped status lines, so the user always knows what is happening."""

	def __init__(self, stream=None, prefix: str = "[tules-auto] "):
		self.stream = stream or sys.stdout
		self.prefix = prefix

	def status(self, message: str) -> None:
		self.stream.write(f"{self.prefix}{time.strftime('%H:%M:%S')} {message}\n")
		self.stream.flush()

	def error(self, message: str) -> None:
		self.status(f"PAUSED: {message}")

	def line(self, message: str) -> None:
		self.stream.write(f"  {message}\n")
		self.stream.flush()


class AutoLoop:
	"""One process-wide automation loop, triggered by the hotkey."""

	def __init__(
		self,
		agent: Agent,
		clipboard: Clipboard,
		connect: Callable[[], BrowserPage],
		store: ProfileStore,
		trigger,
		reporter: Optional[Reporter] = None,
		response_timeout: float = 600.0,
		first_message: str = "",
		task: str = "",
		clock: Optional[Clock] = None,
	):
		self.agent = agent
		self.clipboard = clipboard
		self.connect = connect
		self.store = store
		self.trigger = trigger
		self.reporter = reporter or Reporter()
		self.first_message = first_message or BOOTSTRAP
		if task:
			self.first_message = f"{self.first_message}\n\nTASK from the user:\n{task}\n"
		self.clock = clock or Clock()
		self.completion = CompletionConfig(timeout_seconds=response_timeout)
		self.mode = MODE_FRESH
		self.pending: Optional[str] = None
		self.active = False
		self.cycles = 0

	# --- trigger ------------------------------------------------------------

	def request_start(self) -> None:
		"""Ask for a session from any thread (the hotkey watcher, or a test)."""
		self.trigger.request()

	def consume_trigger(self) -> bool:
		return self.trigger.consume()

	# --- session ------------------------------------------------------------

	def run_session(self) -> None:
		"""Run one automated session; never raises, always reports."""
		self.active = True
		self.trigger.consume()  # a press made mid-session is dropped, not queued
		try:
			self._session()
		except AutomationPaused as exc:
			self.mode = exc.mode
			self.reporter.error(exc.message)
			self.reporter.status(RESUME_HINT)
			beep()
		except BrowserError as exc:
			# The mode is left as it is: nothing submitted keeps its paste-for-
			# next-time plan, and a session past submitting resumes watching.
			self.reporter.error(f"browser problem: {exc.message}")
			self.reporter.status(RESUME_HINT)
			beep()
		except Exception as exc:  # never let the automation crash the monitor
			self.reporter.error(f"unexpected automation failure: {type(exc).__name__}: {exc}")
			self.reporter.status(RESUME_HINT)
			beep()
		finally:
			self.active = False

	def _session(self) -> None:
		try:
			page = self.connect()
		except BrowserUnavailable as exc:
			raise AutomationPaused(f"cannot reach the browser: {exc.message}", self.mode) from exc
		state = page.state()
		self.reporter.status(f"Attached to {state.url or 'the browser tab'}")
		host = state.host
		self._apply_saved_generating_selector(page, host)

		message = self._next_message()
		while True:
			if message is not None:
				fresh_state = page.state()
				element = self._resolve_input(page, fresh_state, host)
				if self.mode == MODE_FRESH:
					box = page.box_text(element)
					if box is not None and box.len > 0:
						raise AutomationPaused(BOX_NOT_EMPTY, self.mode)
				self.reporter.status("Pasting the agent's message into the AI edit box")
				outcome = page.submit_message(
					element,
					message,
					send_selector=self._saved_selector(host, "send_selector"),
					response_selector=(
						self._saved_selector(host, "response_selector")
						or page.response_selectors[0]
					),
					before_count=fresh_state.response.response_count,
				)
				if not outcome.ok:
					detail = f"the message could not be submitted: {outcome.detail}"
					raise AutomationPaused(detail, MODE_RESEND)
				self.pending = None
				self.mode = MODE_AWAITING
				message = None
				self.reporter.status("Message submitted. Waiting for the AI to respond.")

			self.reporter.status("Waiting for the AI to finish responding")
			outcome = self._wait_for_response(page)
			if not outcome.complete:
				hint = "" if outcome.generating else " If it looks complete, retrain the site."
				detail = f"gave up waiting after {int(outcome.elapsed)} s: {outcome.reason}.{hint}"
				raise AutomationPaused(detail, MODE_AWAITING)

			self.reporter.status("Waiting for the Copy button")
			before = self.clipboard.read()  # snapshot before teaching, so a
			# teach click that copies is still seen as a change
			copy_element, clicked_by_user = self._resolve_copy(page, host)

			self.reporter.status("Reading the clipboard")
			text = self._read_response(page, copy_element, clicked_by_user, before)
			if text is None:
				raise AutomationPaused(NOTHING_COPIED, MODE_AWAITING)
			if is_reply(text):
				raise AutomationPaused(WRONG_COPY, MODE_AWAITING)

			block = find_block(text)
			if block is None:
				self.reporter.status("The AI replied without a command block - nothing to execute.")
				self.reporter.status(
					"Automated session finished. Answer manually if you like,"
					" then press the hotkey to resume."
				)
				self.mode = MODE_AWAITING
				self.pending = None
				beep()
				return

			self.cycles += 1
			head = f"Processing the AI response (cycle {self.cycles}, executing actions)"
			self.reporter.status(head)
			reply = run_payload(self.agent, block, log=self.reporter.line)

			self.reporter.status("Writing the agent reply to the clipboard")
			if not self.clipboard.write(reply):
				raise AutomationPaused(
					"the reply could not be written to the clipboard", MODE_RESEND
				)
			self.pending = reply
			self.mode = MODE_RESEND
			message = reply
			self.reporter.status("Pasting the agent's reply for the next round trip")

	# --- steps --------------------------------------------------------------

	def _next_message(self) -> Optional[str]:
		if self.mode == MODE_FRESH:
			self.reporter.status("Fresh start: pasting the TULES bootstrap prompt for the AI.")
			return self.first_message
		if self.mode == MODE_RESEND:
			self.reporter.status("Resuming: pasting the message that was not submitted yet.")
			return self.pending or self.first_message
		self.reporter.status("Resuming: watching for the AI's next response (nothing to paste).")
		return None

	def _wait_for_response(self, page: BrowserPage) -> CompletionOutcome:
		watcher = CompletionWatcher(
			self.completion,
			self.clock,
			lambda: self._activity(page),
			on_progress=self.reporter.status,
		)
		return watcher.wait()

	def _activity(self, page: BrowserPage) -> ActivityView:
		return page.state().response

	def _resolve_input(self, page: BrowserPage, state: PageState, host: str) -> Element:
		"""Saved selector, then built-in hints, then detection, then teaching."""
		saved = self.store.load(host)
		if saved and saved.input_selector:
			element = page.element_by_selector(saved.input_selector)
			if element is not None and self._looks_editable(element):
				return element
			self.reporter.status(f"The saved message box location fails on {host}{STALE_SITE_HINT}")
		hints = known_site_defaults(host)
		if hints.input_selector:
			element = page.element_by_selector(hints.input_selector)
			if element is not None and self._looks_editable(element):
				self.reporter.status(f"Recognized the message box: {element.describe()}")
				self._remember(host, "input_selector", hints.input_selector)
				return element
		element = page.find_input_with_focus(state)
		if element is None:
			element = page.find_input(state)
		if element is not None:
			self.reporter.status(f"Identified the message box automatically: {element.describe()}")
			self._remember_derived(page, host, "input_selector", element)
			return element
		return self._teach(page, host, "input")

	def _resolve_copy(self, page: BrowserPage, host: str) -> Tuple[Element, bool]:
		"""Returns the button and whether teaching already clicked it for us."""
		saved = self.store.load(host)
		if saved and saved.copy_selector:
			element = page.element_by_selector(saved.copy_selector)
			if element is not None:
				return element, False
			self.reporter.status(f"The saved Copy button location fails on {host}{STALE_SITE_HINT}")
		state = page.state()
		element = page.find_copy(state)
		if element is not None:
			self.reporter.status(f"Identified the Copy button: {element.describe()}")
			self._remember_derived(page, host, "copy_selector", element)
			return element, False
		taught = self._teach(page, host, "copy")
		return taught, True

	def _teach(self, page: BrowserPage, host: str, kind: str) -> Element:
		teacher = Teacher(page, self.store, self.clock, self.reporter.status)
		try:
			return teacher.learn(kind, host)[0]
		except TeachingTimeout as exc:
			polite = "message box" if kind == "input" else "Copy button"
			pause_mode = self.mode if kind == "input" else MODE_AWAITING
			raise AutomationPaused(
				f"could not identify the {polite}: {exc}. Nothing was clicked.",
				pause_mode,
			) from exc

	def _read_response(
		self,
		page: BrowserPage,
		copy_element: Element,
		clicked_by_user: bool,
		before: str,
	) -> Optional[str]:
		"""Click Copy (unless teaching already did) and wait for the clipboard."""
		if not clicked_by_user:
			page.click(copy_element)
		deadline = self.clock.now() + CLIPBOARD_WAIT_SECONDS
		retry_at = self.clock.now() + CLIPBOARD_WAIT_SECONDS / 2
		retried = False
		while self.clock.now() < deadline:
			text = self.clipboard.read()
			if text and text != before:
				return text
			if not retried and self.clock.now() >= retry_at:
				retried = True
				page.click(copy_element)  # one conservative second attempt
			self.clock.sleep(0.3)
		return None

	# --- helpers ------------------------------------------------------------

	@staticmethod
	def _looks_editable(element: Element) -> bool:
		return (
			element.tag == "textarea"
			or element.editable
			or (element.tag == "input" and element.kind in ("", "text", "search"))
		)

	def _apply_saved_generating_selector(self, page, host: str) -> None:
		"""Let a saved profile name this site's "still writing" element first."""
		saved = self._saved_selector(host, "generating_selector")
		if saved and saved not in page.generating_selectors:
			page.generating_selectors.insert(0, saved)

	def _saved_selector(self, host: str, kind: str) -> str:
		saved = self.store.load(host)
		value = getattr(saved, kind, "") if saved else ""
		return value if valid_selector(value) else ""

	def _remember(self, host: str, kind: str, selector: str) -> None:
		if not valid_selector(selector):
			return
		profile = self.store.load(host) or SiteProfile(host=host)
		if getattr(profile, kind) == selector:
			return
		self.store.save(profile.with_selector(kind, selector))
		name = kind.replace("_selector", "")
		self.reporter.status(f"Saved the {name} location for {host} in {self.store.path}")

	def _remember_derived(self, page: BrowserPage, host: str, kind: str, element: Element) -> None:
		try:
			selector = page.best_selector_for(element)
		except BrowserError:
			selector = None
		if selector:
			self._remember(host, kind, selector)
