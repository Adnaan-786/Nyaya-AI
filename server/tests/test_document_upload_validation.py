"""B.9 upload limits, at the level where they are decided."""

import pytest

from app.core import envelope
from app.core.config import get_settings
from app.integrations import storage
from app.services.document_service import (
    upload_limit_bytes,
    validate_size,
    validate_upload,
)

CONTRACT_MIME_TYPES = [
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]


@pytest.mark.parametrize("mime_type", CONTRACT_MIME_TYPES)
def test_every_contract_mime_type_is_accepted(mime_type: str) -> None:
    validate_upload(mime_type, 1024)


def test_the_allow_list_is_the_configured_one_not_a_second_copy() -> None:
    """It used to be hard-coded in storage.py *and* in settings — two lists that could
    disagree, with only one of them settable per deployment."""
    assert set(CONTRACT_MIME_TYPES) == get_settings().document_allowed_mime_type_set


def test_unsupported_type_is_rejected() -> None:
    with pytest.raises(envelope.ApiError) as raised:
        validate_upload("application/x-msdownload", 1024)
    assert raised.value.code == "VALIDATION_ERROR"


def test_oversized_file_is_rejected() -> None:
    with pytest.raises(envelope.ApiError) as raised:
        validate_upload("application/pdf", 51 * 1024 * 1024)
    assert raised.value.code == "VALIDATION_ERROR"


def test_empty_file_is_rejected() -> None:
    """Zero bytes is a failed read on the device, not a document."""
    with pytest.raises(envelope.ApiError):
        validate_upload("application/pdf", 0)


def test_size_is_checked_against_the_document_limit() -> None:
    limit = upload_limit_bytes()
    validate_size(limit)
    with pytest.raises(envelope.ApiError):
        validate_size(limit + 1)


def test_the_tighter_of_the_two_upload_limits_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """A deployment that tightened MAX_UPLOAD_BYTES must not be quietly ignored."""
    settings = get_settings()
    monkeypatch.setattr(settings, "max_upload_bytes", 1024)
    monkeypatch.setattr(settings, "document_max_upload_bytes", 50 * 1024 * 1024)

    assert upload_limit_bytes() == 1024
    with pytest.raises(envelope.ApiError):
        validate_size(2048)


def test_storage_keys_stay_inside_the_tenant_prefix() -> None:
    """The filename arrives from the device and is the only attacker-controlled part
    of the key — a traversal here would let one firm write over another's prefix."""
    key = storage.storage_key("t1", "d1", "../../etc/passwd")
    assert key.startswith("tenant/t1/d1/")
    assert ".." not in key.removeprefix("tenant/t1/d1/")

    assert storage.storage_key("t1", "d1", r"C:\Users\x\order.pdf").endswith("order.pdf")
    assert storage.storage_key("t1", "d1", "   ").endswith("/file")
