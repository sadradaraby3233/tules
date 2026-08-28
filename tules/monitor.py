"""Watches the clipboard for command blocks and writes the answer back."""

import time
from typing import Callable, Optional

from .agent import Agent
from .clipboard import Clipboard, beep
from .errors import TulesError
from .formatting import render, render_batch
from .models import Result
from .protocol import decode, find_block

POLL_SECONDS = 0.5
BANNER = "=" * 60
# Prefixes of the plain-text replies TULES writes back, so the monitor can tell
# its own output apart from a command block a model produced.
REPLY_MARKERS = ("STATUS: SUCCESS", "STATUS: FAILED", "BATCH EXECUTION COMPLETE")


def is_reply(text: str) -> bool:
	"""True when the clipboard holds a reply TULES itself produced."""
	return text.lstrip().startswith(REPLY_MARKERS)


class ClipboardMonitor:
	"""Polls the clipboard, runs what it finds, and never exits on a bad payload."""

	def __init__(
		self,
		agent: Agent,
		clipboard: Optional[Clipboard] = None,
		notify: Callable[[], None] = beep,
		verbose: bool = False,
	):
		self.agent = agent
		self.clipboard = clipboard or Clipboard()
		self.notify = notify
		self.verbose = verbose
		self.seen = ""
		self.running = False

	def start(self, poll_seconds: float = POLL_SECONDS) -> None:
		self.running = True
		print(BANNER)
		print(" TULES clipboard monitor active")
		print(f" Workspace: {self.agent.root}")
		print(" Waiting for 'edit: ... endedit' blocks. Ctrl+C to stop.")
		print(BANNER)
		self.seen = self.clipboard.read()
		try:
			while self.running:
				self.poll()
				time.sleep(poll_seconds)
		except KeyboardInterrupt:
			print("\nTULES monitor stopped.")
		finally:
			self.running = False

	def stop(self) -> None:
		self.running = False

	def poll(self) -> Optional[str]:
		"""Handle one clipboard change; returns the reply that was written back.

		Dedup is by observed content, so the same block copied again re-runs: after
		a run the clipboard holds our reply, and a fresh copy of the block differs
		from it. Our own replies are recognized outright and never re-processed.
		"""
		current = self.clipboard.read()
		if current == self.seen:
			return None
		self.seen = current
		if is_reply(current):
			return None
		payload = find_block(current)
		if payload is None:
			if self.verbose and current.strip():
				print(f"[tules] no command block in clipboard: {current[:120]!r}")
			return None
		print("\n[tules] command detected, running...")
		reply = self.handle(payload)
		if self.clipboard.write(reply):
			self.seen = reply
			self.notify()
			print("[tules] reply copied to the clipboard.")
		else:
			print(reply)
		return reply

	def handle(self, payload: str) -> str:
		return run_payload(self.agent, payload, log=print)


def run_payload(agent: Agent, payload: str, log: Optional[Callable[[str], None]] = None) -> str:
	"""Decode a payload, run every command in it and render the reply."""
	try:
		commands = decode(payload)
	except TulesError as exc:
		return render(Result.fail(exc.message, **exc.details))
	if not commands:
		return render(Result.fail("Payload contained no commands"))
	results = agent.run_batch(commands)
	if log:
		for result in results:
			log(f"  {'OK  ' if result.success else 'FAIL'} {result.message}")
	return render(results[0]) if len(results) == 1 else render_batch(results)
