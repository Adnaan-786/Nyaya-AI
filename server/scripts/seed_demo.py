"""Seed a demo firm with data a lawyer would recognise.

Run with:  ./.venv/bin/python -m scripts.seed_demo

The point of this script is that the demo is *legible*. Lorem-ipsum seed data makes
every screen look plausible and prove nothing; a reviewer cannot tell whether the
Today screen sorted correctly, whether the overdue badge fired, or whether the lakh
grouping is right. So the data here is deliberately shaped:

* hearings land yesterday, **today**, tomorrow and next month, so Today, the calendar
  and the "in 3 days" chip all have something true to show;
* invoices cover draft, sent, overdue and paid, so every status badge appears;
* one case has no CNR (added manually), because that is the escape hatch in D.5 and
  it should be visible in the demo that it works;
* amounts span thousands to lakhs, so `1,50,000` grouping is on screen rather than
  taken on trust.

Re-running wipes and recreates the demo tenant only. Other tenants are untouched.
"""

import asyncio
import datetime as dt
import logging
import uuid

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.db import SessionFactory, create_all
from app.core.india import INDIA, today_in_india
from app.models import (
    AiJob,
    Base,
    Case,
    CaseNote,
    Client,
    Document,
    Expense,
    Hearing,
    Invoice,
    Notification,
    Payment,
    Task,
    Tenant,
    TimeEntry,
    User,
)
from app.services import invoicing

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("seed")

DEMO_FIRM = "Iyer & Associates, Advocates"
LAWYER_PHONE = "+919876543210"
JUNIOR_PHONE = "+919876543211"
CLIENT_PHONE = "+919812345678"


def at(day: dt.date, hour: int = 10, minute: int = 0) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(hour, minute), tzinfo=INDIA)


async def wipe(session, tenant_id: uuid.UUID) -> None:
    """Delete the demo tenant's rows in FK-safe order.

    Explicit rather than relying on cascades so a re-run is predictable even if a
    future model forgets an `ondelete`.
    """
    for model in (
        Payment, Invoice, TimeEntry, Expense, Notification, Task, CaseNote,
        AiJob, Document, Hearing, Case, User, Client,
    ):
        await session.execute(delete(model).where(model.tenant_id == tenant_id))
    await session.execute(delete(Tenant).where(Tenant.id == tenant_id))
    await session.commit()


async def release_demo_phones(session) -> None:
    """`users.phone` is globally unique, so a leftover dev account on one of the demo
    numbers blocks the seed entirely.

    Those rows are cleared here — but loudly, naming the firm, because deleting a
    login is not something a script should do quietly. The environment guard in
    `seed()` is what keeps this from ever reaching real users.
    """
    holders = (
        await session.execute(
            select(User, Tenant.name)
            .join(Tenant, Tenant.id == User.tenant_id)
            .where(
                User.phone.in_([LAWYER_PHONE, JUNIOR_PHONE, CLIENT_PHONE]),
                Tenant.name != DEMO_FIRM,
            )
        )
    ).all()

    for user, firm in holders:
        logger.warning(
            "releasing %s from leftover firm %r (role=%s)", user.phone, firm, user.role
        )
        await session.delete(user)

    if holders:
        await session.commit()


async def seed() -> None:
    settings = get_settings()
    if settings.environment == "prod":
        # This script deletes rows. It exists for local and staging demos only.
        raise SystemExit("refusing to seed demo data into a prod environment")

    await create_all()
    today = today_in_india()

    async with SessionFactory() as session:
        existing = (
            await session.scalars(select(Tenant).where(Tenant.name == DEMO_FIRM))
        ).first()
        if existing:
            logger.info("resetting existing demo firm %s", existing.id)
            await wipe(session, existing.id)

        await release_demo_phones(session)

        tenant = Tenant(name=DEMO_FIRM, plan="firm")
        session.add(tenant)
        await session.flush()

        lawyer = User(
            tenant_id=tenant.id,
            name="Adv. Meera Iyer",
            phone=LAWYER_PHONE,
            email="meera@iyerassociates.in",
            role="firm_admin",
            language="en",
            bar_council_id="MAH/1234/2011",
        )
        junior = User(
            tenant_id=tenant.id,
            name="Adv. Rohit Deshpande",
            phone=JUNIOR_PHONE,
            role="lawyer",
            language="hi",
        )
        session.add_all([lawyer, junior])
        await session.flush()

        clients = [
            Client(
                tenant_id=tenant.id,
                name="Sharma Textiles Pvt Ltd",
                phone=CLIENT_PHONE,
                email="accounts@sharmatextiles.in",
                address="14, Nariman Point\nMumbai 400021\nMaharashtra",
                tags=["corporate", "retainer"],
                notes="GST registered. Prefers invoices under reverse charge.",
            ),
            Client(
                tenant_id=tenant.id,
                name="Kavita Rao",
                phone="+919820011223",
                address="Flat 7B, Hiranandani Gardens\nPowai, Mumbai 400076",
                tags=["individual", "matrimonial"],
            ),
            Client(
                tenant_id=tenant.id,
                name="Deccan Logistics LLP",
                phone="+919845566778",
                email="legal@deccanlogistics.co.in",
                address="Plot 22, MIDC Bhosari\nPune 411026",
                tags=["corporate"],
            ),
        ]
        session.add_all(clients)
        await session.flush()
        sharma, kavita, deccan = clients

        # Client-mode login for the portal demo (D.10). Same OTP flow, role=client.
        session.add(
            User(
                tenant_id=tenant.id,
                name=sharma.name,
                phone=CLIENT_PHONE,
                role="client",
                client_id=sharma.id,
            )
        )

        cases = [
            Case(
                tenant_id=tenant.id,
                cnr="MHMU010123452024",
                title="Sharma Textiles Pvt Ltd vs. Anil Traders",
                case_number="COMS/482/2024",
                court_name="Bombay High Court",
                court_type="High Court",
                judge_name="Hon'ble Justice S. R. Kulkarni",
                case_type="Commercial Suit",
                stage="Evidence",
                status="active",
                client_id=sharma.id,
                next_hearing_date=today,
                ecourts_synced=True,
                last_synced_at=dt.datetime.now(dt.UTC) - dt.timedelta(hours=2),
            ),
            Case(
                tenant_id=tenant.id,
                cnr="MHMU020456782025",
                title="Kavita Rao vs. Suresh Rao",
                case_number="MJ/311/2025",
                court_name="Family Court, Bandra",
                court_type="District Court",
                judge_name="Hon'ble Judge P. M. Nadkarni",
                case_type="Matrimonial Petition",
                stage="Mediation",
                status="active",
                client_id=kavita.id,
                next_hearing_date=today + dt.timedelta(days=3),
                ecourts_synced=True,
                last_synced_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=1),
            ),
            Case(
                tenant_id=tenant.id,
                cnr="MHPU030998872025",
                title="Deccan Logistics LLP vs. State of Maharashtra",
                case_number="WP/7712/2025",
                court_name="Bombay High Court, Bench at Aurangabad",
                court_type="High Court",
                case_type="Writ Petition",
                stage="Admission",
                status="active",
                client_id=deccan.id,
                next_hearing_date=today + dt.timedelta(days=28),
                ecourts_synced=True,
            ),
            # No CNR: added by hand. D.5's escape hatch for when eCourts has nothing,
            # and worth seeing in the demo because it is the realistic case for
            # tribunal and arbitration matters.
            Case(
                tenant_id=tenant.id,
                title="Sharma Textiles — GST appeal (Appellate Authority)",
                case_number="GST-APP/119/2026",
                court_name="Office of the Commissioner (Appeals), Mumbai",
                court_type="Tribunal",
                case_type="Tax Appeal",
                stage="Filed",
                status="active",
                client_id=sharma.id,
                next_hearing_date=today + dt.timedelta(days=11),
            ),
            Case(
                tenant_id=tenant.id,
                cnr="MHMU040112232023",
                title="Sharma Textiles Pvt Ltd vs. Mehta Fabrics",
                case_number="COMS/88/2023",
                court_name="Bombay High Court",
                case_type="Commercial Suit",
                stage="Disposed",
                status="disposed",
                client_id=sharma.id,
                ecourts_synced=True,
            ),
        ]
        session.add_all(cases)
        await session.flush()
        commercial, matrimonial, writ, gst_appeal, disposed = cases

        session.add_all(
            [
                # Yesterday, today, tomorrow, and further out — so Today, the
                # calendar and the relative-date chip each have real content.
                Hearing(
                    tenant_id=tenant.id, case_id=commercial.id,
                    date=today - dt.timedelta(days=21), time=dt.time(11, 0),
                    purpose="Framing of issues", courtroom="Court Room 12",
                    outcome_notes="Issues framed. Matter posted for evidence.",
                    source="ecourts",
                ),
                Hearing(
                    tenant_id=tenant.id, case_id=commercial.id,
                    date=today, time=dt.time(10, 30),
                    purpose="Evidence — PW1 examination", courtroom="Court Room 12",
                    source="ecourts",
                ),
                Hearing(
                    tenant_id=tenant.id, case_id=matrimonial.id,
                    date=today + dt.timedelta(days=3), time=dt.time(14, 0),
                    purpose="Mediation session", courtroom="Mediation Centre",
                    source="ecourts",
                ),
                Hearing(
                    tenant_id=tenant.id, case_id=gst_appeal.id,
                    date=today + dt.timedelta(days=11), time=dt.time(11, 30),
                    purpose="Personal hearing", source="manual",
                ),
                Hearing(
                    tenant_id=tenant.id, case_id=writ.id,
                    date=today + dt.timedelta(days=28),
                    purpose="Admission", source="ecourts",
                ),
                Hearing(
                    tenant_id=tenant.id, case_id=disposed.id,
                    date=today - dt.timedelta(days=90), time=dt.time(10, 0),
                    purpose="Final arguments",
                    outcome_notes="Suit decreed in favour of the plaintiff with costs.",
                    source="ecourts",
                ),
            ]
        )

        session.add_all(
            [
                CaseNote(
                    tenant_id=tenant.id, case_id=commercial.id, author_id=lawyer.id,
                    body=(
                        "PW1 to be examined on the invoices at Exh. 24-31. Anil Traders' "
                        "counsel has signalled they will dispute the delivery challans — "
                        "keep the courier receipts ready for re-examination."
                    ),
                ),
                CaseNote(
                    tenant_id=tenant.id, case_id=matrimonial.id, author_id=lawyer.id,
                    body=(
                        "Client open to settlement if interim maintenance is agreed "
                        "at Rs 35,000/month."
                    ),
                ),
            ]
        )

        session.add_all(
            [
                Task(
                    tenant_id=tenant.id, case_id=commercial.id,
                    title="Prepare PW1 examination-in-chief",
                    assignee_id=lawyer.id, created_by=lawyer.id,
                    due_date=today, status="open",
                ),
                Task(
                    tenant_id=tenant.id, case_id=gst_appeal.id,
                    title="File reply to show-cause notice",
                    assignee_id=junior.id, created_by=lawyer.id,
                    # Overdue on purpose: the overdue styling should be visible.
                    due_date=today - dt.timedelta(days=2), status="open",
                ),
                Task(
                    tenant_id=tenant.id, case_id=matrimonial.id,
                    title="Draft settlement terms for mediation",
                    assignee_id=lawyer.id, created_by=lawyer.id,
                    due_date=today + dt.timedelta(days=2), status="open",
                ),
                Task(
                    tenant_id=tenant.id, case_id=commercial.id,
                    title="Collect courier receipts from client",
                    assignee_id=junior.id, created_by=lawyer.id,
                    due_date=today - dt.timedelta(days=5), status="done",
                ),
            ]
        )

        session.add_all(
            [
                Document(
                    tenant_id=tenant.id, case_id=commercial.id, client_id=sharma.id,
                    name="Plaint — COMS 482 of 2024.pdf", folder="Pleadings",
                    mime_type="application/pdf", size_bytes=482_113,
                    storage_key=f"{tenant.id}/seed/plaint.pdf",
                    ocr_status="done", confirmed=True, uploaded_by=lawyer.id,
                    ocr_text=(
                        "IN THE HIGH COURT OF JUDICATURE AT BOMBAY\n"
                        "COMMERCIAL SUIT NO. 482 OF 2024\n"
                        "Sharma Textiles Pvt Ltd ... Plaintiff\n"
                        "versus\nAnil Traders ... Defendant\n"
                        "The plaintiff states that goods were supplied against invoices "
                        "dated 12.03.2024 and 04.04.2024 and remain unpaid."
                    ),
                ),
                Document(
                    tenant_id=tenant.id, case_id=commercial.id, client_id=sharma.id,
                    name="Delivery challans (bundle).pdf", folder="Evidence",
                    mime_type="application/pdf", size_bytes=1_204_887,
                    storage_key=f"{tenant.id}/seed/challans.pdf",
                    # A scan with no text layer: OCR honestly reports it needs a
                    # provider rather than pretending to have read it.
                    ocr_status="failed", confirmed=True, uploaded_by=junior.id,
                ),
                Document(
                    tenant_id=tenant.id, case_id=matrimonial.id, client_id=kavita.id,
                    name="Petition — MJ 311 of 2025.pdf", folder="Pleadings",
                    mime_type="application/pdf", size_bytes=311_902,
                    storage_key=f"{tenant.id}/seed/petition.pdf",
                    ocr_status="done", confirmed=True, uploaded_by=lawyer.id,
                    ocr_text=(
                        "IN THE FAMILY COURT AT BANDRA, MUMBAI\n"
                        "PETITION NO. 311 OF 2025 under Section 13(1)(ia) of the "
                        "Hindu Marriage Act, 1955."
                    ),
                ),
                Document(
                    tenant_id=tenant.id, case_id=gst_appeal.id, client_id=sharma.id,
                    name="Show cause notice.pdf", folder="Correspondence",
                    mime_type="application/pdf", size_bytes=98_441,
                    storage_key=f"{tenant.id}/seed/scn.pdf",
                    ocr_status="pending", confirmed=True, uploaded_by=junior.id,
                ),
            ]
        )

        session.add_all(
            [
                TimeEntry(
                    tenant_id=tenant.id, case_id=commercial.id, user_id=lawyer.id,
                    started_at=at(today - dt.timedelta(days=2), 15, 0),
                    duration_seconds=5400, description="Conference with client on evidence",
                    billable=True, rate_paise=1_500_00,
                ),
                TimeEntry(
                    tenant_id=tenant.id, case_id=commercial.id, user_id=junior.id,
                    started_at=at(today - dt.timedelta(days=1), 11, 0),
                    duration_seconds=10800, description="Drafting examination-in-chief",
                    billable=True, rate_paise=800_00,
                ),
                TimeEntry(
                    tenant_id=tenant.id, case_id=matrimonial.id, user_id=lawyer.id,
                    started_at=at(today - dt.timedelta(days=4), 16, 30),
                    duration_seconds=3600, description="Internal case review",
                    billable=False,
                ),
            ]
        )

        session.add_all(
            [
                Expense(
                    tenant_id=tenant.id, case_id=commercial.id,
                    description="Court fee — commercial suit", amount_paise=12_500_00,
                    category="Court fee", incurred_on=today - dt.timedelta(days=30),
                ),
                Expense(
                    tenant_id=tenant.id, case_id=matrimonial.id,
                    description="Process fee and typing charges", amount_paise=1_850_00,
                    category="Miscellaneous", incurred_on=today - dt.timedelta(days=12),
                ),
            ]
        )

        session.add(
            AiJob(
                tenant_id=tenant.id, user_id=lawyer.id, type="summarize", status="done",
                input={"doc_type_hint": "plaint"},
                estimated_seconds=45,
                completed_at=dt.datetime.now(dt.UTC) - dt.timedelta(hours=5),
                result={
                    "summary_markdown": (
                        "**Commercial Suit 482 of 2024** — Sharma Textiles seeks recovery "
                        "of Rs 41,20,000 against Anil Traders for goods supplied under two "
                        "invoices in March and April 2024. The defence disputes delivery. "
                        "The matter is at the evidence stage with PW1 yet to be examined."
                    ),
                    "key_points": [
                        "Two invoices dated 12.03.2024 and 04.04.2024 remain unpaid",
                        "Delivery is disputed; challans are the contested documents",
                        "Interest claimed at 18% per annum from the date of each invoice",
                    ],
                    "parties": ["Sharma Textiles Pvt Ltd", "Anil Traders"],
                    "sections_invoked": ["Section 34, CPC", "Order VII Rule 1, CPC"],
                    "dates": ["2024-03-12", "2024-04-04"],
                    "doc_type_detected": "plaint",
                },
            )
        )

        await _seed_invoices(session, tenant, sharma, kavita, commercial, matrimonial, today)

        session.add_all(
            [
                Notification(
                    tenant_id=tenant.id, user_id=lawyer.id, type="hearing_reminder",
                    title="Hearing today — 10:30 AM",
                    body="Sharma Textiles vs. Anil Traders, Court Room 12, Bombay High Court",
                    deep_link=f"nyayaai://case/{commercial.id}",
                    payload={"case_id": str(commercial.id), "date": today.isoformat()},
                ),
                Notification(
                    tenant_id=tenant.id, user_id=lawyer.id, type="task_due",
                    title="Task overdue",
                    body="File reply to show-cause notice was due 2 days ago",
                    deep_link="nyayaai://today",
                    read_at=dt.datetime.now(dt.UTC) - dt.timedelta(hours=1),
                ),
            ]
        )

        await session.commit()

    logger.info("")
    logger.info("Demo firm ready: %s", DEMO_FIRM)
    logger.info("  lawyer login : %s   (OTP 123456 in FAKE_MODE)", LAWYER_PHONE)
    logger.info("  junior login : %s   (Hindi UI)", JUNIOR_PHONE)
    logger.info("  client login : %s   (client mode / portal)", CLIENT_PHONE)
    logger.info("  %d cases, hearings incl. one today, 4 invoice states", len(cases))


async def _seed_invoices(session, tenant, sharma, kavita, commercial, matrimonial, today):
    """One invoice per status, so every badge in D.9 appears in the demo."""
    def item(description: str, rate_rupees: int, quantity: int = 1) -> dict:
        return {
            "description": description,
            "quantity": quantity,
            "rate_paise": rate_rupees * 100,
        }

    specs = [
        (
            "draft", sharma, commercial,
            [item("Professional fees — evidence stage", 7_500)],
            False, today + dt.timedelta(days=15),
        ),
        (
            "sent", sharma, commercial,
            [
                item("Drafting of plaint and annexures", 45_000),
                item("Appearance before Bombay High Court", 15_000, quantity=4),
            ],
            # Sharma is a business entity: reverse charge applies (see the module
            # docstring in app/services/invoicing.py).
            True, today + dt.timedelta(days=10),
        ),
        (
            "overdue", kavita, matrimonial,
            [item("Professional fees — matrimonial petition", 60_000)],
            # An individual, not a business: normal 18% GST.
            False, today - dt.timedelta(days=6),
        ),
        (
            "paid", sharma, None,
            # A lakh-scale amount, so the Indian digit grouping is on screen.
            [item("Retainer — quarter ending March 2026", 1_50_000)],
            True, today - dt.timedelta(days=20),
        ),
    ]

    for status, client, case, items, reverse_charge, due in specs:
        subtotal, gst, total = invoicing.compute_totals(items, 18, reverse_charge)
        invoice = Invoice(
            tenant_id=tenant.id,
            client_id=client.id,
            case_id=case.id if case else None,
            number=await invoicing.next_invoice_number(session, tenant.id, today),
            line_items=items,
            subtotal_paise=subtotal,
            gst_rate=18,
            gst_paise=gst,
            total_paise=total,
            status=status,
            due_date=due,
            payment_link=None if status == "draft" else "https://rzp.io/i/demoLink01",
        )
        session.add(invoice)
        await session.flush()

        if status == "paid":
            session.add(
                Payment(
                    tenant_id=tenant.id,
                    invoice_id=invoice.id,
                    razorpay_order_id=f"order_demo{uuid.uuid4().hex[:12]}",
                    razorpay_payment_id=f"pay_demo{uuid.uuid4().hex[:12]}",
                    amount_paise=total,
                    status="captured",
                    verified_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=18),
                )
            )


if __name__ == "__main__":
    assert Base is not None  # keeps the metadata import honest
    asyncio.run(seed())
