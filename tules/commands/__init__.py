"""Importing this package registers every action in the registry."""

from . import edits, files, review, search, shell
from ..registry import REGISTRY, alias

alias("help", "list_actions")

__all__ = ["REGISTRY", "edits", "files", "review", "search", "shell"]
