"""Workspace-wide literal, regex, and fuzzy line search."""

from typing import Any, Dict, List

from ..models import Result, SearchResult
from ..registry import command, decimal, flag, text

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
