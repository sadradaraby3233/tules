"""Analysis, review and pre-flight validation actions."""

from typing import Any, Dict

from ..errors import TulesError
from ..matching import locate_block
from ..models import Result
from ..registry import command, lookup, text

EDIT_ACTIONS = {
	"replace": "search",
	"str_replace": "old_str",
	"surgical_replace": "search",
	"context_replace": "search",
	"search_and_replace_all": "search",
	"smart_replace": "search",
}
UNIQUE_ACTIONS = {"str_replace", "smart_replace"}
FUZZY_ACTIONS = {"surgical_replace", "context_replace"}


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
	if action == "create_file":
		path = agent.workspace.resolve(text(payload, "file"))
		if path.exists():
			return {"valid": False, "reason": "File already exists"}
		return {"valid": True, "reason": "Safe to create"}
	if action in ("delete_file", "undo"):
		agent.workspace.require(text(payload, "file"))
		return {"valid": True, "reason": "File exists"}
	if action not in EDIT_ACTIONS:
		return {"valid": True, "reason": "No pre-flight check for this action"}
	document = agent.workspace.load(text(payload, "file"), strict=False)
	search = text(payload, EDIT_ACTIONS[action], "")
	if not search:
		return {"valid": False, "reason": f"Missing '{EDIT_ACTIONS[action]}'"}
	count = document.text.count(search)
	if count == 0:
		return _check_fuzzy(document, search, action)
	if count > 1 and action in UNIQUE_ACTIONS:
		return {"valid": False, "reason": f"NOT_UNIQUE: {count} matches"}
	return {"valid": True, "reason": f"{count} match(es)"}


def _check_fuzzy(document, search: str, action: str) -> Dict[str, Any]:
	if action not in FUZZY_ACTIONS:
		return {"valid": False, "reason": "Search string not found"}
	first, last, confidence = locate_block(document.lines, search.split("\n"))
	if first < 0 or confidence < 0.85:
		return {"valid": False, "reason": f"No confident match (best {confidence:.0%})"}
	return {"valid": True, "reason": f"Fuzzy match at lines {first + 1}-{last} ({confidence:.0%})"}
