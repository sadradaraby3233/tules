"""Exceptions the dispatcher turns into failed command results."""

from typing import Any, Dict


class TulesError(Exception):
	"""Base error carrying structured details for the reply payload."""

	def __init__(self, message: str, **details: Any):
		super().__init__(message)
		self.message = message
		self.details: Dict[str, Any] = details


class WorkspaceError(TulesError):
	"""A path is missing, unreadable or outside the workspace root."""


class MatchError(TulesError):
	"""A search block could not be located confidently."""


class SyntaxGuardError(TulesError):
	"""The edit would have introduced a syntax error, so it was refused."""
