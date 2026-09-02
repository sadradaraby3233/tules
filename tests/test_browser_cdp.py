"""The DevTools client: protocol plumbing against a fake CDP endpoint.

The fake server speaks real WebSocket frames, so connection handling, id
matching, event skipping, and evaluate plumbing are all exercised for real.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tules.browser.cdp import (
	BrowserError,
	BrowserUnavailable,
	CDPConnection,
	Target,
	list_targets,
	pick_target,
)


class FakeDevTools:
	"""A minimal DevTools endpoint: /json/list over HTTP, calls over WS."""

	def __init__(self):
		self.received = []
		self.port = None
		self.http_port = None
		self._loop = None
		self.holder = {"ready": threading.Event(), "stop": None}
		self._http = None

	def start(self):
		import asyncio

		import websockets.asyncio.server as ws_server

		async def handler(websocket):
			async for raw in websocket:
				message = json.loads(raw)
				self.received.append(message)
				# An unsolicited event first: the client must skip it.
				await websocket.send(
					json.dumps({"method": "Page.frameStartedLoading", "params": {"frame": {}}})
				)
				await websocket.send(json.dumps(self._answer(message)))

		async def main():
			async with ws_server.serve(handler, host="127.0.0.1", port=0) as server:
				self.port = server.sockets[0].getsockname()[1]
				self.holder["ready"].set()
				await self.holder["stop"].wait()

		self._loop = asyncio.new_event_loop()
		self.holder = {"ready": threading.Event(), "stop": asyncio.Event()}
		threading.Thread(target=self._loop.run_until_complete, args=(main(),), daemon=True).start()
		assert self.holder["ready"].wait(timeout=5.0), "fake devtools server did not start"
		self._start_http()

	def _start_http(self):
		outer = self

		class Handler(BaseHTTPRequestHandler):
			def do_GET(self):
				body = json.dumps(
					[
						{
							"id": "TARGETID",
							"type": "page",
							"title": "Fake chat",
							"url": "https://fake-chat.example/chat",
							"webSocketDebuggerUrl": f"ws://127.0.0.1:{outer.port}/devtools/page/TARGETID",
						}
					]
				).encode()
				self.send_response(200)
				self.send_header("Content-Type", "application/json")
				self.send_header("Content-Length", str(len(body)))
				self.end_headers()
				self.wfile.write(body)

			def log_message(self, *args):
				pass

		self._http = HTTPServer(("127.0.0.1", 0), Handler)
		self.http_port = self._http.server_address[1]
		threading.Thread(target=self._http.serve_forever, daemon=True).start()

	def _answer(self, message):
		method = message.get("method", "")
		params = message.get("params", {})
		if method == "Runtime.evaluate":
			expression = params.get("expression", "")
			if expression == "boom":
				return {
					"id": message["id"],
					"result": {
						"exceptionDetails": {
							"text": "ReferenceError",
							"exception": {"description": "ReferenceError: boom is not defined"},
						}
					},
				}
			if expression == "slow":
				import time

				time.sleep(0.2)
			value = 2 if expression == "1+1" else {"echo": expression}
			return {"id": message["id"], "result": {"result": {"type": "object", "value": value}}}
		if method == "Input.insertText":
			assert isinstance(params.get("text"), str)
		return {"id": message["id"], "result": {}}

	def stop(self):
		if self._http:
			self._http.shutdown()
		if self._loop is not None:
			self._loop.call_soon_threadsafe(self.holder["stop"].set)


@pytest.fixture()
def devtools():
	fake = FakeDevTools()
	fake.start()
	yield fake
	fake.stop()


def make_target(port):
	return Target(
		{
			"id": "TARGETID",
			"type": "page",
			"title": "Fake chat",
			"url": "https://fake-chat.example/chat",
			"webSocketDebuggerUrl": f"ws://127.0.0.1:{port}/devtools/page/TARGETID",
		}
	)


def test_list_targets_parses_the_debug_endpoint(devtools):
	targets = list_targets(port=devtools.http_port)
	assert len(targets) == 1
	assert targets[0]["url"] == "https://fake-chat.example/chat"


def test_list_targets_when_nothing_listens():
	with pytest.raises(BrowserUnavailable):
		list_targets(port=1)  # nothing can listen on port 1 here


def test_evaluate_matches_ids_and_skips_events(devtools):
	conn = CDPConnection.attach(make_target(devtools.port))
	assert conn.evaluate("1+1") == 2
	assert conn.evaluate("({x: 1})") == {"echo": "({x: 1})"}
	conn.close()


def test_evaluate_turns_page_exceptions_into_browser_errors(devtools):
	conn = CDPConnection.attach(make_target(devtools.port))
	with pytest.raises(BrowserError) as excinfo:
		conn.evaluate("boom")
	assert "ReferenceError" in str(excinfo.value.message)
	conn.close()


def test_input_calls_reach_the_browser(devtools):
	conn = CDPConnection.attach(make_target(devtools.port))
	conn.insert_text("hello there")
	conn.press_enter()
	conn.click_at(12, 34)
	methods = [message["method"] for message in devtools.received]
	assert methods.count("Input.insertText") == 1
	assert methods.count("Input.dispatchKeyEvent") == 3
	assert methods.count("Input.dispatchMouseEvent") == 2
	conn.close()


def test_pick_target_single_and_filtered():
	only = make_target(1)
	assert pick_target([only]) is only
	ai = Target(
		{
			"id": "2",
			"type": "page",
			"title": "AI",
			"url": "https://chat.example.com/x",
			"webSocketDebuggerUrl": "ws://x/2",
		}
	)
	other = Target(
		{
			"id": "3",
			"type": "page",
			"title": "Docs",
			"url": "https://docs.example.com",
			"webSocketDebuggerUrl": "ws://x/3",
		}
	)
	assert pick_target([other, ai], prefer_host="chat.example.com") is ai


def test_pick_target_asks_via_the_chooser_when_ambiguous():
	first = make_target(1)
	second = Target(
		{
			"id": "2",
			"type": "page",
			"title": "t",
			"url": "https://b.example.com",
			"webSocketDebuggerUrl": "ws://x/2",
		}
	)
	assert pick_target([first, second], chooser=lambda pages: pages[1]) is second


def test_pick_target_without_a_choice_raises():
	with pytest.raises(BrowserError):
		pick_target([])


def test_attach_failure_is_a_browser_unavailable():
	bad = Target(
		{
			"id": "x",
			"type": "page",
			"title": "",
			"url": "https://x",
			"webSocketDebuggerUrl": "ws://127.0.0.1:1/nope",
		}
	)
	with pytest.raises(BrowserUnavailable):
		CDPConnection.attach(bad, timeout=1.0)
