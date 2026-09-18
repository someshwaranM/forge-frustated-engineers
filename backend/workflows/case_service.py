"""
Vigil — Phase 8: Case Workflow Service (backend/workflows/case_service.py)

Manages compliance case workflow actions:
- mark_reviewed (CONFIRMED_ACTION_TAKEN)
- dismiss (DISMISSED_FALSE_POSITIVE)
- escalate (escalated=True)
- assign (reassignment or initial assignment)
- add_note (case notes)

Follows transactional dual-write discipline:
1. Atomic MySQL transaction (compliance_case + case_activity_log)
2. Post-commit denormalized status update on ES compliance_findings
3. Structured DRIFT_RISK logging and sync_status='partial' reporting on ES failure
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from backend.db.session import get_db_connection
from backend.elastic.client import get_es_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom Exceptions for Case Workflow
# ---------------------------------------------------------------------------

class CaseNotFoundError(Exception):
    def __init__(self, case_id: str):
        self.case_id = case_id
        super().__init__(f"Case '{case_id}' was not found.")


class CaseAlreadyResolvedError(Exception):
    def __init__(self, case_id: str, current_resolution: Optional[str] = None):
        self.case_id = case_id
        self.current_resolution = current_resolution
        super().__init__(f"Case '{case_id}' is already RESOLVED ({current_resolution or 'no resolution type specified'}).")


class CaseAlreadyEscalatedError(Exception):
    def __init__(self, case_id: str):
        self.case_id = case_id
        super().__init__(f"Case '{case_id}' has already been escalated to the committee.")


class ReviewerNotFoundError(Exception):
    def __init__(self, reviewer_id: str):
        self.reviewer_id = reviewer_id
        super().__init__(f"Reviewer '{reviewer_id}' does not exist.")


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _validate_reviewer_exists(cur, reviewer_id: str) -> None:
    """Validate that the given reviewer exists in MySQL (reviewer table or users table)."""
    cur.execute("SELECT reviewer_id FROM reviewer WHERE reviewer_id = %s", (reviewer_id,))
    if cur.fetchone():
        return
    cur.execute("SELECT user_id FROM users WHERE user_id = %s OR username = %s", (reviewer_id, reviewer_id))
    if cur.fetchone():
        return
    raise ReviewerNotFoundError(reviewer_id)


def _get_case_for_update(cur, case_id: str) -> Dict[str, Any]:
    """Fetch case row with FOR UPDATE lock for transactional mutation."""
    cur.execute(
        """
        SELECT case_id, finding_id, call_id, rm_id, customer_id, category,
               severity, status, escalated, assigned_to, created_at, updated_at,
               resolution_notes, resolution_type
        FROM compliance_case
        WHERE case_id = %s
        FOR UPDATE
        """,
        (case_id,),
    )
    case_row = cur.fetchone()
    if not case_row:
        raise CaseNotFoundError(case_id)
    return case_row


def _update_es_finding_status(case_id: str, finding_id: str, new_status: str) -> bool:
    """
    Update denormalized status on matching ES compliance_findings document.
    Returns True on success; returns False and logs DRIFT_RISK on failure.
    """
    if not finding_id:
        return True
    try:
        es = get_es_client()
        es.update(
            index="compliance_findings",
            id=finding_id,
            doc={"status": new_status, "updated_at": datetime.utcnow().isoformat() + "Z"},
            refresh="wait_for",
        )
        logger.info(f"Successfully dual-wrote status='{new_status}' to ES compliance_findings for finding {finding_id}")
        return True
    except Exception as exc:
        logger.error(
            "DRIFT_RISK: Failed to update denormalized status in Elasticsearch compliance_findings",
            extra={
                "event": "DRIFT_RISK",
                "case_id": case_id,
                "finding_id": finding_id,
                "attempted_status": new_status,
                "error": str(exc),
            },
        )
        print(f"[DRIFT_RISK] case_id={case_id} finding_id={finding_id} attempted_status={new_status} error={exc}")
        return False


# ---------------------------------------------------------------------------
# Public Workflow Operations
# ---------------------------------------------------------------------------

def mark_reviewed(case_id: str, reviewer_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Transition case to RESOLVED with resolution_type='CONFIRMED_ACTION_TAKEN'.
    Only valid when status == 'OPEN'.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            _validate_reviewer_exists(cur, reviewer_id)
            case = _get_case_for_update(cur, case_id)

            if case["status"] == "RESOLVED":
                raise CaseAlreadyResolvedError(case_id, case.get("resolution_type"))

            new_status = "RESOLVED"
            new_resolution_type = "CONFIRMED_ACTION_TAKEN"
            action = "STATUS_CHANGE"
            log_details = f"Status changed to RESOLVED (CONFIRMED_ACTION_TAKEN). Notes: {notes}" if notes else "Status changed to RESOLVED (CONFIRMED_ACTION_TAKEN)."

            # Update case
            cur.execute(
                """
                UPDATE compliance_case
                SET status = %s,
                    resolution_type = %s,
                    resolution_notes = %s,
                    updated_at = NOW()
                WHERE case_id = %s
                """,
                (new_status, new_resolution_type, notes, case_id),
            )

            # Insert activity log
            cur.execute(
                """
                INSERT INTO case_activity_log (case_id, action, actor, details, timestamp)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (case_id, action, reviewer_id, log_details),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # Step b: Post-commit ES dual-write
    es_ok = _update_es_finding_status(case_id, case["finding_id"], new_status)
    sync_status = "complete" if es_ok else "partial"

    return {
        "case_id": case_id,
        "finding_id": case["finding_id"],
        "status": new_status,
        "resolution_type": new_resolution_type,
        "escalated": bool(case["escalated"]),
        "assigned_to": case["assigned_to"],
        "resolution_notes": notes,
        "sync_status": sync_status,
        "message": f"Case {case_id} marked as reviewed and action taken."
        if es_ok
        else f"Case {case_id} marked as reviewed in MySQL, but ES synchronization is incomplete (drift risk logged).",
    }


def dismiss(case_id: str, reviewer_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Transition case to RESOLVED with resolution_type='DISMISSED_FALSE_POSITIVE'.
    Only valid when status == 'OPEN'.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            _validate_reviewer_exists(cur, reviewer_id)
            case = _get_case_for_update(cur, case_id)

            if case["status"] == "RESOLVED":
                raise CaseAlreadyResolvedError(case_id, case.get("resolution_type"))

            new_status = "RESOLVED"
            new_resolution_type = "DISMISSED_FALSE_POSITIVE"
            action = "STATUS_CHANGE"
            log_details = f"Status changed to RESOLVED (DISMISSED_FALSE_POSITIVE). Notes: {notes}" if notes else "Status changed to RESOLVED (DISMISSED_FALSE_POSITIVE)."

            cur.execute(
                """
                UPDATE compliance_case
                SET status = %s,
                    resolution_type = %s,
                    resolution_notes = %s,
                    updated_at = NOW()
                WHERE case_id = %s
                """,
                (new_status, new_resolution_type, notes, case_id),
            )

            cur.execute(
                """
                INSERT INTO case_activity_log (case_id, action, actor, details, timestamp)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (case_id, action, reviewer_id, log_details),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # Step b: Post-commit ES dual-write
    es_ok = _update_es_finding_status(case_id, case["finding_id"], new_status)
    sync_status = "complete" if es_ok else "partial"

    return {
        "case_id": case_id,
        "finding_id": case["finding_id"],
        "status": new_status,
        "resolution_type": new_resolution_type,
        "escalated": bool(case["escalated"]),
        "assigned_to": case["assigned_to"],
        "resolution_notes": notes,
        "sync_status": sync_status,
        "message": f"Case {case_id} dismissed as false positive."
        if es_ok
        else f"Case {case_id} dismissed in MySQL, but ES synchronization is incomplete (drift risk logged).",
    }


def escalate(case_id: str, reviewer_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Escalate case to committee. escalated=True, status UNCHANGED (stays OPEN).
    Only valid when escalated is False.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            _validate_reviewer_exists(cur, reviewer_id)
            case = _get_case_for_update(cur, case_id)

            if case["escalated"]:
                raise CaseAlreadyEscalatedError(case_id)

            action = "ESCALATED"
            log_details = f"Escalated to committee. Notes: {notes}" if notes else "Escalated to committee."

            cur.execute(
                """
                UPDATE compliance_case
                SET escalated = TRUE,
                    updated_at = NOW()
                WHERE case_id = %s
                """,
                (case_id,),
            )

            cur.execute(
                """
                INSERT INTO case_activity_log (case_id, action, actor, details, timestamp)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (case_id, action, reviewer_id, log_details),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "case_id": case_id,
        "finding_id": case["finding_id"],
        "status": case["status"],
        "resolution_type": case.get("resolution_type"),
        "escalated": True,
        "assigned_to": case["assigned_to"],
        "sync_status": "complete",
        "message": f"Case {case_id} successfully escalated to committee.",
    }


def assign(case_id: str, reviewer_id_performing_action: str, assignee_reviewer_id: str) -> Dict[str, Any]:
    """
    Assign case to a reviewer. Allowed regardless of current assignment.
    If assignee_reviewer_id is already the current assigned_to, succeeds without erroring
    and does not write a redundant activity-log entry.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            _validate_reviewer_exists(cur, reviewer_id_performing_action)
            _validate_reviewer_exists(cur, assignee_reviewer_id)
            case = _get_case_for_update(cur, case_id)

            if case["assigned_to"] == assignee_reviewer_id:
                # No-op reassignment
                return {
                    "case_id": case_id,
                    "finding_id": case["finding_id"],
                    "status": case["status"],
                    "resolution_type": case.get("resolution_type"),
                    "escalated": bool(case["escalated"]),
                    "assigned_to": assignee_reviewer_id,
                    "sync_status": "complete",
                    "message": f"Case {case_id} is already assigned to reviewer {assignee_reviewer_id}.",
                }

            action = "ASSIGNED"
            log_details = f"Assigned to reviewer {assignee_reviewer_id} by {reviewer_id_performing_action}."

            cur.execute(
                """
                UPDATE compliance_case
                SET assigned_to = %s,
                    updated_at = NOW()
                WHERE case_id = %s
                """,
                (assignee_reviewer_id, case_id),
            )

            cur.execute(
                """
                INSERT INTO case_activity_log (case_id, action, actor, details, timestamp)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (case_id, action, reviewer_id_performing_action, log_details),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "case_id": case_id,
        "finding_id": case["finding_id"],
        "status": case["status"],
        "resolution_type": case.get("resolution_type"),
        "escalated": bool(case["escalated"]),
        "assigned_to": assignee_reviewer_id,
        "sync_status": "complete",
        "message": f"Case {case_id} assigned to reviewer {assignee_reviewer_id}.",
    }


def add_note(case_id: str, reviewer_id: str, note_text: str) -> Dict[str, Any]:
    """
    Add note to case activity log. Allowed on OPEN or RESOLVED cases.
    Does not change status, resolution_type, or assigned_to.
    """
    if not note_text or not note_text.strip():
        raise ValueError("Note text cannot be empty.")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            _validate_reviewer_exists(cur, reviewer_id)
            case = _get_case_for_update(cur, case_id)

            action = "NOTE_ADDED"
            details = note_text.strip()

            cur.execute(
                """
                INSERT INTO case_activity_log (case_id, action, actor, details, timestamp)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (case_id, action, reviewer_id, details),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "case_id": case_id,
        "action": "NOTE_ADDED",
        "actor": reviewer_id,
        "details": note_text.strip(),
        "sync_status": "complete",
        "message": f"Note added to case {case_id}.",
    }
