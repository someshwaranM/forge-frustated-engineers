"""
Vigil — Cases API Routes (backend/api/routes/cases.py)

Exposes:
- GET /api/cases: Filterable case list with computed needs_review flag based on stored confidence_threshold
- GET /api/cases/{case_id}: Assembled Full Evidence Chain (case + finding + call + activity log)
- PATCH /api/cases/{case_id}/status: Mark Reviewed / Dismiss
- POST /api/cases/{case_id}/escalate: Escalate to Committee
- POST /api/cases/{case_id}/assign: Assign / Reassign to reviewer
- POST /api/cases/{case_id}/notes: Add note to case
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from backend.db.session import get_db_connection
from backend.elastic.client import get_es_client
from backend.api.routes.settings import get_current_confidence_threshold
from backend.workflows.case_service import (
    mark_reviewed,
    dismiss,
    escalate,
    assign,
    add_note,
    CaseNotFoundError,
    CaseAlreadyResolvedError,
    CaseAlreadyEscalatedError,
    ReviewerNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["Cases"])


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------

class CaseStatusUpdateRequest(BaseModel):
    reviewer_id: str
    action: str  # "mark_reviewed" | "dismiss"
    notes: Optional[str] = None


class CaseEscalateRequest(BaseModel):
    reviewer_id: str
    notes: Optional[str] = None


class CaseAssignRequest(BaseModel):
    reviewer_id: str
    assignee_reviewer_id: str


class CaseNoteRequest(BaseModel):
    reviewer_id: str
    note_text: str


# ---------------------------------------------------------------------------
# Helper: Fetch batch findings from ES to augment case listings
# ---------------------------------------------------------------------------

def _fetch_findings_batch(finding_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Fetch multiple findings by finding_id from ES compliance_findings."""
    if not finding_ids:
        return {}
    try:
        es = get_es_client()
        docs = [{"_index": "compliance_findings", "_id": fid} for fid in finding_ids]
        mget_res = es.mget(docs=docs)
        result = {}
        for item in mget_res.get("docs", []):
            if item.get("found"):
                result[item["_id"]] = item["_source"]
        return result
    except Exception as exc:
        logger.warning(f"Failed to batch fetch findings from ES: {exc}")
        return {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=Dict[str, Any])
def list_cases(
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = Query(None),
    rm_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List compliance cases with optional filters.
    Computes needs_review: true dynamically if finding confidence < current confidence_threshold.
    """
    threshold = get_current_confidence_threshold()
    where_clauses = []
    params: List[Any] = []

    if status_filter:
        where_clauses.append("c.status = %s")
        params.append(status_filter.upper())
    if severity:
        where_clauses.append("c.severity = %s")
        params.append(severity.upper())
    if rm_id:
        where_clauses.append("c.rm_id = %s")
        params.append(rm_id)
    if category:
        where_clauses.append("c.category = %s")
        params.append(category)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Count total matching rows
            cur.execute(f"SELECT COUNT(*) as total FROM compliance_case c {where_sql}", params)
            total = cur.fetchone()["total"]

            # Query page
            query = f"""
                SELECT c.case_id, c.finding_id, c.call_id, c.rm_id, c.customer_id,
                       c.category, c.severity, c.status, c.resolution_type, c.escalated,
                       c.assigned_to, c.resolution_notes, c.created_at, c.updated_at,
                       r.full_name as rm_name,
                       cust.full_name as customer_name,
                       rev.full_name as assignee_name
                FROM compliance_case c
                LEFT JOIN rm r ON c.rm_id = r.rm_id
                LEFT JOIN customer cust ON c.customer_id = cust.customer_id
                LEFT JOIN reviewer rev ON c.assigned_to = rev.reviewer_id
                {where_sql}
                ORDER BY c.created_at DESC
                LIMIT %s OFFSET %s
            """
            cur.execute(query, params + [limit, offset])
            cases = cur.fetchall()
    finally:
        conn.close()

    # Augment with ES finding confidence for read-time needs_review computation
    finding_ids = [c["finding_id"] for c in cases if c.get("finding_id")]
    findings_map = _fetch_findings_batch(finding_ids)

    enriched_cases = []
    for c in cases:
        finding = findings_map.get(c["finding_id"], {})
        confidence = finding.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (ValueError, TypeError):
                confidence = None

        # Read-time computed flag
        needs_review = (confidence is not None and confidence < threshold)

        enriched_case = dict(c)
        enriched_case["escalated"] = bool(c["escalated"])
        enriched_case["confidence"] = confidence
        enriched_case["needs_review"] = needs_review
        enriched_case["regulation_citation_label"] = finding.get("regulation_citation_label")
        enriched_cases.append(enriched_case)

    return {
        "total": total,
        "confidence_threshold": threshold,
        "items": enriched_cases,
    }

@router.get("/{case_id}")
def get_case_detail(case_id: str):
    """
    Assemble the FULL Evidence Chain in one response:
    - compliance_case row (MySQL)
    - finding document (ES compliance_findings)
    - call document (ES calls, including full transcript_segments)
    - case_activity_log history (MySQL, ordered by timestamp) with reviewer names
    - computed needs_review flag
    """
    threshold = get_current_confidence_threshold()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.case_id, c.finding_id, c.call_id, c.rm_id, c.customer_id,
                       c.category, c.severity, c.status, c.resolution_type, c.escalated,
                       c.assigned_to, c.resolution_notes, c.created_at, c.updated_at,
                       r.full_name as rm_name, r.branch as rm_branch,
                       cust.full_name as customer_name, cust.risk_profile as customer_risk_profile,
                       cust.investment_experience as customer_investment_experience,
                       rev.full_name as assignee_name, rev.role as assignee_role
                FROM compliance_case c
                LEFT JOIN rm r ON c.rm_id = r.rm_id
                LEFT JOIN customer cust ON c.customer_id = cust.customer_id
                LEFT JOIN reviewer rev ON c.assigned_to = rev.reviewer_id
                WHERE c.case_id = %s
                """,
                (case_id,),
            )
            case_row = cur.fetchone()

            if not case_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "CASE_NOT_FOUND", "message": f"Case '{case_id}' not found."},
                )

            # Fetch activity log with user name and user id
            cur.execute(
                """
                SELECT log.log_id, log.case_id, log.action, log.actor, log.details, log.timestamp,
                       COALESCE(u.full_name, rev.full_name, log.actor) as actor_name,
                       COALESCE(u.role, rev.role, 'Compliance Officer') as actor_role,
                       COALESCE(u.user_id, rev.reviewer_id, log.actor) as actor_id
                FROM case_activity_log log
                LEFT JOIN reviewer rev ON log.actor = rev.reviewer_id
                LEFT JOIN users u ON (log.actor = u.user_id OR log.actor = u.username)
                WHERE log.case_id = %s
                ORDER BY log.timestamp ASC
                """,
                (case_id,),
            )
            activity_logs = cur.fetchall()
            for al in activity_logs:
                if al.get("timestamp"):
                    al["timestamp"] = str(al["timestamp"])
    finally:
        conn.close()

    case_row["escalated"] = bool(case_row["escalated"])

    # Fetch finding from ES
    es = get_es_client()
    finding_doc = None
    finding_id = case_row.get("finding_id")
    if finding_id:
        try:
            f_res = es.get(index="compliance_findings", id=finding_id)
            if f_res.get("found"):
                finding_doc = f_res.get("_source")
                # Enrich with regulation clause text if not already present
                if finding_doc and not finding_doc.get("regulation_clause_text"):
                    reg_id = finding_doc.get("regulation_chunk_id") or finding_doc.get("regulation_id")
                    if reg_id:
                        try:
                            r_res = es.get(index="regulations", id=reg_id)
                            if r_res.get("found"):
                                r_src = r_res.get("_source", {})
                                finding_doc["regulation_clause_text"] = r_src.get("clause_text") or r_src.get("chunk_text")
                                if not finding_doc.get("regulation_citation_label"):
                                    finding_doc["regulation_citation_label"] = r_src.get("citation_label")
                        except Exception:
                            pass
        except Exception as exc:
            logger.warning(f"Could not retrieve finding {finding_id} from ES: {exc}")

    # Fetch call from ES
    call_doc = None
    call_id = case_row.get("call_id")
    if call_id:
        try:
            c_res = es.get(index="calls", id=call_id)
            if c_res.get("found"):
                call_doc = c_res.get("_source")
        except Exception as exc:
            logger.warning(f"Could not retrieve call {call_id} from ES: {exc}")

        # Enrich call_doc with all cases for this call from MySQL
        # (the raw ES call document does NOT carry cases — that join is done at the API layer)
        if call_doc is not None:
            try:
                conn2 = get_db_connection()
                with conn2.cursor() as cur2:
                    cur2.execute(
                        """
                        SELECT case_id, finding_id, call_id, category, severity, status,
                               created_at, updated_at
                        FROM compliance_case
                        WHERE call_id = %s
                        ORDER BY created_at ASC
                        """,
                        (call_id,),
                    )
                    sibling_cases = cur2.fetchall()
                    for sc in sibling_cases:
                        if sc.get("created_at"):
                            sc["created_at"] = str(sc["created_at"])
                        if sc.get("updated_at"):
                            sc["updated_at"] = str(sc["updated_at"])
                    call_doc["cases"] = sibling_cases
                conn2.close()
            except Exception as exc:
                logger.warning(f"Could not enrich call {call_id} with sibling cases: {exc}")

    # Compute needs_review
    confidence = None
    if finding_doc and "confidence" in finding_doc:
        try:
            confidence = float(finding_doc["confidence"])
        except (ValueError, TypeError):
            confidence = None

    needs_review = (confidence is not None and confidence < threshold)

    return {
        "case": case_row,
        "finding": finding_doc,
        "call": call_doc,
        "activity_log": activity_logs,
        "confidence": confidence,
        "confidence_threshold": threshold,
        "needs_review": needs_review,
    }


@router.patch("/{case_id}/status")
def update_case_status(case_id: str, payload: CaseStatusUpdateRequest, response: Response):
    """
    Mark Reviewed or Dismiss a compliance case.
    Action must be 'mark_reviewed' or 'dismiss'.
    Rejects invalid state transitions with 409 Conflict.
    """
    action = payload.action.strip().lower()
    if action not in ("mark_reviewed", "dismiss"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_ACTION",
                "message": f"Action '{payload.action}' is invalid. Must be 'mark_reviewed' or 'dismiss'.",
            },
        )

    try:
        if action == "mark_reviewed":
            res = mark_reviewed(case_id, payload.reviewer_id, payload.notes)
        else:
            res = dismiss(case_id, payload.reviewer_id, payload.notes)

        if res.get("sync_status") == "partial":
            response.status_code = status.HTTP_207_MULTI_STATUS

        return res

    except CaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "CASE_NOT_FOUND", "message": str(exc)},
        )
    except ReviewerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "REVIEWER_NOT_FOUND", "message": str(exc)},
        )
    except CaseAlreadyResolvedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "CASE_ALREADY_RESOLVED", "message": str(exc)},
        )


@router.post("/{case_id}/escalate")
def escalate_case(case_id: str, payload: CaseEscalateRequest):
    """
    Escalate a compliance case to the committee.
    Escalated flag becomes true; status remains OPEN.
    Rejects duplicate escalation with 409 Conflict.
    """
    try:
        res = escalate(case_id, payload.reviewer_id, payload.notes)
        return res
    except CaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "CASE_NOT_FOUND", "message": str(exc)},
        )
    except ReviewerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "REVIEWER_NOT_FOUND", "message": str(exc)},
        )
    except CaseAlreadyEscalatedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "CASE_ALREADY_ESCALATED", "message": str(exc)},
        )


@router.post("/{case_id}/assign")
def assign_case(case_id: str, payload: CaseAssignRequest):
    """
    Assign or reassign a compliance case to a reviewer.
    """
    try:
        res = assign(case_id, payload.reviewer_id, payload.assignee_reviewer_id)
        return res
    except CaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "CASE_NOT_FOUND", "message": str(exc)},
        )
    except ReviewerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "REVIEWER_NOT_FOUND", "message": str(exc)},
        )


@router.post("/{case_id}/notes")
def add_case_note(case_id: str, payload: CaseNoteRequest):
    """
    Add an audit note to a case. Allowed on OPEN or RESOLVED cases.
    """
    try:
        res = add_note(case_id, payload.reviewer_id, payload.note_text)
        return res
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_NOTE", "message": str(exc)},
        )
    except CaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "CASE_NOT_FOUND", "message": str(exc)},
        )
    except ReviewerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "REVIEWER_NOT_FOUND", "message": str(exc)},
        )
