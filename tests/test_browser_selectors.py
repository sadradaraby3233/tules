"""Element recognition: descriptors to selectors, without a browser."""

from tules.browser.selectors import (
	Element,
	choose_copy,
	choose_input,
	choose_input_from,
	copy_score,
	derive_candidates,
	score_input,
)


def make(**kwargs):
	defaults = {
		"ref": 0,
		"tag": "div",
		"visible": True,
		"connected": True,
		"rect": {"w": 300, "h": 60},
	}
	defaults.update(kwargs)
	return Element(**defaults)


def test_derive_candidates_orders_stable_id_first_and_skips_hashy_ids():
	strong = make(tag="textarea", id="prompt-input", classes=["chat-box"])
	candidates = derive_candidates(strong)
	assert candidates[0] == "#prompt-input"

	generated = make(tag="textarea", id=":r1a:", classes=["chat-box"])
	assert not any(c.startswith("#") for c in derive_candidates(generated))

	digits = make(tag="textarea", id="box123456789")
	assert all(not c.startswith("#box") for c in derive_candidates(digits))


def test_derive_candidates_prefers_testid_then_aria_then_placeholder():
	el = make(
		tag="textarea",
		testid="chat-composer",
		aria="Message",
		placeholder="Ask me anything",
	)
	candidates = derive_candidates(el)
	assert candidates[0] == '[data-testid="chat-composer"]'
	assert 'textarea[aria-label="Message"]' in candidates
	assert 'textarea[placeholder="Ask me anything"]' in candidates


def test_derive_candidates_drops_hash_like_classes_but_keeps_plain_ones():
	el = make(tag="button", classes=["css-1x2y3z4a", "copy-btn", "IconButton__hash9f2e1d"])
	assert derive_candidates(el) == ["button.copy-btn"]


def test_structural_path_anchors_on_the_nearest_stable_ancestor():
	el = make(tag="button", classes=[])
	path = [
		{"tag": "main"},
		{"tag": "div", "id": "thread"},
		{"tag": "div", "nth": 2},
	]
	selector = derive_candidates(el, path)[-1]
	assert selector == "#thread div:nth-of-type(2) button"


def test_score_input_prefers_large_message_box_over_a_search_field():
	composer = make(tag="textarea", placeholder="Message the AI", rect={"w": 300, "h": 60})
	search = make(tag="input", kind="text", placeholder="Search chats", rect={"w": 300, "h": 24})
	composer_score = score_input(composer)
	search_score = score_input(search)
	assert composer_score is not None and search_score is not None
	assert composer_score - search_score >= 2


def test_choose_input_refuses_to_guess_between_two_plausible_boxes():
	first = make(tag="textarea", placeholder="Message the AI", rect={"w": 300, "h": 60})
	second = make(tag="div", editable=True, placeholder="Your message", rect={"w": 300, "h": 60})
	assert choose_input([first, second]) is None
	assert choose_input([first]) is first


def test_choose_input_prefers_the_focused_element():
	composer = make(tag="textarea", placeholder="Message the AI", rect={"w": 300, "h": 60})
	other = make(tag="div", editable=True, rect={"w": 300, "h": 120})
	assert choose_input_from([composer, other], focused=composer) is composer
	assert choose_input_from([composer], focused=None) is composer


def test_copy_score_excludes_copy_link_and_rejects_copy_code():
	real = make(tag="button", aria="Copy", label="copy")
	link = make(tag="button", aria="Copy link", label="copy link")
	code = make(tag="button", aria="Copy code", label="copy code")
	assert copy_score(real) == 10
	assert copy_score(link) is None
	assert copy_score(code) is None  # copies a snippet, not the response


def test_an_icon_only_button_with_a_copy_class_is_a_weak_candidate():
	icon = make(tag="button", classes=["copy-icon"])
	assert copy_score(icon) == 2
	assert choose_copy([make(tag="button", aria="Copy", label="copy"), icon]) is not icon


def test_choose_copy_takes_the_last_button_when_scores_tie():
	earlier = make(tag="button", aria="Copy", label="copy")
	later = make(tag="button", aria="Copy", label="copy")
	assert choose_copy([earlier, later]) is later


def test_choose_copy_ignores_hidden_and_non_button_elements():
	hidden = make(tag="button", aria="Copy", label="copy", visible=False)
	text = make(tag="span", aria="Copy", label="copy")
	assert choose_copy([hidden, text]) is None
