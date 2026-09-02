#!/usr/bin/env python3
"""End-to-end smoke test: the real automation loop against a real browser.

Serves smoke/fake_ai_site.html locally, launches Chrome/Chromium/Edge with a
remote-debugging port, and runs the production AutoLoop - real CDP, real page
probes, real clicks, real completion detection, real agent commands - against
it. The scripted AI replies drive two full TULES cycles and finish with a
message that has no command block, which is where the automated session ends.

Usage:
    python smoke/run_smoke.py            # headless, cleans up after itself
    python smoke/run_smoke.py --keep     # leave the browser and site running
    python smoke/run_smoke.py --browser /path/to/chrome

Exit codes: 0 pass, 1 fail, 2 skipped (no browser available).
Requires: pip install "tules[browser]" (websocket-client).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SMOKE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SMOKE_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from tules.agent import Agent  # noqa: E402
from tules.browser.cdp import BrowserUnavailable, connect  # noqa: E402
from tules.browser.hotkey import Trigger  # noqa: E402
from tules.browser.loop import AutoLoop, Reporter  # noqa: E402
from tules.browser.page import BrowserPage  # noqa: E402
from tules.browser.profiles import ProfileStore  # noqa: E402

BROWSER_NAMES = [
	"chromium", "chromium-browser", "google-chrome-stable", "google-chrome",
	"chrome", "microsoft-edge", "msedge", "brave-browser",
]

PLAYWRIGHT_GLOBS = [
	"~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell",
	"~/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
	"~/Library/Caches/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-mac64/chrome-headless-shell",
	"~/Library/Caches/ms-playwright/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
]


def find_browser(explicit: str = "") -> str:
	if explicit:
		return explicit
	for name in BROWSER_NAMES:
		found = shutil.which(name)
		if found:
			return found
	for pattern in PLAYWRIGHT_GLOBS:
		matches = sorted(Path(os.path.expanduser(pattern)).parent.glob(Path(pattern).name))
		if matches:
			return str(matches[-1])
	return ""


class SmokeClipboard:
	"""Reads what the site's Copy button copied, via the page itself.

	In a headed browser the site's Copy lands on the real system clipboard and
	TULES reads it with pyperclip; headless browsers have no shared clipboard,
	so the smoke run reads it through the page (navigator.clipboard with a
	mirror kept by the fake site as a fallback).
	"""

	def __init__(self, conn):
		self.conn = conn

	def read(self) -> str:
		try:
			raw = self.conn.evaluate(
				"navigator.clipboard.readText()"
				".then((t) => ({ ok: true, text: t }), (e) => ({ ok: false }))"
			)
			if isinstance(raw, dict) and raw.get("ok"):
				return str(raw.get("text", ""))
		except Exception:
			pass
		try:
			return str(self.conn.evaluate("window.__tulesLastCopied || ''") or "")
		except Exception:
			return ""

	def write(self, text: str) -> bool:
		import json as json_module

		expr = "navigator.clipboard.writeText(" + json_module.dumps(text) + ")"
		try:
			self.conn.evaluate(expr)
			self.conn.evaluate("window.__tulesLastCopied = " + json_module.dumps(text))
			return True
		except Exception:
			return False


def wait_for_debug_port(port: int, timeout: float = 25.0) -> bool:
	deadline = time.time() + timeout
	while time.time() < deadline:
		try:
			with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.0) as response:
				json.loads(response.read().decode("utf-8"))
				return True
		except Exception:
			time.sleep(0.3)
	return False


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--browser", default=os.environ.get("TULES_SMOKE_CHROME", ""),
		help="path to a Chromium-family browser (otherwise a well-known one is sought)")
	parser.add_argument("--port", type=int, default=9333, help="remote debugging port")
	parser.add_argument("--site-port", type=int, default=0, help="port for the fake site (0: ephemeral)")
	parser.add_argument("--keep", action="store_true", help="leave the browser and site running")
	parser.add_argument("--headed", action="store_true", help="show the browser window")
	options = parser.parse_args()

	browser = find_browser(options.browser)
	if not browser:
		print("SKIP: no Chromium-family browser found.")
		print("Install one, or point TULES_SMOKE_CHROME at a binary and re-run.")
		return 2
	print(f"[smoke] browser: {browser}")

	workspace = Path(tempfile.mkdtemp(prefix="tules-smoke-ws-"))
	hello = workspace / "hello.txt"
	hello.write_text("HELLO WORLD\n", encoding="utf-8")

	class Handler(SimpleHTTPRequestHandler):
		def __init__(self, *args, **kwargs):
			super().__init__(*args, directory=str(SMOKE_DIR), **kwargs)

		def log_message(self, *args):
			pass

	site = ThreadingHTTPServer(("127.0.0.1", options.site_port), Handler)
	site_port = site.server_address[1]
	url = f"http://127.0.0.1:{site_port}/fake_ai_site.html"
	print(f"[smoke] fake site: {url}")

	profile_dir = tempfile.mkdtemp(prefix="tules-smoke-profile-")
	command = [browser, f"--remote-debugging-port={options.port}",
		f"--user-data-dir={profile_dir}", "--no-first-run",
		"--no-default-browser-check", "--disable-gpu"]
	if not options.headed:
		command.append("--headless=new")
	command.append(url)
	browser_process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

	try:
		if not wait_for_debug_port(options.port):
			print(f"FAIL: the browser did not open port {options.port}.")
			return 1

		target, conn = connect(port=options.port, prefer_host="127.0.0.1")
		page = BrowserPage(conn)

		grant = (
			"navigator.permissions.query({name: 'clipboard-read'})"
			".then((p) => p.state).catch((e) => 'denied')"
		)
		try:
			state = conn.evaluate(grant)
			print(f"[smoke] page clipboard permission: {state}")
		except Exception as exc:
			print(f"[smoke] clipboard permission probe unavailable ({exc}); using the mirror fallback")

		store = ProfileStore(Path(tempfile.mkdtemp(prefix="tules-smoke-cfg-")) / "sites.json")
		loop = AutoLoop(
			agent=Agent(root=str(workspace)),
			clipboard=SmokeClipboard(conn),
			connect=lambda: page,
			store=store,
			trigger=Trigger(),
			reporter=Reporter(),
			response_timeout=120.0,
			task="Make the hello file say TULES WAS HERE",
		)

		started = time.time()
		loop.run_session()
		print(f"[smoke] session finished in {time.time() - started:.1f} s,"
			f" cycles: {loop.cycles}, mode: {loop.mode}")

		content = hello.read_text(encoding="utf-8")
		if "TULES WAS HERE" in content and loop.cycles == 2:
			print("[smoke] PASS: two automated cycles ran and the edit landed on disk.")
			if options.keep:
				print(f"[smoke] keeping browser (debug port {options.port}) and site ({url});"
					f" workspace: {workspace}. Ctrl+C to exit.")
				browser_process.wait()
			return 0
		print(f"FAIL: hello.txt is {content!r}, cycles: {loop.cycles}")
		return 1
	except BrowserUnavailable as exc:
		print(f"FAIL: {exc.message}")
		return 1
	except KeyboardInterrupt:
		print("[smoke] interrupted.")
		return 1
	finally:
		if not options.keep:
			browser_process.terminate()
			site.shutdown()


if __name__ == "__main__":
	raise SystemExit(main())
