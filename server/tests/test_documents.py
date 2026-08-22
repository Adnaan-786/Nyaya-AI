"""B.9 upload flow, OCR, and the security around signed URLs."""

import time
import uuid

import pytest
from httpx import AsyncClient

from app.integrations import storage
from tests.conftest import BASE, sign_in

pytestmark = pytest.mark.asyncio


def _pdf(lines: list[str]) -> bytes:
    """A minimal but genuinely valid PDF with a real text layer.

    Built rather than fixtured so the OCR assertions below are testing extraction, not
    a checked-in blob whose contents nobody can see in a diff.
    """
    content = "BT /F1 11 Tf 60 780 Td 16 TL\n" + "\n".join(
        f"({line}) Tj T*" for line in lines
    ) + "\nET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(out)


CHARGESHEET = _pdf(
    [
        "IN THE CITY CIVIL COURT AT BENGALURU",
        "CHARGESHEET under Section 138 of the Negotiable Instruments Act",
        "The cheque bearing number 004512 was dishonoured for insufficiency of funds.",
    ]
)


async def _upload(http: AsyncClient, headers: dict, name: str, data: bytes) -> str:
    """The full three-step B.9 flow, as the app performs it."""
    issued = (
        await http.post(
            f"{BASE}/documents/upload-url",
            headers=headers,
            json={
                "name": name,
                "mime_type": "application/pdf",
                "size_bytes": len(data),
                "folder": "Chargesheets",
            },
        )
    ).json()["data"]

    put = await http.put(issued["upload_url"], content=data)
    assert put.status_code == 200

    await http.post(f"{BASE}/documents/{issued['document_id']}/confirm", headers=headers)
    return issued["document_id"]


async def test_upload_extracts_text_and_becomes_searchable(client: AsyncClient) -> None:
    headers = await sign_in(client, "Docs Firm")
    document_id = await _upload(client, headers, "Chargesheet.pdf", CHARGESHEET)

    document = (
        await client.get(f"{BASE}/documents/{document_id}", headers=headers)
    ).json()["data"]
    assert document["ocr_status"] == "done"
    assert document["download_url"]

    # The point of extraction: findable by a phrase that appears only *inside* the
    # file, never in its name.
    found = (
        await client.get(f"{BASE}/search", headers=headers, params={"q": "dishonoured"})
    ).json()["data"]
    assert len(found["documents"]) == 1
    assert "dishonoured" in found["documents"][0]["highlight"]


async def test_unconfirmed_upload_is_not_listed(client: AsyncClient) -> None:
    """An abandoned upload must not appear as a document that cannot be opened."""
    headers = await sign_in(client, "Abandon Firm")

    await client.post(
        f"{BASE}/documents/upload-url",
        headers=headers,
        json={"name": "never.pdf", "mime_type": "application/pdf", "size_bytes": 10},
    )

    listed = (await client.get(f"{BASE}/documents", headers=headers)).json()
    assert listed["meta"]["total"] == 0


async def test_rejects_unsupported_type_and_oversized_file(client: AsyncClient) -> None:
    headers = await sign_in(client, "Limits Firm")

    bad_type = await client.post(
        f"{BASE}/documents/upload-url",
        headers=headers,
        json={"name": "x.exe", "mime_type": "application/x-msdownload", "size_bytes": 10},
    )
    assert bad_type.json()["error"]["code"] == "VALIDATION_ERROR"

    too_big = await client.post(
        f"{BASE}/documents/upload-url",
        headers=headers,
        json={"name": "x.pdf", "mime_type": "application/pdf", "size_bytes": 51 * 1024 * 1024},
    )
    assert too_big.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_upload_url_cannot_be_forged_or_replayed_after_expiry(
    client: AsyncClient,
) -> None:
    """The signed URL is the only authorisation on the PUT endpoint, exactly as with
    S3 — so forging and expiry are the whole security model, not edge cases."""
    headers = await sign_in(client, "Signed Firm")
    issued = (
        await client.post(
            f"{BASE}/documents/upload-url",
            headers=headers,
            json={"name": "s.pdf", "mime_type": "application/pdf", "size_bytes": 100},
        )
    ).json()["data"]

    tampered = issued["upload_url"].replace("signature=a", "signature=b")
    if tampered == issued["upload_url"]:
        tampered = issued["upload_url"][:-1] + ("0" if issued["upload_url"][-1] != "0" else "1")
    forged = await client.put(tampered, content=b"%PDF-1.4")
    assert forged.json()["error"]["code"] == "UPLOAD_URL_INVALID"

    document_id = issued["document_id"]
    past = int(time.time()) - 10
    expired = (
        f"{BASE}/uploads/{document_id}"
        f"?expires={past}&signature={storage.sign(document_id, past)}"
    )
    stale = await client.put(expired, content=b"%PDF-1.4")
    assert stale.json()["error"]["code"] == "UPLOAD_URL_EXPIRED"


async def test_documents_are_tenant_isolated(client: AsyncClient) -> None:
    a_headers = await sign_in(client, "Doc Firm A")
    b_headers = await sign_in(client, "Doc Firm B")
    document_id = await _upload(client, a_headers, "Private.pdf", CHARGESHEET)

    # B cannot read the metadata, and therefore can never obtain a signed download URL.
    denied = await client.get(f"{BASE}/documents/{document_id}", headers=b_headers)
    assert denied.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"

    # B's search must not surface A's document text either.
    found = (
        await client.get(f"{BASE}/search", headers=b_headers, params={"q": "dishonoured"})
    ).json()["data"]
    assert found["documents"] == []


async def test_download_returns_the_original_bytes(client: AsyncClient) -> None:
    headers = await sign_in(client, "Download Firm")
    document_id = await _upload(client, headers, "Original.pdf", CHARGESHEET)

    document = (
        await client.get(f"{BASE}/documents/{document_id}", headers=headers)
    ).json()["data"]

    # No Authorization header: a viewer or share sheet opens this URL directly.
    downloaded = await client.get(document["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.content == CHARGESHEET
    assert downloaded.headers["content-type"].startswith("application/pdf")


async def test_a_scan_that_cannot_be_read_fails_honestly_and_keeps_the_file(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point of the OCR provider chain degrading rather than throwing.

    With no provider configured the document must end `failed` with a stored reason —
    not `done` with nothing in it, and not a lost upload.
    """
    from app.core.config import get_settings
    from app.core.db import SessionFactory
    from app.models import Document

    monkeypatch.setattr(get_settings(), "fake_mode", False)

    headers = await sign_in(client, "Scan Firm")
    scanned = _pdf([])  # valid PDF, no text layer — a scan, as far as pypdf can tell
    document_id = await _upload(client, headers, "Scan.pdf", scanned)

    document = (
        await client.get(f"{BASE}/documents/{document_id}", headers=headers)
    ).json()["data"]
    assert document["ocr_status"] == "failed"

    async with SessionFactory() as session:
        row = await session.get(Document, uuid.UUID(document_id))
        assert row.ocr_error
        assert row.ocr_text is None

    # The bytes are still there: a document nobody could read is still a document.
    downloaded = await client.get(document["download_url"])
    assert downloaded.content == scanned


async def test_upload_url_expiry_follows_the_configured_window(
    client: AsyncClient,
) -> None:
    from app.core.config import get_settings

    headers = await sign_in(client, "Expiry Firm")
    issued = (
        await client.post(
            f"{BASE}/documents/upload-url",
            headers=headers,
            json={"name": "e.pdf", "mime_type": "application/pdf", "size_bytes": 100},
        )
    ).json()["data"]

    assert issued["expires_in_seconds"] == get_settings().document_upload_url_expiry_seconds


async def test_a_put_larger_than_the_limit_is_rejected(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Step 1 only sees the size the client claims; step 2 sees the file."""
    from app.core.config import get_settings

    headers = await sign_in(client, "Oversize Firm")
    issued = (
        await client.post(
            f"{BASE}/documents/upload-url",
            headers=headers,
            json={"name": "lie.pdf", "mime_type": "application/pdf", "size_bytes": 10},
        )
    ).json()["data"]

    monkeypatch.setattr(get_settings(), "document_max_upload_bytes", 16)
    put = await client.put(issued["upload_url"], content=b"x" * 64)

    assert put.json()["error"]["code"] == "VALIDATION_ERROR"
