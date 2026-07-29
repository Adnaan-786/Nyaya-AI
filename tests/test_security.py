import time

import pytest

from app.core.exceptions import AuthenticationException, TokenExpiredException
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_otp,
    generate_refresh_token,
    hash_otp,
    hash_token,
    verify_otp_hash,
)


def test_generate_otp_default_length():
    otp = generate_otp()
    assert len(otp) == 6
    assert otp.isdigit()


def test_generate_otp_custom_length():
    otp = generate_otp(4)
    assert len(otp) == 4


def test_hash_otp_is_deterministic_and_verifiable():
    otp = "123456"
    hashed = hash_otp(otp)

    assert hashed != otp
    assert verify_otp_hash(otp, hashed) is True
    assert verify_otp_hash("000000", hashed) is False


def test_generate_refresh_token_is_high_entropy_and_hashable():
    token_a = generate_refresh_token()
    token_b = generate_refresh_token()

    assert token_a != token_b
    assert len(token_a) > 32

    assert hash_token(token_a) != hash_token(token_b)
    # hashing must be deterministic so we can look tokens up by hash
    assert hash_token(token_a) == hash_token(token_a)


def test_access_token_round_trip():
    import uuid

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="lawyer")
    payload = decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["role"] == "lawyer"
    assert "exp" in payload


def test_decode_access_token_rejects_garbage():
    with pytest.raises(AuthenticationException):
        decode_access_token("not-a-real-token")


def test_decode_access_token_rejects_expired(monkeypatch):
    import uuid

    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "access_token_expire_minutes", 0)

    token = create_access_token(
        user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), role="lawyer"
    )

    time.sleep(1)

    with pytest.raises(TokenExpiredException):
        decode_access_token(token)
