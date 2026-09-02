"""Browser automation for TULES: the Ctrl+F12 loop over an AI chat website.

Optional extra: ``pip install "tules[browser]"``. Everything here is lazy at
the CLI boundary, so plain clipboard TULES never needs these dependencies.
"""

from .hotkey import HotkeyWatcher, Trigger
from .loop import AutoLoop, MODE_AWAITING, MODE_FRESH, MODE_RESEND, Reporter
from .profiles import ProfileStore, SiteProfile, default_store_path, normalize_host

__all__ = [
	"MODE_AWAITING",
	"MODE_FRESH",
	"MODE_RESEND",
	"AutoLoop",
	"HotkeyWatcher",
	"ProfileStore",
	"Reporter",
	"SiteProfile",
	"Trigger",
	"default_store_path",
	"normalize_host",
]
