"""Action name to handler mapping, filled in by the command modules."""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .errors import TulesError
from .models import Result

Handler = Callable[[Any, Dict[str, Any]], Result]


@dataclass(frozen=True)
class Command:
	name: str
	summary: str
	handler: Handler
	mutates: bool = False


REGISTRY: Dict[str, Command] = {}
ALIASES: Dict[str, str] = {}


def command(name: str, summary: str, mutates: bool = False) -> Callable[[Handler], Handler]:
	"""Register a handler under an action name used in the JSON protocol."""

	def register(handler: Handler) -> Handler:
		if name in REGISTRY:
			raise RuntimeError(f"Duplicate command: {name}")
		REGISTRY[name] = Command(name, summary, handler, mutates)
		return handler

	return register


def alias(name: str, target: str) -> None:
	"""Accept an older action name for a command that has been renamed."""
	if target not in REGISTRY:
		raise RuntimeError(f"Cannot alias {name} to unknown command {target}")
	ALIASES[name] = target


def lookup(action: str) -> Command:
	found = REGISTRY.get(action) or REGISTRY.get(ALIASES.get(action, ""))
	if not found:
		raise TulesError(f"Unknown action: {action}", available=sorted(REGISTRY))
	return found


def describe() -> List[Dict[str, str]]:
	return [
		{"action": item.name, "summary": item.summary}
		for item in sorted(REGISTRY.values(), key=lambda item: item.name)
	]


def text(payload: Dict[str, Any], key: str, default: Optional[str] = None) -> str:
	value = payload.get(key, default)
	if value is None:
		raise TulesError(f"Missing '{key}'")
	if not isinstance(value, str):
		raise TulesError(f"'{key}' must be a string, got {type(value).__name__}")
	return value


def number(payload: Dict[str, Any], key: str, default: Optional[int] = None) -> int:
	value = payload.get(key, default)
	if value is None:
		raise TulesError(f"Missing '{key}'")
	try:
		return int(value)
	except (TypeError, ValueError) as exc:
		raise TulesError(f"'{key}' must be an integer, got {value!r}") from exc


def decimal(payload: Dict[str, Any], key: str, default: float) -> float:
	try:
		return float(payload.get(key, default))
	except (TypeError, ValueError) as exc:
		raise TulesError(f"'{key}' must be a number") from exc


def flag(payload: Dict[str, Any], key: str, default: bool = False) -> bool:
	return bool(payload.get(key, default))
