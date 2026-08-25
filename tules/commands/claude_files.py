"""Claude Code compatible Read/Write/Edit/Glob/Grep and NotebookEdit tools.

These actions accept Claude Code's public parameter names while retaining TULES'
workspace confinement, backups, newline preservation, and Python syntax guard.
"""

import fnmatch
import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from ..editor import check_syntax
from ..errors import MatchError, SyntaxGuardError, TulesError, WorkspaceError
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


@command("read", "Claude-compatible file reader with offset and limit")
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


@command("write", "Claude-compatible file create or overwrite", mutates=True)
def write(agent, payload: Dict[str, Any]) -> Result:
	relpath = _path(payload, "file_path", "file")
	content = text(payload, "content", "")
	path = agent.workspace.resolve(relpath)
	if path.suffix == ".py":
		problem = check_syntax(content, relpath)
		if problem:
			raise SyntaxGuardError("SYNTAX_ERROR_PREVENTED", error=problem)
	if path.exists():
		document = agent.workspace.load(relpath)
		if document.text == content:
			raise TulesError("NO_CHANGE: content is identical to the existing file")
		backup = agent.workspace.save(document, content)
		return Result.ok(
			"Updated " + document.relpath,
			type="update",
			content=content,
			original_file=document.text,
			backup=agent.workspace.relativize(backup),
		)
	agent.workspace.write(path, content)
	return Result.ok(
		"Created " + agent.workspace.relativize(path),
		type="create",
		content=content,
		original_file=None,
	)


def _normalize_quotes(value: str) -> str:
	quotes = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'}
	return value.translate(str.maketrans(quotes))


def _actual_match(content: str, needle: str) -> str:
	if needle in content:
		return needle
	normal_content, normal_needle = _normalize_quotes(content), _normalize_quotes(needle)
	start = normal_content.find(normal_needle)
	if start >= 0:
		return content[start : start + len(needle)]
	raise MatchError("String to replace not found in file", old_string=needle)


@command("edit", "Claude-compatible unique string replacement", mutates=True)
def edit(agent, payload: Dict[str, Any]) -> Result:
	relpath = _path(payload, "file_path", "file")
	old = text(payload, "old_string", payload.get("old_str"))
	new = text(payload, "new_string", payload.get("new_str", ""))
	replace_all = flag(payload, "replace_all")
	if old == new:
		raise TulesError("No changes to make: old_string and new_string are exactly the same")
	path = agent.workspace.resolve(relpath)
	if not path.exists() and old == "":
		return agent.editor.create(relpath, new)
	document = agent.workspace.load(relpath)
	if old == "":
		if document.text.strip():
			raise TulesError("Cannot create new file - file already exists")
		return agent.editor._apply(document, new, "Claude Edit", occurrences=1)
	actual = _actual_match(document.text, old)
	count = document.text.count(actual)
	if count > 1 and not replace_all:
		raise MatchError(
			f"Found {count} matches of the string to replace, but replace_all is false. "
			"Set replace_all to true or provide more context.",
			occurrences=count,
		)
	# Claude removes the following newline when deleting a whole line.
	actual_for_edit = actual
	if not new and not actual.endswith("\n") and actual + "\n" in document.text:
		actual_for_edit += "\n"
	updated = document.text.replace(actual_for_edit, new, -1 if replace_all else 1)
	return agent.editor._apply(
		document,
		updated,
		"Claude Edit",
		occurrences=count,
		match_level="exact" if actual == old else "normalized_quotes",
		replace_all=replace_all,
	)


@command("glob", "Claude-compatible glob search")
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


@command("grep", "Claude-compatible regex search with content, file and count modes")
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


@command("notebook_edit", "Claude-compatible Jupyter notebook cell editor", mutates=True)
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
