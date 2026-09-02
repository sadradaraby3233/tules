"""Ctrl+F12: the global hotkey that starts an automation session.

pynput provides the global hotkey where the desktop allows it; where it does
not (headless boxes, restricted Wayland sessions, missing dependency) the
watcher falls back to reading the terminal, so Enter always works as a trigger
and the automation never depends on desktop-specific features to be testable.
"""

import sys
import threading
from contextlib import suppress
from typing import Callable, Optional


class Trigger:
	"""A thread-safe, one-shot-pending flag shared by watcher and monitor."""

	def __init__(self):
		self._event = threading.Event()

	def request(self) -> None:
		self._event.set()

	def consume(self) -> bool:
		if self._event.is_set():
			self._event.clear()
			return True
		return False

	def wait(self, timeout: Optional[float] = None) -> bool:
		return self._event.wait(timeout)


class HotkeyWatcher:
	"""Listens for Ctrl+F12 (pynput) or terminal Enter (fallback) in a thread."""

	def __init__(self, trigger: Trigger, report: Callable[[str], None]):
		self.trigger = trigger
		self.report = report
		self._thread: Optional[threading.Thread] = None
		self._listener = None
		self.mode = "off"

	def start(self, prefer: str = "auto") -> "HotkeyWatcher":
		if prefer in ("auto", "pynput") and self._start_pynput():
			self.mode = "ctrl+f12"
			self.report("Hotkey active: press Ctrl+F12 in the browser to start the automation.")
			return self
		if prefer in ("auto", "stdin"):
			self._start_stdin()
			self.mode = "terminal"
			self.report(
				"Global hotkey unavailable here; press Enter in this terminal to start"
				" the automation loop instead (Ctrl+F12 works wherever pynput runs)."
			)
			return self
		self.report("Hotkey disabled; trigger the automation from tests or with --hotkey stdin.")
		return self

	def _start_pynput(self) -> bool:
		try:
			from pynput import keyboard
		except Exception:
			return False
		try:
			self._listener = keyboard.GlobalHotKeys({"<ctrl>+<f12>": self.trigger.request})
			self._listener.daemon = True
			self._listener.start()
		except Exception as exc:
			self.report(f"pynput could not grab the keyboard ({exc}); using the terminal instead.")
			return False
		return True

	def _start_stdin(self) -> None:
		def read_triggers() -> None:
			try:
				for line in sys.stdin:
					if not line.strip() or line.strip().lower() in ("go", "g", "start"):
						self.trigger.request()
			except Exception:
				pass  # a closed or unusable terminal must not crash the monitor

		self._thread = threading.Thread(
			target=read_triggers, name="tules-hotkey-stdin", daemon=True
		)
		self._thread.start()

	def stop(self) -> None:
		if self._listener is not None:
			with suppress(Exception):
				self._listener.stop()
