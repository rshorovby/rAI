from analytics import (
    EVENT_FEEDBACK_CLEAR,
    EVENT_FEEDBACK_NEGATIVE,
    EVENT_FEEDBACK_POSITIVE,
)
from bot import _FEEDBACK_EVENTS, _feedback_keyboard, _split_message


def test_short_text_single_chunk():
    assert _split_message("привет") == ["привет"]


def test_long_text_is_split():
    text = "\n".join(f"строка {i}" for i in range(2000))
    chunks = _split_message(text, limit=1000)
    assert len(chunks) > 1
    assert all(len(c) <= 1000 for c in chunks)


def test_split_preserves_all_lines():
    text = "\n".join(f"line{i}" for i in range(500))
    chunks = _split_message(text, limit=500)
    rejoined = "\n".join(chunks)
    for i in range(500):
        assert f"line{i}" in rejoined


def test_feedback_keyboard_has_three_buttons():
    markup = _feedback_keyboard("ru")
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    assert len(buttons) == 3
    assert {btn.callback_data for btn in buttons} == {"fb:pos", "fb:neg", "fb:clear"}


def test_feedback_events_mapping():
    assert _FEEDBACK_EVENTS["pos"] == EVENT_FEEDBACK_POSITIVE
    assert _FEEDBACK_EVENTS["neg"] == EVENT_FEEDBACK_NEGATIVE
    assert _FEEDBACK_EVENTS["clear"] == EVENT_FEEDBACK_CLEAR
