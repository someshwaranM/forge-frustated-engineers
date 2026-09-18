"""
Vigil — Phase 13: Elastic Observability API Routes (backend/api/routes/observability.py)

Exposes four secure endpoints that aggregate real operational telemetry
from Elasticsearch and MySQL. No Elastic credentials are exposed to the browser.

Endpoints:
  GET /api/observability/summary   — operational KPIs (calls, findings, cases, success rate)
  GET /api/observability/pipeline  — per-stage latency from real pipeline timestamps
  GET /api/observability/errors    — recent pipeline errors from ES + in-memory error log
  GET /api/observability/services  — live service health (proxies /api/system/health)

All endpoints gracefully handle Elasticsearch/MySQL unavailability.
No mock values — all data is from real application activity.
"""

import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Tuple

from fastapi import APIRouter

from backend.elastic.client import get_es_client
from backend.db.session import get_db_connection
from backend.observability.stage_timer import get_pipeline_latency_summary
from backend.observability.apm import is_apm_enabled, get_apm_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/observability", tags=["Observability"])

# ---------------------------------------------------------------------------
# In-memory error ring buffer
# Stores recent error events for the /errors endpoint.
# Populated by:
#   1. record_pipeline_error() — called explicitly from pipeline code
#   2. RingBufferLogHandler   — auto-captures any logger.error() / logger.critical()
#      across the entire backend (chat agent, route handlers, agents, etc.)
# Max 200 entries — oldest are discarded.
# ---------------------------------------------------------------------------
_error_ring: Deque[Dict[str, Any]] = deque(maxlen=200)


class RingBufferLogHandler(logging.Handler):
    """
    A Python logging.Handler that captures ERROR and CRITICAL log records
    from ANY logger in the application into the shared _error_ring buffer.

    This means every logger.error(...) call — including those in chat_agent,
    route handlers, agents, etc. — is automatically surfaced in the
    Observability Error Stream tab without requiring manual instrumentation.
    """

    # Loggers to suppress from the ring to avoid noise (e.g. elastic transport INFO)
    _SUPPRESS_PREFIXES = (
        "elastic_transport",
        "urllib3",
        "httpcore",
        "httpx",
    )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Skip noisy low-signal loggers
            for prefix in self._SUPPRESS_PREFIXES:
                if record.name.startswith(prefix):
                    return

            entry: Dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": self._infer_stage(record.name),
                "error_type": record.levelname,
                "message": self.format(record)[:600],
                "logger": record.name,
                "source": "log",
            }

            # Attach exception type name if available
            if record.exc_info and record.exc_info[0] is not None:
                entry["error_type"] = record.exc_info[0].__name__

            _error_ring.appendleft(entry)
        except Exception:
            pass  # Never let logging infrastructure raise

    @staticmethod
    def _infer_stage(logger_name: str) -> str:
        """Map logger name to a human-readable pipeline stage."""
        name = logger_name.lower()
        if "chat" in name:
            return "chat"
        if "agent" in name or "investigat" in name:
            return "investigation"
        if "detect" in name:
            return "detection"
        if "speaker" in name or "speaker_map" in name:
            return "speaker_mapping"
        if "ingest" in name or "audio" in name or "sarvam" in name:
            return "ingestion"
        if "route" in name or "api" in name:
            return "api"
        if "elastic" in name or "es" in name:
            return "elasticsearch"
        return "system"


def configure_errors_log_capture() -> None:
    """
    Attach the RingBufferLogHandler to the root logger so that every
    ERROR+ log record emitted anywhere in the backend is automatically
    captured into the error ring buffer.

    Call once at application startup (after configure_logging()).
    """
    handler = RingBufferLogHandler()
    handler.setLevel(logging.ERROR)
    # Use a plain formatter — message only, no timestamps (ring stores its own)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    # Avoid duplicate handlers if called multiple times (e.g. during hot-reload)
    if not any(isinstance(h, RingBufferLogHandler) for h in root.handlers):
        root.addHandler(handler)
        logging.getLogger(__name__).info(
            "[Observability] RingBufferLogHandler attached — auto-capturing ERROR+ events"
        )


def record_pipeline_error(
    stage: str,
    error_type: str,
    message: str,
    call_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Record a pipeline error into the in-memory ring buffer.
    Call this from pipeline stages when a significant error occurs.
    Never include PII, API keys, passwords, raw transcripts.
    """
    entry: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "error_type": error_type,
        "message": message[:500],  # Truncate to avoid runaway strings
        "source": "pipeline",
    }
    if call_id:
        entry["call_id"] = call_id
    if extra:
        # Allow only safe string fields
        for k, v in extra.items():
            if isinstance(v, (str, int, float, bool)) and len(str(v)) < 200:
                entry[k] = v
    _error_ring.appendleft(entry)


# ---------------------------------------------------------------------------
# Helper: format seconds → human-readable string
# ---------------------------------------------------------------------------

def _fmt_seconds(seconds: Optional[float]) -> Optional[str]:
    if seconds is None:
        return None
    if seconds < 1.0:
        return f"{seconds * 1000:.0f}ms"
    return f"{seconds:.2f}s"


# ---------------------------------------------------------------------------
# GET /api/observability/summary
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=Dict[str, Any])
def get_observability_summary():
    """
    Returns real operational KPIs for the Vigil system.
    Sources: Elasticsearch (calls, compliance_findings) + MySQL (compliance_case)
    """
    result: Dict[str, Any] = {
        "status": "ok",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "apm_enabled": is_apm_enabled(),
        "calls_processed": 0,
        "failed_calls": 0,
        "findings_generated": 0,
        "cases_created": 0,
        "processing_success_rate": None,
        "avg_processing_time_seconds": None,
        "data_sources": [],
    }

    # --- Elasticsearch ---
    try:
        es = get_es_client()

        # Total calls indexed
        calls_count = es.count(index="calls")
        result["calls_processed"] = calls_count.get("count", 0)
        result["data_sources"].append("elasticsearch:calls")

        # Failed calls (processing_status = FAILED)
        failed_resp = es.count(
            index="calls",
            query={"term": {"processing_status": "FAILED"}},
        )
        result["failed_calls"] = failed_resp.get("count", 0)

        # Total findings
        findings_count = es.count(index="compliance_findings")
        result["findings_generated"] = findings_count.get("count", 0)
        result["data_sources"].append("elasticsearch:compliance_findings")

        # Success rate
        total = result["calls_processed"]
        if total > 0:
            succeeded = total - result["failed_calls"]
            result["processing_success_rate"] = round((succeeded / total) * 100, 1)

        # Average end-to-end processing time (from stage timer data)
        try:
            latency = get_pipeline_latency_summary()
            e2e_mean = latency.get("headline", {}).get("mean_end_to_end_seconds")
            if e2e_mean is not None:
                result["avg_processing_time_seconds"] = e2e_mean
                result["avg_processing_time_human"] = _fmt_seconds(e2e_mean)
        except Exception:
            pass

    except Exception as exc:
        logger.warning(f"[Observability] ES summary query failed: {exc}")
        result["status"] = "partial"
        result["es_error"] = "Elasticsearch temporarily unavailable"

    # --- MySQL ---
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as total FROM compliance_case")
                row = cur.fetchone()
                result["cases_created"] = int(row["total"] if isinstance(row, dict) else row[0])
                result["data_sources"].append("mysql:compliance_case")
        finally:
            conn.close()
    except Exception as exc:
        logger.warning(f"[Observability] MySQL summary query failed: {exc}")
        result.setdefault("db_error", "Database temporarily unavailable")

    # Throughput (calls per hour, approximate from last N calls)
    result["data_freshness"] = "real-time"
    return result


# ---------------------------------------------------------------------------
# GET /api/observability/pipeline
# ---------------------------------------------------------------------------

@router.get("/pipeline", response_model=Dict[str, Any])
def get_observability_pipeline():
    """
    Returns per-stage pipeline performance metrics derived from real
    Elasticsearch document timestamps computed by the stage timer.

    Source: backend/observability/stage_timer.py (business-level timing)
    Also returns APM availability status for display in the frontend.
    """
    result: Dict[str, Any] = {
        "status": "ok",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "apm_enabled": is_apm_enabled(),
        "apm_service_name": "vigil-backend",
        "stages": {},
        "summary": {},
    }

    try:
        latency = get_pipeline_latency_summary()
        stages = latency.get("stages", {})

        # Map stage names to display-friendly info
        stage_display = {
            "ingestion": {
                "label": "Audio Ingestion",
                "description": "Filename validation + stability check + audio validation + Sarvam transcription + ES indexing",
            },
            "detection": {
                "label": "Compliance Detection",
                "description": "Deterministic rules + suitability checks + disclosure checks + regulation retrieval",
            },
            "investigation": {
                "label": "Investigator / AI",
                "description": "Bedrock/Gemini forensic investigation + finding + case creation",
            },
            "end_to_end": {
                "label": "End-to-End",
                "description": "Total time from audio received to case creation",
            },
        }

        for stage_key, stats in stages.items():
            display = stage_display.get(stage_key, {"label": stage_key.replace("_", " ").title(), "description": ""})
            result["stages"][stage_key] = {
                "label": display["label"],
                "description": display["description"],
                "count": stats.get("count", 0),
                "mean_seconds": stats.get("mean_seconds"),
                "median_seconds": stats.get("median_seconds"),
                "min_seconds": stats.get("min_seconds"),
                "max_seconds": stats.get("max_seconds"),
                "mean_human": _fmt_seconds(stats.get("mean_seconds")),
                "median_human": _fmt_seconds(stats.get("median_seconds")),
            }

        result["summary"] = {
            "total_calls_monitored": latency.get("total_calls_monitored", 0),
            "complete_pipeline_runs": latency.get("complete_pipeline_runs", 0),
            "legacy_or_partial_runs": latency.get("legacy_or_partial_runs", 0),
        }

        result["headline"] = latency.get("headline", {})

    except Exception as exc:
        logger.warning(f"[Observability] Pipeline metrics failed: {exc}")
        result["status"] = "unavailable"
        result["error"] = "Pipeline metrics temporarily unavailable"

    return result


# ---------------------------------------------------------------------------
# GET /api/observability/errors
# ---------------------------------------------------------------------------

@router.get("/errors", response_model=Dict[str, Any])
def get_observability_errors():
    """
    Returns recent pipeline errors from two sources:
    1. In-memory error ring buffer (populated by pipeline error events)
    2. Recent FAILED calls from Elasticsearch

    Combined and sorted by timestamp descending.
    """
    errors: List[Dict[str, Any]] = []

    # Source 1: In-memory ring buffer (pipeline explicit records + auto-captured log errors)
    for entry in list(_error_ring)[:50]:
        errors.append({
            "source": entry.get("source", "pipeline"),
            "timestamp": entry.get("timestamp"),
            "stage": entry.get("stage", "unknown"),
            "error_type": entry.get("error_type", "ERROR"),
            "message": entry.get("message", ""),
            "call_id": entry.get("call_id"),
            "logger": entry.get("logger"),
        })

    # Source 2: Failed calls from Elasticsearch
    try:
        es = get_es_client()

        # Calls with FAILED processing status
        failed_calls_resp = es.search(
            index="calls",
            query={"term": {"processing_status": "FAILED"}},
            sort=[{"indexed_at": {"order": "desc"}}],
            size=10,
            source=["call_id", "processing_status", "indexed_at", "failure_reason"],
        )
        for hit in failed_calls_resp.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            errors.append({
                "source": "elasticsearch",
                "timestamp": src.get("indexed_at"),
                "stage": "ingestion",
                "error_type": src.get("failure_reason", "PIPELINE_FAILED"),
                "message": f"Call {src.get('call_id', hit['_id'])} failed during ingestion",
                "call_id": src.get("call_id") or hit["_id"],
            })

        # Also check for calls stuck without detection completion (possible failures)
        # Only flag if indexed more than 10 minutes ago and never completed detection
        stuck_resp = es.search(
            index="calls",
            query={
                "bool": {
                    "must": [
                        {"term": {"processing_status": "TRANSCRIBED"}},
                    ],
                    "must_not": [
                        {"exists": {"field": "detection_completed_at"}},
                    ],
                    "filter": [
                        {"range": {"indexed_at": {"lte": "now-10m"}}}
                    ],
                }
            },
            sort=[{"indexed_at": {"order": "desc"}}],
            size=5,
            source=["call_id", "indexed_at"],
        )
        for hit in stuck_resp.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            errors.append({
                "source": "elasticsearch",
                "timestamp": src.get("indexed_at"),
                "stage": "detection",
                "error_type": "DETECTION_NOT_COMPLETED",
                "message": f"Call {src.get('call_id', hit['_id'])} stuck — detection not completed after 10min",
                "call_id": src.get("call_id") or hit["_id"],
            })

    except Exception as exc:
        logger.warning(f"[Observability] Error query from ES failed: {exc}")
        errors.append({
            "source": "system",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": "system",
            "error_type": "ES_UNAVAILABLE",
            "message": "Elasticsearch temporarily unavailable for error query",
            "call_id": None,
        })

    # Sort by timestamp descending (most recent first)
    def _ts_key(e: Dict[str, Any]) -> str:
        return e.get("timestamp") or "1970-01-01T00:00:00Z"

    errors.sort(key=_ts_key, reverse=True)

    return {
        "status": "ok",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "total_errors": len(errors),
        "errors": errors[:10],
    }


# ---------------------------------------------------------------------------
# GET /api/observability/services
# ---------------------------------------------------------------------------

@router.get("/services", response_model=Dict[str, Any])
def get_observability_services():
    """
    Returns live service health for all Vigil dependencies.
    Calls the existing system health logic and reshapes it for the observability page.
    Also includes Elastic APM service status.
    """
    from backend.api.routes.system import get_system_health

    health = get_system_health()
    services_raw = health.get("services", {})

    def _normalize_status(raw_status: str) -> str:
        """Normalize varied status strings to: healthy | degraded | unknown"""
        s = raw_status.upper()
        if s in ("CONNECTED", "HEALTHY", "OPERATIONAL", "ACTIVE (FALLBACK FIRED)"):
            return "healthy"
        if s in ("DISCONNECTED", "ERROR", "NOT_USED"):
            return "degraded"
        if s in ("STANDBY",):
            return "healthy"  # Configured and ready — treat as healthy
        return "unknown"

    services_out: List[Dict[str, Any]] = []

    # Vigil API itself
    services_out.append({
        "name": "Vigil API",
        "key": "api",
        "status": "healthy",
        "latency_ms": None,
        "message": "FastAPI application running",
    })

    # Elasticsearch
    es_data = services_raw.get("elasticsearch", {})
    services_out.append({
        "name": "Elasticsearch",
        "key": "elasticsearch",
        "status": _normalize_status(es_data.get("status", "unknown")),
        "latency_ms": es_data.get("latency_ms"),
        "message": es_data.get("message", ""),
        "cluster_name": es_data.get("cluster_name"),
        "build_flavor": es_data.get("build_flavor"),
    })

    # MySQL / Database
    db_data = services_raw.get("mysql", {})
    services_out.append({
        "name": "Database (MySQL)",
        "key": "database",
        "status": _normalize_status(db_data.get("status", "unknown")),
        "latency_ms": db_data.get("latency_ms"),
        "message": db_data.get("message", ""),
    })

    # Sarvam (ASR)
    sarvam_data = services_raw.get("sarvam", {})
    services_out.append({
        "name": "Sarvam (STT)",
        "key": "sarvam",
        "status": _normalize_status(sarvam_data.get("status", "NOT_USED")),
        "latency_ms": None,
        "message": sarvam_data.get("message", ""),
        "calls_transcribed": sarvam_data.get("calls_transcribed", 0),
        "last_call_id": sarvam_data.get("last_call_id"),
    })

    # Investigator (Bedrock primary)
    bedrock_data = services_raw.get("bedrock", {})
    gemini_data = services_raw.get("gemini", {})
    investigator_status = "healthy" if (
        bedrock_data.get("status") == "OPERATIONAL" or
        bedrock_data.get("status") == "STANDBY" or
        gemini_data.get("status") in ("STANDBY", "ACTIVE (FALLBACK FIRED)")
    ) else "unknown"
    services_out.append({
        "name": "Investigator (AI)",
        "key": "investigator",
        "status": investigator_status,
        "latency_ms": None,
        "message": bedrock_data.get("message", ""),
        "findings_count": bedrock_data.get("findings_count", 0),
        "gemini_fallback_count": gemini_data.get("fallback_fired_count", 0),
    })

    # Elastic APM
    services_out.append({
        "name": "Elastic APM",
        "key": "apm",
        "status": "healthy" if is_apm_enabled() else "degraded",
        "latency_ms": None,
        "message": "APM agent active — transactions being captured" if is_apm_enabled()
                   else "APM not configured (ELASTIC_APM_SERVER_URL missing)",
    })

    overall = health.get("status", "UNKNOWN")

    return {
        "overall_status": "healthy" if overall == "HEALTHY" else "degraded",
        "checked_at": health.get("checked_at"),
        "apm_enabled": is_apm_enabled(),
        "apm_service_name": "vigil-backend",
        "services": services_raw,
        "services_list": services_out,
    }
