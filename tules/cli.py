"""Command line entry point."""

import argparse
import sys
from typing import List, Optional

from .agent import Agent
from .clipboard import Clipboard
from .guide import BOOTSTRAP
from .errors import TulesError
from .formatting import DEFAULT_BUDGET, set_budget
from .monitor import POLL_SECONDS, ClipboardMonitor, run_payload
from .protocol import find_block

DESCRIPTION = "Clipboard driven code agent: reads edit: ... endedit blocks and applies them."


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(prog="tules", description=DESCRIPTION)
	parser.add_argument("root", nargs="?", default=".", help="workspace root (default: .)")
	parser.add_argument(
		"--exec",
		dest="payload",
		metavar="FILE",
		help="run one JSON payload and exit; use - to read stdin",
	)
	parser.add_argument(
		"--actions", action="store_true", help="list the supported actions and exit"
	)
	parser.add_argument(
		"--prompt",
		action="store_true",
		help="print the short bootstrap prompt to paste into the AI chat, and exit",
	)
	parser.add_argument(
		"--copy", action="store_true", help="with --prompt, copy it to the clipboard instead"
	)
	parser.add_argument("--no-shell", action="store_true", help="refuse the run action")
	parser.add_argument(
		"--all-files",
		action="store_true",
		help="search files that .gitignore excludes (off by default)",
	)
	parser.add_argument(
		"--no-auto-review", action="store_true", help="do not review a file after editing it"
	)
	parser.add_argument("--shell-timeout", type=int, default=30, metavar="SECONDS")
	parser.add_argument(
		"--budget",
		type=int,
		default=DEFAULT_BUDGET,
		metavar="CHARS",
		help=(
			"how much of any single value to show the model, in characters "
			f"(default {DEFAULT_BUDGET}; try 800 for a small free-tier context window)"
		),
	)
	parser.add_argument(
		"--poll",
		type=float,
		default=POLL_SECONDS,
		metavar="SECONDS",
		help="clipboard poll interval",
	)
	parser.add_argument("--verbose", action="store_true", help="log ignored clipboard content")
	parser.add_argument(
		"--auto",
		action="store_true",
		help="enable browser automation: open the AI chat, focus its edit box, and press"
		" Ctrl+F12 (or Enter in this terminal) to run the copy/paste loop automatically",
	)
	parser.add_argument(
		"--task", default="",
		help="with --auto: a task for the AI, appended to the bootstrap prompt",
	)
	parser.add_argument(
		"--cdp-host", default=None, metavar="HOST",
		help="browser debug host (default 127.0.0.1)",
	)
	parser.add_argument(
		"--cdp-port", type=int, default=None, metavar="PORT",
		help="browser debug port (default 9222)",
	)
	parser.add_argument(
		"--launch-browser",
		dest="launch_browser",
		metavar="NAME",
		default=None,
		help="with --auto: start chrome/chromium/edge/brave with the debug port, then continue",
	)
	parser.add_argument(
		"--hotkey",
		choices=("auto", "pynput", "stdin", "off"),
		default="auto",
		help="how the automation is triggered (auto: Ctrl+F12 when possible, else this terminal)",
	)
	parser.add_argument(
		"--response-timeout",
		type=float,
		default=600.0,
		metavar="SECONDS",
		help="with --auto: how long to wait for an AI response before pausing (default 600)",
	)
	parser.add_argument(
		"--page-clipboard",
		action="store_true",
		help="with --auto: read/write the clipboard through the page (headless or remote browsers)",
	)
	parser.add_argument(
		"--sites-file",
		dest="sites_file",
		default=None,
		metavar="PATH",
		help="where learned website element locations are saved"
		" (default ~/.tules/browser_sites.json)",
	)
	parser.add_argument(
		"--forget-site",
		dest="forget_site",
		default=None,
		metavar="HOST",
		help="delete the saved element locations for a website, then exit",
	)
	return parser


def main(argv: Optional[List[str]] = None) -> int:
	options = build_parser().parse_args(argv)
	if options.prompt:
		return _emit_prompt(copy=options.copy)
	set_budget(options.budget)
	if options.forget_site:
		return _forget_site(options.forget_site, options.sites_file)
	try:
		agent = Agent(
			root=options.root,
			allow_shell=not options.no_shell,
			shell_timeout=options.shell_timeout,
			auto_review=not options.no_auto_review,
			respect_ignores=not options.all_files,
		)
	except TulesError as exc:
		print(f"ERROR: {exc.message}", file=sys.stderr)
		return 2

	if options.actions:
		for item in agent.describe():
			print(f"{item['action']:<24} {item['summary']}")
		return 0

	if options.payload:
		return _run_once(agent, options.payload)

	auto_loop = None
	if options.auto:
		auto_loop = _build_auto_loop(options, agent)
	ClipboardMonitor(
		agent,
		verbose=options.verbose,
		auto_loop=auto_loop,
	).start(poll_seconds=options.poll)
	return 0


def _forget_site(host: str, sites_file: Optional[str]) -> int:
	from pathlib import Path

	from .browser.profiles import ProfileStore

	store = ProfileStore(Path(sites_file) if sites_file else None)
	if store.forget(host):
		print(f"Forgot the saved element locations for {host} ({store.path}).")
		return 0
	print(f"No saved locations for {host} in {store.path}.")
	return 1


def _build_auto_loop(options: argparse.Namespace, agent: Agent):
	"""Assemble the browser automation loop with its hotkey trigger."""
	from pathlib import Path

	from .browser.cdp import DEFAULT_HOST, DEFAULT_PORT
	from .browser.hotkey import HotkeyWatcher, Trigger
	from .browser.loop import AutoLoop, Reporter
	from .browser.page import BrowserPage, LazyClipboard, PageClipboard
	from .browser.profiles import ProfileStore

	host = options.cdp_host or DEFAULT_HOST
	port = options.cdp_port or DEFAULT_PORT
	store = ProfileStore(Path(options.sites_file) if options.sites_file else None)
	reporter = Reporter()
	if store.warning:
		print(f"WARNING: {store.warning}", file=sys.stderr)
	trigger = Trigger()
	attached = {}

	def connect():
		_, conn = _connect_with_chooser(host, port)
		attached["conn"] = conn
		return BrowserPage(conn)

	def clipboard_backend():
		if options.page_clipboard and "conn" in attached:
			return PageClipboard(attached["conn"])
		return Clipboard()

	loop = AutoLoop(
		agent=agent,
		clipboard=LazyClipboard(clipboard_backend),
		connect=connect,
		store=store,
		trigger=trigger,
		reporter=reporter,
		response_timeout=options.response_timeout,
		task=options.task,
	)
	if options.launch_browser:
		from .browser.launch import launch

		launch(options.launch_browser, port=port)
	loop.hotkey = HotkeyWatcher(trigger, reporter.status).start(prefer=options.hotkey)
	return loop


def _connect_with_chooser(host: str, port: int):
	"""Attach to the AI chat tab, asking on the terminal when several are open."""
	from .browser.cdp import BrowserError, connect as cdp_connect

	def chooser(pages):
		print("Several tabs are open. Which one is the AI chat?")
		for index, page in enumerate(pages):
			print(f"  {index + 1}. {page.describe()}")
		raw = input("Number: ").strip()
		try:
			return pages[int(raw) - 1]
		except (ValueError, IndexError) as exc:
			raise BrowserError("no tab chosen") from exc

	return cdp_connect(host=host, port=port, chooser=chooser)


def _emit_prompt(copy: bool = False) -> int:
	"""Hand the user the whole context the model needs: a few hundred characters."""
	if not copy:
		print(BOOTSTRAP, end="")
		return 0
	if not Clipboard().write(BOOTSTRAP):
		return 2
	print(f"Bootstrap prompt copied to the clipboard ({len(BOOTSTRAP)} characters).")
	return 0


def _run_once(agent: Agent, source: str) -> int:
	if source == "-":
		text = sys.stdin.read()
	else:
		with open(source, encoding="utf-8") as handle:
			text = handle.read()
	print(run_payload(agent, find_block(text) or text, log=None))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
