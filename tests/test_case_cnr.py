import pytest

from app.core.exceptions import CNRInvalidException
from app.services.case_service import validate_cnr


def test_validate_cnr_accepts_16_char_alphanumeric():
    validate_cnr("MH01120200012345")  # 16 chars, no exception


@pytest.mark.parametrize(
    "bad_cnr",
    [
        "",
        "TOOSHORT",
        "THISISWAYTOOLONG1234567890",
        "MH0112020001234!",  # punctuation
        "MH01 1202000 1234",  # whitespace
    ],
)
def test_validate_cnr_rejects_invalid_formats(bad_cnr):
    with pytest.raises(CNRInvalidException):
        validate_cnr(bad_cnr)
