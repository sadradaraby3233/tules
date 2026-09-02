"""Completion detection: never click Copy while the AI is still generating."""

from tules.browser.cdp import BrowserError
from tules.browser.page import (
	ActivityView,
	CompletionConfig,
	CompletionWatcher,
)
from tests.browser_sim import FakeClock

FAST = CompletionConfig(
	poll_seconds=0.1,
	stability_seconds=1.0,
	min_wait_seconds=0.2,
	timeout_seconds=30.0,
	progress_every=1e9,
)


class ScriptedSource:
	"""Feeds the watcher a scripted timeline, repeating the last entry after it."""

	def __init__(self, timeline):
		self.timeline = list(timeline)
		self.last = ActivityView()
		self.clock = FakeClock()

	def __call__(self) -> ActivityView:
		if self.timeline:
			self.last = self.timeline.pop(0)
		return self.last


def run(source, config=FAST, limit=2000):
	watcher = CompletionWatcher(config, source.clock, source)
	return watcher.wait()


def test_a_stable_silent_response_completes():
	source = ScriptedSource(
		[
			ActivityView(generating=True, response_len=10),
			ActivityView(generating=False, response_len=120),
			ActivityView(generating=False, response_len=120),
			ActivityView(generating=False, response_len=120),
			ActivityView(generating=False, response_len=120),
		]
	)
	outcome = run(source)
	assert outcome.complete
	assert outcome.response_len == 120


def test_streaming_growth_keeps_it_waiting_until_stable():
	source = ScriptedSource(
		[ActivityView(generating=False, response_len=10 * n) for n in range(1, 12)]
		+ [ActivityView(generating=False, response_len=110) for _ in range(15)]
	)
	outcome = run(source)
	assert outcome.complete
	assert outcome.response_len == 110


def test_a_stop_button_blocks_completion_even_when_text_is_stable():
	source = ScriptedSource([ActivityView(generating=True, response_len=500) for _ in range(40)])
	outcome = run(source)
	assert not outcome.complete
	assert outcome.generating


def test_the_copy_button_appearing_early_does_not_fool_it():
	"""ActivityView has no copy field on purpose: only growth and indicators."""
	source = ScriptedSource(
		[
			ActivityView(generating=False, response_len=300),
		]
	)
	outcome = run(source)
	assert outcome.complete  # but only after the stability window elapsed
	assert outcome.elapsed >= FAST.min_wait_seconds


def test_a_pause_then_resume_does_not_complete_during_the_pause():
	source = ScriptedSource(
		[ActivityView(generating=False, response_len=100)]
		+ [ActivityView(generating=True, response_len=100) for _ in range(8)]
		+ [ActivityView(generating=False, response_len=100) for _ in range(15)]
	)
	outcome = run(source)
	assert outcome.complete


def test_timeout_reports_still_generating():
	config = CompletionConfig(
		poll_seconds=0.1,
		stability_seconds=0.5,
		min_wait_seconds=0.1,
		timeout_seconds=2.0,
		progress_every=1e9,
	)
	source = ScriptedSource([ActivityView(generating=True, response_len=50) for _ in range(500)])
	outcome = run(source, config)
	assert not outcome.complete
	assert outcome.generating
	assert "generating" in outcome.reason


def test_timeout_when_no_response_is_ever_seen_hints_at_training():
	config = CompletionConfig(
		poll_seconds=0.1,
		stability_seconds=0.5,
		min_wait_seconds=0.1,
		timeout_seconds=1.0,
		progress_every=1e9,
	)
	source = ScriptedSource([ActivityView() for _ in range(500)])
	outcome = run(source, config)
	assert not outcome.complete
	assert outcome.response_len == 0
	assert "training" in outcome.reason


def test_repeated_page_errors_end_the_wait():
	class Broken(ScriptedSource):
		def __call__(self):
			raise BrowserError("detached")

	config = CompletionConfig(
		poll_seconds=0.05,
		stability_seconds=0.2,
		min_wait_seconds=0.0,
		timeout_seconds=60.0,
		max_errors=3,
		progress_every=1e9,
	)
	outcome = run(Broken([]), config)
	assert not outcome.complete
	assert "lost contact" in outcome.reason
