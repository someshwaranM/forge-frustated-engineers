"""
Vigil — Reports Module (backend/reports/__init__.py)
Phase 15: RM Compliance Report Generation & Email Delivery
"""

from .email_service import send_email, validate_recipients, EmailServiceError
from .rm_report_service import get_rm_report_data, record_report_audit, check_idempotency
from .rm_report_renderer import render_rm_report_html, render_rm_report_text

__all__ = [
    "send_email",
    "validate_recipients",
    "EmailServiceError",
    "get_rm_report_data",
    "record_report_audit",
    "check_idempotency",
    "render_rm_report_html",
    "render_rm_report_text",
]
