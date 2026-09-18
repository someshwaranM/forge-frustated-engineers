"""
Vigil — Phase 15 Automated Test Suite (backend/tests/test_phase15_reports.py)

Tests:
1. Recipient validation, normalization, CRLF injection guard, and domain classification.
2. Authoritative RM compliance report data assembly (RM005, RM001, unknown RM, clean state).
3. Responsive HTML & plain-text report renderer (escaping, Indic font fallback, cards, badges).
4. Email service transport with Kibana connector & error handling.
5. POST /api/rm/{rm_id}/report/email endpoint:
   - Authentication (401 on missing token)
   - Role authorization (403 on unauthorized role)
   - 404 RM_NOT_FOUND
   - 422 INVALID_RECIPIENT / RECIPIENT_REQUIRED
   - 200 Success response
   - Request-level idempotency
6. MySQL audit trail logging in report_audit_log.
"""

import os
import sys
from pathlib import Path
import json
import pytest
from unittest.mock import patch, AsyncMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from backend.main import app
from backend.db.session import get_db_connection
from backend.reports.email_service import (
    validate_recipients,
    RecipientValidationError,
    EmailServiceError,
    send_email,
)
from backend.reports.rm_report_service import (
    get_rm_report_data,
    RMNotFoundError,
    check_idempotency,
    store_idempotency_result,
    init_report_audit_table,
)
from backend.reports.rm_report_renderer import (
    render_rm_report_html,
    render_rm_report_text,
    esc,
)
from backend.workflows.user_service import create_access_token


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_headers():
    """Generate JWT auth headers for default Audit Officer."""
    user = {
        "user_id": "USR-001",
        "username": "admin",
        "email": "audit.officer@vigil.com",
        "role": "Audit Officer",
        "team": "Compliance",
        "access_level": "All",
        "full_name": "Audit Officer",
    }
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Recipient Validation Tests
# ---------------------------------------------------------------------------

def test_recipient_validation_success():
    clean, domain_class = validate_recipients(["  Audit.Officer@Vigil.com  ", "audit.officer@vigil.com"])
    assert len(clean) == 1
    assert clean[0] == "audit.officer@vigil.com"
    assert domain_class == "internal"


def test_recipient_validation_external_domain():
    clean, domain_class = validate_recipients(["compliance.reviewer@gmail.com"])
    assert clean[0] == "compliance.reviewer@gmail.com"
    assert domain_class == "external"


def test_recipient_validation_empty():
    with pytest.raises(RecipientValidationError) as exc:
        validate_recipients([])
    assert exc.value.error_code == "RECIPIENT_REQUIRED"


def test_recipient_validation_malformed():
    with pytest.raises(RecipientValidationError) as exc:
        validate_recipients(["not-an-email"])
    assert exc.value.error_code == "INVALID_RECIPIENT"


def test_recipient_validation_crlf_injection():
    with pytest.raises(RecipientValidationError) as exc:
        validate_recipients(["test@vigil.com\r\nBcc: evil@attacker.com"])
    assert exc.value.error_code == "INVALID_RECIPIENT"


def test_recipient_validation_max_limit():
    too_many = [f"user{i}@vigil.com" for i in range(10)]
    with pytest.raises(RecipientValidationError) as exc:
        validate_recipients(too_many)
    assert exc.value.error_code == "MAX_RECIPIENTS_EXCEEDED"


# ---------------------------------------------------------------------------
# 2. Authoritative Report Data Assembly Tests
# ---------------------------------------------------------------------------

def test_report_data_assembly_rm005():
    """RM005 (Rahul Desai) should have authoritative calls and findings loaded."""
    data = get_rm_report_data("RM005")
    assert data["rm"]["rm_id"] == "RM005"
    assert data["rm"]["full_name"] == "Rahul Desai"
    assert data["metrics"]["total_calls"] >= 2
    assert data["metrics"]["total_findings"] >= 1
    assert len(data["calls"]) >= 2
    assert "report_id" in data
    assert "status_evaluation" in data
    print("\n--- RM005 Report Telemetry Verified ---")
    print("Report ID:", data["report_id"])
    print("Headline:", data["status_evaluation"]["headline"])


def test_report_data_assembly_rm001():
    """RM001 (Arjun Mehta) should load high severity and repeat violation data."""
    data = get_rm_report_data("RM001")
    assert data["rm"]["rm_id"] == "RM001"
    assert data["rm"]["full_name"] == "Arjun Mehta"
    assert data["metrics"]["high_severity_count"] >= 1
    assert any(c["violation_status"] == "REVIEW REQUIRED" for c in data["calls"])


def test_report_data_unknown_rm():
    """Querying a nonexistent RM should raise RMNotFoundError."""
    with pytest.raises(RMNotFoundError):
        get_rm_report_data("RM999_NONEXISTENT")


# ---------------------------------------------------------------------------
# 3. HTML & Plain-Text Report Renderer Tests
# ---------------------------------------------------------------------------

def test_html_and_text_renderer():
    data = get_rm_report_data("RM005")
    html_out = render_rm_report_html(data)
    text_out = render_rm_report_text(data)

    # Email HTML compliance checks
    assert "<!DOCTYPE html>" in html_out
    assert '<meta charset="UTF-8">' in html_out
    assert "Noto Sans" in html_out
    assert "Noto Sans Devanagari" in html_out
    assert "Noto Sans Tamil" in html_out
    assert esc(data["rm"]["full_name"]) in html_out
    assert data["report_id"] in html_out

    # Plain text checks
    assert "VIGIL" in text_out
    assert data["rm"]["full_name"] in text_out


def test_html_escaping_security():
    """Verify that potentially hostile injection strings are escaped."""
    malicious_data = {
        "report_id": "RPT-TEST-XSS",
        "generated_at": "2026-09-16",
        "rm": {
            "rm_id": "RM005",
            "full_name": "<script>alert('xss')</script>",
            "branch": "Branch <img src=x onerror=alert(1)>",
            "region": "West Region",
            "manager_name": "Manager",
            "joined_date": "2023-01-01",
        },
        "metrics": {
            "total_calls": 1,
            "clean_calls": 0,
            "calls_with_findings": 1,
            "open_cases": 1,
            "risk_score": 50,
            "reporting_period": "2026",
        },
        "status_evaluation": {
            "status_type": "REVIEW_REQUIRED",
            "headline": "<iframe src='evil.com'>",
            "summary": "Summary & notes",
        },
        "calls": [],
        "findings": [],
        "cases": [],
    }

    html_out = render_rm_report_html(malicious_data)
    assert "<script>" not in html_out
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in html_out
    assert "<img src=x" not in html_out
    assert "<iframe" not in html_out


# ---------------------------------------------------------------------------
# 4. Email Transport Service Tests
# ---------------------------------------------------------------------------

def test_email_service_mocked_success():
    """Test send_email with mocked Kibana HTTP transport."""
    import asyncio
    mock_res = {
        "status": "ok",
        "data": {
            "accepted": ["audit.officer@vigil.com"],
            "rejected": [],
            "response": "250 2.0.0 OK",
        },
        "connector_id": "vigil-mail",
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(status_code=200, json=lambda: mock_res)
        result = asyncio.run(
            send_email(
                recipients=["audit.officer@vigil.com"],
                subject="Test Subject",
                html_body="<h1>Report</h1>",
            )
        )
        assert result["success"] is True
        assert result["status"] == "SENT"
        assert result["recipients"] == ["audit.officer@vigil.com"]


def test_email_service_provider_failure():
    """Connector error response should raise EmailServiceError with 502."""
    import asyncio
    mock_res = {
        "status": "error",
        "message": "SMTP connection refused",
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(status_code=200, json=lambda: mock_res)
        with pytest.raises(EmailServiceError) as exc:
            asyncio.run(
                send_email(
                    recipients=["audit.officer@vigil.com"],
                    subject="Test Subject",
                    html_body="<h1>Report</h1>",
                )
            )
        assert exc.value.status_code == 502
        assert exc.value.error_code == "EMAIL_SEND_FAILED"


# ---------------------------------------------------------------------------
# 5. API Route Tests: POST /api/rm/{rm_id}/report/email
# ---------------------------------------------------------------------------

def test_api_report_unauthenticated(client):
    """Missing auth token must return 401."""
    res = client.post(
        "/api/rm/RM005/report/email",
        json={"recipients": ["audit.officer@vigil.com"]},
    )
    assert res.status_code == 401


def test_api_report_unauthorized_role(client):
    """User with unprivileged role should be rejected with 403."""
    unauthorized_user = {
        "user_id": "USR-UNPRIVILEGED",
        "username": "guest",
        "email": "guest@vigil.com",
        "role": "Guest Viewer",
        "team": "Sales",
        "access_level": "None",
        "full_name": "Guest",
    }
    token = create_access_token(unauthorized_user)
    res = client.post(
        "/api/rm/RM005/report/email",
        headers={"Authorization": f"Bearer {token}"},
        json={"recipients": ["audit.officer@vigil.com"]},
    )
    assert res.status_code == 403
    assert res.json()["error"] == "FORBIDDEN"


def test_api_report_nonexistent_rm(client, auth_headers):
    """Attempting to dispatch a report for unknown RM returns 404."""
    res = client.post(
        "/api/rm/RM999_NONEXISTENT/report/email",
        headers=auth_headers,
        json={"recipients": ["audit.officer@vigil.com"]},
    )
    assert res.status_code == 404
    assert res.json()["error"] == "RM_NOT_FOUND"


def test_api_report_invalid_recipient(client, auth_headers):
    """Malformed recipient email returns 422."""
    res = client.post(
        "/api/rm/RM005/report/email",
        headers=auth_headers,
        json={"recipients": ["not-an-email"]},
    )
    assert res.status_code == 422
    assert res.json()["error"] == "INVALID_RECIPIENT"


def test_api_report_send_success_and_idempotency(client, auth_headers):
    """
    Successful dispatch:
    1. Returns 200 with report_id and sent_at.
    2. Replaying with same request_id returns cached idempotent result.
    """
    mock_res = {
        "status": "ok",
        "data": {
            "accepted": ["audit.officer@vigil.com"],
            "rejected": [],
            "response": "250 2.0.0 OK",
        },
        "connector_id": "vigil-mail",
    }

    import uuid
    test_request_id = f"req_test_idempotency_{uuid.uuid4().hex[:8]}"

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(status_code=200, json=lambda: mock_res)

        # First request
        res1 = client.post(
            "/api/rm/RM005/report/email",
            headers=auth_headers,
            json={
                "recipients": ["audit.officer@vigil.com"],
                "request_id": test_request_id,
            },
        )
        assert res1.status_code == 200, res1.text
        body1 = res1.json()
        assert body1["success"] is True
        assert body1["rm_id"] == "RM005"
        assert "report_id" in body1
        assert "sent_at" in body1
        assert body1.get("idempotent_replay") is None

        # Second request (same request_id -> idempotency hit)
        res2 = client.post(
            "/api/rm/RM005/report/email",
            headers=auth_headers,
            json={
                "recipients": ["audit.officer@vigil.com"],
                "request_id": test_request_id,
            },
        )
        assert res2.status_code == 200
        body2 = res2.json()
        assert body2["success"] is True
        assert body2["idempotent_replay"] is True
        assert body2["report_id"] == body1["report_id"]


# ---------------------------------------------------------------------------
# 6. MySQL Audit Trail Logging Verification
# ---------------------------------------------------------------------------

def test_report_audit_log_persisted():
    """Verify report_audit_log table contains entries with proper domain classification."""
    init_report_audit_table()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT report_id, rm_id, requested_by, recipients, status, recipient_domain_class
                FROM report_audit_log
                WHERE rm_id = 'RM005'
                ORDER BY log_id DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            assert row is not None, "Expected an audit log row for RM005"
            assert row["rm_id"] == "RM005"
            assert row["status"] in ("SENT", "REQUESTED", "FAILED")
            assert row["recipient_domain_class"] in ("internal", "external")
            print("\n--- Audit Row Verified in MySQL ---")
            print(json.dumps(row, indent=2, default=str))
    finally:
        conn.close()
