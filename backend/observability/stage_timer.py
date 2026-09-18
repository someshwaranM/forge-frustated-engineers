"""
Vigil — Phase 12: Stage-Timer Observability Engine (backend/observability/stage_timer.py)

Computes per-call and aggregate stage durations across the pipeline:
1. Ingestion:     processing_started_at -> indexed_at
2. Detection:     indexed_at            -> detection_completed_at
3. Investigation: detection_completed_at -> investigation_completed_at
4. End-to-End:    processing_started_at -> investigation_completed_at

Exposes:
- Per-call duration breakdown
- Aggregate statistics: mean, median, min, max per stage
- Honest handling of legacy or partial pipeline runs (never fabricating timestamps)
"""

import os
import json
import logging
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from backend.elastic.client import get_es_client

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANDIDATES_DIR = PROJECT_ROOT / "backend" / "compliance" / "candidates"
INVESTIGATIONS_DIR = PROJECT_ROOT / "backend" / "agents" / "investigations"


def parse_iso_datetime(ts_str: Optional[str]) -> Optional[datetime]:
    """Parse an ISO 8601 string into a timezone-aware UTC datetime."""
    if not ts_str:
        return None
    try:
        s = ts_str.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception as exc:
        logger.debug(f"Failed to parse datetime '{ts_str}': {exc}")
        return None


def _load_stage_timestamps_for_call(call_id: str, call_source: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Extracts the four stage timestamps for a call document, falling back to
    authoritative local candidate and investigation audit files if not on ES doc.
    """
    processing_started_at = call_source.get("processing_started_at")
    indexed_at = call_source.get("indexed_at")
    detection_completed_at = call_source.get("detection_completed_at")
    investigation_completed_at = call_source.get("investigation_completed_at")

    # Fallback to candidates directory if detection_completed_at not on ES doc
    if not detection_completed_at:
        cand_path = CANDIDATES_DIR / f"{call_id}.json"
        if not cand_path.exists() and call_id.startswith("CALL_"):
            cand_path = CANDIDATES_DIR / f"{call_id[5:]}.json"
        if cand_path.exists():
            try:
                with open(cand_path, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                    detection_completed_at = cdata.get("detection_completed_at") or cdata.get("generated_at")
            except Exception as exc:
                logger.warning(f"Could not read candidate file for {call_id}: {exc}")

    # Fallback to investigations directory if investigation_completed_at not on ES doc
    if not investigation_completed_at:
        inv_path = INVESTIGATIONS_DIR / f"{call_id}.json"
        if inv_path.exists():
            try:
                with open(inv_path, "r", encoding="utf-8") as f:
                    idata = json.load(f)
                    investigation_completed_at = idata.get("investigation_completed_at") or idata.get("generated_at")
            except Exception as exc:
                logger.warning(f"Could not read investigation file for {call_id}: {exc}")

    return {
        "processing_started_at": processing_started_at,
        "indexed_at": indexed_at,
        "detection_completed_at": detection_completed_at,
        "investigation_completed_at": investigation_completed_at,
    }


def compute_call_stage_durations(call_id: str, call_source: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes stage durations for a single call document.
    Returns calculated durations in seconds or None if prerequisite timestamps are missing.
    """
    ts = _load_stage_timestamps_for_call(call_id, call_source)

    dt_start = parse_iso_datetime(ts["processing_started_at"])
    dt_index = parse_iso_datetime(ts["indexed_at"])
    dt_detect = parse_iso_datetime(ts["detection_completed_at"])
    dt_invest = parse_iso_datetime(ts["investigation_completed_at"])

    ingestion_duration: Optional[float] = None
    detection_duration: Optional[float] = None
    investigation_duration: Optional[float] = None
    end_to_end_duration: Optional[float] = None
    notes: List[str] = []

    # 1. Ingestion: processing_started_at -> indexed_at
    if dt_start and dt_index:
        delta = (dt_index - dt_start).total_seconds()
        if delta >= 0:
            ingestion_duration = round(delta, 3)
        else:
            notes.append("ingestion: indexed_at precedes processing_started_at")
    elif not dt_start and dt_index:
        notes.append("ingestion: processing_started_at not recorded (pre-Phase 12 legacy ingestion)")

    # 2. Detection: indexed_at -> detection_completed_at
    if dt_index and dt_detect:
        delta = (dt_detect - dt_index).total_seconds()
        # Ensure timestamps were from the same continuous run (not separated across days)
        if 0 <= delta <= 7200:  # Max 2 hours for a single live pipeline run
            detection_duration = round(delta, 3)
        else:
            notes.append(f"detection: indexed_at and detection_completed_at span different execution sessions ({delta:.0f}s apart)")

    # 3. Investigation: detection_completed_at -> investigation_completed_at
    if dt_detect and dt_invest:
        delta = (dt_invest - dt_detect).total_seconds()
        if 0 <= delta <= 7200:
            investigation_duration = round(delta, 3)
        else:
            notes.append(f"investigation: detection and investigation span different execution sessions ({delta:.0f}s apart)")

    # 4. End-to-End: processing_started_at -> investigation_completed_at
    if dt_start and dt_invest:
        delta = (dt_invest - dt_start).total_seconds()
        if 0 <= delta <= 7200:
            end_to_end_duration = round(delta, 3)
        else:
            notes.append(f"end_to_end: processing_started_at and investigation_completed_at span different execution sessions ({delta:.0f}s apart)")

    is_complete_run = (
        ingestion_duration is not None and
        detection_duration is not None and
        investigation_duration is not None and
        end_to_end_duration is not None
    )

    return {
        "call_id": call_id,
        "is_complete_run": is_complete_run,
        "timestamps": ts,
        "durations": {
            "ingestion_duration_seconds": ingestion_duration,
            "detection_duration_seconds": detection_duration,
            "investigation_duration_seconds": investigation_duration,
            "end_to_end_duration_seconds": end_to_end_duration,
        },
        "notes": notes,
    }


def _calc_stats(values: List[float]) -> Dict[str, Optional[float]]:
    """Calculates mean, median, min, max for a list of floats."""
    if not values:
        return {
            "mean_seconds": None,
            "median_seconds": None,
            "min_seconds": None,
            "max_seconds": None,
            "count": 0,
        }
    return {
        "mean_seconds": round(statistics.mean(values), 2),
        "median_seconds": round(statistics.median(values), 2),
        "min_seconds": round(min(values), 2),
        "max_seconds": round(max(values), 2),
        "count": len(values),
    }


def get_all_stage_timings() -> Dict[str, Any]:
    """
    Computes per-call durations and stage-level aggregates across all calls in Elasticsearch.
    """
    es = get_es_client()
    try:
        res = es.search(index="calls", size=200)
        hits = res.get("hits", {}).get("hits", [])
    except Exception as exc:
        logger.error(f"Failed to fetch calls from Elasticsearch for stage timing: {exc}")
        hits = []

    per_call_list: List[Dict[str, Any]] = []
    ingestion_vals: List[float] = []
    detection_vals: List[float] = []
    investigation_vals: List[float] = []
    end_to_end_vals: List[float] = []

    for hit in hits:
        cid = hit["_id"]
        source = hit.get("_source", {})
        metrics = compute_call_stage_durations(cid, source)
        per_call_list.append(metrics)

        d = metrics["durations"]
        if d["ingestion_duration_seconds"] is not None:
            ingestion_vals.append(d["ingestion_duration_seconds"])
        if d["detection_duration_seconds"] is not None:
            detection_vals.append(d["detection_duration_seconds"])
        if d["investigation_duration_seconds"] is not None:
            investigation_vals.append(d["investigation_duration_seconds"])
        if d["end_to_end_duration_seconds"] is not None:
            end_to_end_vals.append(d["end_to_end_duration_seconds"])

    complete_count = sum(1 for c in per_call_list if c["is_complete_run"])
    total_calls = len(per_call_list)

    return {
        "status": "active",
        "total_calls_monitored": total_calls,
        "complete_pipeline_runs": complete_count,
        "legacy_or_partial_runs": total_calls - complete_count,
        "stages": {
            "ingestion": _calc_stats(ingestion_vals),
            "detection": _calc_stats(detection_vals),
            "investigation": _calc_stats(investigation_vals),
            "end_to_end": _calc_stats(end_to_end_vals),
        },
        "per_call": per_call_list,
    }


def get_pipeline_latency_summary() -> Dict[str, Any]:
    """
    Generates the pipeline_latency summary payload tailored for GET /api/dashboard/summary.
    """
    timings = get_all_stage_timings()
    stages = timings["stages"]

    return {
        "status": "active",
        "total_calls_monitored": timings["total_calls_monitored"],
        "complete_pipeline_runs": timings["complete_pipeline_runs"],
        "legacy_or_partial_runs": timings["legacy_or_partial_runs"],
        "stages": stages,
        "headline": {
            "mean_ingestion_seconds": stages["ingestion"]["mean_seconds"],
            "mean_detection_seconds": stages["detection"]["mean_seconds"],
            "mean_investigation_seconds": stages["investigation"]["mean_seconds"],
            "mean_end_to_end_seconds": stages["end_to_end"]["mean_seconds"],
        },
    }
