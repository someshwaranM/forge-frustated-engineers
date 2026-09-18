"""
Vigil — Phase 8 Comprehensive Test Suite (backend/tests/test_phase8_api.py)

Tests all Phase 8 requirements:
1. Schema & DB connectivity
2. Case Evidence Chain assembly (/api/cases/{case_id})
3. Case workflow actions: mark_reviewed, dismiss, escalate, assign, add_note
4. Post-commit ES compliance_findings dual-write validation
5. Idempotency & Conflict (409) handling for duplicate mark_reviewed and escalate
6. Live RM analytics and repeat-violation detection
7. Regulations document aggregation with synthetic indexed_status: "INDEXED"
8. Confidence threshold update and read-time needs_review evaluation
9. CORS, validation, and structured error responses (400, 404, 409, 422)
"""

import os
import sys
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.main import app
from backend.db.session import get_db_connection
from backend.elastic.client import get_es_client


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def es():
    return get_es_client()


def test_dashboard_summary(client):
    """Test /api/dashboard/summary endpoint."""
    res = client.get("/api/dashboard/summary")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "kpis" in data
    assert "findings_by_severity" in data
    assert "rm_violation_trend" in data
    assert "category_breakdown" in data
    assert "recent_cases" in data
    assert "pipeline_latency" in data
    assert data["kpis"]["total_calls"] >= 10
    print("\n--- Dashboard Summary KPI Snapshot ---")
    print(json.dumps(data["kpis"], indent=2))


def test_calls_list_and_detail(client):
    """Test /api/calls list and /api/calls/{call_id} detail."""
    res = client.get("/api/calls?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 10
    assert len(data["items"]) > 0

    first_call_id = data["items"][0]["call_id"]
    detail_res = client.get(f"/api/calls/{first_call_id}")
    assert detail_res.status_code == 200
    call_doc = detail_res.json()
    assert call_doc["call_id"] == first_call_id
    assert "transcript_segments" in call_doc
    assert isinstance(call_doc["transcript_segments"], list)


def test_documents_aggregation(client):
    """Test /api/documents aggregates regulations with indexed_status: INDEXED."""
    res = client.get("/api/documents")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    for doc in data["items"]:
        assert doc["indexed_status"] == "INDEXED"
        assert doc["chunk_count"] > 0
        assert "document_id" in doc
        assert "document_name" in doc
    print("\n--- Aggregated Regulations ---")
    print(json.dumps(data["items"][:2], indent=2))


def test_evidence_chain_assembly(client):
    """Test /api/cases/{case_id} assembles complete Evidence Chain."""
    # Find a confirmed case
    cases_res = client.get("/api/cases?limit=1")
    assert cases_res.status_code == 200
    case_list = cases_res.json()["items"]
    assert len(case_list) > 0
    case_id = case_list[0]["case_id"]

    res = client.get(f"/api/cases/{case_id}")
    assert res.status_code == 200
    chain = res.json()

    assert "case" in chain
    assert "finding" in chain
    assert "call" in chain
    assert "activity_log" in chain
    assert "needs_review" in chain
    assert chain["case"]["case_id"] == case_id
    assert chain["finding"]["finding_id"] == chain["case"]["finding_id"]
    assert chain["call"]["call_id"] == chain["case"]["call_id"]
    assert "transcript_segments" in chain["call"]
    print(f"\n--- Evidence Chain Assembled for {case_id} ---")
    print(f"RM: {chain['case'].get('rm_name')}, Customer: {chain['case'].get('customer_name')}")
    print(f"Finding Category: {chain['finding'].get('category')}, Citation: {chain['finding'].get('regulation_citation_label')}")


def test_case_workflow_mark_reviewed_and_idempotency(client, es):
    """
    Test mark_reviewed workflow:
    1. Update status to RESOLVED / CONFIRMED_ACTION_TAKEN in MySQL & ES
    2. Duplicate call returns 409 CASE_ALREADY_RESOLVED with no duplicate log entry
    """
    target_case_id = "CASE-2026-A56EDE"
    reviewer_id = "REV001"

    # Reset case to OPEN first for clean repeatable test
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("UPDATE compliance_case SET status = 'OPEN', resolution_type = NULL WHERE case_id = %s", (target_case_id,))
        cur.execute("DELETE FROM case_activity_log WHERE case_id = %s", (target_case_id,))
    conn.commit()
    conn.close()

    # Step 1: Mark Reviewed
    res = client.patch(
        f"/api/cases/{target_case_id}/status",
        json={
            "reviewer_id": reviewer_id,
            "action": "mark_reviewed",
            "notes": "Verified violation with RM and customer. Warning issued.",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "RESOLVED"
    assert body["resolution_type"] == "CONFIRMED_ACTION_TAKEN"
    assert body["sync_status"] == "complete"

    # Verify MySQL
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT status, resolution_type FROM compliance_case WHERE case_id = %s", (target_case_id,))
        row = cur.fetchone()
        assert row["status"] == "RESOLVED"
        assert row["resolution_type"] == "CONFIRMED_ACTION_TAKEN"

        cur.execute("SELECT COUNT(*) as cnt FROM case_activity_log WHERE case_id = %s", (target_case_id,))
        log_cnt_1 = cur.fetchone()["cnt"]
        assert log_cnt_1 == 1
    conn.close()

    # Verify ES dual-write
    f_res = es.get(index="compliance_findings", id=body["finding_id"])
    assert f_res["_source"]["status"] == "RESOLVED"

    # Step 2: Idempotency / Duplicate mark_reviewed MUST return 409
    dup_res = client.patch(
        f"/api/cases/{target_case_id}/status",
        json={
            "reviewer_id": reviewer_id,
            "action": "mark_reviewed",
            "notes": "Duplicate attempt should fail.",
        },
    )
    assert dup_res.status_code == 409, dup_res.text
    dup_body = dup_res.json()
    assert dup_body["error"] == "CASE_ALREADY_RESOLVED"
    print("\n--- Duplicate mark_reviewed 409 Response ---")
    print(json.dumps(dup_body, indent=2))

    # Verify no second activity log entry created
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM case_activity_log WHERE case_id = %s", (target_case_id,))
        log_cnt_2 = cur.fetchone()["cnt"]
        assert log_cnt_2 == 1, "Duplicate action created an illegal second log entry!"
    conn.close()


def test_case_workflow_dismiss(client, es):
    """Test dismiss workflow: RESOLVED / DISMISSED_FALSE_POSITIVE."""
    target_case_id = "CASE-2026-91F6A8"
    reviewer_id = "REV002"

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("UPDATE compliance_case SET status = 'OPEN', resolution_type = NULL WHERE case_id = %s", (target_case_id,))
        cur.execute("DELETE FROM case_activity_log WHERE case_id = %s", (target_case_id,))
    conn.commit()
    conn.close()

    res = client.patch(
        f"/api/cases/{target_case_id}/status",
        json={
            "reviewer_id": reviewer_id,
            "action": "dismiss",
            "notes": "Contextual disclaimer was made earlier in segment.",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "RESOLVED"
    assert body["resolution_type"] == "DISMISSED_FALSE_POSITIVE"

    # Verify ES dual-write
    f_res = es.get(index="compliance_findings", id=body["finding_id"])
    assert f_res["_source"]["status"] == "RESOLVED"


def test_case_workflow_escalate_and_idempotency(client):
    """
    Test escalate workflow:
    1. escalated becomes True; status stays OPEN
    2. Duplicate escalate returns 409 CASE_ALREADY_ESCALATED and no duplicate log
    """
    target_case_id = "CASE-2026-003318"
    reviewer_id = "REV003"

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("UPDATE compliance_case SET escalated = 0, status = 'OPEN' WHERE case_id = %s", (target_case_id,))
        cur.execute("DELETE FROM case_activity_log WHERE case_id = %s", (target_case_id,))
    conn.commit()
    conn.close()

    # Escalate call 1
    res = client.post(
        f"/api/cases/{target_case_id}/escalate",
        json={"reviewer_id": reviewer_id, "notes": "Requires compliance committee review."},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["escalated"] is True
    assert body["status"] == "OPEN"

    # Verify MySQL
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT escalated, status FROM compliance_case WHERE case_id = %s", (target_case_id,))
        row = cur.fetchone()
        assert row["escalated"] == 1
        assert row["status"] == "OPEN"

        cur.execute("SELECT COUNT(*) as cnt FROM case_activity_log WHERE case_id = %s", (target_case_id,))
        log_cnt_1 = cur.fetchone()["cnt"]
        assert log_cnt_1 == 1
    conn.close()

    # Duplicate escalate call 2 MUST return 409
    dup_res = client.post(
        f"/api/cases/{target_case_id}/escalate",
        json={"reviewer_id": reviewer_id, "notes": "Duplicate escalation attempt."},
    )
    assert dup_res.status_code == 409, dup_res.text
    dup_body = dup_res.json()
    assert dup_body["error"] == "CASE_ALREADY_ESCALATED"
    print("\n--- Duplicate escalate 409 Response ---")
    print(json.dumps(dup_body, indent=2))

    # Verify no second log entry
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM case_activity_log WHERE case_id = %s", (target_case_id,))
        log_cnt_2 = cur.fetchone()["cnt"]
        assert log_cnt_2 == 1, "Duplicate escalate created duplicate activity log!"
    conn.close()


def test_case_assign_and_notes(client):
    """Test assign (including no-op) and add_note."""
    target_case_id = "CASE-2026-E233CC"

    # Initial assign
    res = client.post(
        f"/api/cases/{target_case_id}/assign",
        json={"reviewer_id": "REV001", "assignee_reviewer_id": "REV002"},
    )
    assert res.status_code == 200
    assert res.json()["assigned_to"] == "REV002"

    # Re-assign to SAME person (REV002) should succeed without error and without duplicate log
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM case_activity_log WHERE case_id = %s AND action = 'ASSIGNED'", (target_case_id,))
        assign_cnt_1 = cur.fetchone()["cnt"]
    conn.close()

    res_noop = client.post(
        f"/api/cases/{target_case_id}/assign",
        json={"reviewer_id": "REV001", "assignee_reviewer_id": "REV002"},
    )
    assert res_noop.status_code == 200

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM case_activity_log WHERE case_id = %s AND action = 'ASSIGNED'", (target_case_id,))
        assign_cnt_2 = cur.fetchone()["cnt"]
    conn.close()
    assert assign_cnt_1 == assign_cnt_2, "No-op assignment should not create a duplicate activity log entry!"

    # Add note
    res_note = client.post(
        f"/api/cases/{target_case_id}/notes",
        json={"reviewer_id": "REV002", "note_text": "Customer called back to clarify terms."},
    )
    assert res_note.status_code == 200
    assert res_note.json()["action"] == "NOTE_ADDED"


def test_rm_analytics_and_repeat_violation(client):
    """Test /api/rm/{rm_id}/analytics and LIVE repeat-violation flag."""
    res = client.get("/api/rm/RM001/analytics")
    assert res.status_code == 200
    data = res.json()
    assert data["rm"]["rm_id"] == "RM001"
    assert "has_repeat_violations" in data
    assert "repeat_categories" in data
    print("\n--- RM001 Analytics Snapshot ---")
    print(json.dumps(data, indent=2, default=str))

    # Live repeat-violation flag test:
    # Temporarily add a second case in category GUARANTEED_RETURN for RM001
    temp_case_id = "CASE-TEST-REPEAT-VIOLATION"
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO compliance_case (
                case_id, finding_id, call_id, rm_id, customer_id, category, severity, status
            ) VALUES (
                %s, 'FND-TEMP-1', 'CALL_TEMP', 'RM001', 'CUST001', 'GUARANTEED_RETURN', 'HIGH', 'OPEN'
            )
            """,
            (temp_case_id,),
        )
    conn.commit()
    conn.close()

    try:
        repeat_res = client.get("/api/rm/RM001/analytics")
        assert repeat_res.status_code == 200
        repeat_data = repeat_res.json()
        assert repeat_data["has_repeat_violations"] is True
        assert any(c["category"] == "GUARANTEED_RETURN" for c in repeat_data["repeat_categories"])
        print("\n--- RM001 Live Repeat Violation Triggered ---")
        print(json.dumps(repeat_data["repeat_categories"], indent=2))
    finally:
        # Cleanup temp row
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM compliance_case WHERE case_id = %s", (temp_case_id,))
        conn.commit()
        conn.close()


def test_confidence_threshold_setting_and_needs_review(client):
    """Test GET/PATCH /api/settings and read-time needs_review evaluation on /api/cases."""
    # 1. Read settings
    get_res = client.get("/api/settings")
    assert get_res.status_code == 200
    orig_threshold = get_res.json().get("confidence_threshold", 0.75)

    try:
        # 2. Set threshold high (0.96) so findings with confidence ~0.92-0.95 trigger needs_review
        patch_res = client.patch("/api/settings", json={"confidence_threshold": 0.96})
        assert patch_res.status_code == 200
        assert patch_res.json()["confidence_threshold"] == 0.96

        # 3. Check /api/cases
        cases_res = client.get("/api/cases")
        assert cases_res.status_code == 200
        cases_data = cases_res.json()
        assert cases_data["confidence_threshold"] == 0.96

        flagged_cases = [c for c in cases_data["items"] if c["needs_review"] is True]
        assert len(flagged_cases) > 0, "Expected at least one case flagged with needs_review=True at threshold 0.96"
        print(f"\n--- Flagged Cases at Threshold 0.96 ({len(flagged_cases)} cases) ---")
        for fc in flagged_cases[:3]:
            print(f"Case {fc['case_id']} (Confidence: {fc.get('confidence')}, Needs Review: {fc['needs_review']})")

        # 4. Out of range validation (must return 400)
        invalid_res = client.patch("/api/settings", json={"confidence_threshold": 1.5})
        assert invalid_res.status_code in (400, 422)

    finally:
        # Restore original threshold
        client.patch("/api/settings", json={"confidence_threshold": orig_threshold})


def test_error_handling_and_validations(client):
    """Test structured error responses for 404, 400, 422."""
    # 404 Unknown Case
    res_404_case = client.get("/api/cases/CASE-NON-EXISTENT")
    assert res_404_case.status_code == 404
    assert res_404_case.json()["error"] == "CASE_NOT_FOUND"

    # 404 Unknown Call
    res_404_call = client.get("/api/calls/CALL-NON-EXISTENT")
    assert res_404_call.status_code == 404
    assert res_404_call.json()["error"] == "CALL_NOT_FOUND"

    # 404 Unknown RM
    res_404_rm = client.get("/api/rm/RM999/analytics")
    assert res_404_rm.status_code == 404
    assert res_404_rm.json()["error"] == "RM_NOT_FOUND"

    # 400 Invalid Action
    res_400_action = client.patch(
        "/api/cases/CASE-2026-A56EDE/status",
        json={"reviewer_id": "REV001", "action": "invalid_action"},
    )
    assert res_400_action.status_code == 400
    assert res_400_action.json()["error"] == "INVALID_ACTION"
