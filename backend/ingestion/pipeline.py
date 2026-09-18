"""
Vigil — Phase 5: Audio Ingestion Pipeline Orchestrator.
Phase 13: Instrumented with Elastic APM native spans.

Orchestrates:
1. File stability check (wait for file write completion)
2. Filename validation & MySQL RM/Customer lookup
3. Audio format & duration validation
4. Sarvam transcription + diarization (verbatim original + English translation)
5. Gemini-primary speaker role mapping (with timing heuristic fallback)
6. Elasticsearch document preparation matching Phase 3.1 'calls' schema
7. Index document into 'calls' index and read-back verification
8. File movement: CallAudio-Archive/ on success, CallAudio-Failed/ with sidecar error log on failure

Elastic APM spans (native elastic-apm, NOT OpenTelemetry):
  audio.ingestion      — steps 1-3
  sarvam.transcription — step 4
  transcript.normalization — step 5
  elasticsearch.index  — step 7
"""

import os
import json
import shutil
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from dotenv import load_dotenv

# Phase 13: Elastic APM instrumentation (native elastic-apm)
from backend.observability.apm import apm_span, report_error, set_transaction_labels
from backend.observability.logging_config import log_pipeline_event
from backend.api.routes.observability import record_pipeline_error

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)

# Debug logger (enabled via VIGIL_DEBUG_PIPELINE=true)
try:
    from backend.observability.debug_logger import (
        log_ingestion_start,
        log_audio_metadata,
        log_ingestion_success,
        log_ingestion_failure,
    )
except ImportError:
    def log_ingestion_start(*a, **kw): pass
    def log_audio_metadata(*a, **kw): pass
    def log_ingestion_success(*a, **kw): pass
    def log_ingestion_failure(*a, **kw): pass

from backend.ingestion.filename_parser import (
    parse_and_validate_filename,
    FilenameValidationError,
    ParsedFileInfo,
)
from backend.ingestion.stability_check import (
    wait_for_file_stability,
    FileStabilityError,
)
from backend.ingestion.audio_validator import (
    validate_and_extract_duration,
    AudioValidationError,
)
from backend.sarvam.sarvam_client import (
    SarvamClient,
    TranscriptionError,
    TranscriptionResult,
)
from backend.ingestion.speaker_mapper import (
    map_speakers,
    SpeakerMappingOutput,
)
from backend.indexing.create_index import get_es_client

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CALL_AUDIO_DIR = PROJECT_ROOT / "CallAudio"
ARCHIVE_DIR = PROJECT_ROOT / "CallAudio-Archive"
FAILED_DIR = PROJECT_ROOT / "CallAudio-Failed"
CALLS_INDEX = "calls"


class IngestionPipelineError(Exception):
    """General error for pipeline failures with a specific error code."""
    def __init__(self, reason: str, message: str = ""):
        self.reason = reason
        super().__init__(message or reason)


def _handle_failure(source_file: Path, reason: str, details: str = ""):
    """Moves rejected file to CallAudio-Failed/ and writes a sidecar error JSON."""
    FAILED_DIR.mkdir(parents=True, exist_ok=True)
    dest_file = FAILED_DIR / source_file.name

    # If already exists in failed, add timestamp to avoid clobber
    if dest_file.exists():
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest_file = FAILED_DIR / f"{source_file.stem}_{timestamp}{source_file.suffix}"

    try:
        shutil.move(str(source_file), str(dest_file))
        logger.info(f"Moved failed file to: {dest_file}")
    except Exception as exc:
        logger.error(f"Failed to move file to {dest_file}: {exc}")

    # Write sidecar error JSON
    sidecar_path = dest_file.with_suffix(dest_file.suffix + ".error.json")
    error_payload = {
        "original_filename": source_file.name,
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "details": details,
    }
    try:
        with open(sidecar_path, "w", encoding="utf-8") as f:
            json.dump(error_payload, f, indent=2)
        logger.info(f"Wrote failure sidecar log to: {sidecar_path}")
    except Exception as exc:
        logger.error(f"Failed to write sidecar error file {sidecar_path}: {exc}")


def process_audio_file(
    file_path: str | Path,
    sarvam_client: Optional[SarvamClient] = None,
    es_client=None,
) -> Dict[str, Any]:
    """
    Runs the full ingestion pipeline for a single audio file.
    Phase 13: Instrumented with Elastic APM native spans.

    Args:
        file_path: Path to the audio file in CallAudio/
        sarvam_client: Optional pre-initialized SarvamClient
        es_client: Optional pre-initialized Elasticsearch client

    Returns:
        Dict: Indexed Elasticsearch document on success, or error dict on rejection.
    """
    src_path = Path(file_path).resolve()
    filename = src_path.name
    pipeline_start_ms = time.perf_counter() * 1000
    logger.info(f"=== Starting Ingestion Pipeline for: '{filename}' ===")

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)

    if not src_path.exists():
        logger.error(f"Source file does not exist: {src_path}")
        return {"status": "FAILED", "reason": "FILE_NOT_FOUND", "file": filename}

    # Phase 13: APM transaction labels (safe identifiers only)
    # call_id not yet known — will be set after filename parse

    with apm_span("audio.ingestion", "app", "pipeline", labels={"stage": "audio.ingestion"}):
        # STEP 1: Filename validation & MySQL lookup
        try:
            parsed: ParsedFileInfo = parse_and_validate_filename(src_path)
            logger.info(f"Filename validated: RM={parsed.rm_id}, Customer={parsed.customer_id}")
            # Set APM transaction labels with safe identifiers
            set_transaction_labels({"call_id": parsed.call_id, "rm_id": parsed.rm_id})
            log_ingestion_start(parsed.call_id, str(src_path), src_path.stat().st_size if src_path.exists() else 0)
        except FilenameValidationError as fve:
            logger.warning(f"Step 1 failed for '{filename}': {fve.reason} - {fve}")
            report_error(fve, {"stage": "filename_validation", "reason": fve.reason})
            record_pipeline_error("audio.ingestion", fve.reason, str(fve)[:200])
            log_ingestion_failure(filename, fve.reason, fve)
            _handle_failure(src_path, fve.reason, str(fve))
            return {"status": "FAILED", "reason": fve.reason, "file": filename, "details": str(fve)}

        # STEP 2: File stability check
        try:
            wait_for_file_stability(src_path, delay_seconds=2.0, max_attempts=3)
            logger.info(f"Step 2: File stability confirmed for '{filename}'.")
        except FileStabilityError as fse:
            logger.warning(f"Step 2 failed for '{filename}': {fse.reason} - {fse}")
            report_error(fse, {"stage": "stability_check", "reason": fse.reason})
            record_pipeline_error("audio.ingestion", fse.reason, str(fse)[:200], call_id=filename)
            log_ingestion_failure(getattr(parsed, 'call_id', filename), fse.reason, fse)
            _handle_failure(src_path, fse.reason, str(fse))
            return {"status": "FAILED", "reason": fse.reason, "file": filename, "details": str(fse)}

        # Phase 12: Record real wall-clock processing_started_at
        processing_started_at = datetime.now(timezone.utc).isoformat()

        # STEP 3: Audio format & duration validation
        try:
            duration_seconds = validate_and_extract_duration(src_path)
            logger.info(f"Step 3: Audio valid, duration: {duration_seconds}s.")
            log_audio_metadata(parsed.call_id, duration_seconds, {"duration_seconds": duration_seconds, "filename": filename})
        except AudioValidationError as ave:
            logger.warning(f"Step 3 failed for '{filename}': {ave.reason} - {ave}")
            report_error(ave, {"stage": "audio_validation", "reason": ave.reason})
            record_pipeline_error("audio.ingestion", ave.reason, str(ave)[:200],
                                  call_id=getattr(parsed, 'call_id', None))
            log_ingestion_failure(getattr(parsed, 'call_id', filename), ave.reason, ave)
            _handle_failure(src_path, ave.reason, str(ave))
            return {"status": "FAILED", "reason": ave.reason, "file": filename, "details": str(ave)}

    # End audio.ingestion span

    # STEP 4: Sarvam transcription + diarization
    # Phase 13: Wrapped in its own APM span for STT latency visibility
    stt_start_ms = time.perf_counter() * 1000
    log_pipeline_event(logger, "sarvam.transcription.started", call_id=parsed.call_id, stage="sarvam", status="started")
    try:
        with apm_span("sarvam.transcription", "external", "sarvam",
                      labels={"call_id": parsed.call_id}):
            client = sarvam_client or SarvamClient()
            transcription: TranscriptionResult = client.process_audio(src_path, call_id=parsed.call_id)
        stt_ms = (time.perf_counter() * 1000) - stt_start_ms
        logger.info(
            f"Step 4: Sarvam completed. Language={transcription.language}, "
            f"Segments={len(transcription.segments)}, duration={stt_ms:.0f}ms"
        )
        log_pipeline_event(logger, "sarvam.transcription.completed", call_id=parsed.call_id,
                           stage="sarvam", status="success", duration_ms=stt_ms)
    except TranscriptionError as te:
        logger.warning(f"Step 4 failed for '{filename}': {te.reason} - {te}")
        report_error(te, {"stage": "sarvam_transcription", "call_id": parsed.call_id, "reason": te.reason})
        record_pipeline_error("sarvam.transcription", te.reason, str(te)[:200], call_id=parsed.call_id)
        log_pipeline_event(logger, "sarvam.transcription.failed", call_id=parsed.call_id,
                           stage="sarvam", status="failed", level=logging.ERROR)
        log_ingestion_failure(parsed.call_id, te.reason, te)
        _handle_failure(src_path, te.reason, str(te))
        return {"status": "FAILED", "reason": te.reason, "file": filename, "details": str(te)}
    except Exception as exc:
        logger.error(f"Step 4 unexpected exception for '{filename}': {exc}")
        report_error(exc, {"stage": "sarvam_transcription", "call_id": parsed.call_id})
        record_pipeline_error("sarvam.transcription", "TRANSCRIPTION_FAILED", str(exc)[:200], call_id=parsed.call_id)
        log_ingestion_failure(parsed.call_id, "TRANSCRIPTION_FAILED", exc)
        _handle_failure(src_path, "TRANSCRIPTION_FAILED", str(exc))
        return {"status": "FAILED", "reason": "TRANSCRIPTION_FAILED", "file": filename, "details": str(exc)}

    # STEP 5: Speaker role mapping
    segments_dicts = [
        {
            "segment_id": s.segment_id,
            "speaker_raw": s.speaker_raw,
            "text_original": s.text_original,
            "text_english": s.text_english,
            "start_time": s.start_time,
            "end_time": s.end_time,
        }
        for s in transcription.segments
    ]
    speaker_output: SpeakerMappingOutput = map_speakers(
        segments=segments_dicts,
        rm_name=parsed.rm_name,
        customer_name=parsed.customer_name,
        call_id=parsed.call_id,
    )
    logger.info(
        f"Step 5: Speaker mapping decided by '{speaker_output.method}': {speaker_output.mapping}"
    )

    # If Bedrock and Gemini failed/unavailable and we fell back to heuristic, record it in
    # the observability error ring so it surfaces in the Error Stream tab.
    if speaker_output.method == "heuristic_fallback":
        _fallback_reason = (speaker_output.reasoning or "Speaker mapping fell back to timing heuristic")[:400]
        record_pipeline_error(
            stage="speaker_mapping",
            error_type="SPEAKER_MAPPING_FALLBACK",
            message=f"Speaker mapping fell back to heuristic: {_fallback_reason}",
            call_id=parsed.call_id,
        )

    # Determine archive path
    final_archive_path = ARCHIVE_DIR / filename
    if final_archive_path.exists():
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        final_archive_path = ARCHIVE_DIR / f"{src_path.stem}_{timestamp}{src_path.suffix}"

    # STEP 6: Build call document matching 'calls' ES mapping
    indexed_segments = []
    for s in transcription.segments:
        assigned_role = speaker_output.mapping.get(s.speaker_raw, "CUSTOMER")
        # Ensure role is strictly RM or CUSTOMER
        if assigned_role not in ("RM", "CUSTOMER"):
            assigned_role = "CUSTOMER"

        indexed_segments.append({
            "segment_id": s.segment_id,
            "speaker": assigned_role,
            "text_original": s.text_original,
            "text_english": s.text_english,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "is_violation": False,
        })

    call_document = {
        "call_id": parsed.call_id,
        "rm_id": parsed.rm_id,
        "customer_id": parsed.customer_id,
        "date_time": parsed.date_time,
        "duration_seconds": int(round(duration_seconds)),
        "audio_file_path": str(final_archive_path).replace("\\", "/"),
        "processing_status": "TRANSCRIBED",
        "processing_started_at": processing_started_at,
        "language": transcription.language,
        "transcript_original_text": transcription.transcript_original_text,
        "transcript_english_text": transcription.transcript_english_text,
        "transcript_semantic": transcription.transcript_english_text,
        "transcript_segments": indexed_segments,
        "speaker_mapping_method": speaker_output.method,
        "has_violation": False,
        "finding_ids": [],
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }

    # STEP 7: Index call document into Elasticsearch
    # Phase 13: Wrapped in APM span for ES indexing latency visibility
    log_pipeline_event(logger, "elasticsearch.index.started", call_id=parsed.call_id,
                       stage="elasticsearch", status="started")
    try:
        with apm_span("elasticsearch.index", "db", "elasticsearch",
                      labels={"call_id": parsed.call_id, "index": CALLS_INDEX}):
            es = es_client or get_es_client()
            logger.info(f"Step 7: Indexing document '{parsed.call_id}' into '{CALLS_INDEX}'...")
            es.index(index=CALLS_INDEX, id=parsed.call_id, document=call_document, refresh=True)

            # Confirm write by reading back
            readback = es.get(index=CALLS_INDEX, id=parsed.call_id)
            if not readback.get("found"):
                raise RuntimeError(f"Read-back failed: document '{parsed.call_id}' not found after index.")
        logger.info(f"Document '{parsed.call_id}' successfully indexed and verified in '{CALLS_INDEX}'.")
        log_pipeline_event(logger, "elasticsearch.index.completed", call_id=parsed.call_id,
                           stage="elasticsearch", status="success")
    except Exception as exc:
        logger.error(f"Step 7 indexing failed for '{parsed.call_id}': {exc}")
        report_error(exc, {"stage": "elasticsearch_index", "call_id": parsed.call_id})
        record_pipeline_error("elasticsearch.index", "INDEXING_FAILED", str(exc)[:200], call_id=parsed.call_id)
        log_pipeline_event(logger, "elasticsearch.index.failed", call_id=parsed.call_id,
                           stage="elasticsearch", status="failed", level=logging.ERROR)
        _handle_failure(src_path, "INDEXING_FAILED", str(exc))
        return {"status": "FAILED", "reason": "INDEXING_FAILED", "file": filename, "details": str(exc)}

    # STEP 8: Move file to CallAudio-Archive/
    try:
        shutil.move(str(src_path), str(final_archive_path))
        logger.info(f"Step 8: File successfully moved to archive: {final_archive_path}")
    except Exception as exc:
        logger.error(f"Failed to move file to archive {final_archive_path}: {exc}")
        # Note: document is already indexed, so we log error but document exists

    total_ms = (time.perf_counter() * 1000) - pipeline_start_ms
    log_pipeline_event(logger, "audio.ingestion.completed", call_id=parsed.call_id,
                       stage="pipeline", status="success", duration_ms=total_ms)
    log_ingestion_success(parsed.call_id, parsed.call_id)
    logger.info(f"=== Ingestion Pipeline COMPLETED Successfully for '{filename}' ({total_ms:.0f}ms) ===")
    return {
        "status": "SUCCESS",
        "call_id": parsed.call_id,
        "file": filename,
        "archive_path": str(final_archive_path),
        "document": call_document,
        "speaker_mapping_method": speaker_output.method,
        "speaker_reasoning": speaker_output.reasoning,
    }
