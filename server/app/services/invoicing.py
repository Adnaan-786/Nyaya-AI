"""Invoice totals, numbering, and PDF rendering.

Two rules here are specific to Indian legal practice and are the difference between
an invoice a lawyer can actually issue and a generic one they'd have to redo:

**Reverse charge.** Legal services supplied by an advocate to a business entity are
taxed under the GST reverse charge mechanism — the *recipient* pays the GST, and the
advocate's invoice carries none but must say so. An invoice that silently adds 18%
to such a supply is wrong, and the client's accounts team will bounce it.

**Sequential numbering per financial year.** GST rules require invoice numbers to be
unique and consecutive within a financial year, and India's runs April–March, not
January–December. `NY/2026-27/0001` restarts at 0001 each April.
"""

import datetime as dt
import io
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.india import to_india
from app.models import Client, Invoice, Tenant

# India's financial year starts in April.
FY_START_MONTH = 4

# The same Noto Sans Devanagari the app bundles. fpdf2's built-in fonts are latin-1,
# which cannot encode the rupee sign at all and *raises* on a client named in Hindi —
# and "Sharma Textiles" is only one kind of client this product has. One embedded font
# covering Latin, Devanagari and U+20B9 avoids both problems.
FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
BODY_FONT = "NotoSans"
RUPEE = "\u20b9"


def financial_year(on: dt.date) -> str:
    """2026-07-27 -> '2026-27'; 2026-02-11 -> '2025-26'."""
    start = on.year if on.month >= FY_START_MONTH else on.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


async def next_invoice_number(session: AsyncSession, tenant_id, on: dt.date) -> str:
    """Sequential within the tenant and financial year.

    Counting existing invoices for the year is safe here because invoice creation is
    a single transaction per request; a high-concurrency firm would want a dedicated
    sequence row to avoid two invoices racing to the same number.
    """
    fy = financial_year(on)
    prefix = f"NY/{fy}/"

    used = await session.scalar(
        select(func.count())
        .select_from(Invoice)
        .where(Invoice.tenant_id == tenant_id, Invoice.number.startswith(prefix))
    )
    return f"{prefix}{(used or 0) + 1:04d}"


def compute_totals(
    line_items: list[dict], gst_rate: int, reverse_charge: bool
) -> tuple[int, int, int]:
    """Returns (subtotal_paise, gst_paise, total_paise), all integers.

    Rounding is half-up on the paise, done once on the whole subtotal rather than
    per line — rounding each line separately drifts by a rupee or two on a long
    invoice and makes the total disagree with a hand check.
    """
    subtotal = sum(int(item["quantity"]) * int(item["rate_paise"]) for item in line_items)

    if reverse_charge or gst_rate == 0:
        return subtotal, 0, subtotal

    gst = (subtotal * gst_rate + 50) // 100
    return subtotal, gst, subtotal + gst


def format_paise(paise: int) -> str:
    """Indian digit grouping: 15000000 paise -> '1,50,000.00' (lakh), not '150,000.00'.

    Mirrors `Paise.formatRupees()` in the Android client — the two must agree, or an
    invoice PDF and the app screen showing it will print different-looking amounts.
    """
    negative = paise < 0
    rupees, remainder = divmod(abs(paise), 100)
    digits = str(rupees)

    if len(digits) > 3:
        last_three = digits[-3:]
        rest = digits[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        grouped = ",".join(groups) + "," + last_three
    else:
        grouped = digits

    return f"{'-' if negative else ''}{grouped}.{remainder:02d}"


async def render_pdf(session: AsyncSession, invoice: Invoice) -> bytes:
    """A GST-shaped tax invoice, not a generic receipt."""
    from fpdf import FPDF

    tenant = await session.get(Tenant, invoice.tenant_id)
    client = await session.get(Client, invoice.client_id)
    reverse_charge = invoice.gst_paise == 0 and invoice.gst_rate > 0

    pdf = FPDF(unit="mm", format="A4")
    pdf.add_font(BODY_FONT, "", FONT_DIR / "NotoSansDevanagari-Regular.ttf")
    pdf.add_font(BODY_FONT, "B", FONT_DIR / "NotoSansDevanagari-SemiBold.ttf")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    pdf.set_font(BODY_FONT, "B", 16)
    pdf.cell(0, 10, "TAX INVOICE", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font(BODY_FONT, "B", 12)
    pdf.cell(0, 7, tenant.name if tenant else "", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font(BODY_FONT, "", 10)
    pdf.cell(95, 6, f"Invoice No: {invoice.number}")
    invoice_date = to_india(invoice.created_at).date()
    pdf.cell(0, 6, f"Date: {invoice_date.isoformat()}", new_x="LMARGIN", new_y="NEXT")
    if invoice.due_date:
        pdf.cell(95, 6, "")
        pdf.cell(0, 6, f"Due: {invoice.due_date.isoformat()}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_font(BODY_FONT, "B", 10)
    pdf.cell(0, 6, "Billed to", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(BODY_FONT, "", 10)
    pdf.cell(0, 6, client.name if client else "", new_x="LMARGIN", new_y="NEXT")
    if client and client.address:
        pdf.multi_cell(120, 5, client.address)
    pdf.ln(4)

    pdf.set_font(BODY_FONT, "B", 10)
    pdf.cell(95, 8, "Description", border="B")
    pdf.cell(20, 8, "Qty", border="B", align="R")
    pdf.cell(30, 8, "Rate", border="B", align="R")
    pdf.cell(30, 8, "Amount", border="B", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font(BODY_FONT, "", 10)
    for item in invoice.line_items:
        amount = int(item["quantity"]) * int(item["rate_paise"])
        pdf.cell(95, 7, str(item["description"])[:60])
        pdf.cell(20, 7, str(item["quantity"]), align="R")
        pdf.cell(30, 7, format_paise(int(item["rate_paise"])), align="R")
        pdf.cell(30, 7, format_paise(amount), align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)
    pdf.cell(115, 7, "")
    pdf.cell(30, 7, "Subtotal", align="R")
    pdf.cell(30, 7, format_paise(invoice.subtotal_paise), align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.cell(115, 7, "")
    pdf.cell(30, 7, f"GST @ {invoice.gst_rate}%", align="R")
    pdf.cell(30, 7, format_paise(invoice.gst_paise), align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font(BODY_FONT, "B", 11)
    pdf.cell(115, 9, "")
    pdf.cell(30, 9, "Total", border="T", align="R")
    pdf.cell(
        30,
        9,
        f"{RUPEE} {format_paise(invoice.total_paise)}",
        border="T",
        align="R",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    if reverse_charge:
        pdf.ln(4)
        pdf.set_font(BODY_FONT, "", 9)
        pdf.multi_cell(
            0,
            5,
            "GST payable by the recipient under reverse charge mechanism "
            "(Notification No. 13/2017-Central Tax (Rate)). No GST charged on this invoice.",
        )

    pdf.ln(6)
    pdf.set_font(BODY_FONT, "", 8)
    pdf.multi_cell(0, 4, "Generated by NyayaAI. This is a computer-generated invoice.")

    buffer = io.BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()
