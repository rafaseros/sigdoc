"""Unit tests for JWT handler (task 3.2)."""
import time
from datetime import datetime, timedelta, timezone

import pytest
from jose import JWTError, jwt

from app.infrastructure.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("mysecretpass")
        assert hashed != "mysecretpass"

    def test_verify_correct_password(self):
        hashed = hash_password("correct-horse-battery-staple")
        assert verify_password("correct-horse-battery-staple", hashed) is True

    def test_reject_wrong_password(self):
        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """bcrypt uses a random salt — same password hashes differently each time."""
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2

    def test_verify_empty_password(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("notempty", hashed) is False


# ---------------------------------------------------------------------------
# Access token
# ---------------------------------------------------------------------------


class TestCreateAccessToken:
    def test_decode_returns_correct_sub(self):
        user_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        tenant_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        token = create_access_token(user_id, tenant_id, "admin")
        payload = decode_token(token)
        assert payload["sub"] == user_id

    def test_decode_returns_correct_tenant_id(self):
        user_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        tenant_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        token = create_access_token(user_id, tenant_id, "admin")
        payload = decode_token(token)
        assert payload["tenant_id"] == tenant_id

    def test_decode_returns_correct_role(self):
        token = create_access_token("uid", "tid", "manager")
        payload = decode_token(token)
        assert payload["role"] == "manager"

    def test_type_is_access(self):
        token = create_access_token("uid", "tid", "user")
        payload = decode_token(token)
        assert payload["type"] == "access"

    def test_has_exp_claim(self):
        token = create_access_token("uid", "tid", "user")
        payload = decode_token(token)
        assert "exp" in payload


# ---------------------------------------------------------------------------
# Refresh token
# ---------------------------------------------------------------------------


class TestCreateRefreshToken:
    def test_type_is_refresh(self):
        token = create_refresh_token("uid", "tid")
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_decode_returns_correct_sub(self):
        user_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
        token = create_refresh_token(user_id, "tid")
        payload = decode_token(token)
        assert payload["sub"] == user_id

    def test_no_role_in_refresh_token(self):
        token = create_refresh_token("uid", "tid")
        payload = decode_token(token)
        assert "role" not in payload


# ---------------------------------------------------------------------------
# Token validation failures
# ---------------------------------------------------------------------------


class TestDecodeTokenFailures:
    def test_tampered_token_raises_jwt_error(self):
        token = create_access_token("uid", "tid", "user")
        # Tamper with the payload portion (second segment)
        parts = token.split(".")
        parts[1] = parts[1][::-1]  # reverse the payload bytes
        tampered = ".".join(parts)
        with pytest.raises(JWTError):
            decode_token(tampered)

    def test_wrong_signature_raises_jwt_error(self):
        token = create_access_token("uid", "tid", "user")
        # Tamper with the signature (third segment)
        parts = token.split(".")
        parts[2] = "invalidsignature"
        tampered = ".".join(parts)
        with pytest.raises(JWTError):
            decode_token(tampered)

    def test_malformed_token_raises_jwt_error(self):
        with pytest.raises(JWTError):
            decode_token("not.a.valid.jwt.token")

    def test_empty_token_raises_jwt_error(self):
        with pytest.raises(JWTError):
            decode_token("")

    def test_expired_token_raises_jwt_error(self, monkeypatch):
        """Create a token that is already expired by patching the expiry to the past."""
        from app.config import get_settings

        settings = get_settings()

        # Build an already-expired token by hand
        expired_payload = {
            "sub": "uid",
            "tenant_id": "tid",
            "role": "user",
            "type": "access",
            # exp = 2 seconds in the past
            "exp": datetime.now(timezone.utc) - timedelta(seconds=2),
        }
        expired_token = jwt.encode(
            expired_payload, settings.secret_key, algorithm="HS256"
        )

        with pytest.raises(JWTError):
            decode_token(expired_token)
