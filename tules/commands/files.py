"""Reading, listing, creating and restoring files."""

import re
from typing import Any, Dict

from ..errors import TulesError
from ..models import Result
from ..registry import command, number, text

MEMORY_FILES = {"scratchpad": "scratchpad.md", "todo": "todo.md"}
MEMORY_SLUG = re.compile(r"[^A-Za-z0-9_-]+")
PREVIEW_LINES = 400


def _memory_filename(target: str) -> str:
	"""Map a memory target to a filename, allowing custom names beyond the defaults."""
	if target in MEMORY_FILES:
		return MEMORY_FILES[target]
	slug = MEMORY_SLUG.sub("_", target).strip("_")
	if not slug:
		raise TulesError(f"Invalid memory target: {target!r}")
	return f"{slug}.md"


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


@command("memory", "Append to, read, or list agent memory files")
def memory(agent, payload: Dict[str, Any]) -> Result:
	mode = text(payload, "action_type", "read")
	if mode == "list":
		agent.workspace.state_root.mkdir(exist_ok=True)
		names = sorted(item.name for item in agent.workspace.state_root.glob("*.md"))
		return Result.ok(f"{len(names)} memory file(s)", files=names)
	path = agent.workspace.state_file(_memory_filename(text(payload, "target", "scratchpad")))
	if mode == "read":
		body = path.read_text(encoding="utf-8") if path.exists() else ""
		return Result.ok(f"Read {path.name}", content=body)
	if mode == "write":
		with path.open("a", encoding="utf-8") as handle:
			handle.write(text(payload, "content") + "\n")
		return Result.ok(f"Appended to {path.name}")
	raise TulesError("'action_type' must be 'read', 'write' or 'list'")
