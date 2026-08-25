import pytest

from tules.errors import TulesError
from tules.protocol import carve_json, decode, find_block, repair


def test_find_block_extracts_the_payload():
	assert find_block('noise edit: {"action": "help"} endedit tail') == '{"action": "help"}'


def test_find_block_strips_code_fences():
	text = 'edit:\n```json\n{"action": "help"}\n```\nendedit'
	assert find_block(text) == '{"action": "help"}'


def test_find_block_is_case_insensitive():
	assert find_block('EDIT: {"action": "help"} ENDEDIT') == '{"action": "help"}'


def test_find_block_returns_none_without_markers():
	assert find_block("just some copied code") is None


def test_carve_json_ignores_braces_inside_strings():
	assert carve_json('prefix {"a": "}"} suffix') == '{"a": "}"}'


def test_carve_json_finds_an_array():
	assert carve_json("text [1, 2] more") == "[1, 2]"


def test_repair_drops_trailing_commas():
	assert repair('{"a": 1,}') == '{"a": 1}'


def test_repair_escapes_newlines_inside_strings():
	assert repair('{"a": "x\ny"}') == '{"a": "x\\ny"}'


def test_decode_wraps_a_single_object():
	assert decode('{"action": "help"}') == [{"action": "help"}]


def test_decode_keeps_an_array():
	assert decode('[{"action": "help"}, {"action": "analyze"}]') == [
		{"action": "help"},
		{"action": "analyze"},
	]


def test_decode_repairs_a_broken_payload():
	assert decode('{"action": "help", "note": "line\nbreak",}') == [
		{"action": "help", "note": "line\nbreak"}
	]


def test_decode_rejects_a_scalar():
	with pytest.raises(TulesError):
		decode("42")


def test_decode_reports_unparseable_input():
	with pytest.raises(TulesError) as caught:
		decode("{not json at all")
	assert "Invalid JSON" in caught.value.message
