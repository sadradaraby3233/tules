"""TULES: a clipboard driven local code agent."""

from .agent import Agent
from .editor import Editor
from .errors import MatchError, SyntaxGuardError, TulesError, WorkspaceError
from .models import Result, SearchResult
from .search import Searcher
from .workspace import Workspace

__version__ = "2.0.0"
__all__ = [
	"Agent", "Editor", "MatchError", "Result", "SearchResult", "Searcher",
	"SyntaxGuardError", "TulesError", "Workspace", "WorkspaceError", "__version__",
]
