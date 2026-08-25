"""Universal replacement cascade and Claude-compatible shell tools."""

from unittest.mock import patch


def replace(agent, file, old, new, **extra):
	return agent.run(
		{
			"action": "replace",
			"file": file,
			"old_string": old,
			"new_string": new,
			**extra,
		}
	)


def test_universal_replace_exact_and_parameter_compatibility(agent):
	result = replace(agent, "notes.md", "alpha", "ALPHA")
	assert result.success
	assert result.details["match_level"] == "exact"


def test_universal_replace_preserves_curly_quote_typography(agent):
	path = agent.root / "quotes.md"
	path.write_text("He said “old words” today.\n")
	result = replace(agent, "quotes.md", 'He said "old words" today.', 'He said "new words" today.')
	assert result.success
	assert result.details["match_level"] == "normalized_quotes"
	assert path.read_text() == "He said “new words” today.\n"


def test_universal_replace_whitespace_fallback(agent):
	path = agent.root / "spacing.txt"
	path.write_text("before\n\tif ready:\n\t\tlaunch()\nafter\n")
	result = replace(agent, "spacing.txt", "if ready:\n    launch()", "if ready:\n    start()")
	assert result.success
	assert result.details["match_level"] == "whitespace"
	assert "\tif ready:\n\t\tstart()" in path.read_text()


def test_universal_replace_token_fallback(agent):
	path = agent.root / "tokens.txt"
	path.write_text("value    =    make(  1  )\n")
	result = replace(agent, "tokens.txt", "value = make( 1 )", "value = make(2)")
	assert result.success
	assert result.details["match_level"] == "tokens"


def test_universal_replace_ast_fallback(agent):
	result = replace(
		agent, "sample.py", "def greet(name): ...", "def greet(name):\n\treturn name.upper()"
	)
	assert result.success
	assert result.details["match_level"] == "ast"


def test_universal_replace_fuzzy_fallback_is_confidence_gated(agent):
	path = agent.root / "fuzzy.txt"
	path.write_text("before\nthe quick brown fox jumps\nafter\n")
	result = replace(
		agent,
		"fuzzy.txt",
		"the quick brown fox jmps",
		"the quick red fox jumps",
		confidence_threshold=0.85,
	)
	assert result.success
	assert result.details["match_level"] == "fuzzy"
	failed = replace(agent, "fuzzy.txt", "completely unrelated", "x")
	assert not failed.success
	assert "NO_CONFIDENT_MATCH" in failed.message


def test_universal_replace_refuses_ambiguity_and_returns_candidates(agent):
	path = agent.root / "ambiguous.txt"
	path.write_text("same\nmiddle\nsame\n")
	result = replace(agent, "ambiguous.txt", "same", "changed")
	assert not result.success
	assert result.details["occurrences"] == 2
	assert len(result.details["candidates"]) == 2
	assert path.read_text() == "same\nmiddle\nsame\n"


def test_universal_replace_resolves_ambiguity_with_context(agent):
	path = agent.root / "context-choice.txt"
	path.write_text("first\nsame\nsecond\nsame\nlast\n")
	result = replace(
		agent, "context-choice.txt", "same", "changed",
		context_before="second", context_after="last")
	assert result.success
	assert result.details["match_level"] == "context"
	assert path.read_text() == "first\nsame\nsecond\nchanged\nlast\n"


def test_universal_replace_resolves_ambiguity_with_match_id(agent):
	path = agent.root / "chosen.txt"
	path.write_text("same\nmiddle\nsame\n")
	result = replace(agent, "chosen.txt", "same", "changed", match_id=1)
	assert result.success
	assert path.read_text() == "same\nmiddle\nchanged\n"


def test_universal_replace_deletes_a_whole_line_without_blank_space(agent):
	path = agent.root / "delete-line.txt"
	path.write_text("before\nremove me\nafter\n")
	result = replace(agent, "delete-line.txt", "remove me", "")
	assert result.success
	assert path.read_text() == "before\nafter\n"


def test_universal_replace_all_is_explicit(agent):
	path = agent.root / "all.txt"
	path.write_text("same same same\n")
	result = replace(agent, "all.txt", "same", "changed", replace_all=True)
	assert result.success
	assert result.details["occurrences"] == 3
	assert path.read_text() == "changed changed changed\n"


def test_universal_replace_can_create_or_fill_empty_file(agent):
	created = replace(agent, "new.txt", "", "new content\n")
	assert created.success
	assert (agent.root / "new.txt").read_text() == "new content\n"
	(agent.root / "empty.txt").write_text("")
	filled = replace(agent, "empty.txt", "", "filled\n")
	assert filled.success
	assert filled.details["match_level"] == "empty_file"
	failed = replace(agent, "notes.md", "", "overwrite")
	assert not failed.success


def test_every_legacy_replace_name_uses_universal_engine(agent):
	aliases = [
		("edit", {"file_path": "alias.txt", "old_string": "one", "new_string": "two"}),
		("str_replace", {"file": "alias.txt", "old_str": "one", "new_str": "two"}),
		("surgical_replace", {"file": "alias.txt", "search": "one", "replace_with": "two"}),
		("context_replace", {"file": "alias.txt", "search": "one", "replace_with": "two"}),
	]
	for action, fields in aliases:
		(agent.root / "alias.txt").write_text("one\n")
		result = agent.run({"action": action, **fields})
		assert result.success
		assert result.details["match_level"] == "exact"


def test_bash_uses_workspace_supports_metadata_and_reports_nonzero(agent):
	result = agent.run(
		{
			"action": "bash",
			"command": "printf '%s' \"$PWD\"",
			"description": "show working directory",
			"timeout": 5,
		}
	)
	assert result.success
	assert result.details["stdout"] == str(agent.root)
	assert result.details["shell"] == "Bash"
	assert result.details["description"] == "show working directory"
	failed = agent.run({"action": "bash", "command": "echo bad >&2; exit 9"})
	assert not failed.success
	assert failed.details["exit_code"] == 9
	assert "bad" in failed.details["stderr"]


def test_shell_rejects_invalid_timeout_and_background(agent):
	assert not agent.run({"action": "bash", "command": "true", "timeout": 0}).success
	result = agent.run({"action": "bash", "command": "sleep 1", "run_in_background": True})
	assert not result.success
	assert "Background" in result.message


def test_powershell_has_clear_unavailable_error_or_executes(agent):
	result = agent.run({"action": "powershell", "command": "Write-Output 'hello'"})
	if result.success:
		assert "hello" in result.details["stdout"]
		assert result.details["shell"] == "PowerShell"
	else:
		assert "not installed" in result.message.lower()


def test_powershell_command_construction_when_pwsh_is_available(agent):
	completed = __import__("subprocess").CompletedProcess([], 0, "hello\n", "")
	with (
		patch(
			"tules.commands.shell.shutil.which",
			side_effect=lambda name: "/usr/bin/pwsh" if name == "pwsh" else None,
		),
		patch("tules.commands.shell.subprocess.run", return_value=completed) as invoked,
	):
		result = agent.run({"action": "powershell", "command": "Write-Output hello"})
	assert result.success
	argv = invoked.call_args.args[0]
	assert argv[:4] == ["/usr/bin/pwsh", "-NoLogo", "-NoProfile", "-NonInteractive"]
	assert argv[-2:] == ["-Command", "Write-Output hello"]
