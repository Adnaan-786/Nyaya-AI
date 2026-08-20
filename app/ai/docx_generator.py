"""
Minimal markdown -> DOCX renderer for draftsman output.

Deliberately simple: handles the subset of markdown the draft prompts
(app/ai/prompts.py) actually ask the LLM to produce -- `#`/`##`
headings, `**bold**` inline spans, and plain paragraphs. This is not a
general-purpose markdown renderer; it doesn't need to be, since we
control both ends of this pipeline (the prompt and the parser).
"""

import io
import re

from docx import Document

_BOLD_SPAN_RE = re.compile(r"\*\*(.+?)\*\*")


def _add_paragraph_with_inline_bold(document: Document, line: str) -> None:
    paragraph = document.add_paragraph()
    pos = 0
    for match in _BOLD_SPAN_RE.finditer(line):
        if match.start() > pos:
            paragraph.add_run(line[pos : match.start()])
        bold_run = paragraph.add_run(match.group(1))
        bold_run.bold = True
        pos = match.end()
    if pos < len(line):
        paragraph.add_run(line[pos:])


def markdown_to_docx_bytes(markdown_text: str) -> bytes:
    document = Document()

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()

        if not line:
            continue

        if line.startswith("### "):
            document.add_heading(line[4:].strip(), level=3)
        elif line.startswith("## "):
            document.add_heading(line[3:].strip(), level=2)
        elif line.startswith("# "):
            document.add_heading(line[2:].strip(), level=1)
        else:
            _add_paragraph_with_inline_bold(document, line)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
