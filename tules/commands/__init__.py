"""Importing this package registers every action in the registry."""

from . import edits, file_tools, review, search, shell, web
from ..registry import REGISTRY, alias

# Public compatibility aliases live in one place so command modules stay focused.
alias("help", "list_actions")

# Older replace names remain accepted, but all use one universal engine.
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

__all__ = ["REGISTRY", "edits", "file_tools", "review", "search", "shell", "web"]
