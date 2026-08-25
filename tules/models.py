"""Value objects passed between the searcher, the editor and the protocol layer."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SearchResult:
	file: str
	line: int
	text: str
	context_before: str = ""
	context_after: str = ""
	kind: str = "exact"

	def summarize(self, width: int = 100) -> Dict[str, Any]:
		return {"file": self.file, "line": self.line, "content": self.text[:width]}


@dataclass
class Result:
	success: bool
	message: str
	details: Dict[str, Any] = field(default_factory=dict)
	warnings: List[str] = field(default_factory=list)
	errors: List[str] = field(default_factory=list)

	@classmethod
	def ok(cls, message: str, **details: Any) -> "Result":
		return cls(True, message, details)

	@classmethod
	def fail(cls, message: str, errors: Optional[List[str]] = None, **details: Any) -> "Result":
		return cls(False, message, details, errors=list(errors or []))

	def annotate(self, **details: Any) -> "Result":
		self.details.update(details)
		return self

	def warn(self, message: str) -> "Result":
		self.warnings.append(message)
		return self
