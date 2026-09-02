"""The interactive console: type `tules`, answer questions, remember no flags."""

from tules import cli
from tules import console as console_module
from tules.browser.profiles import ProfileStore, SiteProfile
from tules.console import Console, run_console


class Script:
	"""Scripted stdin: pops canned answers; records everything printed."""

	def __init__(self, answers):
		self.answers = list(answers)
		self.printed = []

	def input_fn(self, prompt=""):
		self.printed.append(prompt)
		if not self.answers:
			raise EOFError
		item = self.answers.pop(0)
		if isinstance(item, BaseException):
			raise item
		self.printed.append(f"{item}\n")
		return item

	def output(self, text=""):
		self.printed.append(f"{text}\n")

	def text(self):
		return "".join(self.printed)


def make(answers, **kwargs):
	script = Script(answers)
	code = run_console(input_fn=script.input_fn, output=script.output, **kwargs)
	return script, code


def test_the_console_asks_the_basics_then_quits_cleanly():
	script, code = make(["", "", "", "q"])  # folder, budget, shell, quit
	assert code == 0
	text = script.text()
	assert "Workspace folder" in text
	assert "Result size limit" in text
	assert "Allow shell commands" in text
	assert "Clipboard monitor" in text
	assert "Bye." in text


def test_enter_at_the_menu_starts_the_clipboard_monitor(monkeypatch):
	started = []

	class StubMonitor:
		def __init__(self, agent, **kwargs):
			started.append(kwargs)

		def start(self, poll_seconds=0.5):
			started.append("run")

	monkeypatch.setattr("tules.monitor.ClipboardMonitor", StubMonitor)
	script, code = make(["", "", "", "", "q"])  # folder, budget, shell, menu Enter, quit
	assert code == 0
	assert {} in started and "run" in started
	assert script.text().count("What would you like to do?") == 2  # menu offered again


def test_showing_the_bootstrap_prompt():
	script, code = make(["", "", "", "3", "q"])
	assert code == 0
	assert "TULES - you are the brain" in script.text()


def test_copying_the_bootstrap_prompt_reports_either_way():
	script, code = make(["", "", "", "4", "q"])
	assert code == 0
	text = script.text()
	assert "Bootstrap prompt copied" in text or "Could not reach the system clipboard" in text


def test_listing_actions_shows_the_registry():
	script, code = make(["", "", "", "5", "q"])
	assert code == 0
	text = script.text()
	assert "replace" in text and "read_file" in text and "bash" in text


def test_running_one_payload_file_uses_the_normal_pipeline(tmp_path):
	payload = tmp_path / "p.json"
	payload.write_text('{"action":"help"}', encoding="utf-8")
	script, code = make(["", "", "", "6", str(payload), "q"])
	assert code == 0
	assert "STATUS: SUCCESS" in script.text()


def test_running_a_missing_payload_file_reports_not_crashes():
	script, code = make(["", "", "", "6", "/no/such/file.json", "q"])
	assert code == 0  # the console survives and returns to its menu
	assert "Could not read" in script.text()


def test_forgetting_a_saved_site(tmp_path):
	sites = tmp_path / "sites.json"
	store = ProfileStore(sites)
	store.save(SiteProfile(host="old.example", input_selector="#box"))
	script, code = make(["", "", "", "7", "old.example", "q"], root=".", sites_file=str(sites))
	assert code == 0
	assert "Forgot old.example" in script.text()
	assert store.load("old.example") is None


def test_a_bad_folder_is_rejected_and_asked_again():
	script, code = make(["/definitely/not/a/real/folder", "", "", "", "q"])
	assert code == 0
	assert "No such folder" in script.text()
	assert "Workspace: " in script.text()


def test_shell_can_be_disabled_from_the_console():
	script = Script(["", "", "n", "q"])
	console = Console(root=".", input_fn=script.input_fn, output=script.output)
	assert console.run() == 0
	assert console.agent.allow_shell is False


def test_automation_answers_wire_the_real_loop(monkeypatch, tmp_path):
	seen = {}

	class StubMonitor:
		def __init__(self, agent, auto_loop=None, **kwargs):
			seen["auto_loop"] = auto_loop

		def start(self, poll_seconds=0.5):
			seen["started"] = True

	monkeypatch.setattr("tules.monitor.ClipboardMonitor", StubMonitor)
	answers = [
		"",  # folder: accept the default
		"",  # budget: default
		"",  # shell: default yes
		"2",  # menu: browser automation
		"make the tests pass",  # task line
		"",  # task: finished
		"9333",  # debug port
		"77",  # response timeout
		"n",  # do not start a browser for me
		"q",  # leave after the stub returns
	]
	script = Script(answers)
	console = Console(
		root=".",
		sites_file=str(tmp_path / "sites.json"),
		input_fn=script.input_fn,
		output=script.output,
	)
	assert console.run() == 0
	assert seen["started"]
	loop = seen["auto_loop"]
	assert "make the tests pass" in loop.first_message
	assert loop.completion.timeout_seconds == 77.0
	assert loop.hotkey.mode in ("ctrl+f12", "terminal")
	assert "Ctrl+F12" in script.text()


def test_eof_and_interrupt_quit_cleanly():
	script = Script([EOFError()])
	assert run_console(input_fn=script.input_fn, output=script.output) == 0
	assert "Bye." in script.text()

	script = Script(["", KeyboardInterrupt()])
	assert run_console(input_fn=script.input_fn, output=script.output) == 0
	assert "Bye." in script.text()


def test_an_unanswerable_menu_choice_is_asked_again():
	script = Script(["", "", "", "11", "shout", "q"])
	assert Console(root=".", input_fn=script.input_fn, output=script.output).run() == 0
	assert "Pick 1-8" in script.text()


def test_bare_tules_opens_the_console_but_flags_do_not(monkeypatch, capsys):
	calls = []
	monkeypatch.setattr(console_module, "run_console", lambda **kwargs: calls.append(kwargs) or 0)
	assert cli.main([]) == 0
	assert calls == [{"root": "."}]
	assert cli.main(["sub/folder"]) == 0
	assert calls[-1] == {"root": "sub/folder"}
	assert cli.main(["--prompt"]) == 0  # flags keep working, console untouched
	assert len(calls) == 2
	capsys.readouterr()
