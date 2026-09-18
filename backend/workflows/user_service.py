"""
Vigil — User Service & Authentication Boundary (backend/workflows/user_service.py)

Manages:
1. MySQL `users` table schema creation & verification.
2. Initial default user auto-seeding (Role: Audit Officer, Team: Compliance, access: All).
3. Secure password hashing & verification via bcrypt.
4. JWT token creation and validation.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import bcrypt
import jwt
from backend.db.session import db_connection, db_transaction

logger = logging.getLogger("vigil.user_service")

# JWT configuration
JWT_SECRET = os.getenv("VIGIL_JWT_SECRET", "vigil-super-secure-audit-jwt-secret-key-2026-compliance")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("VIGIL_JWT_EXPIRATION_HOURS", "24"))

# Default initial user credentials
DEFAULT_USER = {
    "user_id": "USR-001",
    "username": "admin",
    "email": "audit.officer@vigil.com",
    "password": "admin12345",
    "role": "Audit Officer",
    "team": "Compliance",
    "access_level": "All",
    "full_name": "Audit Officer",
}


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password with a strong bcrypt salt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as exc:
        logger.warning(f"Password verification failed with error: {exc}")
        return False


def create_access_token(user: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT access token for the authenticated user."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(hours=JWT_EXPIRATION_HOURS))
    
    payload = {
        "sub": user["user_id"],
        "user_id": user["user_id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "team": user["team"],
        "access": user.get("access_level", "All"),
        "full_name": user.get("full_name", user["username"]),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.info("Access token has expired.")
        return None
    except jwt.InvalidTokenError as exc:
        logger.warning(f"Invalid access token: {exc}")
        return None


def init_user_table_and_seed() -> None:
    """
    Ensure the `users` table exists in MySQL and that the default user is seeded.
    Safe to call repeatedly on app startup.
    """
    ddl = """
    CREATE TABLE IF NOT EXISTS users (
        user_id        VARCHAR(64) PRIMARY KEY,
        username       VARCHAR(50) NOT NULL UNIQUE,
        email          VARCHAR(100) NOT NULL UNIQUE,
        password_hash  VARCHAR(255) NOT NULL,
        role           VARCHAR(50) NOT NULL DEFAULT 'Audit Officer',
        team           VARCHAR(50) NOT NULL DEFAULT 'Compliance',
        access_level   VARCHAR(50) NOT NULL DEFAULT 'All',
        full_name      VARCHAR(100) NOT NULL DEFAULT 'Audit Officer',
        is_active      BOOLEAN DEFAULT TRUE,
        last_login_at  TIMESTAMP NULL,
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );
    """
    try:
        with db_transaction() as cur:
            cur.execute(ddl)
            logger.info("Checked/created users table in MySQL.")

            # Check if default user exists
            cur.execute(
                "SELECT user_id FROM users WHERE username = %s OR email = %s LIMIT 1",
                (DEFAULT_USER["username"], DEFAULT_USER["email"])
            )
            existing = cur.fetchone()

            if not existing:
                pwd_hash = hash_password(DEFAULT_USER["password"])
                insert_sql = """
                INSERT INTO users (
                    user_id, username, email, password_hash,
                    role, team, access_level, full_name, is_active
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, TRUE
                )
                """
                cur.execute(
                    insert_sql,
                    (
                        DEFAULT_USER["user_id"],
                        DEFAULT_USER["username"],
                        DEFAULT_USER["email"],
                        pwd_hash,
                        DEFAULT_USER["role"],
                        DEFAULT_USER["team"],
                        DEFAULT_USER["access_level"],
                        DEFAULT_USER["full_name"],
                    )
                )
                logger.info(
                    f"Seeded default user: username='{DEFAULT_USER['username']}', "
                    f"role='{DEFAULT_USER['role']}', team='{DEFAULT_USER['team']}', "
                    f"email='{DEFAULT_USER['email']}'"
                )
            else:
                logger.debug("Default user already present in users table.")
    except Exception as exc:
        logger.exception(f"Failed to initialize users table or seed default user: {exc}")
        raise


def get_user_by_username_or_email(identifier: str) -> Optional[Dict[str, Any]]:
    """Retrieve a user row by either username or email."""
    sql = """
    SELECT user_id, username, email, password_hash, role, team,
           access_level, full_name, is_active, last_login_at, created_at, updated_at
    FROM users
    WHERE (username = %s OR email = %s) AND is_active = TRUE
    LIMIT 1
    """
    with db_connection() as cur:
        cur.execute(sql, (identifier, identifier))
        return cur.fetchone()


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a user by user_id."""
    sql = """
    SELECT user_id, username, email, role, team,
           access_level, full_name, is_active, last_login_at, created_at, updated_at
    FROM users
    WHERE user_id = %s AND is_active = TRUE
    LIMIT 1
    """
    with db_connection() as cur:
        cur.execute(sql, (user_id,))
        return cur.fetchone()


def list_users() -> List[Dict[str, Any]]:
    """Return all active users without exposing password hashes."""
    sql = """
    SELECT user_id, username, email, role, team,
           access_level, full_name, is_active, last_login_at, created_at
    FROM users
    ORDER BY created_at ASC
    """
    with db_connection() as cur:
        cur.execute(sql)
        return cur.fetchall() or []


def record_user_login(user_id: str) -> None:
    """Update last_login_at timestamp for the user."""
    sql = "UPDATE users SET last_login_at = NOW() WHERE user_id = %s"
    try:
        with db_transaction() as cur:
            cur.execute(sql, (user_id,))
    except Exception as exc:
        logger.warning(f"Failed to record last login for user {user_id}: {exc}")


def authenticate_user(identifier: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate a user by username or email and password.
    Returns user dict (without password_hash) on success, or None on failure.
    """
    user = get_user_by_username_or_email(identifier)
    if not user:
        return None

    if not verify_password(password, user["password_hash"]):
        return None

    # Update last login
    record_user_login(user["user_id"])

    # Strip sensitive fields
    user.pop("password_hash", None)
    return user
