"""File reading, writing, discovery, content search, notebooks, and memory.

The three read actions (``read``, ``read_file``, ``view``) differ only in the
argument names they accept and how they render a line; they share one windowing
helper so a change to the budget or the resume hint applies to all of them.
"""

import fnmatch
import json
import re
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from ..errors import TulesError, WorkspaceError
from ..formatting import budget
from ..models import Result
from ..registry import command, first_text, flag, number, text
from ..workspace import Document, SKIPPED_DIRS

READ_LIMIT = 2000
GLOB_LIMIT = 100
GREP_LIMIT = 250
GREP_LINE_WIDTH = 500
PREVIEW_LINES = 400
GREP_MODES = ("content", "files_with_matches", "count")
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
# Shared path, windowing, and traversal helpers
# ---------------------------------------------------------------------------


def _fit(lines: Sequence[str], first: int) -> List[str]:
	"""Take as many lines from ``first`` as the render budget will actually show."""
	window: List[str] = []
	used = 0
	for line in lines[first:]:
		used += len(line) + 1
		if window and used > budget():
			break
		window.append(line)
	return window


def _resume(
	action: str, key: str, relpath: str, start: str, nxt: int, total: int
) -> Dict[str, Any]:
	"""Tell the model, in its own command language, how to read what it has not seen."""
	if nxt >= total:
		return {"truncated": False}
	return {
		"truncated": True,
		"next": (
			f'{{"action":"{action}","{key}":"{relpath}","{start}":{nxt + 1}}}'
			f"  ({total - nxt} of {total} lines still unread)"
		),
	}


class Window:
	"""One slice of a file, plus everything a read result needs to report it."""

	def __init__(self, document: Document, first: int, lines: List[str]):
		self.document = document
		self.first = first  # 1-based number of the first line in the window
		self.lines = lines
		self.total = len(document.lines)

	@property
	def last(self) -> int:
		return self.first + len(self.lines) - 1

	def resume(self, action: str, key: str, start: str) -> Dict[str, Any]:
		return _resume(
			action, key, self.document.relpath, start, self.first - 1 + len(self.lines), self.total
		)

	def render(self, template: Optional[Callable[[int, str], str]] = None) -> str:
		if template is None:
			return "\n".join(self.lines)
		return "\n".join(
			template(self.first + offset, line) for offset, line in enumerate(self.lines)
		)


def _window(
	agent,
	relpath: str,
	first: int,
	count: Optional[int],
) -> Window:
	"""Load ``relpath`` and slice it, defaulting to as much as the budget shows."""
	document = agent.workspace.load(relpath, strict=False)
	lines = document.lines
	if first < 1 or (count is not None and count < 1):
		raise TulesError("line numbers must be positive integers: 'offset'/'start_line' start at 1")
	start = min(first - 1, len(lines))
	if count is None:
		return Window(document, first, _fit(lines, start))
	return Window(document, first, lines[start : start + count])


def _line_count(
	payload: Dict[str, Any], first: int, default_span: Optional[int] = None
) -> Optional[int]:
	"""Turn an optional inclusive ``end_line`` into a line count, or None to fit."""
	if payload.get("end_line") is None:
		return None
	last = number(payload, "end_line")
	if default_span is not None:
		last = min(last, first + default_span - 1)
	return max(0, last - first + 1)


def _relative_base(agent, value: Any) -> Path:
	if value in (None, ""):
		return agent.root
	path = agent.workspace.resolve(str(value))
	if not path.exists():
		raise WorkspaceError(f"Path does not exist: {value}")
	return path


def _iter_files(agent, base: Path) -> Iterable[Path]:
	"""Every non-ignored regular file at or below ``base``."""
	if base.is_file():
		yield base
		return
	for path in sorted(base.rglob("*")):
		try:
			parts = path.relative_to(agent.root).parts
		except ValueError:
			continue
		if any(part in SKIPPED_DIRS for part in parts[:-1]):
			continue
		try:
			if not path.is_file():
				continue
		except OSError:
			continue
		if agent.workspace.ignores.ignored("/".join(parts)):
			continue
		yield path


def _page(
	entries: List[str], payload: Dict[str, Any], default_limit: int
) -> Tuple[List[str], int, int]:
	"""Apply the caller's offset/limit, where limit 0 means 'everything left'."""
	offset = max(0, number(payload, "offset", 0))
	raw_limit = payload.get("head_limit")
	limit = default_limit if raw_limit is None else max(0, number(payload, "head_limit"))
	page = entries[offset:] if limit == 0 else entries[offset : offset + limit]
	return page, offset, limit


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


@command("read", "Read a numbered window of a text file")
def read(agent, payload: Dict[str, Any]) -> Result:
	first = number(payload, "offset", 1)
	count = number(payload, "limit", READ_LIMIT) if "limit" in payload else None
	window = _window(agent, first_text(payload, "file_path", "file"), first, count)
	return Result.ok(
		f"Read {window.document.relpath} lines {window.first}-{window.last}",
		content=window.render(lambda number_, line: f"{number_:6d}\u2192{line}"),
		raw_content=window.render(),
		start_line=window.first,
		num_lines=len(window.lines),
		total_lines=window.total,
		**window.resume("read", "file_path", "offset"),
	)


@command("read_file", "Read a file, optionally a line range")
def read_file(agent, payload: Dict[str, Any]) -> Result:
	first = number(payload, "start_line", 1)
	window = _window(agent, text(payload, "file"), first, _line_count(payload, first))
	return Result.ok(
		f"Read lines {window.first}-{window.last} of {window.document.relpath}",
		content=window.render(),
		total_lines=window.total,
		**window.resume("read_file", "file", "start_line"),
	)


@command("view", "Read a file with line numbers, ready to quote back")
def view(agent, payload: Dict[str, Any]) -> Result:
	first = number(payload, "start_line", 1)
	count = _line_count(payload, first, PREVIEW_LINES)
	window = _window(agent, text(payload, "file"), first, count)
	return Result.ok(
		f"Viewed {window.document.relpath} lines {window.first}-{window.last}",
		content=window.render(lambda number_, line: f"{number_:4d} | {line}"),
		total_lines=window.total,
		**window.resume("view", "file", "start_line"),
	)


@command("write", "Create or fully overwrite a file", mutates=True)
def write(agent, payload: Dict[str, Any]) -> Result:
	return agent.editor.write_file(
		first_text(payload, "file_path", "file"),
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
		if not (fnmatch.fnmatch(path.relative_to(base).as_posix(), pattern) or path.match(pattern)):
			continue
		try:
			modified = path.stat().st_mtime
		except OSError:
			continue  # the file vanished mid-walk
		found.append((modified, agent.workspace.relativize(path)))
	found.sort(key=lambda item: (-item[0], item[1]))
	files = [name for _, name in found[:GLOB_LIMIT]]
	return Result.ok(
		f"Found {len(files)} files",
		filenames=files,
		files=files,
		num_files=len(files),
		truncated=len(found) > GLOB_LIMIT,
	)


def _glob_match(path: Path, base: Path, patterns: str) -> bool:
	rel = path.relative_to(base).as_posix() if base.is_dir() else path.name
	for raw in re.split(r"[\s,]+", patterns):
		if raw and (fnmatch.fnmatch(rel, raw) or path.match(raw)):
			return True
	return False


def _type_match(path: Path, type_filter: str) -> bool:
	return path.suffix.lower() in TYPE_SUFFIXES.get(type_filter, ("." + type_filter,))


def _context_span(payload: Dict[str, Any], side: str) -> int:
	"""Lines of context for one side: an explicit -A/-B, else -C or 'context'."""
	both = payload.get("context", payload.get("-C"))
	return max(0, int(payload.get(side, both) or 0))


@command("grep", "Advanced regex search with content, file and count modes")
def grep(agent, payload: Dict[str, Any]) -> Result:
	pattern = text(payload, "pattern", payload.get("search"))
	try:
		expression = re.compile(pattern, re.IGNORECASE if flag(payload, "-i") else 0)
	except re.error as exc:
		raise TulesError(f"Invalid regex: {exc}") from exc
	base = _relative_base(agent, payload.get("path"))
	mode = payload.get("output_mode", "files_with_matches")
	if mode not in GREP_MODES:
		raise TulesError("output_mode must be content, files_with_matches, or count")
	before, after = _context_span(payload, "-B"), _context_span(payload, "-A")
	glob_filter, type_filter = payload.get("glob"), payload.get("type")
	entries: List[str] = []
	filenames: List[str] = []
	total = 0
	for path in _iter_files(agent, base):
		if glob_filter and not _glob_match(
			path, base if base.is_dir() else base.parent, str(glob_filter)
		):
			continue
		if type_filter and not _type_match(path, str(type_filter)):
			continue
		try:
			lines = agent.workspace.load_path(path, strict=False).lines
		except WorkspaceError:
			continue
		matches = [index for index, line in enumerate(lines) if expression.search(line)]
		if not matches:
			continue
		name = agent.workspace.relativize(path)
		filenames.append(name)
		total += len(matches)
		if mode == "count":
			entries.append(f"{name}:{len(matches)}")
		elif mode == "content":
			entries.extend(_content_entries(name, lines, matches, before, after))
	if mode == "files_with_matches":
		entries = filenames
	page, offset, limit = _page(entries, payload, GREP_LIMIT)
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


def _content_entries(
	name: str, lines: Sequence[str], matches: Sequence[int], before: int, after: int
) -> List[str]:
	"""Matching lines with their context, each shown once, in file order."""
	wanted: Dict[int, bool] = {}
	for index in matches:
		for line_index in range(max(0, index - before), min(len(lines), index + after + 1)):
			wanted.setdefault(line_index, False)
		wanted[index] = True
	return [
		f"{name}{':' if is_match else '-'}{index + 1}"
		f"{':' if is_match else '-'}{lines[index][:GREP_LINE_WIDTH]}"
		for index, is_match in sorted(wanted.items())
	]


@command("list_files", "List workspace files matching a name fragment")
def list_files(agent, payload: Dict[str, Any]) -> Result:
	matches = agent.searcher.find_files(payload.get("pattern", ""))
	return Result.ok(f"Found {len(matches)} files", files=matches)


# ---------------------------------------------------------------------------
# Structured notebook editing
# ---------------------------------------------------------------------------


@command("notebook_edit", "Insert, replace, or delete a Jupyter notebook cell", mutates=True)
def notebook_edit(agent, payload: Dict[str, Any]) -> Result:
	relpath = first_text(payload, "notebook_path", "file")
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
		cell = _new_cell(payload, mode)
		cells.insert(index + 1 if index >= 0 else 0, cell)
	updated = json.dumps(notebook, ensure_ascii=False, indent=1) + "\n"
	return agent.editor.apply(
		document,
		updated,
		"Notebook Edit",
		cell_id=cell.get("id", cell_id),
		cell_type=cell.get("cell_type"),
		edit_mode=mode,
	)


def _new_cell(payload: Dict[str, Any], mode: str) -> Dict[str, Any]:
	if mode != "insert" or payload.get("cell_type") not in ("code", "markdown"):
		raise TulesError("Insert requires cell_type of code or markdown")
	cell: Dict[str, Any] = {
		"id": uuid.uuid4().hex[:8],
		"cell_type": payload["cell_type"],
		"metadata": {},
		"source": text(payload, "new_source", "").splitlines(True),
	}
	if cell["cell_type"] == "code":
		cell.update({"execution_count": None, "outputs": []})
	return cell


# ---------------------------------------------------------------------------
# File lifecycle, backups, and persistent notes
# ---------------------------------------------------------------------------

MEMORY_FILES = {"scratchpad": "scratchpad.md", "todo": "todo.md"}
MEMORY_SLUG = re.compile(r"[^A-Za-z0-9_-]+")


def _memory_filename(target: str) -> str:
	"""Map a memory target to a filename, allowing custom names beyond the defaults."""
	if target in MEMORY_FILES:
		return MEMORY_FILES[target]
	slug = MEMORY_SLUG.sub("_", target).strip("_")
	if not slug:
		raise TulesError(f"Invalid memory target: {target!r}")
	return f"{slug}.md"


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
	if mode not in ("read", "write"):
		raise TulesError("'action_type' must be 'read', 'write' or 'list'")
	path = agent.workspace.state_file(_memory_filename(text(payload, "target", "scratchpad")))
	try:
		if mode == "read":
			body = path.read_text(encoding="utf-8") if path.exists() else ""
			return Result.ok(f"Read {path.name}", content=body)
		with path.open("a", encoding="utf-8") as handle:
			handle.write(text(payload, "content") + "\n")
	except OSError as exc:
		raise WorkspaceError(f"Cannot access {path.name}: {exc}") from exc
	return Result.ok(f"Appended to {path.name}")
