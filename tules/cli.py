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
	return parser


def main(argv: Optional[List[str]] = None) -> int:
	options = build_parser().parse_args(argv)
	if options.prompt:
		return _emit_prompt(copy=options.copy)
	set_budget(options.budget)
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
	ClipboardMonitor(agent, verbose=options.verbose).start(poll_seconds=options.poll)
	return 0


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
