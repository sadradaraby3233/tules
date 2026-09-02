from tules.monitor import ClipboardMonitor, run_payload


class FakeClipboard:
	def __init__(self, text=""):
		self.text = text
		self.writes = []

	def read(self):
		return self.text

	def write(self, text):
		self.text = text
		self.writes.append(text)
		return True


def test_unknown_action_lists_the_available_ones(agent):
	result = agent.run({"action": "teleport"})
	assert not result.success
	assert "search" in result.details["content"]


def test_non_object_command_is_rejected(agent):
	assert not agent.run(["not", "a", "dict"]).success


def test_missing_argument_is_reported(agent):
	result = agent.run({"action": "read_file"})
	assert not result.success
	assert "file" in result.message


def test_read_file_returns_the_content(agent):
	result = agent.run({"action": "read_file", "file": "sample.py"})
	assert result.success
	assert "def greet" in result.details["content"]


def test_view_numbers_the_lines(agent):
	result = agent.run({"action": "view", "file": "notes.md"})
	assert result.details["content"].splitlines()[0].endswith("| # notes")


def test_search_finds_a_literal(agent):
	result = agent.run({"action": "search", "search": "greet"})
	assert result.success
	assert {match["file"] for match in result.details["matches"]} == {"sample.py"}


def test_search_regex_reports_matches(agent):
	result = agent.run({"action": "search_regex", "search": r"^class \w+"})
	assert result.details["matches"][0]["line"] == 8


def test_help_is_an_alias_for_list_actions(agent):
	assert agent.run({"action": "help"}).success


def test_str_replace_edits_and_reviews(agent):
	result = agent.run(
		{"action": "str_replace", "file": "sample.py", "old_str": "import os\n", "new_str": ""}
	)
	assert result.success
	assert "backup" in result.details


def test_post_edit_review_warns_about_unused_imports(agent):
	result = agent.run(
		{
			"action": "str_replace",
			"file": "sample.py",
			"old_str": "class Widget:",
			"new_str": "class Gadget:",
		}
	)
	assert any("unused import" in warning for warning in result.warnings)


def test_syntax_guard_surfaces_the_blast_radius(agent):
	result = agent.run(
		{
			"action": "str_replace",
			"file": "sample.py",
			"old_str": "def greet(name):",
			"new_str": "def greet(name:",
		}
	)
	assert not result.success
	assert result.details["blast_radius"]


def test_validate_batch_checks_every_command(agent):
	result = agent.run(
		{
			"action": "validate_batch",
			"commands": [
				{"action": "str_replace", "file": "sample.py", "old_str": "greet"},
				{"action": "str_replace", "file": "sample.py", "old_str": "absent"},
			],
		}
	)
	assert not result.success
	assert result.details["checks"][0]["valid"] is False
	assert "NOT_UNIQUE" in result.details["checks"][0]["reason"]
	assert result.details["checks"][1]["reason"].startswith("Search string not found")


def test_validate_batch_accepts_an_ambiguous_replace_that_says_how_to_resolve_it(agent):
	result = agent.run(
		{
			"action": "validate_batch",
			"commands": [
				{
					"action": "replace",
					"file": "sample.py",
					"old_string": "greet",
					"new_string": "hello",
					"replace_all": True,
				},
				{
					"action": "replace",
					"file": "sample.py",
					"old_string": 'return f"hello {name}"',
					"new_string": "return name",
				},
			],
		}
	)
	assert result.success
	assert [item["valid"] for item in result.details["checks"]] == [True, True]


def test_validate_batch_reports_a_fuzzy_replace_as_landable(agent):
	result = agent.run(
		{
			"action": "validate_batch",
			"commands": [
				{
					"action": "replace",
					"file": "sample.py",
					"old_string": "def  greet( name ):",
					"new_string": "def greet(name):",
				}
			],
		}
	)
	check = result.details["checks"][0]
	assert check["valid"] is True
	assert "Fuzzy match" in check["reason"]


def test_run_is_refused_when_shell_is_disabled(agent):
	agent.allow_shell = False
	assert not agent.run({"action": "run", "command": "echo hi"}).success


def test_run_executes_in_the_workspace_root(agent):
	result = agent.run({"action": "run", "command": 'python -c "import os;print(os.getcwd())"'})
	assert result.success
	assert str(agent.root) in result.details["stdout"]


def test_memory_round_trip(agent):
	agent.run({"action": "memory", "action_type": "write", "content": "remember this"})
	result = agent.run({"action": "memory", "action_type": "read"})
	assert "remember this" in result.details["content"]


def test_memory_supports_a_custom_target(agent):
	agent.run(
		{
			"action": "memory",
			"action_type": "write",
			"target": "design notes",
			"content": "keep it simple",
		}
	)
	result = agent.run({"action": "memory", "action_type": "read", "target": "design notes"})
	assert "keep it simple" in result.details["content"]
	assert agent.run({"action": "memory", "action_type": "read"}).details["content"] == ""


def test_memory_lists_its_files(agent):
	agent.run({"action": "memory", "action_type": "write", "target": "todo", "content": "x"})
	agent.run({"action": "memory", "action_type": "write", "target": "ideas", "content": "y"})
	files = agent.run({"action": "memory", "action_type": "list"}).details["files"]
	assert set(files) == {"todo.md", "ideas.md"}


def test_memory_rejects_a_target_that_sanitizes_to_nothing(agent):
	result = agent.run({"action": "memory", "action_type": "read", "target": "../.."})
	assert not result.success
	assert "Invalid memory target" in result.message


def test_undo_restores_the_previous_version(agent):
	agent.run({"action": "str_replace", "file": "notes.md", "old_str": "alpha", "new_str": "omega"})
	assert agent.run({"action": "undo", "file": "notes.md"}).success
	assert "alpha" in (agent.root / "notes.md").read_text(encoding="utf-8")


def test_batch_runs_every_command(agent):
	results = agent.run_batch(
		[
			{"action": "read_file", "file": "notes.md"},
			{"action": "read_file", "file": "missing.md"},
		]
	)
	assert [item.success for item in results] == [True, False]


def test_run_payload_renders_a_reply(agent):
	reply = run_payload(agent, '{"action": "read_file", "file": "notes.md"}')
	assert reply.startswith("STATUS: SUCCESS")


def test_run_payload_reports_bad_json(agent):
	assert run_payload(agent, "{oops").startswith("STATUS: FAILED")


def test_monitor_handles_a_clipboard_block(agent):
	clipboard = FakeClipboard('edit: {"action": "read_file", "file": "notes.md"} endedit')
	monitor = ClipboardMonitor(agent, clipboard=clipboard, notify=lambda: None)
	reply = monitor.poll()
	assert reply.startswith("STATUS: SUCCESS")
	assert clipboard.writes == [reply]


def test_monitor_ignores_its_own_reply(agent):
	clipboard = FakeClipboard('edit: {"action": "read_file", "file": "notes.md"} endedit')
	monitor = ClipboardMonitor(agent, clipboard=clipboard, notify=lambda: None)
	monitor.poll()
	assert monitor.poll() is None
	assert len(clipboard.writes) == 1


def test_monitor_ignores_unrelated_clipboard_text(agent):
	monitor = ClipboardMonitor(
		agent, clipboard=FakeClipboard("just a copied word"), notify=lambda: None
	)
	assert monitor.poll() is None


def test_monitor_reruns_the_same_block_when_copied_again(agent):
	block = 'edit: {"action": "read_file", "file": "notes.md"} endedit'
	clipboard = FakeClipboard(block)
	monitor = ClipboardMonitor(agent, clipboard=clipboard, notify=lambda: None)
	first = monitor.poll()
	assert first.startswith("STATUS: SUCCESS")
	# The reply now sits on the clipboard; copying the identical block re-triggers.
	clipboard.text = block
	second = monitor.poll()
	assert second == first
	assert len(clipboard.writes) == 2


def test_monitor_skips_a_reply_pasted_back_as_input(agent):
	clipboard = FakeClipboard("STATUS: SUCCESS\nMESSAGE: Edited app.py")
	monitor = ClipboardMonitor(agent, clipboard=clipboard, notify=lambda: None)
	assert monitor.poll() is None
	assert clipboard.writes == []
