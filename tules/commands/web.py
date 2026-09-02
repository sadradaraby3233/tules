"""Safe, dependency-free web search, page inspection, and file downloads."""

import ipaddress
import json
import re
import socket
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..errors import TulesError, WorkspaceError
from ..models import Result
from ..registry import command, flag, number, text
from ..version import __version__

PROJECT_URL = "https://github.com/sadradaraby3233/tules"
USER_AGENT = f"TULES/{__version__} (+{PROJECT_URL})"
DEFAULT_TIMEOUT = 20
MAX_TIMEOUT = 60
DEFAULT_FETCH_BYTES = 4 * 1024 * 1024
MAX_FETCH_BYTES = 16 * 1024 * 1024
DEFAULT_DOWNLOAD_BYTES = 100 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 500 * 1024 * 1024
SEARCH_LIMIT = 20
TEXT_LIMIT = 100_000
HTML_LIMIT = 200_000


class PageParser(HTMLParser):
	"""Collect useful page structure while producing readable visible text."""

	SKIPPED: ClassVar[Set[str]] = {"script", "style", "noscript", "template", "svg"}
	BLOCKS: ClassVar[Set[str]] = {
		"article",
		"br",
		"div",
		"footer",
		"h1",
		"h2",
		"h3",
		"h4",
		"h5",
		"h6",
		"header",
		"li",
		"main",
		"nav",
		"p",
		"section",
		"table",
		"tr",
	}

	def __init__(self, base_url: str):
		super().__init__(convert_charrefs=True)
		self.base_url = base_url
		self.title = ""
		self.text_parts: List[str] = []
		self.links: List[Dict[str, str]] = []
		self.elements: List[Dict[str, Any]] = []
		self.metadata: Dict[str, str] = {}
		self._stack: List[Dict[str, Any]] = []
		self._skip_depth = 0

	def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
		attributes = {key: value or "" for key, value in attrs}
		entry: Dict[str, Any] = {"tag": tag, "attrs": attributes, "text": []}
		self._stack.append(entry)
		if tag in self.SKIPPED:
			self._skip_depth += 1
		if tag in self.BLOCKS and not self._skip_depth:
			self.text_parts.append("\n")
		if tag == "meta":
			name = attributes.get("name") or attributes.get("property")
			if name and attributes.get("content"):
				self.metadata[name] = attributes["content"]

	def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
		self.handle_starttag(tag, attrs)
		self.handle_endtag(tag)

	def handle_data(self, data: str) -> None:
		if self._skip_depth:
			return
		self.text_parts.append(data)
		for entry in self._stack:
			entry["text"].append(data)

	def handle_endtag(self, tag: str) -> None:
		if not self._stack:
			return
		index = next(
			(i for i in range(len(self._stack) - 1, -1, -1) if self._stack[i]["tag"] == tag), -1
		)
		if index < 0:
			return
		entry = self._stack[index]
		del self._stack[index:]
		content = _clean_text("".join(entry["text"]))
		attrs = entry["attrs"]
		if tag == "title" and content:
			self.title = content
		if tag == "a" and attrs.get("href"):
			self.links.append({"text": content, "url": urljoin(self.base_url, attrs["href"])})
		if content and (tag in self.BLOCKS or attrs.get("id") or attrs.get("class")):
			self.elements.append(
				{
					"tag": tag,
					"id": attrs.get("id", ""),
					"class": attrs.get("class", ""),
					"text": content,
				}
			)
		if tag in self.SKIPPED and self._skip_depth:
			self._skip_depth -= 1
		if tag in self.BLOCKS and not self._skip_depth:
			self.text_parts.append("\n")

	@property
	def visible_text(self) -> str:
		lines = (_clean_text(line) for line in "".join(self.text_parts).splitlines())
		return "\n".join(line for line in lines if line)


class SafeRedirectHandler(HTTPRedirectHandler):
	def redirect_request(self, req, fp, code, msg, headers, newurl):
		_validate_public_url(newurl)
		return super().redirect_request(req, fp, code, msg, headers, newurl)


def _clean_text(value: str) -> str:
	return re.sub(r"\s+", " ", value).strip()


def _validate_public_url(url: str) -> None:
	parsed = urlparse(url)
	if parsed.scheme not in ("http", "https") or not parsed.hostname:
		raise TulesError("URL must use http or https and include a host", url=url)
	if parsed.username or parsed.password:
		raise TulesError("Credentials in URLs are not allowed")
	port = parsed.port or (80 if parsed.scheme == "http" else 443)
	try:
		addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
	except socket.gaierror as exc:
		raise TulesError(f"Could not resolve host: {parsed.hostname}") from exc
	for address in addresses:
		ip = ipaddress.ip_address(address[4][0])
		if not ip.is_global:
			raise TulesError(
				"Private, local, and reserved network addresses are not allowed",
				host=parsed.hostname,
			)


def _timeout(payload: Dict[str, Any]) -> int:
	value = number(payload, "timeout", DEFAULT_TIMEOUT)
	if not 1 <= value <= MAX_TIMEOUT:
		raise TulesError(f"'timeout' must be between 1 and {MAX_TIMEOUT} seconds")
	return value


def _request(url: str, timeout: int, max_bytes: int) -> Tuple[bytes, str, str, int]:
	_validate_public_url(url)
	request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
	try:
		with build_opener(SafeRedirectHandler()).open(request, timeout=timeout) as response:
			content_length = response.headers.get("Content-Length")
			if content_length and int(content_length) > max_bytes:
				raise TulesError(
					"Response exceeds the configured size limit",
					bytes=int(content_length),
					limit=max_bytes,
				)
			body = response.read(max_bytes + 1)
			if len(body) > max_bytes:
				raise TulesError("Response exceeds the configured size limit", limit=max_bytes)
			return (
				body,
				response.geturl(),
				response.headers.get("Content-Type", ""),
				response.status,
			)
	except HTTPError as exc:
		raise TulesError(f"HTTP {exc.code}: {exc.reason}", url=url, status=exc.code) from exc
	except URLError as exc:
		raise TulesError(f"Request failed: {exc.reason}", url=url) from exc
	except (OSError, ValueError) as exc:
		raise TulesError(f"Request failed: {exc}", url=url) from exc


def _decode(body: bytes, content_type: str) -> str:
	match = re.search(r"charset=([^;\s]+)", content_type, re.IGNORECASE)
	encoding = match.group(1).strip("\"'") if match else "utf-8"
	try:
		return body.decode(encoding, errors="replace")
	except LookupError:
		return body.decode("utf-8", errors="replace")


def _selection(items: List[Dict[str, Any]], payload: Dict[str, Any]) -> List[Dict[str, Any]]:
	tag = payload.get("tag")
	element_id = payload.get("id")
	class_name = payload.get("class")
	selected = items
	if tag:
		selected = [item for item in selected if item.get("tag") == tag]
	if element_id:
		selected = [item for item in selected if item.get("id") == element_id]
	if class_name:
		selected = [item for item in selected if class_name in item.get("class", "").split()]
	offset = max(0, number(payload, "offset", 0))
	limit = number(payload, "limit", 100)
	return selected[offset:] if limit == 0 else selected[offset : offset + max(0, limit)]


@command("web_fetch", "Retrieve and inspect a web page, its HTML, links, text, or elements")
def web_fetch(agent, payload: Dict[str, Any]) -> Result:
	url = text(payload, "url")
	max_bytes = number(payload, "max_bytes", DEFAULT_FETCH_BYTES)
	if not 1 <= max_bytes <= MAX_FETCH_BYTES:
		raise TulesError(f"'max_bytes' must be between 1 and {MAX_FETCH_BYTES}")
	body, final_url, content_type, status = _request(url, _timeout(payload), max_bytes)
	source = _decode(body, content_type)
	parser = PageParser(final_url)
	if "html" in content_type.lower() or "<html" in source[:1000].lower():
		parser.feed(source)
	mode = text(payload, "mode", "text")
	total_lines = None
	total_chars = None
	if mode == "html":
		total_chars = len(source)
		first = max(0, number(payload, "start_char", 0))
		last = number(payload, "end_char", min(len(source), first + HTML_LIMIT))
		if last < first:
			raise TulesError("'end_char' must not be before 'start_char'")
		content: Any = source[first : min(len(source), last)]
	elif mode == "links":
		content = _selection(parser.links, payload)
	elif mode == "elements":
		content = _selection(parser.elements, payload)
	elif mode == "json":
		try:
			content = json.loads(source)
		except json.JSONDecodeError as exc:
			raise TulesError(f"Response is not valid JSON: {exc}") from exc
	elif mode == "text":
		page_text = parser.visible_text or source
		lines = page_text.splitlines()
		total_lines = len(lines)
		first = number(payload, "start_line", 1)
		last = number(payload, "end_line", min(len(lines), first + 499))
		if first < 1 or last < first:
			raise TulesError("Text line range must be positive and ordered")
		content = "\n".join(lines[first - 1 : last])[:TEXT_LIMIT]
	else:
		raise TulesError("'mode' must be text, html, links, elements, or json")
	if mode == "html":
		truncated = last < len(source)
	elif mode == "text":
		truncated = last < len(lines) or len(content) >= TEXT_LIMIT
	elif mode == "links":
		truncated = len(content) < len(parser.links)
	elif mode == "elements":
		truncated = len(content) < len(parser.elements)
	else:
		truncated = False
	return Result.ok(
		f"Fetched {final_url}",
		url=final_url,
		status=status,
		content_type=content_type,
		bytes=len(body),
		title=parser.title,
		metadata=parser.metadata,
		content=content,
		total_lines=total_lines,
		total_chars=total_chars,
		truncated=truncated,
	)


def _google_results(source: str) -> List[Dict[str, str]]:
	parser = PageParser("https://www.google.com")
	parser.feed(source)
	results = []
	seen = set()
	for link in parser.links:
		url = link["url"]
		parsed = urlparse(url)
		if parsed.path == "/url":
			url = parse_qs(parsed.query).get("q", [""])[0]
		parsed = urlparse(url)
		if parsed.scheme not in ("http", "https") or not parsed.hostname:
			continue
		if parsed.hostname.endswith("google.com") or url in seen:
			continue
		seen.add(url)
		results.append({"title": link["text"] or parsed.hostname, "url": url})
	return results


@command("web_search", "Search the public web with Google")
def web_search(agent, payload: Dict[str, Any]) -> Result:
	query = text(payload, "query", payload.get("search"))
	limit = number(payload, "limit", 10)
	if not query.strip() or not 1 <= limit <= SEARCH_LIMIT:
		raise TulesError(f"A query and a limit between 1 and {SEARCH_LIMIT} are required")
	parameters = {"q": query, "num": limit, "start": max(0, number(payload, "offset", 0)), "gbv": 1}
	if payload.get("language"):
		parameters["hl"] = str(payload["language"])
	url = "https://www.google.com/search?" + urlencode(parameters)
	body, final_url, content_type, status = _request(url, _timeout(payload), DEFAULT_FETCH_BYTES)
	results = _google_results(_decode(body, content_type))[:limit]
	return Result.ok(
		f"Google returned {len(results)} result(s) for {query!r}",
		query=query,
		results=results,
		search_url=final_url,
		status=status,
	)


@command("download_url", "Download a public URL into the workspace", mutates=True)
def download_url(agent, payload: Dict[str, Any]) -> Result:
	url = text(payload, "url")
	max_bytes = number(payload, "max_bytes", DEFAULT_DOWNLOAD_BYTES)
	if not 1 <= max_bytes <= MAX_DOWNLOAD_BYTES:
		raise TulesError(f"'max_bytes' must be between 1 and {MAX_DOWNLOAD_BYTES}")
	body, final_url, content_type, status = _request(url, _timeout(payload), max_bytes)
	relpath = payload.get("file") or payload.get("file_path")
	if not relpath:
		name = Path(urlparse(final_url).path).name
		if not name:
			raise TulesError("The URL has no filename; provide 'file'")
		relpath = name
	path = agent.workspace.resolve(str(relpath))
	if path.exists() and not flag(payload, "overwrite"):
		raise WorkspaceError(f"File already exists: {relpath}; set overwrite=true to replace it")
	backup = agent.workspace.back_up(path) if path.exists() else None
	agent.workspace.write_bytes(path, body)
	return Result.ok(
		f"Downloaded {final_url} to {agent.workspace.relativize(path)}",
		file=agent.workspace.relativize(path),
		url=final_url,
		status=status,
		content_type=content_type,
		bytes=len(body),
		backup=agent.workspace.relativize(backup) if backup else None,
	)
