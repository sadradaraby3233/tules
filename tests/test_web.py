import json

import pytest

from tules.commands import web
from tules.errors import TulesError

PAGE = b"""<!doctype html><html><head><title>Example</title>
<meta name="description" content="A useful page"></head><body>
<main id="content"><h1>Welcome</h1><p class="lead">Read this page.</p>
<a href="/docs">Documentation</a></main><script>ignore me</script></body></html>"""


def fake_request(url, timeout, max_bytes):
	return PAGE, "https://example.com/page", "text/html; charset=utf-8", 200


def test_web_fetch_supports_text_html_links_and_element_filters(agent, monkeypatch):
	monkeypatch.setattr(web, "_request", fake_request)
	plain = agent.run({"action": "web_fetch", "url": "https://example.com"})
	assert plain.success
	assert "Welcome" in plain.details["content"]
	assert "ignore me" not in plain.details["content"]
	assert plain.details["metadata"]["description"] == "A useful page"
	section = agent.run(
		{
			"action": "web_fetch",
			"url": "https://example.com",
			"start_line": 2,
			"end_line": 2,
		}
	)
	assert section.details["content"] == "Welcome"
	assert section.details["total_lines"] >= 3

	links = agent.run({"action": "web_fetch", "url": "https://example.com", "mode": "links"})
	assert links.details["content"] == [
		{"text": "Documentation", "url": "https://example.com/docs"}
	]
	elements = agent.run(
		{"action": "web_fetch", "url": "https://example.com", "mode": "elements", "class": "lead"}
	)
	assert elements.details["content"][0]["text"] == "Read this page."
	html = agent.run({"action": "web_fetch", "url": "https://example.com", "mode": "html"})
	assert "<!doctype html>" in html.details["content"]


def test_web_fetch_parses_json(agent, monkeypatch):
	monkeypatch.setattr(
		web,
		"_request",
		lambda *args: (
			json.dumps({"ok": True}).encode(),
			"https://example.com/api",
			"application/json",
			200,
		),
	)
	result = agent.run({"action": "web_fetch", "url": "https://example.com/api", "mode": "json"})
	assert result.details["content"] == {"ok": True}


def test_google_search_extracts_external_result_links(agent, monkeypatch):
	source = b'<a href="/url?q=https%3A%2F%2Fdocs.python.org%2F3%2F&sa=U">Python docs</a>'
	monkeypatch.setattr(
		web,
		"_request",
		lambda *args: (source, "https://www.google.com/search?q=python", "text/html", 200),
	)
	result = agent.run({"action": "web_search", "query": "python", "limit": 5})
	assert result.success
	assert result.details["results"] == [
		{"title": "Python docs", "url": "https://docs.python.org/3/"}
	]


def test_download_url_writes_and_safely_overwrites(agent, monkeypatch):
	monkeypatch.setattr(
		web,
		"_request",
		lambda *args: (
			b"downloaded",
			"https://example.com/archive.bin",
			"application/octet-stream",
			200,
		),
	)
	created = agent.run({"action": "download_url", "url": "https://example.com/archive.bin"})
	assert created.success
	assert (agent.root / "archive.bin").read_bytes() == b"downloaded"
	refused = agent.run({"action": "download_url", "url": "https://example.com/archive.bin"})
	assert not refused.success
	replaced = agent.run(
		{"action": "download_url", "url": "https://example.com/archive.bin", "overwrite": True}
	)
	assert replaced.success
	assert replaced.details["backup"]


def test_url_validation_rejects_local_and_non_http_addresses(monkeypatch):
	with pytest.raises(TulesError):
		web._validate_public_url("file:///etc/passwd")
	monkeypatch.setattr(
		web.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("127.0.0.1", 80))]
	)
	with pytest.raises(TulesError):
		web._validate_public_url("http://localhost/test")
