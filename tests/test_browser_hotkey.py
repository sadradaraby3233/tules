"""The Ctrl+F12 trigger and its terminal fallback."""

import sys

from tules.browser.hotkey import HotkeyWatcher, Trigger


def test_trigger_is_a_one_shot_flag_across_threads():
	trigger = Trigger()
	assert trigger.consume() is False
	trigger.request()
	assert trigger.consume() is True
	assert trigger.consume() is False  # a second press is a new request


def test_stdin_fallback_triggers_on_enter_or_go(monkeypatch):
	lines = iter(["\n", "go", "unrelated", "q"])
	monkeypatch.setattr(sys, "stdin", type("Stdin", (), {"__iter__": lambda self: lines})())
	trigger = Trigger()
	reports = []
	watcher = HotkeyWatcher(trigger, reports.append).start(prefer="stdin")
	assert watcher.mode == "terminal"
	assert trigger.wait(timeout=2.0)
	assert trigger.consume() is True


def test_stdin_fallback_survives_a_closed_terminal(monkeypatch):
	class Closed:
		def __iter__(self):
			raise OSError("stdin closed")

	monkeypatch.setattr(sys, "stdin", Closed())
	trigger = Trigger()
	reports = []
	watcher = HotkeyWatcher(trigger, reports.append).start(prefer="stdin")
	assert watcher.mode == "terminal"  # the watcher thread dies quietly, no crash


def test_hotkey_off_reports_and_does_not_watch():
	reports = []
	watcher = HotkeyWatcher(Trigger(), reports.append).start(prefer="off")
	assert watcher.mode == "off"
	assert any("disabled" in line for line in reports)


def test_pynput_missing_falls_back_to_terminal(monkeypatch):
	monkeypatch.setitem(sys.modules, "pynput", None)  # import fails
	reports = []
	watcher = HotkeyWatcher(Trigger(), reports.append).start(prefer="auto")
	assert watcher.mode == "terminal"
