"""
Invoice PDF rendering via reportlab (plan C.11.2). Plain drawing calls
instead of an HTML-template + WeasyPrint pipeline, to avoid WeasyPrint's
Cairo/Pango system dependencies in the Docker image.

Not yet included (design decisions, not credential blockers): the UPI
QR code (needs a `qrcode` dependency and the firm's UPI VPA) and the
firm logo (needs somewhere to store/upload it).
"""

import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _rupees(paise: int) -> str:
    return f"Rs. {paise / 100:,.2f}"


def render_invoice_pdf(
    *,
    invoice_number: str,
    firm_name: str,
    firm_gstin: str | None,
    client_name: str,
    client_address: str | None,
    line_items: list[dict],
    subtotal_paise: int,
    gst_rate: int,
    gst_paise: int,
    total_paise: int,
    due_date: str | None,
    status: str,
) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, y, firm_name)
    if firm_gstin:
        y -= 6 * mm
        c.setFont("Helvetica", 9)
        c.drawString(20 * mm, y, f"GSTIN: {firm_gstin}")

    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(width - 20 * mm, height - 25 * mm, "TAX INVOICE")
    c.setFont("Helvetica", 10)
    c.drawRightString(width - 20 * mm, height - 32 * mm, invoice_number)
    if due_date:
        c.drawRightString(width - 20 * mm, height - 38 * mm, f"Due: {due_date}")
    c.drawRightString(width - 20 * mm, height - 44 * mm, f"Status: {status.upper()}")

    y = height - 55 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "Bill to:")
    c.setFont("Helvetica", 10)
    y -= 5 * mm
    c.drawString(20 * mm, y, client_name)
    for line in (client_address or "").splitlines():
        y -= 5 * mm
        c.drawString(20 * mm, y, line)

    y -= 12 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20 * mm, y, "Description")
    c.drawRightString(130 * mm, y, "Qty")
    c.drawRightString(160 * mm, y, "Rate")
    c.drawRightString(190 * mm, y, "Amount")
    y -= 2 * mm
    c.line(20 * mm, y, 190 * mm, y)

    c.setFont("Helvetica", 9)
    for item in line_items:
        y -= 6 * mm
        c.drawString(20 * mm, y, str(item["description"])[:60])
        c.drawRightString(130 * mm, y, str(item["qty"]))
        c.drawRightString(160 * mm, y, _rupees(item["rate_paise"]))
        c.drawRightString(190 * mm, y, _rupees(item["amount_paise"]))

    y -= 4 * mm
    c.line(20 * mm, y, 190 * mm, y)
    c.setFont("Helvetica", 10)
    y -= 8 * mm
    c.drawRightString(160 * mm, y, "Subtotal")
    c.drawRightString(190 * mm, y, _rupees(subtotal_paise))
    y -= 6 * mm
    c.drawRightString(160 * mm, y, f"GST ({gst_rate}%)")
    c.drawRightString(190 * mm, y, _rupees(gst_paise))
    y -= 7 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(160 * mm, y, "Total")
    c.drawRightString(190 * mm, y, _rupees(total_paise))

    c.showPage()
    c.save()
    return buffer.getvalue()
