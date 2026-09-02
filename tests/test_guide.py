"""The bootstrap prompt must stay tiny, and the on-demand usage must stay truthful."""

import json

from tules import formatting, guide
from tules.models import Result
from tules.registry import REGISTRY

PROMPT_BUDGET = 1000


def test_the_pasted_prompt_stays_under_the_context_budget():
	assert len(guide.BOOTSTRAP) < PROMPT_BUDGET


def test_the_action_index_stays_under_the_context_budget():
	assert len(guide.index()) < PROMPT_BUDGET


def test_the_prompt_teaches_the_envelope_and_the_escape_hatch():
	for fragment in ("edit:", "endedit", '{"action":"help"}', '"name":"replace"'):
		assert fragment in guide.BOOTSTRAP


def test_every_registered_action_has_usage_and_no_usage_is_orphaned():
	assert set(guide.USAGE) == set(REGISTRY)


def test_every_action_appears_in_exactly_one_index_group():
	grouped = [name for _, names in guide.GROUPS for name in names]
	assert sorted(grouped) == sorted(REGISTRY)
	assert len(grouped) == len(set(grouped))


def test_every_usage_example_is_valid_json_for_that_action():
	for name, usage in guide.USAGE.items():
		payload = json.loads(usage.example)
		assert payload["action"] == name
		for key in usage.required:
			assert key in payload, f"{name} example omits required '{key}'"


def test_usage_only_advertises_arguments_it_documents():
	for name, usage in guide.USAGE.items():
		assert not set(usage.required) & set(usage.optional), name


def test_resolve_accepts_canonical_names_and_compatibility_aliases():
	assert guide.resolve("replace") == "replace"
	assert guide.resolve("  STR_REPLACE  ") == "replace"
	assert guide.resolve("help") == "list_actions"
	assert guide.resolve("nope") is None


def test_help_without_a_name_returns_the_whole_index(agent):
	result = agent.run({"action": "help"})
	assert result.success
	assert result.details["content"] == guide.index()
	assert "actions" not in result.details


def test_help_with_a_name_returns_one_action_usage(agent):
	result = agent.run({"action": "help", "name": "replace"})
	assert result.success
	assert "required: file, old_string, new_string" in result.details["content"]
	assert '"action":"replace"' in result.details["content"]


def test_help_with_an_unknown_name_points_back_at_the_index(agent):
	result = agent.run({"action": "help", "name": "teleport"})
	assert not result.success
	assert "teleport" in result.message
	assert result.details["content"] == guide.index()


# --- Context budget: what the model is actually shown -----------------------


def test_a_long_read_is_windowed_and_carries_the_command_to_continue(agent):
	body = "\n".join(f"line {n}" for n in range(1, 2001))
	(agent.root / "long.py").write_text(body, encoding="utf-8")
	result = agent.run({"action": "read_file", "file": "long.py"})
	assert result.success
	assert result.details["truncated"] is True
	assert result.details["total_lines"] == 2000
	assert len(result.details["content"]) <= formatting.budget()
	assert '"action":"read_file"' in result.details["next"]
	assert "still unread" in result.details["next"]


def test_continuing_a_windowed_read_reaches_the_end_of_the_file(agent):
	body = "\n".join(f"line {n}" for n in range(1, 401))
	(agent.root / "long.py").write_text(body, encoding="utf-8")
	seen, start, guard = [], 1, 0
	while guard < 50:
		guard += 1
		result = agent.run({"action": "read_file", "file": "long.py", "start_line": start})
		seen.extend(result.details["content"].split("\n"))
		if not result.details.get("truncated"):
			break
		start += len(result.details["content"].split("\n"))
	assert seen == body.split("\n")


def test_a_read_that_fits_is_not_marked_truncated(agent):
	result = agent.run({"action": "read_file", "file": "notes.md"})
	assert result.details["truncated"] is False
	assert "next" not in result.details


def test_command_output_keeps_its_verdict_which_is_written_last():
	noise = "\n".join(f"chatter {n}" for n in range(500))
	rendered = formatting.render(Result.ok("done", stdout=f"{noise}\nFAILED: 1 test"))
	assert "FAILED: 1 test" in rendered
	assert "TRUNCATED" in rendered
	assert "chatter 0" not in rendered


def test_a_clipped_value_says_plainly_that_it_is_incomplete():
	rendered = formatting.render(Result.ok("done", content="x" * 9000))
	assert "TRUNCATED" in rendered
	assert "You have NOT seen the whole value" in rendered


def test_the_budget_controls_how_much_the_model_is_shown():
	original = formatting.budget()
	try:
		formatting.set_budget(400)
		assert len(formatting.render(Result.ok("d", content="x" * 9000))) < 900
		formatting.set_budget(5)
		assert formatting.budget() == formatting.MIN_BUDGET
	finally:
		formatting.set_budget(original)


def test_a_misused_action_is_answered_with_its_own_usage(agent):
	result = agent.run({"action": "replace", "file": "notes.md"})
	assert not result.success
	assert "required: file, old_string, new_string" in result.details["content"]


def test_an_unknown_action_is_answered_with_the_index(agent):
	result = agent.run({"action": "teleport"})
	assert not result.success
	assert result.details["content"] == guide.index()


def test_teaching_never_overwrites_what_the_command_reported(agent):
	result = agent.run({"action": "read", "file_path": "notes.md", "offset": 0})
	assert not result.success
	assert "positive integers" in result.message
