"""
Vigil — Phase 5: Audio Validator.

Validates that the file is a readable WAV audio file and extracts its duration in seconds.
Rejects with INVALID_AUDIO if unreadable, corrupt, or duration is zero.
"""

import wave
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioValidationError(Exception):
    """Raised when an audio file cannot be read or has zero duration."""
    def __init__(self, reason: str, message: str = ""):
        self.reason = reason
        super().__init__(message or reason)


def validate_and_extract_duration(file_path: str | Path) -> float:
    """
    Validates audio file and returns its duration in seconds.
    
    Args:
        file_path: Path to the audio file (.wav)
        
    Returns:
        float: Duration in seconds (rounded to 2 decimal places).
        
    Raises:
        AudioValidationError: If file is invalid audio, unreadable, or duration is 0.
    """
    p = Path(file_path)
    if not p.exists():
        raise AudioValidationError("INVALID_AUDIO", f"File does not exist: {p}")

    try:
        with wave.open(str(p), "rb") as wav_file:
            n_frames = wav_file.getnframes()
            framerate = wav_file.getframerate()

            if framerate <= 0 or n_frames <= 0:
                logger.error(f"Audio file '{p.name}' has 0 frames or invalid framerate: frames={n_frames}, rate={framerate}")
                raise AudioValidationError("INVALID_AUDIO", f"Audio file has zero duration (frames={n_frames}, rate={framerate})")

            duration = round(n_frames / float(framerate), 2)
            if duration <= 0.0:
                logger.error(f"Calculated audio duration is 0.0 for '{p.name}'")
                raise AudioValidationError("INVALID_AUDIO", f"Audio file '{p.name}' duration is 0.0 seconds")

            logger.info(f"Audio validation successful for '{p.name}': duration={duration}s")
            return duration

    except (wave.Error, EOFError, OSError) as exc:
        logger.error(f"Failed to read audio file '{p.name}': {exc}")
        raise AudioValidationError("INVALID_AUDIO", f"Failed to read audio file '{p.name}': {exc}")
