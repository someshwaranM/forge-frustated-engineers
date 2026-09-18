"""
Vigil — Phase 5: File Stability Check.

Ensures audio file is fully written and not still actively being copied/recorded
by checking file size twice over a time delay (default 2 seconds).
"""

import os
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FileStabilityError(Exception):
    """Raised when a file does not stabilize or is empty."""
    def __init__(self, reason: str, message: str = ""):
        self.reason = reason
        super().__init__(message or reason)


def wait_for_file_stability(file_path: str | Path, delay_seconds: float = 2.0, max_attempts: int = 3) -> bool:
    """
    Confirms file exists, has non-zero size, and size remains unchanged over delay_seconds.
    
    Args:
        file_path: Path to the file being checked.
        delay_seconds: Seconds to wait between size checks.
        max_attempts: Number of check cycles before failing.
        
    Returns:
        True if file is stable.
        
    Raises:
        FileStabilityError: if file not found, empty, or size continues changing.
    """
    p = Path(file_path)
    if not p.exists():
        logger.error(f"File not found: {p}")
        raise FileStabilityError("FILE_NOT_FOUND", f"File does not exist: {p}")

    for attempt in range(1, max_attempts + 1):
        size1 = p.stat().st_size
        if size1 == 0:
            logger.warning(f"File {p.name} has 0 bytes (attempt {attempt}/{max_attempts}).")
            if attempt == max_attempts:
                raise FileStabilityError("EMPTY_FILE", f"File {p.name} is empty (0 bytes).")
            time.sleep(delay_seconds)
            continue

        time.sleep(delay_seconds)
        size2 = p.stat().st_size

        if size1 == size2:
            logger.info(f"File {p.name} is stable ({size1} bytes).")
            return True
        else:
            logger.warning(f"File {p.name} size changed from {size1} to {size2} bytes. Retrying...")

    raise FileStabilityError("FILE_NOT_STABLE", f"File {p.name} did not stabilize after {max_attempts} attempts.")
