"""
Vigil — Debug Logger (backend/observability/debug_logger.py)

Writes detailed, human-readable debug logs for every pipeline stage:
  - Ingestion (file validation, audio metadata)
  - Sarvam (raw API response, all segments)
  - Speaker mapping (Gemini input/output)
  - Detection (every candidate, regulation retrieval chunks)
  - Investigator (full prompt to Bedrock/Gemini, raw model response, parsed output)

Enable with env var:  VIGIL_DEBUG_PIPELINE=true
Log file location:    <project_root>/logs/debug_pipeline.log

All log entries are also printed to stdout.
NEVER redact or truncate — full payloads for debugging.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─── Setup ───────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LOG_DIR = _PROJECT_ROOT / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "debug_pipeline.log"

_ENABLED = os.getenv("VIGIL_DEBUG_PIPELINE", "false").lower() in ("true", "1", "yes")

_debug_logger = logging.getLogger("vigil.debug_pipeline")
_debug_logger.setLevel(logging.DEBUG)
_debug_logger.propagate = False

if not _debug_logger.handlers:
    _fmt = logging.Formatter("%(message)s")
    _fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(_fmt)
    _debug_logger.addHandler(_fh)

    # Reconfigure stdout to UTF-8 on Windows (avoids cp1252 UnicodeEncodeError)
    try:
        _stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)
    except Exception:
        _stdout = sys.stdout
    _sh = logging.StreamHandler(_stdout)
    _sh.setLevel(logging.DEBUG)
    _sh.setFormatter(_fmt)
    _debug_logger.addHandler(_sh)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def _sep(char: str = "─", width: int = 100) -> str:
    return char * width

def _header(title: str) -> str:
    return f"\n{_sep('═')}\n  [{_ts()}]  {title}\n{_sep('═')}"

def _section(title: str) -> str:
    return f"\n{_sep()}\n  {title}\n{_sep()}"

def _dump(obj: Any, indent: int = 2) -> str:
    try:
        return json.dumps(obj, indent=indent, ensure_ascii=False, default=str)
    except Exception:
        return repr(obj)

def _emit(msg: str) -> None:
    if _ENABLED:
        _debug_logger.debug(msg)


def is_debug_enabled() -> bool:
    return _ENABLED


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1: INGESTION
# ══════════════════════════════════════════════════════════════════════════════

def log_ingestion_start(call_id: str, file_path: str, file_size_bytes: int) -> None:
    _emit(
        _header(f"INGESTION START  |  call_id={call_id}") +
        f"\n  File    : {file_path}"
        f"\n  Size    : {file_size_bytes:,} bytes"
    )


def log_audio_metadata(call_id: str, duration_sec: float, format_info: Dict[str, Any]) -> None:
    _emit(
        _section(f"AUDIO METADATA  |  call_id={call_id}") +
        f"\n  Duration : {duration_sec:.2f}s  ({duration_sec/60:.1f} min)"
        f"\n  Format   : {_dump(format_info)}"
    )


def log_ingestion_success(call_id: str, es_doc_id: str) -> None:
    _emit(
        _section(f"INGESTION SUCCESS  |  call_id={call_id}") +
        f"\n  ES doc_id : {es_doc_id}"
    )


def log_ingestion_failure(call_id: str, reason: str, exc: Optional[Exception] = None) -> None:
    _emit(
        _section(f"INGESTION FAILURE  |  call_id={call_id}") +
        f"\n  Reason    : {reason}"
        f"\n  Exception : {exc}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2: SARVAM TRANSCRIPTION
# ══════════════════════════════════════════════════════════════════════════════

def log_sarvam_job_created(call_id: str, job_id: str, job_type: str) -> None:
    _emit(
        _section(f"SARVAM JOB CREATED  |  call_id={call_id}") +
        f"\n  Job ID   : {job_id}"
        f"\n  Job Type : {job_type}"
    )


def log_sarvam_job_completed(call_id: str, job_id: str, job_type: str, duration_sec: float) -> None:
    _emit(
        _section(f"SARVAM JOB COMPLETED  |  call_id={call_id}") +
        f"\n  Job ID   : {job_id}"
        f"\n  Job Type : {job_type}"
        f"\n  Duration : {duration_sec:.1f}s"
    )


def log_sarvam_raw_response(call_id: str, job_type: str, raw_data: Dict[str, Any]) -> None:
    _emit(
        _section(f"SARVAM RAW RESPONSE  |  call_id={call_id}  |  job={job_type}") +
        f"\n  language_code : {raw_data.get('language_code', 'N/A')}"
        f"\n  transcript (first 500 chars):\n"
        f"    {str(raw_data.get('transcript', ''))[:500]}"
        f"\n\n  Full raw_data:\n" + _dump(raw_data)
    )


def log_sarvam_segments(call_id: str, segments: List[Any]) -> None:
    lines = [f"\n  Total segments: {len(segments)}\n"]
    for i, seg in enumerate(segments, 1):
        lines.append(
            f"  [{i:03d}]  speaker={getattr(seg, 'speaker_raw', '?'):15s}"
            f"  [{getattr(seg, 'start_time', 0):7.1f}s - {getattr(seg, 'end_time', 0):7.1f}s]"
            f"\n         orig : '{getattr(seg, 'text_original', '')[:80]}'"
            f"\n         eng  : '{getattr(seg, 'text_english', '')[:80]}'\n"
        )
    _emit(
        _section(f"SARVAM ALL SEGMENTS  |  call_id={call_id}") +
        "\n".join(lines)
    )


def log_sarvam_failure(call_id: str, attempt: int, exc: Exception) -> None:
    _emit(
        _section(f"SARVAM FAILURE  |  call_id={call_id}  |  attempt={attempt}") +
        f"\n  Exception : {exc}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3: SPEAKER MAPPING
# ══════════════════════════════════════════════════════════════════════════════

def log_speaker_mapping_prompt(call_id: str, prompt: str) -> None:
    _emit(
        _section(f"SPEAKER MAPPING — PROMPT INPUT  |  call_id={call_id}") +
        f"\n{'▼'*80}\n" + prompt + f"\n{'▲'*80}"
    )


def log_speaker_mapping_output(call_id: str, raw_response: str, mapping_result: Dict[str, Any]) -> None:
    method = mapping_result.get("method", "LLM").upper()
    _emit(
        _section(f"SPEAKER MAPPING — OUTPUT ({method})  |  call_id={call_id}") +
        f"\n  Raw response:\n    {raw_response[:500]}"
        f"\n\n  Parsed mapping:\n" + _dump(mapping_result)
    )


def log_speaker_mapping_fallback(call_id: str, reason: str) -> None:
    _emit(
        _section(f"SPEAKER MAPPING — FALLBACK (heuristic)  |  call_id={call_id}") +
        f"\n  Reason: {reason}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 4: DETECTION — CANDIDATE BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def log_detection_start(call_id: str, segment_count: int) -> None:
    _emit(
        _header(f"DETECTION ENGINE START  |  call_id={call_id}") +
        f"\n  Transcript segments: {segment_count}"
    )


def log_deterministic_rule_fired(call_id: str, rule_name: str, segment_text: str, match: str) -> None:
    _emit(
        _section(f"DETERMINISTIC RULE FIRED  |  call_id={call_id}") +
        f"\n  Rule    : {rule_name}"
        f"\n  Match   : '{match}'"
        f"\n  Segment : '{segment_text[:300]}'"
    )


def log_candidate_built(call_id: str, candidate: Dict[str, Any]) -> None:
    _emit(
        _section(
            f"CANDIDATE BUILT  |  call_id={call_id}  "
            f"|  id={candidate.get('candidate_id', '?')}"
        ) +
        f"\n  Category   : {candidate.get('category', '?')}"
        f"\n  DetType    : {candidate.get('detection_type', '?')}"
        f"\n  Rule       : {candidate.get('rule_fired', '?')}"
        f"\n  Confidence : {candidate.get('confidence_signal', '?')}"
        f"\n  Summary    : {candidate.get('summary', '?')}"
        f"\n\n  Full candidate:\n" + _dump(candidate)
    )


def log_detection_summary(call_id: str, total_candidates: int) -> None:
    _emit(
        _section(f"DETECTION COMPLETE  |  call_id={call_id}") +
        f"\n  Total candidates produced: {total_candidates}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 5: REGULATION RETRIEVAL
# ══════════════════════════════════════════════════════════════════════════════

def log_regulation_retrieval(
    call_id: str,
    candidate_id: str,
    category: str,
    bm25_query: str,
    semantic_query: str,
    bm25_hits: Dict[str, Any],
    semantic_hits: Dict[str, Any],
    final_chunks: List[Dict[str, Any]],
) -> None:
    lines = [
        _section(
            f"REGULATION RETRIEVAL  |  call_id={call_id}  "
            f"|  candidate={candidate_id}  |  category={category}"
        ),
        f"\n  BM25 query     : {bm25_query}",
        f"\n  Semantic query : {semantic_query}",
        f"\n\n  BM25 raw hits ({len(bm25_hits)}):",
    ]
    for cid, data in list(bm25_hits.items())[:10]:
        src = data.get("source", {})
        lines.append(f"\n    score={data.get('score', 0):.4f}  {cid}  '{src.get('citation_label','')}'")

    lines.append(f"\n\n  Semantic raw hits ({len(semantic_hits)}):")
    for cid, data in list(semantic_hits.items())[:10]:
        src = data.get("source", {})
        lines.append(f"\n    score={data.get('score', 0):.4f}  {cid}  '{src.get('citation_label','')}'")

    lines.append(f"\n\n  ── FINAL RANKED CHUNKS (top {len(final_chunks)}) ──")
    for i, chunk in enumerate(final_chunks, 1):
        lines.append(
            f"\n  [{i}] {chunk.get('chunk_id', '?')}"
            f"\n       citation    : {chunk.get('citation_label', '?')}"
            f"\n       bm25        : {chunk.get('bm25_score', 0):.4f}"
            f"\n       semantic    : {chunk.get('semantic_score', 0):.4f}"
            f"\n       heading     : {chunk.get('heading', '')[:80]}"
            f"\n       clause_text :\n         {chunk.get('clause_text', '')[:600]}\n"
        )
    _emit("".join(str(l) for l in lines))


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 6: INVESTIGATOR AGENT
# ══════════════════════════════════════════════════════════════════════════════

def log_investigator_start(call_id: str, candidate_id: str, category: str) -> None:
    _emit(
        _header(f"INVESTIGATOR AGENT  |  call_id={call_id}  |  candidate={candidate_id}") +
        f"\n  Category : {category}"
    )


def log_investigator_context(
    call_id: str,
    candidate_id: str,
    customer_ctx: Dict[str, Any],
    product_ctx: Dict[str, Any],
    rm_history: Tuple[int, List[str]],
) -> None:
    _emit(
        _section(f"INVESTIGATOR — CONTEXT  |  candidate={candidate_id}") +
        f"\n  Customer profile :\n{_dump(customer_ctx)}"
        f"\n\n  Product profile  :\n{_dump(product_ctx)}"
        f"\n\n  RM prior findings: count={rm_history[0]}"
        f"\n  RM categories    : {rm_history[1]}"
    )


def log_investigator_prompt(call_id: str, candidate_id: str, prompt: str) -> None:
    char_count = len(prompt)
    token_est = char_count // 4
    _emit(
        _section(
            f"INVESTIGATOR — FULL PROMPT  |  call_id={call_id}  "
            f"|  candidate={candidate_id}  "
            f"|  ~{char_count} chars  ~{token_est} tokens"
        ) +
        f"\n{'▼'*80}\n" + prompt + f"\n{'▲'*80}"
    )


def log_investigator_model_raw(
    call_id: str,
    candidate_id: str,
    provider: str,
    raw_text: str,
) -> None:
    _emit(
        _section(
            f"INVESTIGATOR — RAW MODEL RESPONSE  |  call_id={call_id}  "
            f"|  candidate={candidate_id}  |  provider={provider}"
        ) +
        f"\n{'▼'*80}\n" + raw_text + f"\n{'▲'*80}"
    )


def log_investigator_parsed(
    call_id: str,
    candidate_id: str,
    provider: str,
    parsed: Dict[str, Any],
) -> None:
    _emit(
        _section(
            f"INVESTIGATOR — PARSED OUTPUT  |  call_id={call_id}  "
            f"|  candidate={candidate_id}  |  provider={provider}"
        ) +
        f"\n{_dump(parsed)}"
    )


def log_investigator_guardrail(call_id: str, candidate_id: str, check: str, result: str, detail: str) -> None:
    icon = "✓" if result == "PASS" else "✗"
    _emit(
        _section(f"INVESTIGATOR — GUARDRAIL  |  candidate={candidate_id}") +
        f"\n  {icon} {check} → {result}"
        f"\n  Detail: {detail}"
    )


def log_investigator_outcome(
    call_id: str,
    candidate_id: str,
    outcome: str,
    finding_id: Optional[str],
    provider: Optional[str],
    reasoning: str,
) -> None:
    _emit(
        _section(f"INVESTIGATOR — OUTCOME  |  call_id={call_id}  |  candidate={candidate_id}") +
        f"\n  Outcome    : {outcome}"
        f"\n  Finding ID : {finding_id or 'None (dismissed)'}"
        f"\n  Provider   : {provider or 'N/A'}"
        f"\n  Reasoning  : {reasoning}"
    )


def log_investigator_dual_write(
    call_id: str,
    finding_id: str,
    es_success: bool,
    mysql_success: bool,
    es_error: Optional[str] = None,
    mysql_error: Optional[str] = None,
) -> None:
    _emit(
        _section(f"INVESTIGATOR — DUAL WRITE  |  call_id={call_id}") +
        f"\n  Finding ID  : {finding_id}"
        f"\n  ES write    : {'✓ OK' if es_success else f'✗ FAILED  {es_error}'}"
        f"\n  MySQL write : {'✓ OK' if mysql_success else f'✗ FAILED  {mysql_error}'}"
    )


def log_investigator_call_summary(
    call_id: str,
    total: int,
    confirmed: int,
    dismissed: int,
    dismissed_no_citation: int,
) -> None:
    _emit(
        _header(f"INVESTIGATOR CALL COMPLETE  |  call_id={call_id}") +
        f"\n  Total candidates       : {total}"
        f"\n  Confirmed (finding)    : {confirmed}"
        f"\n  Dismissed (not genuine): {dismissed}"
        f"\n  Dismissed (no citation): {dismissed_no_citation}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# GENERAL
# ══════════════════════════════════════════════════════════════════════════════

def log_pipeline_error(stage: str, call_id: str, exc: Exception, extra: Optional[Dict] = None) -> None:
    _emit(
        _section(f"PIPELINE ERROR  |  stage={stage}  |  call_id={call_id}") +
        f"\n  Exception : {type(exc).__name__}: {exc}" +
        (f"\n  Extra     : {_dump(extra)}" if extra else "")
    )
