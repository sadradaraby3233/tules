"""Persistent per-website "where things are" profiles for the browser automation.

When TULES learns where an AI chat website keeps its message box or Copy button,
the finding is stored here, keyed by hostname, so the user never teaches the
same website twice. The file is plain JSON and lives outside the workspace
because it describes the website, not the project.
"""

import json
import os
import re
import time
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Dict, Optional

SCHEMA_VERSION = 1
ENV_OVERRIDE = "TULES_SITES_FILE"
DEFAULT_PATH = Path("~/.tules/browser_sites.json")


def default_store_path() -> Path:
	return Path(os.environ.get(ENV_OVERRIDE) or DEFAULT_PATH).expanduser()


def normalize_host(url: str) -> str:
	"""The profile key: a hostname without www, or whatever the URL gives us."""
	host = url
	if "://" in host:
		host = host.split("://", 1)[1]
	host = host.split("/", 1)[0].split(":", 1)[0].strip().lower()
	if host.startswith("www."):
		host = host[4:]
	return host or "unknown"


@dataclass
class SiteProfile:
	"""Everything TULES remembers about one AI chat website."""

	host: str
	input_selector: str = ""
	input_kind: str = ""
	copy_selector: str = ""
	send_selector: str = ""
	response_selector: str = ""
	generating_selector: str = ""
	notes: Dict[str, str] = field(default_factory=dict)
	updated: float = field(default_factory=time.time)

	def to_dict(self) -> Dict[str, object]:
		data: Dict[str, object] = {"host": self.host, "updated": self.updated}
		for item in fields(self):
			if item.name in ("host", "updated"):
				continue
			value = getattr(self, item.name)
			if value:
				data[item.name] = value
		if self.notes:
			data["notes"] = self.notes
		return data

	@classmethod
	def from_dict(cls, data: Dict[str, object]) -> "SiteProfile":
		known = {item.name for item in fields(cls)}
		kwargs = {key: value for key, value in data.items() if key in known}
		kwargs.setdefault("host", str(data.get("host", "unknown")))
		return cls(**kwargs)

	def with_selector(self, kind: str, selector: str) -> "SiteProfile":
		"""A fresh copy with one learned selector and a new timestamp."""
		return replace(self, **{kind: selector, "updated": time.time()})

	@property
	def learned(self) -> int:
		return sum(1 for name in ("input_selector", "copy_selector") if getattr(self, name))


_SELECTOR = re.compile(r"[A-Za-z0-9_\-\[\]=\"'().:#^~*|,+>\s]+\Z")


def valid_selector(selector: str) -> bool:
	"""Cheap sanity check so a corrupted profile can never reach the DOM query."""
	return bool(selector) and len(selector) <= 500 and bool(_SELECTOR.match(selector))


class ProfileStore:
	"""Loads and saves the JSON file holding every learned website profile."""

	def __init__(self, path: Optional[Path] = None):
		self.path = Path(path) if path else default_store_path()
		self.warning = ""

	def _read_all(self) -> Dict[str, Dict[str, object]]:
		try:
			raw = self.path.read_text(encoding="utf-8")
		except FileNotFoundError:
			return {}
		except OSError as exc:
			self.warning = f"could not read {self.path}: {exc}"
			return {}
		try:
			data = json.loads(raw)
		except json.JSONDecodeError as exc:
			stamp = time.strftime("%Y%m%d_%H%M%S")
			with open(f"{self.path}.bad-{stamp}", "w", encoding="utf-8") as handle:
				handle.write(raw)
			self.warning = f"{self.path} was corrupt ({exc}); moved aside, starting fresh"
			return {}
		sites = data.get("sites") if isinstance(data, dict) else None
		return sites if isinstance(sites, dict) else {}

	def load(self, host: str) -> Optional[SiteProfile]:
		data = self._read_all().get(normalize_host(host))
		if not isinstance(data, dict):
			return None
		profile = SiteProfile.from_dict(data)
		return profile if profile.learned else None

	def save(self, profile: SiteProfile) -> Path:
		sites = self._read_all()
		sites[normalize_host(profile.host)] = profile.to_dict()
		document = {"version": SCHEMA_VERSION, "sites": sites}
		self.path.parent.mkdir(parents=True, exist_ok=True)
		temporary = self.path.with_suffix(f".{os.getpid()}.tmp")
		temporary.write_text(
			json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
		)
		os.replace(temporary, self.path)
		return self.path

	def forget(self, host: str) -> bool:
		sites = self._read_all()
		key = normalize_host(host)
		if key not in sites:
			return False
		del sites[key]
		document = {"version": SCHEMA_VERSION, "sites": sites}
		self.path.parent.mkdir(parents=True, exist_ok=True)
		self.path.write_text(
			json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
		)
		return True
