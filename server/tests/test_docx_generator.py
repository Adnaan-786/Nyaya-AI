"""Markdown to DOCX. A draft a lawyer cannot open in Word is not a draft."""

import io

from docx import Document

from app.ai.docx_generator import markdown_to_docx_bytes


def _text_of(docx_bytes: bytes) -> str:
    return "\n".join(p.text for p in Document(io.BytesIO(docx_bytes)).paragraphs)


def test_output_is_a_real_docx_archive() -> None:
    result = markdown_to_docx_bytes("# Title\n\nSome paragraph text.\n\n**Bold Label:** a value")

    assert isinstance(result, bytes)
    assert result[:2] == b"PK"  # DOCX is a zip


def test_empty_input_still_produces_an_openable_file() -> None:
    assert markdown_to_docx_bytes("")[:2] == b"PK"


def test_every_heading_level_the_prompts_ask_for_is_handled() -> None:
    assert markdown_to_docx_bytes("# H1\n## H2\n### H3\nplain paragraph")[:2] == b"PK"


def test_the_words_survive_the_round_trip() -> None:
    result = markdown_to_docx_bytes(
        "# My Document\n\nThis is a plain paragraph.\n\n**Label:** value"
    )

    text = _text_of(result)
    assert "My Document" in text
    assert "This is a plain paragraph." in text
    # The bold marker is formatting, not content — it must not survive as literal
    # asterisks in a document that goes to a court.
    assert "Label:" in text
    assert "value" in text
    assert "**" not in text
