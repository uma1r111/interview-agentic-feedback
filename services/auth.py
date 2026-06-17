import hashlib
import hmac
import logging
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from services.database import get_db_connection

logger = logging.getLogger("AuthService")

# ==============================================================================
# Password Hashing — PBKDF2-HMAC-SHA256 with per-user salt
# ==============================================================================
# We avoid adding a new dependency (bcrypt/passlib) since hashlib's pbkdf2_hmac
# is part of the Python standard library and is sufficiently strong for an
# internal tool. 200,000 iterations is OWASP's current minimum recommendation
# for PBKDF2-SHA256.

_PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16


def _hash_password(password: str, salt: bytes) -> str:
    """Derives a hex-encoded hash from a password and salt."""
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
    )
    return derived.hex()


def hash_new_password(password: str) -> str:
    """
    Generates a new salt and returns a combined 'salt:hash' string
    suitable for storage in the users table.
    """
    salt = secrets.token_bytes(_SALT_BYTES)
    hashed = _hash_password(password, salt)
    return f"{salt.hex()}:{hashed}"


def verify_password(password: str, stored: str) -> bool:
    """
    Verifies a plaintext password against a stored 'salt:hash' string.
    Uses constant-time comparison to avoid timing attacks.
    """
    try:
        salt_hex, hash_hex = stored.split(":", 1)
    except ValueError:
        logger.error("Stored password hash is malformed (expected 'salt:hash').")
        return False

    salt = bytes.fromhex(salt_hex)
    candidate_hash = _hash_password(password, salt)
    return hmac.compare_digest(candidate_hash, hash_hex)


# ==============================================================================
# Schema Initialization
# ==============================================================================
# Reuses get_db_connection() from services/database.py instead of opening a
# second, separately-configured connection to the same SQLite file. Keeping
# one connection helper means PRAGMA settings, timeouts, or a future
# PostgreSQL migration (see P3-02) only need to change in one place.

def init_users_table() -> None:
    """
    Creates the users table if it does not already exist.
    Safe to call on every startup alongside init_database().
    """
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                email           TEXT PRIMARY KEY,
                password_hash   TEXT NOT NULL,
                role            TEXT NOT NULL CHECK (role IN ('hr', 'hiring_manager')),
                display_name    TEXT NOT NULL,
                created_at      TEXT NOT NULL,
                last_login_at   TEXT
            )
        """)
        conn.commit()
    logger.info("Users table verified.")


# ==============================================================================
# User Management
# ==============================================================================

def create_user(email: str, password: str, role: str, display_name: str) -> bool:
    """
    Creates a new user with a hashed password.
    Returns False if the email already exists (no overwrite).
    """
    email_normalized = email.strip().lower()
    password_hash = hash_new_password(password)
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO users (email, password_hash, role, display_name, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (email_normalized, password_hash, role, display_name, created_at))
            conn.commit()
        logger.info(f"User created: {email_normalized} ({role})")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"User creation skipped — email already exists: {email_normalized}")
        return False


def get_user(email: str) -> Optional[Dict[str, Any]]:
    """Fetches a user row by email (case-insensitive)."""
    email_normalized = email.strip().lower()
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email_normalized,)
        ).fetchone()
    return dict(row) if row else None


def authenticate(email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Verifies credentials. Returns the user record (without password_hash)
    on success, or None on failure. Updates last_login_at on success.
    """
    user = get_user(email)
    if not user:
        logger.warning(f"Login attempt for unknown email: {email}")
        return None

    if not verify_password(password, user["password_hash"]):
        logger.warning(f"Failed login attempt for: {email}")
        return None

    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = ? WHERE email = ?",
            (datetime.now(timezone.utc).isoformat(), user["email"])
        )
        conn.commit()

    logger.info(f"Successful login: {email} ({user['role']})")

    safe_user = dict(user)
    safe_user.pop("password_hash", None)
    return safe_user