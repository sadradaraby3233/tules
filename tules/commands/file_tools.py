"""Advanced file reading, writing, discovery, search, and notebook tools."""

import fnmatch
import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from ..errors import TulesError, WorkspaceError
from ..models import Result
from ..registry import command, flag, number, text
from ..workspace import SKIPPED_DIRS

READ_LIMIT = 2000
GLOB_LIMIT = 100
GREP_LIMIT = 250
TYPE_SUFFIXES = {
	"py": (".py",),
	"js": (".js", ".jsx"),
	"ts": (".ts", ".tsx"),
	"rust": (".rs",),
	"go": (".go",),
	"java": (".java",),
	"json": (".json",),
	"markdown": (".md", ".markdown"),
	"yaml": (".yaml", ".yml"),
}


# ---------------------------------------------------------------------------
# Shared path and traversal helpers
# ---------------------------------------------------------------------------


def _path(payload: Dict[str, Any], *names: str) -> str:
	for name in names:
		value = payload.get(name)
		if isinstance(value, str) and value:
			return value
	raise TulesError(f"Missing '{names[0]}'")


def _relative_base(agent, value: Any) -> Path:
	if value in (None, ""):
		return agent.root
	path = agent.workspace.resolve(str(value))
	if not path.exists():
		raise WorkspaceError(f"Path does not exist: {value}")
	return path


def _iter_files(agent, base: Path) -> Iterable[Path]:
	if base.is_file():
		yield base
		return
	for path in base.rglob("*"):
		try:
			parts = path.relative_to(agent.root).parts
		except ValueError:
			continue
		if path.is_file() and not any(part in SKIPPED_DIRS for part in parts[:-1]):
			yield path


# ---------------------------------------------------------------------------
# Text file input and output
# ---------------------------------------------------------------------------


@command("read", "Read a numbered window of a text file")
def read(agent, payload: Dict[str, Any]) -> Result:
	document = agent.workspace.load(_path(payload, "file_path", "file"), strict=False)
	lines = document.lines
	offset = number(payload, "offset", 1)
	limit = number(payload, "limit", READ_LIMIT)
	if offset < 1 or limit < 1:
		raise TulesError("'offset' and 'limit' must be positive integers")
	window = lines[offset - 1 : offset - 1 + limit]
	content = "\n".join(f"{offset + i:6d}→{line}" for i, line in enumerate(window))
	return Result.ok(
		f"Read {document.relpath} lines {offset}-{offset + len(window) - 1}",
		content=content,
		raw_content="\n".join(window),
		start_line=offset,
		num_lines=len(window),
		total_lines=len(lines),
		truncated=offset - 1 + len(window) < len(lines),
	)


@command("write", "Create or fully overwrite a file", mutates=True)
def write(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.write_file(
		_path(payload, "file_path", "file"),
		text(payload, "content", ""),
	)


# ---------------------------------------------------------------------------
# File discovery and content search
# ---------------------------------------------------------------------------


@command("glob", "Find files using a glob pattern")
def glob(agent, payload: Dict[str, Any]) -> Result:
	pattern = text(payload, "pattern")
	base = _relative_base(agent, payload.get("path"))
	if not base.is_dir():
		raise WorkspaceError(f"Path is not a directory: {payload.get('path')}")
	found: List[Tuple[float, str]] = []
	for path in _iter_files(agent, base):
		rel_base = path.relative_to(base).as_posix()
		if fnmatch.fnmatch(rel_base, pattern) or path.match(pattern):
			found.append((path.stat().st_mtime, agent.workspace.relativize(path)))
	found.sort(key=lambda item: (-item[0], item[1]))
	truncated = len(found) > GLOB_LIMIT
	files = [name for _, name in found[:GLOB_LIMIT]]
	return Result.ok(
		f"Found {len(files)} files",
		filenames=files,
		files=files,
		num_files=len(files),
		truncated=truncated,
	)


def _glob_match(path: Path, base: Path, patterns: str) -> bool:
	rel = path.relative_to(base).as_posix() if base.is_dir() else path.name
	for raw in re.split(r"[\s,]+", patterns):
		if raw and (fnmatch.fnmatch(rel, raw) or path.match(raw)):
			return True
	return False


@command("grep", "Advanced regex search with content, file and count modes")
def grep(agent, payload: Dict[str, Any]) -> Result:
	pattern = text(payload, "pattern", payload.get("search"))
	try:
		expression = re.compile(pattern, re.IGNORECASE if flag(payload, "-i") else 0)
	except re.error as exc:
		raise TulesError(f"Invalid regex: {exc}") from exc
	base = _relative_base(agent, payload.get("path"))
	mode = payload.get("output_mode", "files_with_matches")
	if mode not in ("content", "files_with_matches", "count"):
		raise TulesError("output_mode must be content, files_with_matches, or count")
	before = int(payload.get("context", payload.get("-C", payload.get("-B", 0))) or 0)
	after = int(payload.get("context", payload.get("-C", payload.get("-A", 0))) or 0)
	glob_filter, type_filter = payload.get("glob"), payload.get("type")
	entries, filenames, total = [], [], 0
	for path in _iter_files(agent, base):
		if glob_filter and not _glob_match(
			path, base if base.is_dir() else base.parent, str(glob_filter)
		):
			continue
		if type_filter and path.suffix.lower() not in TYPE_SUFFIXES.get(
			str(type_filter), ("." + str(type_filter),)
		):
			continue
		try:
			lines = agent.workspace.load_path(path, strict=False).lines
		except WorkspaceError:
			continue
		matches = [i for i, line in enumerate(lines) if expression.search(line)]
		if not matches:
			continue
		name = agent.workspace.relativize(path)
		filenames.append(name)
		total += len(matches)
		if mode == "count":
			entries.append(f"{name}:{len(matches)}")
		elif mode == "content":
			seen = set()
			for index in matches:
				for line_index in range(max(0, index - before), min(len(lines), index + after + 1)):
					if line_index not in seen:
						seen.add(line_index)
						separator = ":" if line_index == index else "-"
						entries.append(
							f"{name}{separator}{line_index + 1}{separator}{lines[line_index][:500]}"
						)
	if mode == "files_with_matches":
		entries = filenames
	offset = max(0, int(payload.get("offset", 0) or 0))
	limit = int(
		payload.get("head_limit", GREP_LIMIT)
		if payload.get("head_limit") is not None
		else GREP_LIMIT
	)
	page = entries[offset:] if limit == 0 else entries[offset : offset + max(0, limit)]
	return Result.ok(
		f"Found {total} occurrences across {len(filenames)} files",
		mode=mode,
		content="\n".join(page),
		filenames=filenames if mode != "content" else [],
		num_files=len(filenames),
		num_matches=total,
		num_lines=len(page),
		truncated=offset + len(page) < len(entries),
		applied_offset=offset,
		applied_limit=limit,
	)


# ---------------------------------------------------------------------------
# Structured notebook editing
# ---------------------------------------------------------------------------


@command("notebook_edit", "Insert, replace, or delete a Jupyter notebook cell", mutates=True)
def notebook_edit(agent, payload: Dict[str, Any]) -> Result:
	relpath = _path(payload, "notebook_path", "file")
	if not relpath.lower().endswith(".ipynb"):
		raise TulesError("File must be a Jupyter notebook (.ipynb file)")
	document = agent.workspace.load(relpath)
	try:
		notebook = json.loads(document.text)
	except json.JSONDecodeError as exc:
		raise TulesError(f"Invalid notebook JSON: {exc}") from exc
	cells = notebook.get("cells")
	if not isinstance(cells, list):
		raise TulesError("Invalid notebook: missing cells array")
	mode = payload.get("edit_mode", "replace")
	cell_id = payload.get("cell_id")
	index = next((i for i, cell in enumerate(cells) if str(cell.get("id", i)) == str(cell_id)), -1)
	if mode in ("replace", "delete") and index < 0:
		raise TulesError(f"Cell ID not found: {cell_id}")
	if mode == "delete":
		cell = cells.pop(index)
	elif mode == "replace":
		cell = cells[index]
		cell["source"] = text(payload, "new_source", "").splitlines(True)
		if payload.get("cell_type"):
			cell["cell_type"] = payload["cell_type"]
	else:
		if mode != "insert" or payload.get("cell_type") not in ("code", "markdown"):
			raise TulesError("Insert requires cell_type of code or markdown")
		cell = {
			"id": uuid.uuid4().hex[:8],
			"cell_type": payload["cell_type"],
			"metadata": {},
			"source": text(payload, "new_source", "").splitlines(True),
		}
		if cell["cell_type"] == "code":
			cell.update({"execution_count": None, "outputs": []})
		cells.insert(index + 1 if index >= 0 else 0, cell)
	updated = json.dumps(notebook, ensure_ascii=False, indent=1) + "\n"
	result = agent.editor._apply(
		document,
		updated,
		"Notebook Edit",
		cell_id=cell.get("id", cell_id),
		cell_type=cell.get("cell_type"),
		edit_mode=mode,
	)
	return result


# ---------------------------------------------------------------------------
# Simple reads, file lifecycle, backups, and persistent notes
# ---------------------------------------------------------------------------

MEMORY_FILES = {"scratchpad": "scratchpad.md", "todo": "todo.md"}
PREVIEW_LINES = 400


@command("read_file", "Read a file, optionally a line range")
def read_file(agent, payload: Dict[str, Any]) -> Result:
	document = agent.workspace.load(text(payload, "file"), strict=False)
	lines = document.lines
	first = payload.get("start_line")
	last = payload.get("end_line")
	if first is None and last is None:
		return Result.ok(f"Read {document.relpath}", content=document.text, total_lines=len(lines))
	first = number(payload, "start_line", 1)
	last = number(payload, "end_line", len(lines))
	body = "\n".join(lines[max(0, first - 1) : min(len(lines), last)])
	return Result.ok(
		f"Read lines {first}-{last} of {document.relpath}", content=body, total_lines=len(lines)
	)


@command("view", "Read a file with line numbers, ready to quote back")
def view(agent, payload: Dict[str, Any]) -> Result:
	document = agent.workspace.load(text(payload, "file"), strict=False)
	lines = document.lines
	first = number(payload, "start_line", 1)
	last = number(payload, "end_line", min(len(lines), first + PREVIEW_LINES - 1))
	window = lines[max(0, first - 1) : min(len(lines), last)]
	body = "\n".join(f"{first + offset:4d} | {line}" for offset, line in enumerate(window))
	return Result.ok(
		f"Viewed {document.relpath} lines {first}-{first + len(window) - 1}",
		content=body,
		total_lines=len(lines),
	)


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
