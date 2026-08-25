"""One universal replacement command plus explicit line and preview operations."""

from typing import Any, Dict

from ..errors import TulesError
from ..models import Result
from ..registry import command, decimal, flag, number, text

DEFAULT_REASON = "AI edit"


def _reason(payload: Dict[str, Any], fallback: str = DEFAULT_REASON) -> str:
	return text(payload, "reason", fallback)


def _first_text(payload: Dict[str, Any], names, default=None) -> str:
	for name in names:
		if name in payload and payload[name] is not None:
			return text(payload, name)
	if default is not None:
		return default
	raise TulesError(f"Missing one of: {', '.join(names)}")


@command("replace", "Universally locate and safely replace text", mutates=True)
def replace(agent, payload: Dict[str, Any]) -> Result:
	"""Accept every supported replacement parameter spelling."""
	relpath = _first_text(payload, ("file", "file_path"))
	search = _first_text(payload, ("old_string", "old_str", "search"))
	replacement = _first_text(payload, ("new_string", "new_str", "replace_with"), "")
	action = str(payload.get("action", "replace")).lower()
	if search == "":
		path = agent.workspace.resolve(relpath)
		if not path.exists():
			return agent.editor.create(relpath, replacement)
		document = agent.workspace.load(relpath)
		if document.text.strip():
			raise TulesError("Cannot use an empty search on a non-empty existing file")
		return agent.editor._apply(
			document,
			replacement,
			_reason(payload, "Universal replace"),
			match_level="empty_file",
			occurrences=1,
		)
	replace_all = flag(payload, "replace_all") or action == "search_and_replace_all"
	match_id = payload.get("match_id")
	if match_id is not None:
		match_id = number(payload, "match_id")
	return agent.editor.replace_best(
		relpath,
		search,
		replacement,
		_reason(payload, "Universal replace"),
		context_before=payload.get("context_before"),
		context_after=payload.get("context_after"),
		threshold=decimal(payload, "confidence_threshold", 0.85),
		replace_all=replace_all,
		match_id=match_id,
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
		text(payload, "file"),
		number(payload, "line_start", 0),
		text(payload, "content"),
		_reason(payload, "Insert"),
	)


@command("delete", "Delete an inclusive line range", mutates=True)
def delete(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.delete_lines(
		text(payload, "file"),
		number(payload, "line_start"),
		number(payload, "line_end"),
		_reason(payload, "Delete lines"),
	)


@command("diff_preview", "Show the diff an edit would produce, without writing")
def diff_preview(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.preview(
		text(payload, "file"), text(payload, "search"), text(payload, "replace_with", "")
	)
