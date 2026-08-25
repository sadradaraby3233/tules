"""Clipboard access and the notification beep, both isolated for testing."""

import os
import platform
import sys

BEEP_FREQUENCY = 1000
BEEP_MILLISECONDS = 150


class Clipboard:
	"""Thin wrapper over pyperclip so the monitor can be driven by a fake."""

	def __init__(self):
		try:
			import pyperclip
		except ImportError as exc:
			raise SystemExit("pyperclip is required: pip install pyperclip") from exc
		self._backend = pyperclip

	def read(self) -> str:
		try:
			return self._backend.paste() or ""
		except Exception:
			return ""

	def write(self, text: str) -> bool:
		try:
			self._backend.copy(text)
			return True
		except Exception as exc:
			print(f"[!] Could not copy to clipboard: {exc}")
			return False


def beep() -> None:
	"""Make an audible noise, falling back to the terminal bell."""
	system = platform.system()
	try:
		if system == "Windows":
			import winsound

			winsound.Beep(BEEP_FREQUENCY, BEEP_MILLISECONDS)
			return
		if system == "Darwin":
			os.system("afplay /System/Library/Sounds/Ping.aiff")
			return
	except Exception:
		pass
	sys.stdout.write("\a")
	sys.stdout.flush()
