"""Analysis, review, and pre-flight validation actions."""

from typing import Any, Dict, Optional

from ..errors import TulesError
from ..matching import locate_block
from ..models import Result
from ..registry import ALIASES, command, lookup, text
from ..workspace import Document

# The universal replace engine reads the search block from whichever of these
# spellings the caller used; validate_batch has to look in the same places.
SEARCH_KEYS = ("old_string", "old_str", "search")
# Arguments that tell the engine what to do about several identical matches.
DISAMBIGUATORS = ("replace_all", "match_id", "context_before", "context_after")
FUZZY_CONFIDENCE = 0.85


@command("analyze", "Summarize one file, or the whole project when no file is given")
def analyze(agent, payload: Dict[str, Any]) -> Result:
	relpath = payload.get("file")
	if not relpath:
		return Result.ok("Project analysis complete", **agent.reviewer.survey())
	document = agent.workspace.load(relpath, strict=False)
	return Result.ok(f"Analyzed {document.relpath}", **agent.analyzer.summarize(document))


@command("extract_symbols", "List the functions, classes and imports of a file")
def extract_symbols(agent, payload: Dict[str, Any]) -> Result:
	document = agent.workspace.load(text(payload, "file"), strict=False)
	symbols = agent.analyzer.extract_symbols(document)
	return Result.ok(f"Extracted {len(symbols)} symbols", symbols=symbols)


@command("review", "Run the static checks over a file")
def review(agent, payload: Dict[str, Any]) -> Result:
	relpath = text(payload, "file")
	issues = agent.reviewer.review(relpath)
	if not issues:
		return Result.ok(f"Review of {relpath}: no issues found", issues=[])
	return Result.ok(f"Review of {relpath}: {len(issues)} issue(s)", issues=issues)


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


@command("validate_batch", "Dry-run a list of commands before sending them")
def validate_batch(agent, payload: Dict[str, Any]) -> Result:
	commands = payload.get("commands")
	if not isinstance(commands, list) or not commands:
		raise TulesError("Missing 'commands' list")
	checks = [_check(agent, index, item) for index, item in enumerate(commands)]
	valid = sum(1 for item in checks if item["valid"])
	verdict = "Batch validation" if valid == len(checks) else "Batch validation FAILED"
	return Result(
		success=valid == len(checks),
		message=f"{verdict}: {valid}/{len(checks)} valid",
		details={"checks": checks},
	)


def _check(agent, index: int, payload: Any) -> Dict[str, Any]:
	entry: Dict[str, Any] = {"index": index, "valid": False}
	if not isinstance(payload, dict):
		return {**entry, "reason": "Command must be a JSON object"}
	action = str(payload.get("action", "")).lower()
	try:
		lookup(action)
	except TulesError as exc:
		return {**entry, "action": action, "reason": exc.message}
	entry["action"] = action
	try:
		return {**entry, **_check_action(agent, action, payload)}
	except TulesError as exc:
		return {**entry, "reason": exc.message}


def _check_action(agent, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
	"""Pre-flight one command, using the canonical name behind any alias."""
	canonical = ALIASES.get(action, action)
	if canonical == "create_file":
		path = agent.workspace.resolve(text(payload, "file"))
		if path.exists():
			return {"valid": False, "reason": "File already exists"}
		return {"valid": True, "reason": "Safe to create"}
	if canonical in ("delete_file", "undo"):
		agent.workspace.require(text(payload, "file"))
		return {"valid": True, "reason": "File exists"}
	if canonical != "replace":
		return {"valid": True, "reason": "No pre-flight check for this action"}
	return _check_replace(agent, action, payload)


def _check_replace(agent, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
	"""Ask of a replace exactly what the universal engine will ask of it."""
	document = agent.workspace.load(_replace_file(payload), strict=False)
	search = _search_block(payload)
	if search is None:
		return {"valid": False, "reason": f"Missing one of: {', '.join(SEARCH_KEYS)}"}
	if not search:
		if document.text.strip():
			return {"valid": False, "reason": "An empty search only works on an empty file"}
		return {"valid": True, "reason": "Empty file, the replacement becomes its content"}
	count = document.text.count(search)
	if count == 1:
		return {"valid": True, "reason": "1 exact match"}
	if count > 1:
		if any(payload.get(key) for key in DISAMBIGUATORS):
			return {"valid": True, "reason": f"{count} matches, disambiguated by the arguments"}
		return {
			"valid": False,
			"reason": (
				f"NOT_UNIQUE: {count} exact matches; add context_before/context_after, "
				"match_id, or replace_all"
			),
		}
	return _check_fuzzy(document, search)


def _check_fuzzy(document: Document, search: str) -> Dict[str, Any]:
	"""No exact match: report whether the fallback cascade would still land."""
	first, last, confidence = locate_block(document.lines, search.split("\n"))
	if first < 0 or confidence < FUZZY_CONFIDENCE:
		return {
			"valid": False,
			"reason": f"Search string not found (closest match {confidence:.0%})",
		}
	return {"valid": True, "reason": f"Fuzzy match at lines {first + 1}-{last} ({confidence:.0%})"}


def _replace_file(payload: Dict[str, Any]) -> str:
	value = payload.get("file") or payload.get("file_path")
	if not isinstance(value, str) or not value:
		raise TulesError("Missing 'file'")
	return value


def _search_block(payload: Dict[str, Any]) -> Optional[str]:
	for key in SEARCH_KEYS:
		value = payload.get(key)
		if isinstance(value, str):
			return value
	return None
