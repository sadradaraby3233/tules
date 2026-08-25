"""Reading, listing, creating and restoring files."""

from typing import Any, Dict

from ..errors import TulesError
from ..models import Result
from ..registry import command, number, text

MEMORY_FILES = {"scratchpad": "scratchpad.md", "todo": "todo.md"}
PREVIEW_LINES = 400


@command("read_file", "Read a file, optionally a line range")
def read_file(agent, payload: Dict[str, Any]) -> Result:
	document = agent.workspace.load(text(payload, "file"), strict=False)
	lines = document.lines
	first = payload.get("start_line")
	last = payload.get("end_line")
	if first is None and last is None:
		return Result.ok(
			f"Read {document.relpath}", content=document.text, total_lines=len(lines))
	first = number(payload, "start_line", 1)
	last = number(payload, "end_line", len(lines))
	body = "\n".join(lines[max(0, first - 1):min(len(lines), last)])
	return Result.ok(
		f"Read lines {first}-{last} of {document.relpath}",
		content=body, total_lines=len(lines))


@command("view", "Read a file with line numbers, ready to quote back")
def view(agent, payload: Dict[str, Any]) -> Result:
	document = agent.workspace.load(text(payload, "file"), strict=False)
	lines = document.lines
	first = number(payload, "start_line", 1)
	last = number(payload, "end_line", min(len(lines), first + PREVIEW_LINES - 1))
	window = lines[max(0, first - 1):min(len(lines), last)]
	body = "\n".join(f"{first + offset:4d} | {line}" for offset, line in enumerate(window))
	return Result.ok(
		f"Viewed {document.relpath} lines {first}-{first + len(window) - 1}",
		content=body, total_lines=len(lines))


@command("list_files", "List workspace files matching a name fragment")
def list_files(agent, payload: Dict[str, Any]) -> Result:
	matches = agent.searcher.find_files(payload.get("pattern", ""))
	return Result.ok(f"Found {len(matches)} files", files=matches)


@command("create_file", "Create a new file", mutates=True)
def create_file(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.create(text(payload, "file"), text(payload, "content", ""))


@command("delete_file", "Delete a file after backing it up", mutates=True)
def delete_file(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.remove(text(payload, "file"))


@command("undo", "Restore a file from its most recent backup", mutates=True)
def undo(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.restore(text(payload, "file"))


@command("memory", "Append to or read the agent scratchpad")
def memory(agent, payload: Dict[str, Any]) -> Result:
	target = text(payload, "target", "scratchpad")
	if target not in MEMORY_FILES:
		raise TulesError(f"Unknown memory target: {target}", available=sorted(MEMORY_FILES))
	path = agent.workspace.state_file(MEMORY_FILES[target])
	mode = text(payload, "action_type", "read")
	if mode == "read":
		body = path.read_text(encoding="utf-8") if path.exists() else ""
		return Result.ok(f"Read {path.name}", content=body)
	if mode == "write":
		with path.open("a", encoding="utf-8") as handle:
			handle.write(text(payload, "content") + "\n")
		return Result.ok(f"Appended to {path.name}")
	raise TulesError("'action_type' must be 'read' or 'write'")
