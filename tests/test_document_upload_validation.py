import pytest

from app.core.exceptions import ValidationException
from app.services.document_service import validate_upload_request


def test_validate_upload_request_accepts_valid_pdf():
    validate_upload_request(mime_type="application/pdf", size_bytes=1024)


def test_validate_upload_request_rejects_oversized_file():
    with pytest.raises(ValidationException):
        validate_upload_request(
            mime_type="application/pdf", size_bytes=51 * 1024 * 1024
        )


def test_validate_upload_request_rejects_disallowed_mime_type():
    with pytest.raises(ValidationException):
        validate_upload_request(
            mime_type="application/x-executable", size_bytes=1024
        )


@pytest.mark.parametrize(
    "mime_type",
    [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ],
)
def test_validate_upload_request_accepts_all_contract_mime_types(mime_type):
    validate_upload_request(mime_type=mime_type, size_bytes=1024)
