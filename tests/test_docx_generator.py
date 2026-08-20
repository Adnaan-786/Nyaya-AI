from app.ai.docx_generator import markdown_to_docx_bytes


def test_markdown_to_docx_produces_valid_docx_bytes():
    md = "# Title\n\nSome paragraph text.\n\n**Bold Label:** a value"
    result = markdown_to_docx_bytes(md)

    assert isinstance(result, bytes)
    assert result[:2] == b"PK"  # DOCX is a zip archive


def test_markdown_to_docx_handles_empty_input():
    result = markdown_to_docx_bytes("")
    assert result[:2] == b"PK"


def test_markdown_to_docx_handles_headings_at_multiple_levels():
    md = "# H1\n## H2\n### H3\nplain paragraph"
    result = markdown_to_docx_bytes(md)
    assert result[:2] == b"PK"


def test_markdown_to_docx_extracts_readable_text():
    from docx import Document
    import io

    md = "# My Document\n\nThis is a plain paragraph.\n\n**Label:** value"
    result = markdown_to_docx_bytes(md)

    document = Document(io.BytesIO(result))
    all_text = "\n".join(p.text for p in document.paragraphs)

    assert "My Document" in all_text
    assert "This is a plain paragraph." in all_text
    assert "Label:" in all_text
    assert "value" in all_text
