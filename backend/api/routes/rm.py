"""
Vigil — Relationship Manager & Compliance Report API Routes (backend/api/routes/rm.py)
Phase 15: RM Analytics and Email Report Generation & Delivery

Exposes:
- GET  /api/rm: Lists all Relationship Managers with summary performance metrics
- GET  /api/rm/{rm_id}/analytics: RM-specific telemetry and LIVE computed repeat-violation flag
- POST /api/rm/{rm_id}/report/email: Authenticated endpoint to generate & send compliance report email
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Header, status
from pydantic import BaseModel, Field

from backend.db.session import get_db_connection
from backend.elastic.client import get_es_client
from backend.api.routes.auth import get_current_user_payload
from backend.reports.email_service import (
    send_email,
    validate_recipients,
    RecipientValidationError,
    EmailServiceError,
)
from backend.reports.rm_report_service import (
    get_rm_report_data,
    record_report_audit,
    check_idempotency,
    store_idempotency_result,
    RMNotFoundError,
)
from backend.reports.rm_report_renderer import render_rm_report_html, render_rm_report_text

logger = logging.getLogger("vigil.api.rm")

router = APIRouter(prefix="/rm", tags=["RM Analytics"])

ALLOWED_ROLES = {
    "Audit Officer",
    "Compliance Officer",
    "Compliance Head",
    "Reviewer",
    "admin",
}


class SendReportRequest(BaseModel):
    recipients: List[str] = Field(..., description="List of recipient email addresses")
    request_id: Optional[str] = Field(None, description="Client-generated idempotency key UUID")


class SendReportResponse(BaseModel):
    success: bool
    rm_id: str
    recipients: List[str]
    sent_at: str
    report_id: str
    idempotent_replay: Optional[bool] = None


@router.get("", response_model=List[Dict[str, Any]])
def list_rms():
    """
    List all Relationship Managers with summary performance and violation stats.
    Queries MySQL rm table, compliance_case, and Elasticsearch calls index.
    """
    conn = get_db_connection()
    rms = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT rm_id, full_name, branch, joined_date, active FROM rm ORDER BY rm_id ASC")
            rm_rows = cur.fetchall()

            for r in rm_rows:
                rm_id = r["rm_id"]

                # Case stats for this RM
                cur.execute(
                    """
                    SELECT
                        COUNT(*) as total_violations,
                        SUM(CASE WHEN severity = 'HIGH' THEN 1 ELSE 0 END) as high_count,
                        SUM(CASE WHEN severity = 'MEDIUM' THEN 1 ELSE 0 END) as med_count,
                        SUM(CASE WHEN severity = 'LOW' THEN 1 ELSE 0 END) as low_count,
                        SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) as open_cases,
                        SUM(CASE WHEN status = 'RESOLVED' THEN 1 ELSE 0 END) as resolved_cases
                    FROM compliance_case
                    WHERE rm_id = %s
                    """,
                    (rm_id,),
                )
                stats = cur.fetchone() or {}
                total_violations = int(stats.get("total_violations") or 0)
                high_count = int(stats.get("high_count") or 0)
                med_count = int(stats.get("med_count") or 0)
                low_count = int(stats.get("low_count") or 0)
                open_cases = int(stats.get("open_cases") or 0)
                resolved_cases = int(stats.get("resolved_cases") or 0)

                # Repeat violation check
                cur.execute(
                    """
                    SELECT category, COUNT(*) as count
                    FROM compliance_case
                    WHERE rm_id = %s
                    GROUP BY category
                    HAVING COUNT(*) > 1
                    ORDER BY count DESC
                    LIMIT 1
                    """,
                    (rm_id,),
                )
                repeat_row = cur.fetchone()
                repeat_violation_flag = repeat_row is not None
                repeat_category = repeat_row["category"] if repeat_row else None

                # Category breakdown
                cur.execute(
                    """
                    SELECT category, COUNT(*) as count
                    FROM compliance_case
                    WHERE rm_id = %s
                    GROUP BY category
                    ORDER BY count DESC
                    """,
                    (rm_id,),
                )
                cat_breakdown = cur.fetchall()

                # Derive region from branch
                branch = r.get("branch") or "Mumbai"
                if "Mumbai" in branch or "Pune" in branch:
                    region = "West Region"
                elif "Bengaluru" in branch or "Chennai" in branch:
                    region = "South Region"
                elif "Delhi" in branch:
                    region = "North Region"
                else:
                    region = "Central Region"

                # Calculate composite risk index (0-100)
                risk_score = min(
                    100,
                    (high_count * 30) + (med_count * 15) + (low_count * 5) + (25 if repeat_violation_flag else 0),
                )

                rms.append({
                    "rm_id": rm_id,
                    "name": r["full_name"],
                    "full_name": r["full_name"],
                    "branch": branch,
                    "region": region,
                    "manager_name": "Suresh Patel (Branch Head)",
                    "joined_date": str(r.get("joined_date") or ""),
                    "active": bool(r.get("active", 1)),
                    "total_calls": 0,  # populated from ES below
                    "total_violations": total_violations,
                    "high_severity_count": high_count,
                    "medium_severity_count": med_count,
                    "low_severity_count": low_count,
                    "open_cases": open_cases,
                    "resolved_cases": resolved_cases,
                    "repeat_violation_flag": repeat_violation_flag,
                    "repeat_violation_category": repeat_category,
                    "risk_score": risk_score,
                    "category_breakdown": cat_breakdown,
                })
    finally:
        conn.close()

    # Query ES calls index for total calls per RM
    try:
        es = get_es_client()
        for item in rms:
            try:
                c_res = es.count(index="calls", query={"term": {"rm_id": item["rm_id"]}})
                item["total_calls"] = c_res.get("count", 0)
            except Exception:
                item["total_calls"] = 0
    except Exception as exc:
        logger.warning(f"Failed to fetch calls count for RMs: {exc}")

    return rms


@router.get("/{rm_id}/analytics", response_model=Dict[str, Any])
def get_rm_analytics(rm_id: str):
    """
    Computes RM-specific analytics and LIVE repeat-violation flag.
    Returns 404 if rm_id does not exist.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Verify RM exists
            cur.execute("SELECT rm_id, full_name, branch, joined_date, active FROM rm WHERE rm_id = %s", (rm_id,))
            rm_info = cur.fetchone()
            if not rm_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "RM_NOT_FOUND", "message": f"Relationship Manager '{rm_id}' not found."},
                )

            # 2. Case totals
            cur.execute(
                """
                SELECT
                    COUNT(*) as total_cases,
                    SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) as open_cases,
                    SUM(CASE WHEN status = 'RESOLVED' THEN 1 ELSE 0 END) as resolved_cases,
                    SUM(CASE WHEN escalated = 1 THEN 1 ELSE 0 END) as escalated_cases
                FROM compliance_case
                WHERE rm_id = %s
                """,
                (rm_id,),
            )
            case_counts = cur.fetchone() or {
                "total_cases": 0,
                "open_cases": 0,
                "resolved_cases": 0,
                "escalated_cases": 0,
            }

            # 3. LIVE Repeat Violation Flag
            cur.execute(
                """
                SELECT category, COUNT(*) as count
                FROM compliance_case
                WHERE rm_id = %s
                GROUP BY category
                HAVING COUNT(*) > 1
                """,
                (rm_id,),
            )
            repeat_rows = cur.fetchall()
            has_repeat_violations = len(repeat_rows) > 0
            repeat_categories = [{"category": r["category"], "count": r["count"]} for r in repeat_rows]

            # 4. Category breakdown
            cur.execute(
                """
                SELECT category, COUNT(*) as count
                FROM compliance_case
                WHERE rm_id = %s
                GROUP BY category
                ORDER BY count DESC
                """,
                (rm_id,),
            )
            category_breakdown = cur.fetchall()

            # 5. Severity breakdown
            cur.execute(
                """
                SELECT severity, COUNT(*) as count
                FROM compliance_case
                WHERE rm_id = %s
                GROUP BY severity
                ORDER BY count DESC
                """,
                (rm_id,),
            )
            severity_breakdown = cur.fetchall()

            # 6. Recent cases
            cur.execute(
                """
                SELECT case_id, finding_id, call_id, customer_id, category, severity,
                       status, resolution_type, escalated, created_at
                FROM compliance_case
                WHERE rm_id = %s
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (rm_id,),
            )
            recent_cases = cur.fetchall()
            for rc in recent_cases:
                rc["escalated"] = bool(rc["escalated"])
    finally:
        conn.close()

    # 7. Total calls for this RM from ES
    total_calls = 0
    try:
        es = get_es_client()
        call_count_res = es.count(index="calls", query={"term": {"rm_id": rm_id}})
        total_calls = call_count_res.get("count", 0)
    except Exception as exc:
        logger.warning(f"Failed to count calls for RM {rm_id}: {exc}")

    return {
        "rm": rm_info,
        "total_calls": total_calls,
        "total_cases": int(case_counts["total_cases"] or 0),
        "open_cases": int(case_counts["open_cases"] or 0),
        "resolved_cases": int(case_counts["resolved_cases"] or 0),
        "escalated_cases": int(case_counts["escalated_cases"] or 0),
        "has_repeat_violations": has_repeat_violations,
        "repeat_categories": repeat_categories,
        "category_breakdown": category_breakdown,
        "severity_breakdown": severity_breakdown,
        "recent_cases": recent_cases,
    }


@router.post(
    "/{rm_id}/report/email",
    response_model=SendReportResponse,
    summary="Send RM Compliance Report on Mail",
    status_code=status.HTTP_200_OK,
)
async def send_rm_report_email(
    rm_id: str,
    body: SendReportRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user_payload: dict = Depends(get_current_user_payload),
):
    """
    Generate authoritative compliance report for RM and dispatch via Elastic Kibana email connector.
    
    Security: Requires authenticated user with compliance surveillance role.
    Idempotency: Replays cached result if duplicate request_id / Idempotency-Key within 60s.
    """
    # 1. Role Authorization check (Section 52.8)
    user_role = user_payload.get("role", "")
    requested_by = user_payload.get("user_id") or user_payload.get("username") or "unknown_user"

    if user_role not in ALLOWED_ROLES:
        logger.warning(f"User {requested_by} with role '{user_role}' denied report dispatch access.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "FORBIDDEN",
                "message": "Only authorized compliance audit officers and reviewers may dispatch statutory reports.",
            },
        )

    # 2. Idempotency Check (Section 52.5)
    effective_req_id = body.request_id or idempotency_key
    cached_replay = check_idempotency(effective_req_id, rm_id)
    if cached_replay:
        return SendReportResponse(
            success=True,
            rm_id=cached_replay["rm_id"],
            recipients=cached_replay["recipients"],
            sent_at=cached_replay["sent_at"],
            report_id=cached_replay["report_id"],
            idempotent_replay=True,
        )

    # 3. Recipient Validation (Section 7, 52.1, 52.2)
    try:
        clean_recipients, domain_class = validate_recipients(body.recipients)
    except RecipientValidationError as rve:
        raise HTTPException(
            status_code=rve.status_code,
            detail={"error": rve.error_code, "message": rve.message},
        )

    # 4. Gather Authoritative RM Report Data (Section 8, 13-19)
    try:
        report_data = get_rm_report_data(rm_id)
    except RMNotFoundError as rne:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "RM_NOT_FOUND", "message": str(rne)},
        )
    except Exception as exc:
        logger.exception(f"Failed to gather report telemetry for RM {rm_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "REPORT_ASSEMBLY_FAILED", "message": "Failed to assemble RM report data."},
        )

    report_id = report_data["report_id"]
    rm_full_name = report_data["rm"]["full_name"]
    subject = f"[Vigil] RM Compliance Report — {rm_full_name} ({rm_id})"

    # 5. Render HTML and Plain-Text fallback (Section 11, 35, 36, 52.6)
    try:
        html_body = render_rm_report_html(report_data)
        text_body = render_rm_report_text(report_data)
    except Exception as exc:
        logger.exception(f"Report rendering error for {report_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "REPORT_RENDER_FAILED", "message": "Could not render compliance report."},
        )

    # Record REQUESTED audit event
    record_report_audit(
        report_id=report_id,
        rm_id=rm_id,
        requested_by=requested_by,
        recipients=clean_recipients,
        status="REQUESTED",
        domain_class=domain_class,
        request_id=effective_req_id,
    )

    # 6. Dispatch via Elastic Kibana Connector (Section 9, 39, 44, 52.3, 52.4)
    try:
        dispatch_result = await send_email(
            recipients=clean_recipients,
            subject=subject,
            html_body=html_body,
            plain_text=text_body,
        )
    except EmailServiceError as ese:
        logger.error(f"Email delivery error for report {report_id}: {ese.message}")
        record_report_audit(
            report_id=report_id,
            rm_id=rm_id,
            requested_by=requested_by,
            recipients=clean_recipients,
            status="FAILED",
            error_code=ese.error_code,
            domain_class=domain_class,
            request_id=effective_req_id,
        )
        raise HTTPException(
            status_code=ese.status_code,
            detail={
                "error": ese.error_code,
                "message": "Unable to send the report. Please verify the recipient address or email service configuration.",
            },
        )
    except Exception as exc:
        logger.exception(f"Unexpected email dispatch error for {report_id}: {exc}")
        record_report_audit(
            report_id=report_id,
            rm_id=rm_id,
            requested_by=requested_by,
            recipients=clean_recipients,
            status="FAILED",
            error_code="INTERNAL_ERROR",
            domain_class=domain_class,
            request_id=effective_req_id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "EMAIL_SEND_FAILED",
                "message": "Unable to send the report. Please verify the recipient address or email service configuration.",
            },
        )

    # 7. Record SENT audit event (Section 25)
    sent_at = datetime.now(timezone.utc).isoformat()
    record_report_audit(
        report_id=report_id,
        rm_id=rm_id,
        requested_by=requested_by,
        recipients=clean_recipients,
        status="SENT",
        domain_class=domain_class,
        request_id=effective_req_id,
    )

    response_payload = {
        "success": True,
        "rm_id": rm_id,
        "recipients": clean_recipients,
        "sent_at": sent_at,
        "report_id": report_id,
    }

    # Store for idempotency
    store_idempotency_result(effective_req_id, response_payload)

    return SendReportResponse(**response_payload)
