"""CLI surface for the browser automation: flags, wiring, and forgetting."""

import pytest

from tules.agent import Agent
from tules.cli import _build_auto_loop, _forget_site, build_parser


def test_auto_flags_exist_and_default_off():
	options = build_parser().parse_args([])
	assert options.auto is False
	assert options.cdp_host is None
	assert options.cdp_port is None
	assert options.response_timeout == 600.0
	assert options.hotkey == "auto"
	assert options.task == ""


def test_auto_flags_parse():
	options = build_parser().parse_args(
		[
			"--auto",
			"--task",
			"fix the bug",
			"--cdp-port",
			"9333",
			"--response-timeout",
			"90",
			"--hotkey",
			"stdin",
			"--sites-file",
			"/tmp/sites.json",
			"--page-clipboard",
		]
	)
	assert options.auto is True
	assert options.task == "fix the bug"
	assert options.cdp_port == 9333
	assert options.response_timeout == 90.0
	assert options.hotkey == "stdin"
	assert options.page_clipboard is True


def test_build_auto_loop_wires_trigger_and_first_message(tmp_path):
	options = build_parser().parse_args(
		[
			"--auto",
			"--sites-file",
			str(tmp_path / "sites.json"),
			"--hotkey",
			"off",
			"--task",
			"Ship it",
		]
	)
	agent = Agent(root=str(tmp_path))
	loop = _build_auto_loop(options, agent)
	assert "Ship it" in loop.first_message
	assert "TULES - you are the brain" in loop.first_message
	assert loop.mode == "fresh"
	assert loop.hotkey.mode == "off"


def test_build_auto_loop_without_a_task_is_the_plain_bootstrap(tmp_path):
	options = build_parser().parse_args(
		[
			"--auto",
			"--sites-file",
			str(tmp_path / "s.json"),
			"--hotkey",
			"off",
		]
	)
	loop = _build_auto_loop(options, Agent(root=str(tmp_path)))
	assert loop.first_message.strip().startswith("TULES - you are the brain")


def test_forgetting_a_site_uses_the_store(tmp_path, capsys):
	from tules.browser.profiles import ProfileStore, SiteProfile

	sites = str(tmp_path / "sites.json")
	store = ProfileStore(tmp_path / "sites.json")
	store.save(SiteProfile(host="old.example", input_selector="#box"))

	assert _forget_site("old.example", sites) == 0
	assert store.load("old.example") is None
	assert "Forgot" in capsys.readouterr().out

	assert _forget_site("old.example", sites) == 1
	assert "No saved locations" in capsys.readouterr().out


def test_build_parser_rejects_unknown_hotkey_choice():
	with pytest.raises(SystemExit):
		build_parser().parse_args(["--auto", "--hotkey", "shout"])
