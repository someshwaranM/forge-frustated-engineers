"""
Vigil — Dashboard Summary API Route (backend/api/routes/dashboard.py)

Exposes:
- GET /api/dashboard/summary:
  Total calls, findings by severity, open/resolved case counts,
  RM-wise violation trends, category breakdown, recent cases with needs_review computed,
  and pipeline latency placeholder.
"""

import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, status

from backend.db.session import get_db_connection
from backend.elastic.client import get_es_client
from backend.api.routes.settings import get_current_confidence_threshold
from backend.api.routes.cases import _fetch_findings_batch
from backend.observability.stage_timer import get_pipeline_latency_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=Dict[str, Any])
def get_dashboard_summary():
    """
    Returns aggregated KPIs, trends, category breakdown, and recent cases.
    """
    threshold = get_current_confidence_threshold()
    es = get_es_client()

    # 1. Total calls from ES
    total_calls = 0
    try:
        calls_count = es.count(index="calls")
        total_calls = calls_count.get("count", 0)
    except Exception as exc:
        logger.warning(f"Failed to count calls in ES: {exc}")

    # 2. Findings by severity from ES
    findings_by_severity = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    total_findings = 0
    try:
        f_agg = es.search(
            index="compliance_findings",
            size=0,
            aggs={
                "by_severity": {
                    "terms": {"field": "severity", "size": 10}
                }
            },
        )
        total_findings = f_agg.get("hits", {}).get("total", {}).get("value", 0)
        buckets = f_agg.get("aggregations", {}).get("by_severity", {}).get("buckets", [])
        for b in buckets:
            sev_key = b["key"].upper()
            if sev_key in findings_by_severity:
                findings_by_severity[sev_key] = b["doc_count"]
            else:
                findings_by_severity[sev_key] = b["doc_count"]
    except Exception as exc:
        logger.warning(f"Failed to aggregate findings by severity: {exc}")

    # 3. MySQL case statistics & breakdowns
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Open vs Resolved vs Escalated
            cur.execute(
                """
                SELECT
                    COUNT(*) as total_cases,
                    SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) as open_cases,
                    SUM(CASE WHEN status = 'RESOLVED' THEN 1 ELSE 0 END) as resolved_cases,
                    SUM(CASE WHEN escalated = 1 THEN 1 ELSE 0 END) as escalated_cases
                FROM compliance_case
                """
            )
            case_stats = cur.fetchone() or {
                "total_cases": 0,
                "open_cases": 0,
                "resolved_cases": 0,
                "escalated_cases": 0,
            }

            # RM-wise violation trend
            cur.execute(
                """
                SELECT c.rm_id, r.full_name as rm_name, r.branch, COUNT(c.case_id) as violation_count
                FROM compliance_case c
                LEFT JOIN rm r ON c.rm_id = r.rm_id
                GROUP BY c.rm_id, r.full_name, r.branch
                ORDER BY violation_count DESC
                """
            )
            rm_trends = cur.fetchall()

            # Category breakdown
            cur.execute(
                """
                SELECT category, COUNT(*) as count
                FROM compliance_case
                GROUP BY category
                ORDER BY count DESC
                """
            )
            category_breakdown = cur.fetchall()

            # Recent cases (last 10)
            cur.execute(
                """
                SELECT c.case_id, c.finding_id, c.call_id, c.rm_id, c.customer_id,
                       c.category, c.severity, c.status, c.resolution_type, c.escalated,
                       c.assigned_to, c.created_at,
                       r.full_name as rm_name,
                       cust.full_name as customer_name
                FROM compliance_case c
                LEFT JOIN rm r ON c.rm_id = r.rm_id
                LEFT JOIN customer cust ON c.customer_id = cust.customer_id
                ORDER BY c.created_at DESC
                LIMIT 10
                """
            )
            recent_cases_raw = cur.fetchall()
    finally:
        conn.close()

    # Augment recent cases with needs_review computed at read-time
    recent_finding_ids = [c["finding_id"] for c in recent_cases_raw if c.get("finding_id")]
    findings_map = _fetch_findings_batch(recent_finding_ids)

    recent_cases = []
    for c in recent_cases_raw:
        finding = findings_map.get(c["finding_id"], {})
        confidence = finding.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (ValueError, TypeError):
                confidence = None

        needs_review = (confidence is not None and confidence < threshold)
        item = dict(c)
        item["escalated"] = bool(c["escalated"])
        item["confidence"] = confidence
        item["needs_review"] = needs_review
        recent_cases.append(item)

    return {
        "kpis": {
            "total_calls": total_calls,
            "total_findings": total_findings,
            "total_cases": int(case_stats["total_cases"] or 0),
            "open_cases": int(case_stats["open_cases"] or 0),
            "resolved_cases": int(case_stats["resolved_cases"] or 0),
            "escalated_cases": int(case_stats["escalated_cases"] or 0),
            "confidence_threshold": threshold,
        },
        "findings_by_severity": findings_by_severity,
        "rm_violation_trend": rm_trends,
        "category_breakdown": category_breakdown,
        "recent_cases": recent_cases,
        "pipeline_latency": get_pipeline_latency_summary(),
    }
