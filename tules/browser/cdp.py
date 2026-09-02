"""A small synchronous Chrome DevTools Protocol client.

This is what lets TULES drive the user's own browser tab at the DOM level:
trusted key and mouse events, text insertion, and JavaScript evaluation.
No coordinates are ever guessed: clicks happen only at rectangles TULES has
just measured on a confidently identified element.

Requires the ``websocket-client`` package (``pip install "tules[browser]"``).
"""

import json
from contextlib import suppress
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9222
CALL_TIMEOUT = 15.0


class BrowserError(Exception):
	"""A browser automation problem that should pause the loop, not crash it."""

	def __init__(self, message: str, **details: Any):
		super().__init__(message)
		self.message = message
		self.details = details


class BrowserUnavailable(BrowserError):
	"""The debug port answered nothing: the browser is not reachable."""


def debug_help(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> str:
	return (
		f"TULES could not reach a browser on {host}:{port}.\n"
		"Start your browser with a remote-debugging port, open the AI chat, then press\n"
		"the hotkey again. Examples:\n"
		"  chrome:   chrome --remote-debugging-port=9222\n"
		"  edge:     msedge --remote-debugging-port=9222\n"
		"  chromium: chromium --remote-debugging-port=9222\n"
		"Or run: tules --launch-browser chrome"
	)


def _http_json(url: str, timeout: float) -> Any:
	request = urllib.request.Request(url, headers={"Connection": "close"})
	with urllib.request.urlopen(request, timeout=timeout) as response:
		return json.loads(response.read().decode("utf-8", "replace"))


def list_targets(
	host: str = DEFAULT_HOST,
	port: int = DEFAULT_PORT,
	timeout: float = 2.0,
) -> List[Dict[str, Any]]:
	"""The pages the debug port exposes (DevTools ``/json/list``)."""
	url = f"http://{host}:{port}/json/list"
	try:
		targets = _http_json(url, timeout)
	except (OSError, urllib.error.URLError, ValueError) as exc:
		raise BrowserUnavailable(f"no browser on {host}:{port} ({exc.__class__.__name__})") from exc
	if not isinstance(targets, list):
		raise BrowserUnavailable(f"unexpected answer from {url}")
	return [item for item in targets if isinstance(item, dict)]


class Target:
	"""One open tab we could attach to."""

	def __init__(self, data: Dict[str, Any]):
		self.target_id = str(data.get("id", ""))
		self.title = str(data.get("title", ""))
		self.url = str(data.get("url", ""))
		self.ws_url = str(data.get("webSocketDebuggerUrl", ""))
		self.type = str(data.get("type", ""))

	@property
	def is_page(self) -> bool:
		return self.type == "page" and bool(self.ws_url)

	def host(self) -> str:
		url = self.url
		if "://" in url:
			url = url.split("://", 1)[1]
		return url.split("/", 1)[0].split(":", 1)[0].lower()

	def describe(self) -> str:
		return f"{self.title[:60]!r} {self.url[:80]}"


def pick_target(targets: List[Target], prefer_host: Optional[str] = None, chooser=None) -> Target:
	"""Choose a tab: the AI site if visible, else the only page, else ask."""
	pages = [item for item in targets if item.is_page]
	if not pages:
		raise BrowserUnavailable("the browser exposes no automatable page")
	if prefer_host:
		matching = [item for item in pages if item.host() == prefer_host]
		if matching:
			pages = matching
	if len(pages) == 1:
		return pages[0]
	if chooser is not None:
		return chooser(pages)
	listing = "\n".join(f"  {index + 1}. {item.describe()}" for index, item in enumerate(pages))
	raise BrowserError(
		"several tabs are open; close the others or pick one:\n" + listing,
		tabs=[item.url for item in pages],
	)


class CDPConnection:
	"""One attached tab. Calls are matched by id; events are ignored."""

	def __init__(self, ws):
		self._ws = ws
		self._next_id = 0

	@classmethod
	def attach(cls, target: Target, timeout: float = 10.0) -> "CDPConnection":
		try:
			import websocket
		except ImportError as exc:  # pragma: no cover - environment guard
			raise BrowserError(
				'websocket-client is required for browser automation: pip install "tules[browser]"'
			) from exc
		try:
			ws = websocket.create_connection(target.ws_url, timeout=timeout, suppress_origin=True)
		except Exception as exc:
			raise BrowserUnavailable(f"could not attach to the tab ({exc})") from exc
		return cls(ws)

	def call(self, method: str, timeout: float = CALL_TIMEOUT, **params: Any) -> Any:
		self._next_id += 1
		identifier = self._next_id
		message = json.dumps({"id": identifier, "method": method, "params": params})
		self._ws.settimeout(timeout)
		try:
			self._ws.send(message)
			while True:
				raw = self._ws.recv()
				if not raw:
					raise BrowserError(f"the browser closed the connection during {method}")
				data = json.loads(raw)
				if data.get("id") != identifier:
					continue  # an event we did not ask for
				if "error" in data:
					error = data["error"]
					raise BrowserError(f"{method} failed: {error.get('message', error)}")
				return data.get("result", {})
		except BrowserError:
			raise
		except Exception as exc:
			raise BrowserError(f"{method} failed: {exc}") from exc

	def evaluate(self, expression: str, timeout: float = CALL_TIMEOUT) -> Any:
		result = self.call(
			"Runtime.evaluate",
			timeout=timeout,
			expression=expression,
			returnByValue=True,
			awaitPromise=True,
		)
		if result.get("exceptionDetails"):
			detail = result["exceptionDetails"]
			text = detail.get("exception", {}).get("description") or detail.get("text")
			text = text or "page error"
			raise BrowserError(f"the page rejected our script: {text[:200]}")
		value = result.get("result", {})
		if value.get("type") == "undefined":
			return None
		return value.get("value")

	def insert_text(self, text: str) -> None:
		"""Trusted IME-style insertion: lands in the focused editable element."""
		self.call("Input.insertText", text=text)

	def press_enter(self) -> None:
		for kind in ("rawKeyDown", "keyDown", "keyUp"):
			params: Dict[str, Any] = {
				"type": kind,
				"key": "Enter",
				"code": "Enter",
				"windowsVirtualKeyCode": 13,
				"nativeVirtualKeyCode": 13,
			}
			if kind != "keyUp":
				params["text"] = "\r"
			self.call("Input.dispatchKeyEvent", **params)

	def click_at(self, x: float, y: float) -> None:
		for kind in ("mousePressed", "mouseReleased"):
			self.call(
				"Input.dispatchMouseEvent",
				type=kind,
				x=int(x),
				y=int(y),
				button="left",
				buttons=1 if kind == "mousePressed" else 0,
				clickCount=1,
			)

	def close(self) -> None:
		with suppress(Exception):
			self._ws.close()


def connect(
	host: str = DEFAULT_HOST,
	port: int = DEFAULT_PORT,
	prefer_host: Optional[str] = None,
	chooser=None,
) -> "tuple[Target, CDPConnection]":
	"""Find the AI chat tab and attach to it."""
	targets = [Target(item) for item in list_targets(host, port)]
	target = pick_target(targets, prefer_host=prefer_host, chooser=chooser)
	return target, CDPConnection.attach(target)
