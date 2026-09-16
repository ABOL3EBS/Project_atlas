from app.ingestion.cleaning import clean_text, split_paragraphs


def test_clean_text_collapses_whitespace():
    assert clean_text("a  b \t c") == "a b c"


def test_clean_text_normalizes_newlines():
    assert clean_text("a\r\nb\rc") == "a\nb\nc"


def test_clean_text_strips_control_characters():
    assert clean_text("a\x00b") == "ab"


def test_clean_text_limits_blank_lines():
    assert clean_text("a\n\n\n\nb") == "a\n\nb"


def test_split_paragraphs_drops_empty():
    paragraphs = split_paragraphs("one\n\n\n\ntwo")
    assert paragraphs == ["one", "two"]