"""
Vigil — MySQL Database Session Boundary (backend/db/session.py)
"""

import os
import logging
from contextlib import contextmanager
from pathlib import Path
import pymysql
import pymysql.cursors
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)


def get_db_connection():
    """Create and return a fresh MySQL connection configured with DictCursor."""
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "qwerty12345"),
        database=os.getenv("MYSQL_DATABASE", "vigil"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


@contextmanager
def db_transaction():
    """
    Context manager providing an atomic MySQL transaction with a DictCursor.
    Commits on successful block completion, rolls back on any exception,
    and reliably closes the connection.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def db_connection():
    """
    Context manager providing a read-only or auto-closing connection with DictCursor.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()
