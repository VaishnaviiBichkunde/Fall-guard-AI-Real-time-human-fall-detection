"""Password verification and role-based API authentication."""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import uuid
from typing import Any, Callable, Dict, Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.database import db_manager

load_dotenv()
logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)
PASSWORD_HASH_ITERATIONS = 310_000
TOKEN_LIFETIME_SECONDS = 8 * 60 * 60

# These salted hashes preserve the existing demonstration accounts without
# keeping their plaintext passwords in the application source.
BOOTSTRAP_USERS = (
    {
        "user_id": "demo-admin",
        "username": "admin",
        "display_name": "System Administrator",
        "role": "admin",
        "email": "admin@fallguard.local",
        "password_hash": "pbkdf2_sha256$310000$3e-BL0cJQr-ukQsfe0MwEA$fIXM4mQrPP2-X5fbDfA8Xex-MIYsggwiYim1Kdi3aQk",
    },
    {
        "user_id": "demo-mohini",
        "username": "mohini",
        "display_name": "Mohini Ravat",
        "role": "caretaker_1",
        "email": "mohini.ravat@fallguard.local",
        "password_hash": "pbkdf2_sha256$310000$-ljQ5y88Guizu1ZptHi9kA$s9NieZttWwt_I3ZLhlaV4OQdcxzhZ-3w67mOCJhARxU",
    },
    {
        "user_id": "demo-radha",
        "username": "radha",
        "display_name": "Radha Raghav",
        "role": "caretaker_2",
        "email": "radha.raghav@fallguard.local",
        "password_hash": "pbkdf2_sha256$310000$t7yYrVZTKhs42o0Be737gg$eMtkQS2MmZ2795O0ET0QeAkvxmuABszSfyZTFWk0rp0",
    },
    {
        "user_id": "demo-resident",
        "username": "user",
        "display_name": "Elderly Resident / Patient",
        "role": "user",
        "email": "resident@fallguard.local",
        "password_hash": "pbkdf2_sha256$310000$jgE-OtjBUv0GeJ4Ng1H3XA$RulX2PSdkot12F4LXP1bsUHMtZHHiw9LLfECiJIVe9E",
    },
)

_configured_secret = os.getenv("SECRET_KEY", "")
if len(_configured_secret) < 32:
    logger.warning("SECRET_KEY is missing or too short; using an ephemeral API signing key.")
    _configured_secret = secrets.token_urlsafe(48)
TOKEN_SIGNING_KEY = _configured_secret.encode("utf-8")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    """Create a salted PBKDF2 hash suitable for database storage."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded_hash: str) -> bool:
    """Constant-time verification of a PBKDF2 password hash."""
    try:
        algorithm, iterations_text, salt_text, digest_text = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        if iterations < 100_000 or iterations > 2_000_000:
            return False
        salt = _b64decode(salt_text)
        expected = _b64decode(digest_text)
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def ensure_bootstrap_users() -> None:
    """Insert legacy demonstration accounts once, without overwriting managed users."""
    for template in BOOTSTRAP_USERS:
        if db_manager.find_one("users", {"username": template["username"]}):
            continue
        user = dict(template)
        user["is_active"] = True
        user["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        db_manager.insert_one("users", user)


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    ensure_bootstrap_users()
    user = db_manager.find_one("users", {"username": username.strip().lower()})
    if not user or not user.get("is_active", True):
        return None

    encoded_hash = user.get("password_hash")
    if not encoded_hash or not verify_password(password, encoded_hash):
        return None
    return user


def create_access_token(user: Dict[str, Any]) -> str:
    now = int(time.time())
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64encode(
        json.dumps(
            {
                "sub": user["user_id"],
                "username": user["username"],
                "role": user["role"],
                "iat": now,
                "exp": now + TOKEN_LIFETIME_SECONDS,
                "jti": uuid.uuid4().hex,
            },
            separators=(",", ":"),
        ).encode()
    )
    signature = hmac.new(
        TOKEN_SIGNING_KEY,
        f"{header}.{payload}".encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{header}.{payload}.{_b64encode(signature)}"


def _decode_access_token(token: str) -> Dict[str, Any]:
    try:
        header, payload, signature = token.split(".")
        expected = hmac.new(
            TOKEN_SIGNING_KEY,
            f"{header}.{payload}".encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(signature)):
            raise ValueError("Invalid token signature")
        token_header = json.loads(_b64decode(header))
        claims = json.loads(_b64decode(payload))
        if token_header.get("alg") != "HS256" or int(claims.get("exp", 0)) <= int(time.time()):
            raise ValueError("Expired or unsupported token")
        return claims
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = _decode_access_token(credentials.credentials)
    user = db_manager.find_one("users", {"user_id": claims.get("sub")})
    if not user or not user.get("is_active", True) or user.get("role") != claims.get("role"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account is inactive or its access has changed.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*allowed_roles: str) -> Callable[..., Any]:
    async def role_dependency(
        user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is not authorized to perform this action.",
            )
        return user

    return role_dependency
