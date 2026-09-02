"""Rendering results back into the plain text block the model reads."""

from typing import Any, Iterable, List

from .models import Result

CONTENT_KEYS = ("content", "diff", "blast_radius", "closest_match", "matched_block")
# Command output puts its verdict last, so these keep the tail and drop the head.
TAIL_KEYS = ("stdout", "stderr")
DEFAULT_BUDGET = 2000
MIN_BUDGET = 200
MAX_LIST_ITEMS = 15
RULE = "=" * 60

_budget = DEFAULT_BUDGET


def set_budget(chars: int) -> None:
	"""Set how much of any single value the model is shown, to suit its context window."""
	global _budget
	_budget = max(MIN_BUDGET, int(chars))


def budget() -> int:
	return _budget


def render(result: Result) -> str:
	lines = [
		f"STATUS: {'SUCCESS' if result.success else 'FAILED'}",
		f"MESSAGE: {result.message}",
	]
	if result.details:
		lines.append("DETAILS:")
		lines.extend(_render_details(result.details))
	if result.warnings:
		lines.append("WARNINGS:")
		lines.extend(f"  - {item}" for item in result.warnings)
	if result.errors:
		lines.append("ERRORS:")
		lines.extend(f"  - {item}" for item in result.errors)
	return "\n".join(lines)


def render_batch(results: List[Result]) -> str:
	succeeded = sum(1 for item in results if item.success)
	lines = [
		"BATCH EXECUTION COMPLETE",
		f"TOTAL: {len(results)} | SUCCESS: {succeeded} | FAILED: {len(results) - succeeded}",
		RULE,
	]
	for index, result in enumerate(results, 1):
		lines.append("")
		lines.append(f"[COMMAND {index}/{len(results)}]")
		lines.append(render(result))
	return "\n".join(lines)


def _render_details(details: dict) -> Iterable[str]:
	for key, value in details.items():
		if key in CONTENT_KEYS and isinstance(value, str):
			yield f"  {key}:"
			yield from (f"    {line}" for line in _clip(value).split("\n"))
		elif key in TAIL_KEYS and isinstance(value, str):
			yield f"  {key}:"
			yield from (f"    {line}" for line in _clip_tail(value).split("\n"))
		elif isinstance(value, (list, tuple)):
			yield f"  {key}: {len(value)} item(s)"
			yield from (f"    - {_summarize(item)}" for item in value[:MAX_LIST_ITEMS])
			if len(value) > MAX_LIST_ITEMS:
				yield f"    ... ({len(value) - MAX_LIST_ITEMS} more)"
		elif isinstance(value, dict):
			yield f"  {key}:"
			yield from (f"    {inner}: {_summarize(item)}" for inner, item in value.items())
		else:
			yield f"  {key}: {_clip(str(value))}"


def _summarize(item: Any) -> str:
	if isinstance(item, dict):
		return ", ".join(f"{key}={_clip(str(value), 80)}" for key, value in item.items())
	return _clip(str(item), 160)


def _clip(text: str, limit: int = 0) -> str:
	"""Keep the head of a value, and say plainly that the rest is missing."""
	limit = limit or _budget
	if len(text) <= limit:
		return text
	return f"{text[:limit]}\n{_notice(len(text) - limit, len(text), 'after')}"


def _clip_tail(text: str, limit: int = 0) -> str:
	"""Keep the tail of a value: command output states its verdict last."""
	limit = limit or _budget
	if len(text) <= limit:
		return text
	return f"{_notice(len(text) - limit, len(text), 'before')}\n{text[-limit:]}"


def _notice(hidden: int, total: int, side: str) -> str:
	return (
		f"[TRUNCATED: {hidden:,} of {total:,} characters withheld {side} this point. "
		"You have NOT seen the whole value. Request a narrower range before relying on it.]"
	)
