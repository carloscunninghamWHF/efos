"""Minimal file-backed authentication for the EFOS prototype.

The user registry is a plain-text file, but passwords are never stored in
plain text. Each record stores a per-user salt and a PBKDF2-SHA256 hash.

File format:
    username|role|salt_hex|password_hash_hex
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
from pathlib import Path

DEFAULT_USERS_FILE = Path(__file__).with_name("users.txt")
PBKDF2_ITERATIONS = 200_000


@dataclass(frozen=True)
class UserRecord:
    username: str
    role: str
    salt_hex: str
    password_hash_hex: str


def load_users(path: str | Path = DEFAULT_USERS_FILE) -> dict[str, UserRecord]:
    """Load the text user registry keyed case-insensitively by username."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró la base de usuarios: {path}")

    users: dict[str, UserRecord] = {}
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 4:
            raise ValueError(f"Registro inválido en {path}:{line_no}")
        username, role, salt_hex, password_hash_hex = parts
        # Validate encoded fields at load time to fail closed on malformed files.
        bytes.fromhex(salt_hex)
        bytes.fromhex(password_hash_hex)
        users[username.casefold()] = UserRecord(username, role, salt_hex, password_hash_hex)
    return users


def authenticate(username: str, password: str, path: str | Path = DEFAULT_USERS_FILE) -> UserRecord | None:
    """Return the authenticated user, or None if credentials are invalid."""
    if not username or not password:
        return None
    users = load_users(path)
    user = users.get(str(username).strip().casefold())
    if user is None:
        # Perform a dummy derivation to reduce username-enumeration timing differences.
        hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), b"0" * 16, PBKDF2_ITERATIONS)
        return None

    salt = bytes.fromhex(user.salt_hex)
    expected = bytes.fromhex(user.password_hash_hex)
    actual = hashlib.pbkdf2_hmac(
        "sha256", str(password).encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return user if hmac.compare_digest(actual, expected) else None
