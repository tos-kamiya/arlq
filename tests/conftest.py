import pytest

from arlq import i18n


@pytest.fixture(autouse=True)
def english_messages():
    """Run every test in English and restore the language afterwards, so a
    test that sets the language from the environment (such as LANG=ja_JP)
    cannot change the messages later tests see."""
    previous_language = i18n.get_language()
    i18n.set_language("en")
    yield
    i18n.set_language(previous_language)
