"""Editing actions, ordered from the strictest matcher to the most forgiving."""

from typing import Any, Dict

from ..models import Result
from ..registry import command, decimal, number, text

DEFAULT_REASON = "AI edit"


def _reason(payload: Dict[str, Any], fallback: str = DEFAULT_REASON) -> str:
	return text(payload, "reason", fallback)


@command("str_replace", "Replace a string that occurs exactly once", mutates=True)
def str_replace(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.replace_unique(
		text(payload, "file"), text(payload, "old_str"), text(payload, "new_str", ""),
		_reason(payload, "Unique string replace"))


@command("replace", "Replace the first occurrence of a string", mutates=True)
def replace(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.replace_first(
		text(payload, "file"), text(payload, "search"), text(payload, "replace_with", ""),
		_reason(payload))


@command("search_and_replace_all", "Replace every occurrence of a string", mutates=True)
def search_and_replace_all(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.replace_all(
		text(payload, "file"), text(payload, "search"), text(payload, "replace_with", ""),
		_reason(payload, "Replace all"))


@command("surgical_replace", "Replace tolerating whitespace, wrapping and AST shape", mutates=True)
def surgical_replace(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.replace_flexible(
		text(payload, "file"), text(payload, "search"), text(payload, "replace_with", ""),
		_reason(payload, "Surgical replace"))


@command("context_replace", "Replace a block located by similarity and context", mutates=True)
def context_replace(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.replace_in_context(
		text(payload, "file"),
		text(payload, "search"),
		text(payload, "replace_with", ""),
		context_before=payload.get("context_before"),
		context_after=payload.get("context_after"),
		threshold=decimal(payload, "confidence_threshold", 0.85),
		reason=_reason(payload, "Context-aware replace"),
	)


@command("replace_by_line", "Replace an inclusive line range", mutates=True)
def replace_by_line(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.replace_lines(
		text(payload, "file"),
		number(payload, "line_start"),
		number(payload, "line_end"),
		text(payload, "replace_with", ""),
		_reason(payload, "Line replace"),
	)


@command("insert", "Insert content after a line number", mutates=True)
def insert(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.insert_lines(
		text(payload, "file"), number(payload, "line_start", 0),
		text(payload, "content"), _reason(payload, "Insert"))


@command("delete", "Delete an inclusive line range", mutates=True)
def delete(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.delete_lines(
		text(payload, "file"), number(payload, "line_start"), number(payload, "line_end"),
		_reason(payload, "Delete lines"))


@command("smart_replace", "Replace when unique, otherwise list the candidates", mutates=True)
def smart_replace(agent, payload: Dict[str, Any]) -> Result:
	relpath = text(payload, "file")
	search = text(payload, "search")
	matches = agent.editor.find_occurrences(relpath, search)
	if len(matches) == 1:
		return agent.editor.replace_first(
			relpath, search, text(payload, "replace_with", ""), _reason(payload, "Smart replace"))
	if not matches:
		return Result.fail("NOT_FOUND: search string is absent from the file")
	return Result.fail(
		f"AMBIGUOUS: {len(matches)} matches. Re-send as confirm_smart_replace with a match_id.",
		matches=matches)


@command("confirm_smart_replace", "Replace one numbered candidate", mutates=True)
def confirm_smart_replace(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.replace_occurrence(
		text(payload, "file"), text(payload, "search"), text(payload, "replace_with", ""),
		number(payload, "match_id", 0), _reason(payload, "Confirmed replace"))


@command("diff_preview", "Show the diff an edit would produce, without writing")
def diff_preview(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.preview(
		text(payload, "file"), text(payload, "search"), text(payload, "replace_with", ""))
