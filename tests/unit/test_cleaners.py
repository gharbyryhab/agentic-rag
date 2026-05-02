from src.ingestion.cleaners import clean_text


def test_clean_text_collapses_whitespace():
    assert clean_text("hello    world") == "hello world"


def test_clean_text_caps_newlines():
    assert clean_text("a\n\n\n\n\nb") == "a\n\nb"


def test_clean_text_handles_empty():
    assert clean_text("") == ""
    assert clean_text("   ") == ""
