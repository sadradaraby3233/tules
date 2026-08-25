"""Search actions."""

from typing import Any, Dict, List

from ..models import Result, SearchResult
from ..registry import command, decimal, flag, number, text

REPORTED_MATCHES = 20


def _report(results: List[SearchResult], kind: str) -> Result:
	shown = [item.summarize() for item in results[:REPORTED_MATCHES]]
	return Result.ok(
		f"Found {len(results)} {kind} match(es)",
		matches=shown,
		truncated=len(results) > len(shown),
	)


@command("search", "Find a literal string across the workspace")
def search(agent, payload: Dict[str, Any]) -> Result:
	results = agent.searcher.find_text(
		text(payload, "search"),
		case_sensitive=flag(payload, "case_sensitive"),
		whole_word=flag(payload, "whole_word"),
	)
	return _report(results, "exact")


@command("search_regex", "Find a regular expression across the workspace")
def search_regex(agent, payload: Dict[str, Any]) -> Result:
	return _report(agent.searcher.find_regex(text(payload, "search")), "regex")


@command("search_fuzzy", "Find lines similar to a string across the workspace")
def search_fuzzy(agent, payload: Dict[str, Any]) -> Result:
	results = agent.searcher.find_similar(
		text(payload, "search"), threshold=decimal(payload, "threshold", 0.8)
	)
	return _report(results, "fuzzy")


@command("impact_check", "List files that import or reference a module")
def impact_check(agent, payload: Dict[str, Any]) -> Result:
	relpath = text(payload, "file")
	dependents = agent.reviewer.find_dependents(relpath)
	if not dependents:
		return Result.ok(f"Nothing references {relpath}", dependents=[])
	return Result.ok(f"{len(dependents)} file(s) depend on {relpath}", dependents=dependents)


@command("check_duplicates", "Report symbols defined more than once")
def check_duplicates(agent, payload: Dict[str, Any]) -> Result:
	duplicates = agent.reviewer.find_duplicates(payload.get("file") or None)
	if not duplicates:
		return Result.ok("No duplicates found", duplicates=[])
	return Result.ok(f"Found {len(duplicates)} duplicate(s)", duplicates=duplicates)


@command("list_actions", "List every action this agent understands")
def list_actions(agent, payload: Dict[str, Any]) -> Result:
	limit = number(payload, "limit", 0)
	actions = agent.describe()
	return Result.ok(f"{len(actions)} actions available", actions=actions[:limit] or actions)
