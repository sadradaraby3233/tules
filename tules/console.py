"""The interactive console: run ``tules`` with no flags and answer questions.

The point is never having to memorize command-line usage. Typing ``tules`` in
the project folder opens a plain terminal conversation that asks which job to
run and anything the job needs, then drives exactly the machinery the old
flags selected. The flags still work for scripts; nothing in day-to-day use
needs them.
"""

import os
from pathlib import Path
from typing import Callable, List, Optional

from .agent import Agent
from .clipboard import Clipboard
from .formatting import DEFAULT_BUDGET, set_budget
from .guide import BOOTSTRAP

MENU = """\
What would you like to do?
  1) Clipboard monitor - you copy and paste, TULES runs the commands
  2) Browser automation - press Ctrl+F12 in the AI chat and watch it work
  3) Show the bootstrap prompt (to paste into a fresh AI chat yourself)
  4) Copy the bootstrap prompt to the clipboard
  5) List everything the AI can ask TULES to do
  6) Run one JSON payload file
  7) Forget a saved website (browser automation memory)
  8) Explain these choices
  q) Quit"""

HELP = """\
  1 - the classic workflow. Paste the bootstrap prompt (option 3 or 4) into an
      AI chat, give it your task, and copy its reply. When the reply holds an
      'edit: ... endedit' block, this monitor runs it and puts the result back
      on your clipboard with a beep - you just paste it into the chat again.
  2 - the same protocol, automated. TULES drives the chat page in your own
      browser: it pastes, presses Enter, waits for the response to finish, and
      clicks Copy for you, over and over, after you press Ctrl+F12 in the chat
      tab. On a website it has not seen before it may ask you to show it the
      message box or Copy button once; it remembers each site afterwards.
  3/4 - the short prompt every AI needs before it can speak TULES.
  5 - the actions the AI may put inside its edit: blocks.
  6 - run a saved payload without any chat involved.
  7 - remove TULES' memory of one site's layout; it re-learns on next use."""


class ConsoleQuit(Exception):
	"""The user chose to leave the console."""


class Console:
	"""Asks plain questions, then runs the same machinery the flags select."""

	def __init__(
		self,
		root: str = ".",
		sites_file: Optional[str] = None,
		input_fn: Optional[Callable[[str], str]] = None,
		output: Optional[Callable[[str], None]] = None,
	):
		self.input_fn = input_fn or input
		self.output = output or print
		self.root = root or "."
		self.sites_file = sites_file
		self.agent: Optional[Agent] = None

	# --- prompting ----------------------------------------------------------

	def ask(self, prompt: str, default: str = "") -> str:
		shown = f" ({default})" if default else ""
		try:
			answer = self.input_fn(f"{prompt}{shown}: ")
			answer = answer.strip()
		except EOFError:
			raise ConsoleQuit from None
		except KeyboardInterrupt:
			raise ConsoleQuit from None
		return answer or default

	def ask_int(self, prompt: str, default: int) -> int:
		while True:
			answer = self.ask(prompt, str(default))
			try:
				return int(answer)
			except ValueError:
				self.output(f"  '{answer}' is not a number - try again.")

	def confirm(self, prompt: str, default: bool) -> bool:
		hint = "Y/n" if default else "y/N"
		while True:
			answer = self.ask(f"{prompt} ({hint})").lower()
			if not answer:
				return default
			if answer in ("y", "yes"):
				return True
			if answer in ("n", "no"):
				return False
			self.output("  Please answer y or n.")

	def ask_multiline(self, prompt: str) -> str:
		self.output(f"{prompt} (finish with an empty line):")
		lines: List[str] = []
		while True:
			try:
				line = self.input_fn("")
			except EOFError:
				break
			if not line.strip():
				break
			lines.append(line.rstrip())
		return "\n".join(lines)

	# --- session ------------------------------------------------------------

	def run(self) -> int:
		self.output("=" * 60)
		self.output(" TULES interactive console")
		self.output("=" * 60)
		try:
			self._setup()
			while True:
				self._dispatch(self._menu_choice())
		except ConsoleQuit:
			self.output("Bye.")
			return 0
		except KeyboardInterrupt:
			self.output("\nInterrupted - bye.")
			return 0

	def _setup(self) -> None:
		folder = self._ask_folder()
		budget = self.ask_int("Result size limit per value, in characters", DEFAULT_BUDGET)
		allow_shell = self.confirm("Allow shell commands (bash / powershell)?", True)
		set_budget(budget)
		self.agent = Agent(root=folder, allow_shell=allow_shell)
		self.output(f" Workspace: {self.agent.root}")

	def _ask_folder(self) -> str:
		while True:
			folder = self.ask("Workspace folder (the project TULES may touch)", self.root)
			if os.path.isdir(folder):
				return folder
			self.output(f"  No such folder: {folder}. Try again.")

	def _menu_choice(self) -> str:
		self.output("")
		self.output(MENU)
		while True:
			choice = self.ask("Choose", "1").lower()
			if choice in ("quit", "exit"):
				choice = "q"
			if choice in ("1", "2", "3", "4", "5", "6", "7", "8", "q"):
				return choice
			self.output("  Pick 1-8, or q to quit.")

	def _dispatch(self, choice: str) -> None:
		if choice == "1":
			self._run_monitor()
		elif choice == "2":
			self._run_automation()
		elif choice == "3":
			self.output(BOOTSTRAP)
		elif choice == "4":
			self._copy_prompt()
		elif choice == "5":
			self._list_actions()
		elif choice == "6":
			self._run_payload_file()
		elif choice == "7":
			self._forget_site()
		elif choice == "8":
			self.output(HELP)
		elif choice == "q":
			raise ConsoleQuit

	# --- jobs ---------------------------------------------------------------

	def _run_monitor(self) -> None:
		from .monitor import ClipboardMonitor

		self.output(
			"Clipboard monitor starting. Copy an AI reply with an 'edit: ... endedit'"
			" block; TULES runs it and beeps when the result is on the clipboard."
			" Ctrl+C returns here."
		)
		ClipboardMonitor(self.agent).start()

	def _run_automation(self) -> None:
		from .browser.wiring import build_auto_loop
		from .monitor import ClipboardMonitor

		self.output(
			"Browser automation: after you press Ctrl+F12, TULES pastes, presses"
			" Enter, waits for the response, and clicks Copy - over and over."
		)
		task = self.ask_multiline("Task for the AI (optional)")
		port = self.ask_int("Browser remote-debugging port", 9222)
		timeout = self.ask_int("Seconds to wait for an AI response before pausing", 600)
		launcher = ""
		if self.confirm("Should I start a browser for you?", False):
			launcher = self.ask("Which browser (chrome / chromium / edge / brave)", "chrome")
		loop = build_auto_loop(
			agent=self.agent,
			task=task,
			cdp_port=port,
			response_timeout=float(timeout),
			sites_file=self.sites_file,
			launch_browser=launcher,
		)
		self.output("")
		self.output(" In your browser: open the AI chat, start a new chat, and click")
		self.output(" into the message box. Then press Ctrl+F12 (or Enter in this")
		self.output(" terminal). Ctrl+C stops and returns here.")
		self.output("")
		ClipboardMonitor(self.agent, auto_loop=loop).start()

	def _copy_prompt(self) -> None:
		if Clipboard().write(BOOTSTRAP):
			self.output(
				f"Bootstrap prompt copied ({len(BOOTSTRAP)} characters)."
				" Paste it into the AI chat as your first message."
			)
		else:
			self.output(
				"Could not reach the system clipboard - use 'Show the bootstrap prompt' instead."
			)

	def _list_actions(self) -> None:
		for item in self.agent.describe():
			self.output(f"{item['action']:<24} {item['summary']}")

	def _run_payload_file(self) -> None:
		from .monitor import run_payload
		from .protocol import find_block

		path = self.ask("Path to the JSON payload file")
		try:
			with open(path, encoding="utf-8") as handle:
				text = handle.read()
		except OSError as exc:
			self.output(f"  Could not read {path}: {exc}")
			return
		self.output(run_payload(self.agent, find_block(text) or text))

	def _forget_site(self) -> None:
		from .browser.profiles import ProfileStore

		store = ProfileStore(Path(self.sites_file) if self.sites_file else None)
		host = self.ask("Website to forget (for example chatgpt.com)")
		if store.forget(host):
			self.output(f"Forgot {host}. TULES will ask you to show it the elements next time.")
		else:
			self.output(f"No saved locations for {host} in {store.path}.")


def run_console(
	root: str = ".",
	sites_file: Optional[str] = None,
	input_fn: Optional[Callable[[str], str]] = None,
	output: Optional[Callable[[str], None]] = None,
) -> int:
	"""Open the interactive console; used by the CLI for a bare `tules` run."""
	console = Console(root=root, sites_file=sites_file, input_fn=input_fn, output=output)
	return console.run()
