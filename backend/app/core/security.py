import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

# Strong parameters: the hash is shipped to mobile devices for offline sign-in (SRS UC-08 AF1),
# so it must resist offline cracking. See docs/DECISIONS.md.
ARGON2_PARAMS = {
    "time_cost": 3,
    "memory_cost": 64 * 1024,  # KiB = 64 MiB
    "parallelism": 2,
    "hash_len": 32,
    "salt_len": 16,
}
_hasher = PasswordHasher(**ARGON2_PARAMS)

_LETTER = re.compile(r"[A-Za-z]")
_DIGIT = re.compile(r"\d")


def password_policy_violation(password: str) -> str | None:
    """SRS §5.5.4: at least 8 characters, letters and numbers. Returns an error code or None."""
    if len(password) < 8:
        return "password_too_short"
    if not (_LETTER.search(password) and _DIGIT.search(password)):
        return "password_needs_letters_and_numbers"
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def hash_params_public() -> dict:
    return {"algorithm": "argon2id", "version": 19, **ARGON2_PARAMS}


def create_access_token(user_id: uuid.UUID, role: str, session_id: uuid.UUID) -> tuple[str, int]:
    s = get_settings()
    now = datetime.now(UTC)
    ttl = s.access_token_minutes * 60
    payload = {
        "sub": str(user_id),
        "role": role,
        "sid": str(session_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), ttl


def decode_access_token(token: str) -> dict:
    s = get_settings()
    payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
