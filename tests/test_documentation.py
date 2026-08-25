"""Keep the user and model documentation synchronized with the live tool registry."""

from pathlib import Path

from tules.agent import Agent

ROOT = Path(__file__).resolve().parents[1]
USER_README = ROOT / "README.md"
AI_GUIDE = ROOT / "AI_TOOL_GUIDE.md"


def test_user_readme_is_short_and_links_to_the_complete_ai_guide():
	user_text = USER_README.read_text(encoding="utf-8")
	ai_text = AI_GUIDE.read_text(encoding="utf-8")
	assert len(user_text.splitlines()) < 500
	assert len(ai_text) > len(user_text)
	assert "[AI_TOOL_GUIDE.md](AI_TOOL_GUIDE.md)" in user_text


def test_both_documents_include_every_canonical_action(tmp_path):
	actions = {item["action"] for item in Agent(str(tmp_path)).describe()}
	for path in (USER_README, AI_GUIDE):
		text = path.read_text(encoding="utf-8")
		missing = {action for action in actions if f"`{action}`" not in text}
		assert not missing, f"{path.name} is missing actions: {sorted(missing)}"


def test_documentation_describes_latest_universal_replace_and_shells():
	for path in (USER_README, AI_GUIDE):
		text = path.read_text(encoding="utf-8")
		assert "universal" in text.lower()
		assert "context_before" in text
		assert "match_id" in text
		assert "replace_all" in text
		assert "`bash`" in text
		assert "`powershell`" in text
		assert "30,000" in text
		assert "1\u2013600" in text


def test_documentation_is_model_independent_and_has_balanced_fences():
	for path in (USER_README, AI_GUIDE):
		text = path.read_text(encoding="utf-8")
		assert "claude" not in text.lower()
		fences = [line for line in text.splitlines() if line.strip().startswith("```")]
		assert len(fences) % 2 == 0, f"Unbalanced Markdown fences in {path.name}"
