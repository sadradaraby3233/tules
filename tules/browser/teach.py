"""Teaching TULES where a website keeps its edit box and Copy button.

Teaching only ever happens after automatic detection has failed, and it uses
the interaction the spec asks for: the user focuses the message box, or clicks
the Copy button once, and TULES records what they touched, derives a robust
selector, verifies it against the live DOM, and saves it for next time.

A teaching click on Copy is not wasted: it copies the response just like the
automatic click would have, so the loop can carry straight on with the text it
put on the clipboard.
"""

from typing import Callable, Dict, Optional

from .page import BrowserPage
from .profiles import ProfileStore, SiteProfile, normalize_host, valid_selector
from .selectors import Element

INPUT_INSTRUCTIONS = """TULES cannot tell which box is the AI message box on this site.

Click inside the AI's message/edit box now (where you would type your prompt).
TULES is listening for the focus and will remember what you click.
"""

COPY_INSTRUCTIONS = """TULES cannot tell which button copies the AI response on this site.

Click the AI response's Copy button ONCE now.
Your click will copy the response to the clipboard as usual, and TULES will
remember which button you clicked.
"""

TIMEOUT_MESSAGE = "no {kind} was identified within {seconds} s"

# Opening guesses for well-known AI chat sites, keyed by normalized hostname.
# Keys must be SiteProfile field names; every value is verified against the live
# DOM before it is used, so a stale entry costs nothing but a fallback.
KNOWN_SITES: Dict[str, Dict[str, str]] = {
	"chatgpt.com": {
		"input_selector": "textarea#prompt-textarea",
		"send_selector": "#composer-submit-button",
	},
	"chat.openai.com": {"input_selector": "textarea#prompt-textarea"},
	"claude.ai": {"input_selector": 'div[contenteditable="true"].ProseMirror'},
	"gemini.google.com": {"input_selector": 'div.ql-editor[contenteditable="true"]'},
	"copilot.microsoft.com": {"input_selector": "textarea#userInput"},
	"chat.deepseek.com": {"input_selector": "textarea#chat-input"},
	"grok.com": {"input_selector": "textarea"},
	"chat.mistral.ai": {"input_selector": "textarea"},
	"perplexity.ai": {"input_selector": "textarea[placeholder]"},
	"chat.qwen.ai": {"input_selector": "textarea"},
	"kimi.com": {"input_selector": "textarea"},
	"duckduckgo.com": {"input_selector": "textarea"},
	"poe.com": {"input_selector": "textarea"},
	"huggingface.co": {"input_selector": "textarea"},
}


class TeachingTimeout(Exception):
	"""The user did not identify the element in time."""


class Teacher:
	"""Runs one teach interaction and persists what it learned."""

	def __init__(
		self,
		page: BrowserPage,
		store: ProfileStore,
		clock,
		report,
		sleep: Optional[Callable[[float], None]] = None,
		poll_seconds: float = 0.5,
		timeout_seconds: float = 120.0,
	):
		self.page = page
		self.store = store
		self.clock = clock
		self.report = report
		self.sleep = sleep or clock.sleep
		self.poll_seconds = poll_seconds
		self.timeout_seconds = timeout_seconds

	def learn(self, kind: str, host: str) -> tuple[Element, Optional[SiteProfile]]:
		"""Interactively identify ``kind`` (``input`` or ``copy``) and save it."""
		self.report(INPUT_INSTRUCTIONS if kind == "input" else COPY_INSTRUCTIONS)
		self.page.reset_teach(kind)
		self.page.arm_teach(kind)
		deadline = self.clock.now() + self.timeout_seconds
		element: Optional[Element] = None
		while self.clock.now() < deadline:
			element = self.page.teach_result(kind)
			if element is not None:
				break
			self.sleep(self.poll_seconds)
		if element is None:
			raise TeachingTimeout(
				TIMEOUT_MESSAGE.format(kind=kind, seconds=int(self.timeout_seconds))
			)
		selector = self.page.best_selector_for(element)
		if selector is None or not valid_selector(selector):
			raise TeachingTimeout(
				f"the {kind} you showed me cannot be described by a stable selector; "
				"this site will need teaching again next time"
			)
		profile = self._save(kind, host, selector)
		self.report(f"Learned the {kind}: {element.describe()}")
		self.report(f"Saved as {selector!r} for {host} in {self.store.path}")
		return element, profile

	def _save(self, kind: str, host: str, selector: str) -> SiteProfile:
		profile = self.store.load(host) or SiteProfile(host=host)
		field = "input_selector" if kind == "input" else "copy_selector"
		profile = profile.with_selector(field, selector)
		self.store.save(profile)
		return profile


def known_site_defaults(host: str) -> SiteProfile:
	"""First-guess selectors for well-known AI chat sites.

	These are hints only: they are verified against the live DOM before use and
	quietly discarded when they do not resolve, so a site redesign degrades to
	detection or teaching rather than a wrong click.
	"""
	return SiteProfile(host=host, **KNOWN_SITES.get(normalize_host(host), {}))
