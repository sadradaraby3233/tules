"""The action that documents the other actions."""

from typing import Any, Dict

from .. import guide
from ..errors import TulesError
from ..models import Result
from ..registry import command


@command("list_actions", "List every action this agent understands")
def list_actions(agent, payload: Dict[str, Any]) -> Result:
	"""Serve the documentation the model would otherwise carry in its context."""
	wanted = payload.get("name") or payload.get("action_name")
	if not wanted:
		return Result.ok(f"{len(agent.describe())} actions available", content=guide.index())
	name = guide.resolve(str(wanted))
	if not name:
		raise TulesError(f"Unknown action: {wanted}", content=guide.index())
	return Result.ok(f"Usage for {name}", content=guide.detail(name))
