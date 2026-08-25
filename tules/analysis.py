"""Read-only inspection: structure, symbols, duplicates, dependents, review."""

import ast
import re
from typing import Any, Dict, Iterable, List, Optional

from .errors import TulesError
from .workspace import Document, Workspace

COMMENT_PREFIXES = {
	".py": ("#",),
	".rb": ("#",),
	".sh": ("#",),
	".bash": ("#",),
	".yaml": ("#",),
	".yml": ("#",),
	".toml": ("#",),
	".js": ("//",),
	".ts": ("//",),
	".jsx": ("//",),
	".tsx": ("//",),
	".java": ("//",),
	".c": ("//",),
	".h": ("//",),
	".cpp": ("//",),
	".hpp": ("//",),
	".cs": ("//",),
	".go": ("//",),
	".rs": ("//",),
	".swift": ("//",),
	".php": ("//", "#"),
	".sql": ("--",),
	".lua": ("--",),
	".nvgt": ("//",),
}
DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
LONG_LINE = 200
JS_SYMBOL = re.compile(r"(?:class|function|const|let|var)\s+([A-Za-z_$][\w$]*)")


def parse_python(document: Document) -> ast.Module:
	try:
		return ast.parse(document.text, filename=document.relpath)
	except SyntaxError as exc:
		raise TulesError(f"Cannot parse {document.relpath}: {exc.msg}", line=exc.lineno) from exc


class CodeAnalyzer:
	"""Counts lines and lists the definitions of a single file."""

	def summarize(self, document: Document) -> Dict[str, Any]:
		prefixes = COMMENT_PREFIXES.get(document.path.suffix.lower(), ())
		summary: Dict[str, Any] = {
			"total_lines": len(document.lines),
			"blank_lines": 0,
			"comment_lines": 0,
			"code_lines": 0,
		}
		for line in document.lines:
			stripped = line.strip()
			if not stripped:
				summary["blank_lines"] += 1
			elif prefixes and stripped.startswith(prefixes):
				summary["comment_lines"] += 1
			else:
				summary["code_lines"] += 1
		summary["symbols"] = self.extract_symbols(document)
		return summary

	def extract_symbols(self, document: Document) -> List[Dict[str, Any]]:
		suffix = document.path.suffix.lower()
		if suffix == ".py":
			return self._python_symbols(document)
		if suffix in (".js", ".ts", ".jsx", ".tsx"):
			return self._pattern_symbols(document)
		return []

	def _python_symbols(self, document: Document) -> List[Dict[str, Any]]:
		tree = parse_python(document)
		symbols = []
		for node in ast.walk(tree):
			if isinstance(node, DEFINITIONS):
				symbols.append(
					{
						"kind": "class" if isinstance(node, ast.ClassDef) else "function",
						"name": node.name,
						"line": node.lineno,
						"docstring": (ast.get_docstring(node) or "")[:120],
					}
				)
			elif isinstance(node, (ast.Import, ast.ImportFrom)):
				symbols.append({"kind": "import", "name": _import_label(node), "line": node.lineno})
		return sorted(symbols, key=lambda item: item["line"])

	def _pattern_symbols(self, document: Document) -> List[Dict[str, Any]]:
		return [
			{
				"kind": "symbol",
				"name": match.group(1),
				"line": document.text.count("\n", 0, match.start()) + 1,
			}
			for match in JS_SYMBOL.finditer(document.text)
		]


class Reviewer:
	"""Cheap static checks that catch what a language model usually breaks."""

	def __init__(self, workspace: Workspace):
		self.workspace = workspace

	def review(self, relpath: str) -> List[Dict[str, Any]]:
		document = self.workspace.load(relpath, strict=False)
		if document.path.suffix != ".py":
			return [
				{
					"severity": "info",
					"line": number,
					"message": f"Very long line ({len(line)} chars)",
				}
				for number, line in enumerate(document.lines, 1)
				if len(line) > LONG_LINE * 1.5
			]
		try:
			tree = ast.parse(document.text, filename=document.relpath)
		except SyntaxError as exc:
			return [{"severity": "error", "line": exc.lineno, "message": f"SyntaxError: {exc.msg}"}]
		issues = self._unused_imports(document, tree)
		issues.extend(self._redefinitions(tree))
		issues.extend(self._layout(document))
		return sorted(issues, key=lambda issue: issue["line"] or 0)

	def find_duplicates(self, relpath: Optional[str] = None) -> List[Dict[str, Any]]:
		if relpath:
			return self._duplicates_within(self.workspace.load(relpath, strict=False))
		return self._duplicates_across()

	def find_dependents(self, relpath: str) -> List[Dict[str, Any]]:
		"""List workspace files that import or reference the given module."""
		target = self.workspace.require(relpath)
		module = self.workspace.relativize(target).removesuffix(".py").replace("/", ".")
		stem = target.stem
		dependents = []
		for path in self.workspace.walk(".py"):
			if path == target:
				continue
			try:
				text = self.workspace.load_path(path, strict=False).text
			except TulesError:
				continue
			kind = self._reference_kind(text, module, stem)
			if kind:
				dependents.append({"file": self.workspace.relativize(path), "kind": kind})
		return dependents

	def survey(self) -> Dict[str, Any]:
		counts: Dict[str, int] = {}
		files = 0
		lines = 0
		for path in self.workspace.walk():
			files += 1
			counts[path.suffix.lower()] = counts.get(path.suffix.lower(), 0) + 1
			try:
				lines += len(self.workspace.load_path(path, strict=False).lines)
			except TulesError:
				continue
		return {"total_files": files, "total_lines": lines, "files_by_type": counts}

	def _reference_kind(self, text: str, module: str, stem: str) -> Optional[str]:
		if re.search(rf"^\s*(from|import)\s+{re.escape(module)}\b", text, re.MULTILINE):
			return "module_import"
		if re.search(rf"^\s*(from|import)\s+[.\w]*\b{re.escape(stem)}\b", text, re.MULTILINE):
			return "name_import"
		if re.search(rf"\b{re.escape(stem)}\.", text):
			return "attribute_reference"
		return None

	def _unused_imports(self, document: Document, tree: ast.Module) -> List[Dict[str, Any]]:
		imported: Dict[str, int] = {}
		for node in ast.walk(tree):
			if isinstance(node, ast.Import):
				for alias in node.names:
					imported[(alias.asname or alias.name).split(".")[0]] = node.lineno
			elif isinstance(node, ast.ImportFrom):
				if node.module == "__future__":
					continue
				for alias in node.names:
					if alias.name != "*":
						imported[alias.asname or alias.name] = node.lineno
		used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
		used.update(node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute))
		used.update(re.findall(r"[A-Za-z_]\w*", " ".join(_string_literals(tree))))
		return [
			{"severity": "warning", "line": line, "message": f"Possibly unused import: {name}"}
			for name, line in sorted(imported.items(), key=lambda item: item[1])
			if name not in used
		]

	def _redefinitions(self, tree: ast.Module) -> List[Dict[str, Any]]:
		issues = []
		for parent in [tree] + [node for node in ast.walk(tree) if isinstance(node, DEFINITIONS)]:
			seen: Dict[str, int] = {}
			for node in getattr(parent, "body", []):
				if not isinstance(node, DEFINITIONS):
					continue
				if node.name in seen:
					issues.append(
						{
							"severity": "warning",
							"line": node.lineno,
							"message": (
								f"Redefinition of {node.name} (first at line {seen[node.name]})"
							),
						}
					)
				else:
					seen[node.name] = node.lineno
		return issues

	def _layout(self, document: Document) -> List[Dict[str, Any]]:
		issues = []
		for number, line in enumerate(document.lines, 1):
			if len(line) > LONG_LINE:
				issues.append(
					{
						"severity": "info",
						"line": number,
						"message": f"Line over {LONG_LINE} chars ({len(line)})",
					}
				)
			indent = line[: len(line) - len(line.lstrip())]
			if "\t" in indent and " " in indent:
				issues.append(
					{
						"severity": "warning",
						"line": number,
						"message": "Mixed tabs and spaces in the indentation",
					}
				)
		return issues

	def _duplicates_within(self, document: Document) -> List[Dict[str, Any]]:
		tree = parse_python(document)
		seen: Dict[str, int] = {}
		duplicates = []
		for node in ast.walk(tree):
			if not isinstance(node, DEFINITIONS):
				continue
			if node.name in seen:
				duplicates.append(
					{
						"name": node.name,
						"file": document.relpath,
						"first_line": seen[node.name],
						"duplicate_line": node.lineno,
					}
				)
			else:
				seen[node.name] = node.lineno
		return duplicates

	def _duplicates_across(self) -> List[Dict[str, Any]]:
		seen: Dict[str, Dict[str, Any]] = {}
		duplicates = []
		for path in self.workspace.walk(".py"):
			try:
				document = self.workspace.load_path(path, strict=False)
				tree = ast.parse(document.text)
			except (TulesError, SyntaxError):
				continue
			for node in tree.body:
				if not isinstance(node, DEFINITIONS):
					continue
				previous = seen.get(node.name)
				if previous and previous["file"] != document.relpath:
					duplicates.append(
						{
							"name": node.name,
							"first": f"{previous['file']}:{previous['line']}",
							"duplicate": f"{document.relpath}:{node.lineno}",
						}
					)
				elif not previous:
					seen[node.name] = {"file": document.relpath, "line": node.lineno}
		return duplicates


def _import_label(node: ast.AST) -> str:
	if isinstance(node, ast.ImportFrom):
		return f"from {node.module or '.'} import " + ", ".join(a.name for a in node.names)
	return "import " + ", ".join(a.name for a in node.names)


def _string_literals(tree: ast.Module) -> Iterable[str]:
	for node in ast.walk(tree):
		if isinstance(node, ast.Constant) and isinstance(node.value, str):
			yield node.value
