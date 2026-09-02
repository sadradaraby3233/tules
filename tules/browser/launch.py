"""Best-effort launcher for a debug-enabled browser.

The automation needs the browser started with a remote-debugging port. This
helper starts a known browser that way so the user can simply open their AI
chat inside it; if no known browser is found, it prints where it looked.
"""

import os
import shutil
import subprocess
import sys
import time
from typing import List, Optional

from .cdp import DEFAULT_HOST, DEFAULT_PORT, list_targets

CANDIDATES: dict = {
	"chrome": ["google-chrome-stable", "google-chrome", "chrome", "chromium", "chromium-browser"],
	"chromium": ["chromium", "chromium-browser", "chromium-freeworld"],
	"edge": ["microsoft-edge-stable", "microsoft-edge", "msedge"],
	"brave": ["brave-browser", "brave"],
}

WINDOWS_PATHS = [
	r"C:\Program Files\Google\Chrome\Application\chrome.exe",
	r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
	r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
	r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
]

MAC_PATHS = [
	"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
	"/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
	"/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
	"/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def find_browser(name: str = "chrome") -> Optional[str]:
	for candidate in CANDIDATES.get(name, CANDIDATES["chrome"]):
		found = shutil.which(candidate)
		if found:
			return found
	for pattern in (WINDOWS_PATHS, MAC_PATHS):
		for path in pattern:
			if os.path.exists(path):
				return path
	return None


def launch(
	name: str = "chrome",
	port: int = DEFAULT_PORT,
	url: str = "",
	wait_seconds: float = 6.0,
) -> int:
	"""Start the browser with the debug port; returns 0 when the port answers."""
	binary = find_browser(name)
	if binary is None:
		print(
			f"Could not find a {name} binary. Open your browser with"
			f" --remote-debugging-port={port} yourself, then run tules --auto.",
			file=sys.stderr,
		)
		return 1
	command: List[str] = [binary, f"--remote-debugging-port={port}"]
	if url:
		command.append(url)
	print(f"Starting {binary} with the debugging port {port}...")
	try:
		subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	except OSError as exc:
		print(f"Could not start {binary}: {exc}", file=sys.stderr)
		return 1
	deadline = time.time() + wait_seconds
	while time.time() < deadline:
		try:
			list_targets(DEFAULT_HOST, port, timeout=1.0)
			print(f"Browser is reachable on {DEFAULT_HOST}:{port}.")
			return 0
		except Exception:
			time.sleep(0.5)
	print(
		f"The browser did not expose port {port} within {int(wait_seconds)} s"
		" (it may already have been running without the flag; close it fully and retry).",
		file=sys.stderr,
	)
	return 1
