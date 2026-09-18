"""
Vigil — Phase 5: Sarvam Transcription & Diarization Client.

Uses official Sarvam Python SDK (sarvamai) with Batch Job API.
Provides both original spoken text and English translation with speaker diarization.
"""

import os
import json
import time
import shutil
import tempfile
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Phase 13: Elastic APM native spans (no OpenTelemetry)
try:
    from backend.observability.apm import apm_span, report_error
except ImportError:
    from contextlib import contextmanager
    @contextmanager
    def apm_span(*a, **kw): yield
    def report_error(*a, **kw): pass

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)

logger = logging.getLogger(__name__)

# Debug logger (enabled via VIGIL_DEBUG_PIPELINE=true)
try:
    from backend.observability.debug_logger import (
        log_sarvam_job_created,
        log_sarvam_job_completed,
        log_sarvam_raw_response,
        log_sarvam_segments,
        log_sarvam_failure,
    )
except ImportError:
    def log_sarvam_job_created(*a, **kw): pass
    def log_sarvam_job_completed(*a, **kw): pass
    def log_sarvam_raw_response(*a, **kw): pass
    def log_sarvam_segments(*a, **kw): pass
    def log_sarvam_failure(*a, **kw): pass


class TranscriptionError(Exception):
    """Raised when Sarvam transcription or translation fails."""
    def __init__(self, reason: str, message: str = ""):
        self.reason = reason
        super().__init__(message or reason)


@dataclass
class DiarizedSegment:
    segment_id: str
    speaker_raw: str
    text_original: str
    text_english: str
    start_time: float
    end_time: float


@dataclass
class TranscriptionResult:
    language: str
    transcript_original_text: str
    transcript_english_text: str
    segments: List[DiarizedSegment]


class SarvamClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SARVAM_API_KEY")
        if not self.api_key:
            raise TranscriptionError("TRANSCRIPTION_FAILED", "SARVAM_API_KEY environment variable is missing.")
        
        # Late import to ensure package is ready
        from sarvamai import SarvamAI
        self.client = SarvamAI(api_subscription_key=self.api_key)

    def process_audio(self, audio_file_path: str | Path, max_retries: int = 1, call_id: Optional[str] = None) -> TranscriptionResult:
        """
        Transcribes and diarizes audio using Sarvam Batch Job API.
        
        Performs speech-to-text translate job.
        - If audio is English (e.g. en-IN), both original and english transcripts are identical.
        - If audio is non-English, runs a speech_to_text transcribe job to obtain verbatim
          original language text alongside the English translation.
        - Timestamps are strictly from Sarvam diarization without overlay.
        
        Retries on failure with exponential backoff before raising TranscriptionError.
        """
        path = Path(audio_file_path).resolve()
        cid = call_id or path.stem
        if not path.exists():
            raise TranscriptionError("TRANSCRIPTION_FAILED", f"Audio file not found: {path}")

        last_error = None
        for attempt in range(1, max_retries + 2):
            try:
                logger.info(f"Submitting Sarvam translate job for '{path.name}' (attempt {attempt}/{max_retries + 1})...")
                return self._run_pipeline(path, call_id=cid)
            except Exception as exc:
                last_error = exc
                log_sarvam_failure(cid, attempt, exc)
                logger.warning(f"Sarvam job attempt {attempt} failed for '{path.name}': {exc}")
                if attempt <= max_retries:
                    time.sleep(5 * attempt)

        logger.error(f"All Sarvam attempts failed for '{path.name}': {last_error}")
        raise TranscriptionError("TRANSCRIPTION_FAILED", f"Transcription failed after retries: {last_error}")

    def _run_pipeline(self, audio_path: Path, call_id: str = "") -> TranscriptionResult:
        tmp_dir = Path(tempfile.mkdtemp(prefix="sarvam_ingest_"))
        cid = call_id or audio_path.stem
        try:
            # 1. Run speech_to_text_translate_job
            with apm_span("sarvam.translate_job", span_type="external.http", span_subtype="sarvam"):
                job = self.client.speech_to_text_translate_job.create_job(
                    model="saaras:v3",
                    with_diarization=True,
                    num_speakers=2
                )
                logger.info(f"Created Sarvam translate job: {job.job_id}")
                log_sarvam_job_created(cid, job.job_id, "translate")
                t0 = time.time()

                job.upload_files(file_paths=[str(audio_path)])
                job.start()
                job.wait_until_complete(poll_interval=5, timeout=600)

                status = job.get_status()
                if status.job_state != "Completed":
                    raise RuntimeError(f"Sarvam translate job did not complete successfully: {status.job_state}")

                duration_sec = time.time() - t0
                log_sarvam_job_completed(cid, job.job_id, "translate", duration_sec)

                translate_output_dir = tmp_dir / "translate"
                job.download_outputs(str(translate_output_dir))

            # Locate downloaded json
            json_files = list(translate_output_dir.glob("*.json"))
            if not json_files:
                raise RuntimeError("No output JSON downloaded from Sarvam translate job.")

            with open(json_files[0], "r", encoding="utf-8") as jf:
                translate_data = json.load(jf)

            log_sarvam_raw_response(cid, "translate", translate_data)

            detected_lang = translate_data.get("language_code", "unknown")
            english_transcript = (translate_data.get("transcript") or "").strip()
            diarized = translate_data.get("diarized_transcript", {})
            entries = diarized.get("entries", [])

            is_english = detected_lang.lower().startswith("en")

            # 2. Handle original text: if non-English, fetch verbatim original via speech_to_text_job
            orig_entries = None
            orig_full_transcript = None
            if not is_english:
                try:
                    logger.info(f"Audio detected as '{detected_lang}' (non-English). Running transcribe job for verbatim native text...")
                    with apm_span("sarvam.transcribe_job", span_type="external.http", span_subtype="sarvam"):
                        transcribe_job = self.client.speech_to_text_job.create_job(
                            model="saaras:v3",
                            mode="transcribe",
                            with_diarization=True,
                            num_speakers=2
                        )
                        log_sarvam_job_created(cid, transcribe_job.job_id, "transcribe")
                        t_transcribe_0 = time.time()
                        transcribe_job.upload_files(file_paths=[str(audio_path)])
                        transcribe_job.start()
                        transcribe_job.wait_until_complete(poll_interval=5, timeout=600)
                        if transcribe_job.get_status().job_state == "Completed":
                            log_sarvam_job_completed(cid, transcribe_job.job_id, "transcribe", time.time() - t_transcribe_0)
                            transcribe_output_dir = tmp_dir / "transcribe"
                            transcribe_job.download_outputs(str(transcribe_output_dir))
                            t_json_files = list(transcribe_output_dir.glob("*.json"))
                            if t_json_files:
                                with open(t_json_files[0], "r", encoding="utf-8") as tjf:
                                    t_data = json.load(tjf)
                                log_sarvam_raw_response(cid, "transcribe", t_data)
                                orig_full_transcript = (t_data.get("transcript") or "").strip()
                                orig_entries = t_data.get("diarized_transcript", {}).get("entries", [])
                except Exception as t_exc:
                    logger.warning(f"Could not complete secondary transcribe job for '{audio_path.name}': {t_exc}. Using translate output for original.")

            # 3. Assemble segments
            segments: List[DiarizedSegment] = []
            orig_text_parts: List[str] = []
            eng_text_parts: List[str] = []

            for idx, entry in enumerate(entries, start=1):
                seg_id = f"seg_{idx}"
                speaker_raw = entry.get("speaker_id", f"speaker_{idx}")
                start_sec = round(float(entry.get("start_time_seconds", 0.0)), 2)
                end_sec = round(float(entry.get("end_time_seconds", 0.0)), 2)
                eng_text = (entry.get("transcript") or "").strip()

                if is_english or not orig_entries or idx - 1 >= len(orig_entries):
                    orig_text = eng_text
                else:
                    orig_text = (orig_entries[idx - 1].get("transcript") or "").strip() or eng_text

                segments.append(
                    DiarizedSegment(
                        segment_id=seg_id,
                        speaker_raw=speaker_raw,
                        text_original=orig_text,
                        text_english=eng_text,
                        start_time=start_sec,
                        end_time=end_sec,
                    )
                )
                orig_text_parts.append(orig_text)
                eng_text_parts.append(eng_text)

            log_sarvam_segments(cid, segments)

            final_orig_text = orig_full_transcript or " ".join(orig_text_parts) if not is_english else english_transcript
            final_eng_text = english_transcript or " ".join(eng_text_parts)

            return TranscriptionResult(
                language=detected_lang,
                transcript_original_text=final_orig_text,
                transcript_english_text=final_eng_text,
                segments=segments,
            )

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
