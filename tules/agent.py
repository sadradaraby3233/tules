"""The agent: one workspace, one command registry, one result per command."""

from typing import Any, Dict, List

from . import commands  # noqa: F401
from .analysis import CodeAnalyzer, Reviewer
from .editor import Editor
from .errors import TulesError
from .models import Result
from .registry import describe, lookup
from .search import Searcher
from .workspace import Workspace

REVIEWED_ISSUES = 3
SHELL_TIMEOUT = 30


class Agent:
	"""Turns a decoded JSON command into a result, and reviews what it changed."""

	def __init__(self, root: str = ".", allow_shell: bool = True,
			shell_timeout: int = SHELL_TIMEOUT, auto_review: bool = True):
		self.workspace = Workspace(root)
		self.editor = Editor(self.workspace)
		self.searcher = Searcher(self.workspace)
		self.analyzer = CodeAnalyzer()
		self.reviewer = Reviewer(self.workspace)
		self.allow_shell = allow_shell
		self.shell_timeout = shell_timeout
		self.auto_review = auto_review

	@property
	def root(self):
		return self.workspace.root

	def describe(self) -> List[Dict[str, str]]:
		return describe()

	def run(self, payload: Any) -> Result:
		if not isinstance(payload, dict):
			return Result.fail(f"Command must be a JSON object, got {type(payload).__name__}")
		action = str(payload.get("action", "")).strip().lower()
		try:
			command = lookup(action)
			result = command.handler(self, payload)
		except TulesError as exc:
			return Result.fail(exc.message, **exc.details)
		except Exception as exc:
			return Result.fail(f"{type(exc).__name__}: {exc}")
		if result.success and command.mutates and self.auto_review:
			self._append_review(result, payload)
		return result

	def run_batch(self, payloads: List[Any]) -> List[Result]:
		return [self.run(payload) for payload in payloads]

	def _append_review(self, result: Result, payload: Dict[str, Any]) -> None:
		relpath = payload.get("file")
		if not isinstance(relpath, str) or not relpath:
			return
		try:
			issues = self.reviewer.review(relpath)
		except TulesError:
			return
		if not issues:
			return
		result.warn(f"Post-edit review: {len(issues)} issue(s)")
		for issue in issues[:REVIEWED_ISSUES]:
			result.warn(f"  {issue['severity']} line {issue['line']}: {issue['message']}")
