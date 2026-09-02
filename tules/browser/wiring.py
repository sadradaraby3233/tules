"""Wiring the automation loop: one builder shared by the console and the flags.

Both entry points - answering questions in the interactive console, or passing
command-line flags - must produce exactly the same loop, so the assembly lives
here once.
"""

import sys
from pathlib import Path
from typing import Optional

from ..agent import Agent
from ..clipboard import Clipboard
from .cdp import DEFAULT_HOST, DEFAULT_PORT
from .hotkey import HotkeyWatcher, Trigger
from .launch import launch
from .loop import AutoLoop, Reporter
from .page import BrowserPage, LazyClipboard, PageClipboard
from .profiles import ProfileStore


def connect_with_chooser(host: str, port: int):
	"""Attach to the AI chat tab, asking on the terminal when several are open."""
	from .cdp import BrowserError, connect as cdp_connect

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


def build_auto_loop(
	agent: Agent,
	task: str = "",
	cdp_host: Optional[str] = None,
	cdp_port: Optional[int] = None,
	sites_file: Optional[str] = None,
	hotkey: str = "auto",
	response_timeout: float = 600.0,
	page_clipboard: bool = False,
	launch_browser: str = "",
	reporter: Optional[Reporter] = None,
) -> AutoLoop:
	"""Assemble the loop, arm its trigger, and optionally start a browser."""
	host = cdp_host or DEFAULT_HOST
	port = cdp_port or DEFAULT_PORT
	store = ProfileStore(Path(sites_file) if sites_file else None)
	reporter = reporter or Reporter()
	if store.warning:
		print(f"WARNING: {store.warning}", file=sys.stderr)
	trigger = Trigger()
	attached = {}

	def connect():
		_, conn = connect_with_chooser(host, port)
		attached["conn"] = conn
		return BrowserPage(conn)

	def clipboard_backend():
		if page_clipboard and "conn" in attached:
			return PageClipboard(attached["conn"])
		return Clipboard()

	loop = AutoLoop(
		agent=agent,
		clipboard=LazyClipboard(clipboard_backend),
		connect=connect,
		store=store,
		trigger=trigger,
		reporter=reporter,
		response_timeout=response_timeout,
		task=task,
	)
	if launch_browser:
		launch(launch_browser, port=port)
	loop.hotkey = HotkeyWatcher(trigger, reporter.status).start(prefer=hotkey)
	return loop
