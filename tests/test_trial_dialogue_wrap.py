import pytest
from blessed import Terminal

from arlq import i18n, stage5


@pytest.mark.parametrize("language", ["en", "ja"])
def test_translated_trial_lines_fit_terminal_and_keep_explicit_breaks(language):
    measure = Terminal(force_styling=False).length
    previous = i18n.get_language()
    try:
        i18n.set_language(language)
        for source in stage5.TRIAL_MEMBER_LINES.values():
            text = i18n.t(source)
            assert "\n" in text
            for on_left in (False, True):
                lines = stage5.trial_dialogue_lines(text, 30, on_left=on_left, measure=measure)
                assert len(lines) == text.count("\n") + 1
                assert all(measure(line) <= 30 for line in lines)
                assert "".join(line[2:] if not on_left else line[:-2] for line in lines) == text.replace("\n", "")
    finally:
        i18n.set_language(previous)


def test_missing_translation_wraps_words_and_long_unspaced_text():
    measure = Terminal(force_styling=False).length
    text = "Words should wrap naturally extraordinarilylongword 日本語の長い文章"
    lines = stage5.trial_dialogue_lines(text, 12, measure=measure)
    assert all(measure(line) <= 12 for line in lines)
    assert "".join(line[2:] for line in lines).replace(" ", "") == text.replace(" ", "")


def test_explicit_break_is_preserved():
    assert stage5.trial_dialogue_lines("Hello\nworld", 30) == ["/ Hello", "\\ world"]
