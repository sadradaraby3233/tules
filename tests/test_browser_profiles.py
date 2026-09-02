"""The per-website profile store: persistence, corruption, forgetting."""

import json

from tules.browser.profiles import ProfileStore, SiteProfile, normalize_host, valid_selector


def test_profiles_roundtrip_by_hostname(tmp_path):
	store = ProfileStore(tmp_path / "sites.json")
	store.save(SiteProfile(host="https://chat.example.com", input_selector="#box"))
	profile = store.load("https://chat.example.com/chat")
	assert profile is not None
	assert profile.input_selector == "#box"
	assert store.load("other.example.com") is None


def test_normalize_host_strips_www_scheme_port_and_path():
	assert normalize_host("https://www.ChatGPT.com/gpts") == "chatgpt.com"
	assert normalize_host("http://chat.example.com:9222/x") == "chat.example.com"
	assert normalize_host("chat.example.com") == "chat.example.com"


def test_a_profile_without_learned_selectors_is_not_loaded(tmp_path):
	store = ProfileStore(tmp_path / "sites.json")
	store.save(SiteProfile(host="x.example", send_selector="#send"))
	assert store.load("x.example") is None


def test_with_selector_updates_one_field_and_the_timestamp(tmp_path):
	profile = SiteProfile(host="x.example", input_selector="#old")
	updated = profile.with_selector("copy_selector", "button.copy")
	assert updated.copy_selector == "button.copy"
	assert updated.input_selector == "#old"
	assert updated.updated >= profile.updated


def test_corrupt_store_is_moved_aside_and_starts_fresh(tmp_path):
	path = tmp_path / "sites.json"
	path.write_text("{not json", encoding="utf-8")
	store = ProfileStore(path)
	assert store.load("x.example") is None
	assert store.warning
	store.save(SiteProfile(host="x.example", input_selector="#box"))
	document = json.loads(path.read_text(encoding="utf-8"))
	assert document["sites"]["x.example"]["input_selector"] == "#box"
	assert any(name.startswith("sites.json.bad-") for name in [p.name for p in tmp_path.iterdir()])


def test_forget_removes_one_site_only(tmp_path):
	store = ProfileStore(tmp_path / "sites.json")
	store.save(SiteProfile(host="a.example", input_selector="#a"))
	store.save(SiteProfile(host="b.example", input_selector="#b"))
	assert store.forget("a.example") is True
	assert store.load("a.example") is None
	assert store.load("b.example") is not None
	assert store.forget("missing.example") is False


def test_valid_selector_rejects_garbage():
	assert valid_selector("#ok-id")
	assert valid_selector('button[aria-label="Copy"]')
	assert not valid_selector("")
	assert not valid_selector("x" * 501)
	assert not valid_selector("has <<<< weird")


def test_every_known_site_builds_a_usable_profile():
	"""KNOWN_SITES feeds SiteProfile(**entry): a typo there is a crash at attach time."""
	from tules.browser.profiles import valid_selector
	from tules.browser.teach import KNOWN_SITES, known_site_defaults

	assert KNOWN_SITES, "the built-in hints must not be empty"
	for host in KNOWN_SITES:
		profile = known_site_defaults(host)
		assert profile.host == host
		assert valid_selector(profile.input_selector), f"{host} has no usable input selector"
		for name in ("copy_selector", "send_selector", "response_selector"):
			value = getattr(profile, name)
			assert not value or valid_selector(value), f"{host}.{name} is not a valid selector"


def test_known_site_hints_are_keyed_by_their_own_normalized_host():
	"""A key like "www.Foo.com" would never be found by the normalized lookup."""
	from tules.browser.teach import KNOWN_SITES

	for host in KNOWN_SITES:
		assert normalize_host(host) == host


def test_an_unknown_host_gets_an_empty_profile_instead_of_an_error():
	from tules.browser.teach import known_site_defaults

	profile = known_site_defaults("https://brand.new.example/chat")
	assert profile.input_selector == ""
	assert profile.learned == 0
