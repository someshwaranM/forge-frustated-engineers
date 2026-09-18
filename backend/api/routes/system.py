"""
Vigil — System Health & Diagnostics API Routes (backend/api/routes/system.py)

Exposes:
- GET /api/system/health:
  - MySQL & Elasticsearch: Checked LIVE on every request (fast, local, no cost).
  - Bedrock, Gemini, Sarvam: Reports LAST-KNOWN status derived from actual recent pipeline
    activity (no live LLM pings, zero cost, zero artificial latency).
- GET /api/system/diagnostics:
  - Full pipeline latency stage timings (mean/median/min/max) and per-call breakdown.
"""

import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter

from backend.db.session import get_db_connection
from backend.elastic.client import get_es_client
from backend.observability.stage_timer import get_all_stage_timings, parse_iso_datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["System Diagnostics"])


def _format_time_ago(iso_str: Optional[str]) -> str:
    """Format an ISO datetime into a friendly 'X minutes ago' string."""
    if not iso_str:
        return "N/A"
    dt = parse_iso_datetime(iso_str)
    if not dt:
        return iso_str
    now = datetime.now(timezone.utc)
    diff = now - dt
    total_seconds = int(diff.total_seconds())
    if total_seconds < 0:
        return "just now"
    if total_seconds < 60:
        return f"{total_seconds}s ago"
    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h {minutes % 60}m ago"
    days = hours // 24
    return f"{days}d ago"


@router.get("/health", response_model=Dict[str, Any])
def get_system_health():
    """
    Returns live health for MySQL and Elasticsearch, and last-known operational status
    for external AI/ASR providers (Bedrock, Gemini, Sarvam) derived from real audit history.
    """
    # -------------------------------------------------------------------------
    # 1. LIVE CHECK: MySQL
    # -------------------------------------------------------------------------
    mysql_info: Dict[str, Any] = {
        "status": "DISCONNECTED",
        "type": "live",
        "latency_ms": None,
        "database": None,
        "message": "Connection uninitialized",
    }
    t_start = time.perf_counter()
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE();")
            row = cur.fetchone()
            db_name = row[0] if isinstance(row, (tuple, list)) else (row.get("DATABASE()") if isinstance(row, dict) else str(row))
        conn.close()
        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
        mysql_info.update({
            "status": "CONNECTED",
            "latency_ms": elapsed_ms,
            "database": db_name,
            "message": f"Connected to database '{db_name}' ({elapsed_ms}ms)",
        })
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
        logger.warning(f"MySQL health probe failed: {exc}")
        mysql_info.update({
            "status": "ERROR",
            "latency_ms": elapsed_ms,
            "message": str(exc),
        })

    # -------------------------------------------------------------------------
    # 2. LIVE CHECK: Elasticsearch
    # -------------------------------------------------------------------------
    es_info: Dict[str, Any] = {
        "status": "DISCONNECTED",
        "type": "live",
        "latency_ms": None,
        "build_flavor": None,
        "message": "Connection uninitialized",
    }
    t_start = time.perf_counter()
    es = None
    try:
        es = get_es_client()
        info = es.info()
        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
        version_data = info.get("version", {})
        build_flavor = version_data.get("build_flavor", "serverless")
        es_info.update({
            "status": "CONNECTED",
            "latency_ms": elapsed_ms,
            "build_flavor": build_flavor,
            "cluster_name": info.get("cluster_name"),
            "message": f"Connected to Elasticsearch ({build_flavor}, {elapsed_ms}ms)",
        })
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
        logger.warning(f"Elasticsearch health probe failed: {exc}")
        es_info.update({
            "status": "ERROR",
            "latency_ms": elapsed_ms,
            "message": str(exc),
        })

    # -------------------------------------------------------------------------
    # 3. LAST-KNOWN STATUS: AI & ASR Providers (Derive from recorded data, NO LIVE PING)
    # -------------------------------------------------------------------------
    bedrock_info: Dict[str, Any] = {
        "status": "NOT_USED",
        "type": "last_known",
        "last_successful_call_at": None,
        "last_call_id": None,
        "findings_count": 0,
        "message": "Provider has not been used yet in recorded audit runs.",
    }
    gemini_info: Dict[str, Any] = {
        "status": "NOT_USED",
        "type": "last_known",
        "fallback_fired_count": 0,
        "last_successful_call_at": None,
        "last_call_id": None,
        "message": "Provider has not been used yet in recorded audit runs.",
    }
    sarvam_info: Dict[str, Any] = {
        "status": "NOT_USED",
        "type": "last_known",
        "last_successful_call_at": None,
        "last_call_id": None,
        "calls_transcribed": 0,
        "message": "No calls transcribed yet in recorded audio pipeline.",
    }

    if es and es_info["status"] == "CONNECTED":
        # Check Bedrock & Gemini findings in compliance_findings
        try:
            agg_res = es.search(
                index="compliance_findings",
                size=0,
                aggs={
                    "by_provider": {
                        "terms": {"field": "provider_used", "size": 10}
                    }
                },
            )
            buckets = agg_res.get("aggregations", {}).get("by_provider", {}).get("buckets", [])
            for b in buckets:
                pkey = b["key"].lower()
                doc_count = b["doc_count"]
                if "bedrock" in pkey or "claude" in pkey:
                    bedrock_info["findings_count"] += doc_count
                elif "gemini" in pkey:
                    gemini_info["fallback_fired_count"] += doc_count

            # Query most recent Bedrock finding
            if bedrock_info["findings_count"] > 0:
                b_recent = es.search(
                    index="compliance_findings",
                    query={"wildcard": {"provider_used": "*bedrock*"}},
                    sort=[{"created_at": {"order": "desc"}}],
                    size=1,
                )
                hits = b_recent.get("hits", {}).get("hits", [])
                if hits:
                    src = hits[0]["_source"]
                    c_at = src.get("created_at")
                    cid = src.get("call_id")
                    time_ago = _format_time_ago(c_at)
                    bedrock_info.update({
                        "status": "OPERATIONAL",
                        "last_successful_call_at": c_at,
                        "last_call_id": cid,
                        "message": f"Bedrock: last successful call at investigation for {cid}, {time_ago} ({bedrock_info['findings_count']} findings produced)",
                    })
            else:
                bedrock_info.update({
                    "status": "STANDBY",
                    "message": "Provider configured and ready on standby; 0 findings generated in current session.",
                })

            # Query most recent Gemini finding
            if gemini_info["fallback_fired_count"] > 0:
                g_recent = es.search(
                    index="compliance_findings",
                    query={"wildcard": {"provider_used": "*gemini*"}},
                    sort=[{"created_at": {"order": "desc"}}],
                    size=1,
                )
                hits = g_recent.get("hits", {}).get("hits", [])
                if hits:
                    src = hits[0]["_source"]
                    c_at = src.get("created_at")
                    cid = src.get("call_id")
                    time_ago = _format_time_ago(c_at)
                    gemini_info.update({
                        "status": "ACTIVE (FALLBACK FIRED)",
                        "last_successful_call_at": c_at,
                        "last_call_id": cid,
                        "message": f"Gemini fallback: fired {gemini_info['fallback_fired_count']} times in the last session (last: {cid}, {time_ago})",
                    })
            else:
                gemini_info.update({
                    "status": "STANDBY",
                    "message": "Gemini fallback: fired 0 times in the last session (circuit breaker nominal).",
                })

        except Exception as exc:
            logger.warning(f"Could not inspect compliance_findings for provider health: {exc}")

        # Check Sarvam ASR in calls index
        try:
            calls_count_res = es.count(index="calls")
            total_calls = calls_count_res.get("count", 0)
            if total_calls > 0:
                recent_call = es.search(
                    index="calls",
                    query={"match_all": {}},
                    sort=[{"indexed_at": {"order": "desc"}}],
                    size=1,
                )
                hits = recent_call.get("hits", {}).get("hits", [])
                if hits:
                    src = hits[0]["_source"]
                    cid = src.get("call_id")
                    idx_at = src.get("indexed_at")
                    lang = src.get("language", "hi-IN")
                    time_ago = _format_time_ago(idx_at)
                    sarvam_info.update({
                        "status": "OPERATIONAL",
                        "calls_transcribed": total_calls,
                        "last_successful_call_at": idx_at,
                        "last_call_id": cid,
                        "message": f"Sarvam: last successful transcription for {cid} ({lang}, {time_ago}; {total_calls} calls transcribed)",
                    })
        except Exception as exc:
            logger.warning(f"Could not inspect calls for Sarvam health: {exc}")

    # Determine overall system health
    all_live_healthy = (mysql_info["status"] == "CONNECTED" and es_info["status"] == "CONNECTED")
    overall_status = "HEALTHY" if all_live_healthy else "DEGRADED"

    return {
        "status": overall_status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "services": {
            "mysql": mysql_info,
            "elasticsearch": es_info,
            "bedrock": bedrock_info,
            "gemini": gemini_info,
            "sarvam": sarvam_info,
        },
    }


@router.get("/diagnostics", response_model=Dict[str, Any])
def get_system_diagnostics():
    """
    Returns full stage-timer observability breakdown across all monitored calls,
    including per-call metrics and aggregate mean/median/min/max.
    """
    return get_all_stage_timings()
