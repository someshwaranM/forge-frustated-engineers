"""
Vigil — Phase 5: Filename Parser and MySQL Validation.

Expected pattern: RM<rm_id_digits>_CUST<customer_id_digits>_<YYYYMMDD>_<HHMM>.wav
e.g. RM001_CUST001_20260310_1030.wav
"""

import os
import re
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import pymysql
from dotenv import load_dotenv

# Ensure environment variables are loaded
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)

logger = logging.getLogger(__name__)

FILENAME_PATTERN = re.compile(
    r"^RM(?P<rm_num>\d+)_CUST(?P<cust_num>\d+)_(?P<date>\d{8})_(?P<time>\d{4})\.wav$",
    re.IGNORECASE
)


class FilenameValidationError(Exception):
    """Raised when filename is malformed or IDs do not exist in MySQL."""
    def __init__(self, reason: str, message: Optional[str] = None):
        self.reason = reason
        super().__init__(message or reason)


@dataclass
class ParsedFileInfo:
    rm_id: str
    customer_id: str
    date_time: str
    call_id: str
    rm_name: str
    customer_name: str


def get_mysql_connection():
    """Create and return a MySQL database connection using backend/.env config."""
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "qwerty12345"),
        database=os.getenv("MYSQL_DATABASE", "vigil"),
        cursorclass=pymysql.cursors.DictCursor
    )


def parse_and_validate_filename(filename_or_path: str, conn=None) -> ParsedFileInfo:
    """
    Parses audio filename and validates RM and Customer against MySQL.
    
    Returns:
        ParsedFileInfo with rm_id, customer_id, date_time, call_id, rm_name, customer_name.
        
    Raises:
        FilenameValidationError: if filename does not match pattern or IDs not found in MySQL.
    """
    filename = Path(filename_or_path).name
    match = FILENAME_PATTERN.match(filename)
    if not match:
        logger.error(f"Filename pattern mismatch: '{filename}'")
        raise FilenameValidationError(
            "FILENAME_PATTERN_MISMATCH",
            f"Filename '{filename}' does not match expected pattern RM<digits>_CUST<digits>_<YYYYMMDD>_<HHMM>.wav"
        )

    rm_num = match.group("rm_num")
    cust_num = match.group("cust_num")
    date_str = match.group("date")
    time_str = match.group("time")

    rm_id = f"RM{rm_num}"
    customer_id = f"CUST{cust_num}"

    # Format ISO-8601 date_time: YYYY-MM-DDTHH:MM:00Z
    year = date_str[:4]
    month = date_str[4:6]
    day = date_str[6:8]
    hour = time_str[:2]
    minute = time_str[2:4]
    date_time = f"{year}-{month}-{day}T{hour}:{minute}:00Z"

    call_id = f"CALL_{rm_id}_{customer_id}_{date_str}_{time_str}"

    # MySQL validation
    should_close_conn = False
    if conn is None:
        conn = get_mysql_connection()
        should_close_conn = True

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT rm_id, full_name FROM rm WHERE rm_id = %s", (rm_id,))
            rm_row = cursor.fetchone()
            if not rm_row:
                logger.error(f"RM ID '{rm_id}' not found in MySQL rm table.")
                raise FilenameValidationError("UNKNOWN_RM_ID", f"RM ID '{rm_id}' not found in database.")
            rm_name = rm_row["full_name"]

            cursor.execute("SELECT customer_id, full_name FROM customer WHERE customer_id = %s", (customer_id,))
            cust_row = cursor.fetchone()
            if not cust_row:
                logger.error(f"Customer ID '{customer_id}' not found in MySQL customer table.")
                raise FilenameValidationError("UNKNOWN_CUSTOMER_ID", f"Customer ID '{customer_id}' not found in database.")
            customer_name = cust_row["full_name"]

        return ParsedFileInfo(
            rm_id=rm_id,
            customer_id=customer_id,
            date_time=date_time,
            call_id=call_id,
            rm_name=rm_name,
            customer_name=customer_name,
        )
    finally:
        if should_close_conn:
            conn.close()
