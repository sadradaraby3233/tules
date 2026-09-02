"""End-to-end: the automated Ctrl+F12 loop against a simulated AI chat site.

Every test here runs the real AutoLoop, the real completion watcher, the real
selector learning, and the real agent/clipboard protocol - only the browser is
simulated (tests.browser_sim), so a full multi-cycle session is exercised the
way the user experiences it, minus the pixels.
"""

import io

from tules.agent import Agent
from tules.browser.hotkey import Trigger
from tules.browser.loop import AutoLoop, MODE_AWAITING, MODE_FRESH, MODE_RESEND, Reporter
from tules.browser.page import CompletionConfig
from tules.browser.profiles import ProfileStore, SiteProfile
from tules.monitor import ClipboardMonitor
from tules.protocol import find_block
from tests.browser_sim import FakeClipboard, FakeClock, FakePage, FakeSite

HOST = "fake-chat.example"

REPLY_VIEW = 'Looking at the file first.\n\nedit:\n{"action":"view","file":"hello.txt"}\nendedit'
REPLY_REPLACE = (
	"Making the edit now.\n\nedit:\n"
	'{"action":"replace","file":"hello.txt","old_string":"WORLD",'
	'"new_string":"TULES WAS HERE"}\nendedit'
)
REPLY_DONE = "The task is complete. No further commands needed."


class Harness:
	"""A wired-up loop over a simulated site, driven by a virtual clock."""

	def __init__(self, tmp_path, replies, **site_options):
		self.clipboard = FakeClipboard()
		self.clock = FakeClock()
		self.site = FakeSite(self.clipboard, replies, **site_options)
		self.page = FakePage(self.site, self.clipboard, self.clock)
		self.store = ProfileStore(tmp_path / "sites.json")
		self.trigger = Trigger()
		self.output = io.StringIO()
		self.reporter = Reporter(stream=self.output)
		self.workspace = tmp_path / "ws"
		self.workspace.mkdir()
		(self.workspace / "hello.txt").write_text("HELLO WORLD\n", encoding="utf-8")
		self.agent = Agent(root=str(self.workspace))
		self.loop = AutoLoop(
			agent=self.agent,
			clipboard=self.clipboard,
			connect=lambda: self.page,
			store=self.store,
			trigger=self.trigger,
			reporter=self.reporter,
			response_timeout=200.0,
			clock=self.clock,
			task="Make the hello file say TULES",
		)
		self.loop.completion = CompletionConfig(
			poll_seconds=0.1,
			stability_seconds=0.8,
			min_wait_seconds=0.2,
			timeout_seconds=200.0,
			progress_every=1e9,
		)

	def status(self) -> str:
		return self.output.getvalue()

	def user_turns(self):
		return [
			el.text
			for el in self.site.chat.children
			if el.attr("data-message-author-role") == "user"
		]


def test_full_session_runs_multiple_cycles_without_intervention(tmp_path):
	h = Harness(tmp_path, [REPLY_VIEW, REPLY_REPLACE, REPLY_DONE])
	h.loop.run_session()

	assert "TULES - you are the brain" in h.user_turns()[0]
	assert "TASK from the user" in h.user_turns()[0]
	assert "TULES WAS HERE" in (h.workspace / "hello.txt").read_text(encoding="utf-8")
	assert h.loop.cycles == 2
	assert h.loop.mode == MODE_AWAITING
	assert h.clipboard.read() == REPLY_DONE
	assert "Automated session finished" in h.status()
	assert len(h.user_turns()) == 3  # bootstrap, then two agent replies


def test_every_required_status_is_reported_during_a_session(tmp_path):
	h = Harness(tmp_path, [REPLY_VIEW, REPLY_DONE])
	h.loop.run_session()
	text = h.status()
	for expected in (
		"Pasting the agent's message",
		"Waiting for the AI to finish responding",
		"Waiting for the Copy button",
		"Reading the clipboard",
		"Processing the AI response",
		"Writing the agent reply to the clipboard",
	):
		assert expected in text, expected


def test_consecutive_sessions_resume_without_repeating_the_bootstrap(tmp_path):
	h = Harness(tmp_path, [REPLY_VIEW, REPLY_REPLACE, REPLY_DONE])
	h.loop.run_session()

	# The user replies manually (types and presses Enter), then hits the hotkey.
	h.site.replies.append(
		"edit:\n" + '{"action":"bash","command":"echo cycled","timeout":30}\nendedit'
	)
	h.site.replies.append("Finished for real this time.")
	h.site.box = "Now run the tests."
	h.site.submit()
	h.loop.run_session()

	assert h.loop.cycles == 3
	bootstraps = [turn for turn in h.user_turns() if "you are the brain" in turn]
	assert len(bootstraps) == 1  # never pasted twice
	assert any("cycled" in turn for turn in h.user_turns())
	assert h.loop.mode == MODE_AWAITING


def test_hotkey_request_starts_exactly_one_session(tmp_path):
	h = Harness(tmp_path, [REPLY_DONE])
	h.loop.request_start()
	assert h.loop.consume_trigger() is True
	h.loop.run_session()
	assert h.loop.consume_trigger() is False
	assert h.status().count("Fresh start") == 1


def test_hotkey_press_with_text_already_in_the_box_pauses_without_overwriting(tmp_path):
	h = Harness(tmp_path, [REPLY_DONE])
	h.site.box = "My own half-typed question"
	h.loop.run_session()

	assert "already contains text" in h.status()
	assert h.site.box == "My own half-typed question"  # untouched
	assert h.loop.mode == MODE_FRESH  # retry pastes the bootstrap again
	assert h.user_turns() == []


def test_first_session_creates_a_profile_and_later_sessions_reuse_it(tmp_path):
	h = Harness(tmp_path, [REPLY_VIEW, REPLY_DONE])
	h.loop.run_session()
	profile = h.store.load(HOST)
	assert profile is not None
	assert profile.input_selector
	assert profile.copy_selector

	h.output.truncate(0)
	h.output.seek(0)
	h.site.replies.append(REPLY_VIEW)
	h.site.replies.append("Done.")
	h.site.box = "Again."
	h.site.submit()
	h.loop.run_session()
	assert "Identified the message box automatically" not in h.status()
	assert "Identified the Copy button" not in h.status()
	assert h.loop.cycles == 2


def test_stale_saved_selector_is_detected_and_relearned(tmp_path):
	h = Harness(tmp_path, [REPLY_DONE])
	h.store.save(SiteProfile(host=HOST, input_selector="#element-from-an-old-design"))
	h.loop.run_session()

	assert "the site may have changed" in h.status()
	assert h.store.load(HOST).input_selector == "#prompt-input"
	assert "Automated session finished" in h.status()


def test_failing_copy_button_pauses_with_guidance(tmp_path):
	h = Harness(tmp_path, [REPLY_DONE], copy_works=False)
	h.loop.run_session()
	assert "did not put anything new on the clipboard" in h.status()
	assert h.loop.mode == MODE_AWAITING


def test_a_tules_reply_on_the_clipboard_pauses_as_a_wrong_copy(tmp_path):
	h = Harness(tmp_path, ["STATUS: SUCCESS\nMESSAGE: this is TULES output"])
	h.loop.run_session()
	assert "holds a TULES reply" in h.status()
	assert h.loop.cycles == 0


def test_response_that_never_completes_hits_the_timeout_and_pauses(tmp_path):
	h = Harness(tmp_path, [REPLY_DONE], rate=0.0)
	h.loop.completion.timeout_seconds = 5.0
	h.loop.run_session()
	assert "gave up waiting after" in h.status()
	assert h.loop.cycles == 0
	assert h.loop.mode == MODE_AWAITING


def test_slow_streaming_response_is_waited_out_not_interrupted(tmp_path):
	h = Harness(tmp_path, [REPLY_VIEW, REPLY_DONE], rate=3.0)
	h.loop.run_session()
	assert h.loop.cycles == 1
	assert "TULES WAS HERE" not in (h.workspace / "hello.txt").read_text(encoding="utf-8")


def test_long_response_survives(tmp_path):
	long_body = "line of analysis\n" * 400 + (
		"edit:\n" + '{"action":"view","file":"hello.txt"}\nendedit'
	)
	h = Harness(tmp_path, [long_body, REPLY_DONE])
	h.loop.run_session()
	assert h.loop.cycles == 1


def test_a_network_style_latency_before_streaming_is_handled(tmp_path):
	h = Harness(tmp_path, [REPLY_DONE], latency=15.0)
	h.loop.run_session()
	assert h.loop.cycles == 0  # finished: the reply had no command block
	assert "Automated session finished" in h.status()


def test_enter_not_submitting_falls_back_to_the_send_button(tmp_path):
	h = Harness(tmp_path, [REPLY_DONE], enter_submits=False)
	h.loop.run_session()
	assert h.site.send_clicks == 1
	assert "Automated session finished" in h.status()


def test_a_failed_submit_resumes_by_repasting(tmp_path):
	h = Harness(tmp_path, [REPLY_VIEW, REPLY_DONE], enter_submits=False)
	h.site.send_button.visible = False  # neither Enter nor a send button works
	h.loop.run_session()
	assert "could not be submitted" in h.status()
	assert h.loop.mode == MODE_RESEND

	h.site.send_button.visible = True  # the user fixes the site, hits the hotkey
	h.loop.run_session()
	assert h.loop.cycles == 1
	assert "Automated session finished" in h.status()


def test_teaching_the_message_box_by_focus(tmp_path):
	h = Harness(tmp_path, [REPLY_DONE], hide_input=True)
	target = h.site.composer.add(
		__import__("tests.browser_sim", fromlist=["FakeEl"]).FakeEl(
			"div", id="editor-box", editable=True, kind="contenteditable"
		)
	)
	h.site.teach_input_target = target
	h.site.teach_delay = 1.0
	h.loop.run_session()

	assert "cannot tell which box is the AI message box" in h.status()
	assert h.store.load(HOST).input_selector == "#editor-box"
	assert "Automated session finished" in h.status()
	assert h.user_turns()  # the bootstrap was pasted through the taught box


def test_teaching_the_copy_button_by_click_also_copies(tmp_path):
	h = Harness(tmp_path, [REPLY_DONE], hide_copy=True)
	h.site.teach_delay = 1.0
	h.loop.run_session()

	assert "Click the AI response's Copy button ONCE" in h.status()
	assert h.site.copy_clicks == 1  # the user's teach click did the copying
	assert h.store.load(HOST).copy_selector == 'button[aria-label="Copy"]'
	assert h.clipboard.read() == REPLY_DONE
	assert "Automated session finished" in h.status()


def test_unreachable_browser_pauses_with_debug_help(tmp_path):
	h = Harness(tmp_path, [REPLY_DONE])

	def broken_connect():
		raise Exception("simulated: no browser")

	h.loop.connect = broken_connect
	h.loop.run_session()
	assert "unexpected automation failure" in h.status()
	assert h.loop.mode == MODE_FRESH


def test_browser_unavailable_reports_paused_state(tmp_path):
	from tules.browser.cdp import BrowserUnavailable

	h = Harness(tmp_path, [REPLY_DONE])

	def offline():
		raise BrowserUnavailable("no browser on 127.0.0.1:9222")

	h.loop.connect = offline
	h.loop.run_session()
	assert "cannot reach the browser" in h.status()
	assert h.loop.mode == MODE_FRESH


def test_monitor_stands_aside_while_a_session_owns_the_clipboard(tmp_path, monkeypatch):
	agent = Agent(root=str(tmp_path))
	clipboard = FakeClipboard()

	class StubLoop:
		active = True

		def consume_trigger(self):
			return False

	monitor = ClipboardMonitor(
		agent, clipboard=clipboard, notify=lambda: None, auto_loop=StubLoop()
	)
	monitor.seen = clipboard.read()
	clipboard.write("edit:\n" + '{"action":"view","file":"x.txt"}\nendedit')
	processed = []
	monkeypatch.setattr(monitor, "handle", lambda payload: processed.append(payload) or "reply")
	monitor.poll()
	assert processed == []  # suppressed while the automation session is active

	StubLoop.active = False
	clipboard.write("edit:\n" + '{"action":"glob","pattern":"*.txt"}\nendedit')
	monitor.poll()
	assert len(processed) == 1  # manual clipboard flow resumes untouched


def test_monitor_consumes_the_hotkey_trigger_and_runs_the_session(tmp_path):
	agent = Agent(root=str(tmp_path))

	class StubLoop:
		active = False

		def __init__(self, monitor):
			self.monitor = monitor
			self.events = []

		def consume_trigger(self):
			self.events.append("trigger")
			self.monitor.stop()
			return True

		def run_session(self):
			self.events.append("session")

	monitor = ClipboardMonitor(agent, clipboard=FakeClipboard(), notify=lambda: None)
	monitor.auto_loop = StubLoop(monitor)
	monitor.start(poll_seconds=0.01)
	assert monitor.auto_loop.events == ["trigger", "session"]


def test_find_block_still_guards_the_loop_protocol():
	payload = 'chat text\nedit:\n{"action":"help"}\nendedit\nthanks'
	assert find_block(payload) == '{"action":"help"}'
	assert find_block("plain answer, nothing to run") is None


def test_a_hotkey_press_made_during_a_session_is_dropped_not_queued(tmp_path):
	h = Harness(tmp_path, [REPLY_DONE])
	h.loop.request_start()  # the user presses again while the session runs
	h.loop.run_session()
	assert h.loop.consume_trigger() is False
	assert h.status().count("Fresh start") == 1


def test_saved_generating_selector_is_offered_to_the_page_first(tmp_path):
	"""A hand-tuned profile field must reach the page, not sit unused on disk."""
	harness = Harness(tmp_path, [REPLY_DONE])
	harness.store.save(
		SiteProfile(
			host=HOST,
			input_selector="#prompt",
			copy_selector="button.copy",
			generating_selector=".busy-dot",
		)
	)
	default_first = harness.page.generating_selectors[0]
	assert default_first != ".busy-dot"
	harness.loop._apply_saved_generating_selector(harness.page, HOST)
	assert harness.page.generating_selectors[0] == ".busy-dot"
	harness.loop._apply_saved_generating_selector(harness.page, HOST)
	assert harness.page.generating_selectors.count(".busy-dot") == 1, "re-attach must not stack"


def test_an_unknown_or_broken_generating_selector_leaves_the_defaults_alone(tmp_path):
	harness = Harness(tmp_path, [REPLY_DONE])
	defaults = list(harness.page.generating_selectors)
	harness.store.save(
		SiteProfile(host=HOST, input_selector="#prompt", copy_selector="button.copy")
	)
	harness.loop._apply_saved_generating_selector(harness.page, HOST)
	harness.loop._apply_saved_generating_selector(harness.page, "never-seen.example")
	assert harness.page.generating_selectors == defaults
