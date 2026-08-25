"""Importing this package registers every action in the registry."""

from . import claude_files, edits, files, review, search, shell
from ..registry import REGISTRY, alias

alias("help", "list_actions")
# Historical replace actions remain accepted, but all use one universal engine.
for old_name in (
	"edit",
	"str_replace",
	"surgical_replace",
	"context_replace",
	"search_and_replace_all",
	"smart_replace",
	"confirm_smart_replace",
):
	alias(old_name, "replace")

__all__ = ["REGISTRY", "claude_files", "edits", "files", "review", "search", "shell"]
