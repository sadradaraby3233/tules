"""Importing this package registers every action in the registry."""

from . import claude_files, edits, files, review, search, shell
from ..registry import REGISTRY, alias

alias("help", "list_actions")

__all__ = ["REGISTRY", "claude_files", "edits", "files", "review", "search", "shell"]
