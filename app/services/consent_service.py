"""
DPDP consent (plan C.12.3): versioned notice text, an auditable
record of who accepted which version (with a hash of the exact text
shown), and the lookup the API-wide consent gate uses.

IMPORTANT: the notice below is a working draft written to make the
flow testable end to end. It must be reviewed by counsel / your Data
Protection Officer before launch, and `CURRENT_VERSION` bumped whenever
the wording changes -- that is what forces every user to re-consent.
"""

import hashlib
import time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ValidationException
from app.core.security import utcnow
from app.models.consent import Consent

CURRENT_VERSION = "2026-10-v1"

_NOTICE = {
    "en": (
        "NyayaAI Privacy Notice (Digital Personal Data Protection Act, 2023)\n\n"
        "We process: your name, phone number, firm and role; the client, case, hearing, "
        "document, billing and task information you or your colleagues enter; and records "
        "of your activity in the app.\n\n"
        "Why: to run your practice-management account, sync court data, process documents "
        "and run AI assistance you request, send reminders, and bill and secure the service.\n\n"
        "Who processes it for us: cloud hosting in India (AWS), SMS and WhatsApp providers, "
        "Firebase (push notifications), Razorpay (payments), Google Document AI (OCR) and an "
        "AI model provider under a no-retention agreement. Your documents are never used to "
        "train AI models.\n\n"
        "Your rights: access and export your data, correct it, withdraw consent, and request "
        "erasure (a 30-day cancellation window applies; data we must keep for legal or "
        "litigation reasons is retained). Contact our grievance officer: {contact}.\n\n"
        "By continuing you consent to this processing."
    ),
    "hi": (
        "NyayaAI Gopniyata Suchna (Digital Personal Data Protection Act, 2023)\n\n"
        "Hum aapka naam, phone number, firm aur role; aur aap ya aapke sahkarmi jo client, case, "
        "peshi, document, billing aur task ki jaankari daalte hain, saath hi app mein aapki "
        "gatividhi ka record process karte hain.\n\n"
        "Kyon: aapka practice-management account chalane, court data sync karne, document aur "
        "aapke manga hua AI sahayata process karne, reminder bhejne, aur seva ko surakshit "
        "rakhne ke liye.\n\n"
        "Hamare liye kaun process karta hai: India mein cloud hosting (AWS), SMS/WhatsApp "
        "providers, Firebase, Razorpay, Google Document AI aur ek AI model provider "
        "(no-retention samjhaute ke tahat). Aapke documents se AI model train nahi kiye jaate.\n\n"
        "Aapke adhikar: apna data dekhna aur export karna, sudhaar, sahmati vapas lena, aur "
        "mitane ka anurodh (30 din ki radd karne ki avadhi). Kanooni ya mukadme ke karan "
        "rakhna zaroori data rakha jaayega. Shikayat adhikari: {contact}.\n\n"
        "Jaari rakhkar aap is processing ke liye sahmati dete hain."
    ),
}


def get_consent_text(language: str = "en") -> dict:
    lang = language if language in _NOTICE else "en"
    body = _NOTICE[lang].format(contact=get_settings().app_support_email)
    return {
        "version": CURRENT_VERSION,
        "language": lang,
        "text": body,
        "text_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }


# Positive-only, short-lived cache so the gate doesn't add a query to
# every request. Consent can only be *added* (never removed) in this
# flow, so a stale "yes" can't wrongly grant access beyond its TTL.
_CACHE_TTL_SECONDS = 300
_consented_until: dict[UUID, float] = {}


def clear_cache() -> None:
    _consented_until.clear()


async def has_current_consent(session: AsyncSession, user_id: UUID) -> bool:
    now = time.monotonic()
    if _consented_until.get(user_id, 0) > now:
        return True

    found = (
        await session.execute(
            select(Consent.id).where(Consent.user_id == user_id).where(Consent.version == CURRENT_VERSION)
        )
    ).first()
    if found is None:
        return False

    _consented_until[user_id] = now + _CACHE_TTL_SECONDS
    return True


async def record_consent(
    session: AsyncSession, user_id: UUID, *, version: str, language: str = "en"
) -> Consent:
    if version != CURRENT_VERSION:
        raise ValidationException(
            "Consent version is out of date; fetch the latest text first.",
            details={"current_version": CURRENT_VERSION},
        )

    existing = (
        await session.execute(
            select(Consent).where(Consent.user_id == user_id).where(Consent.version == version)
        )
    ).scalars().first()
    if existing is not None:
        return existing

    consent = Consent(
        user_id=user_id,
        version=version,
        granted_at=utcnow(),
        text_hash=get_consent_text(language)["text_hash"],
    )
    session.add(consent)
    await session.commit()
    await session.refresh(consent)
    _consented_until[user_id] = time.monotonic() + _CACHE_TTL_SECONDS
    return consent
