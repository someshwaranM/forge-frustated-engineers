"""
Vigil — Email Delivery Service (backend/reports/email_service.py)
Phase 15: Kibana Connector Transport & Recipient Validation

Communicates with Elastic Kibana's Run Connector API:
  POST {KIBANA_BASE_URL}/api/actions/connector/{KIBANA_CONNECTOR_ID}/_execute

Strict constraints:
- No raw SMTP credentials stored or handled.
- No file attachments accepted or forwarded.
- CRLF injection prevention on recipients and subject.
- Domain classification (internal vs external) for BFSI audit trail.
- Bounded retry on transient transport/timeout errors.
"""

import os
import re
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import httpx

logger = logging.getLogger("vigil.reports.email")

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)


class EmailServiceError(Exception):
    """Controlled exception for email delivery failures."""
    def __init__(self, message: str, error_code: str = "EMAIL_SEND_FAILED", status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code


class RecipientValidationError(Exception):
    """Validation failure on email recipients."""
    def __init__(self, message: str, error_code: str = "INVALID_RECIPIENT", status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code


def get_kibana_config() -> Dict[str, Any]:
    """Resolve Kibana email connector configuration from environment."""
    es_url = os.getenv("ELASTICSEARCH_URL", "").strip().rstrip("/")
    # Default Kibana URL derived from Elastic Cloud Elasticsearch URL if not explicitly set
    default_kb_url = ""
    if es_url:
        default_kb_url = es_url.replace(".es.", ".kb.").replace(":443", "")
    
    kibana_base_url = os.getenv("KIBANA_BASE_URL", default_kb_url).strip().rstrip("/")
    connector_id = os.getenv("KIBANA_CONNECTOR_ID", "vigil-mail").strip()
    api_key = os.getenv("ELASTIC_API_KEY") or os.getenv("ELASTICSEARCH_API_KEY", "")
    timeout_seconds = float(os.getenv("EMAIL_REQUEST_TIMEOUT_SECONDS", "20"))
    max_recipients = int(os.getenv("MAX_REPORT_RECIPIENTS", "5"))
    internal_domains = [
        d.strip().lower()
        for d in os.getenv("VIGIL_INTERNAL_EMAIL_DOMAINS", "vigil.com").split(",")
        if d.strip()
    ]

    return {
        "kibana_base_url": kibana_base_url,
        "connector_id": connector_id,
        "api_key": api_key.strip(),
        "timeout_seconds": timeout_seconds,
        "max_recipients": max_recipients,
        "internal_domains": internal_domains,
    }


def validate_recipients(recipients: Optional[List[str]]) -> Tuple[List[str], str]:
    """
    Validate, sanitize, and classify email recipients.
    
    Returns:
        Tuple of (clean_recipients_list, domain_class: "internal" | "external")
    Raises:
        RecipientValidationError on empty, invalid, or malformed input.
    """
    config = get_kibana_config()
    max_recipients = config["max_recipients"]
    internal_domains = config["internal_domains"]

    if not recipients or not isinstance(recipients, list):
        raise RecipientValidationError("At least one recipient email address is required.", error_code="RECIPIENT_REQUIRED")

    cleaned: List[str] = []
    seen = set()
    has_external = False

    for item in recipients:
        if not item or not isinstance(item, str):
            continue

        # CRLF Injection Prevention: reject control characters immediately
        if "\r" in item or "\n" in item or "%0a" in item.lower() or "%0d" in item.lower():
            logger.warning(f"CRLF control character detected in recipient candidate: {repr(item)}")
            raise RecipientValidationError(f"Invalid email recipient: Control characters are not allowed.", error_code="INVALID_RECIPIENT")

        normalized = item.strip().lower()
        if not normalized:
            continue

        if not EMAIL_REGEX.match(normalized):
            raise RecipientValidationError(f"Invalid email address syntax: '{item}'.", error_code="INVALID_RECIPIENT")

        if normalized not in seen:
            seen.add(normalized)
            cleaned.append(normalized)

            # Classify domain
            domain = normalized.split("@")[-1]
            if domain not in internal_domains:
                has_external = True

    if not cleaned:
        raise RecipientValidationError("At least one valid recipient email is required.", error_code="RECIPIENT_REQUIRED")

    if len(cleaned) > max_recipients:
        raise RecipientValidationError(
            f"Recipient list exceeds maximum allowed limit of {max_recipients} recipients.",
            error_code="MAX_RECIPIENTS_EXCEEDED"
        )

    domain_class = "external" if has_external else "internal"
    return cleaned, domain_class


def sanitize_header_text(text: str) -> str:
    """Sanitize subject and header fields to prevent CRLF injection."""
    if not text:
        return ""
    # Strip carriage returns and line feeds
    cleaned = text.replace("\r", " ").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", cleaned)


async def send_email(
    recipients: List[str],
    subject: str,
    html_body: str,
    plain_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send email through Elastic Kibana's .email connector (_execute API).
    
    Constraint: NO ATTACHMENTS ARE ACCEPTED OR SENT.
    """
    clean_recipients, domain_class = validate_recipients(recipients)
    clean_subject = sanitize_header_text(subject)

    config = get_kibana_config()
    kibana_base_url = config["kibana_base_url"]
    connector_id = config["connector_id"]
    api_key = config["api_key"]
    timeout_sec = config["timeout_seconds"]

    if not kibana_base_url:
        logger.error("KIBANA_BASE_URL is not configured.")
        raise EmailServiceError("Email delivery service is misconfigured (missing base URL).")

    if not api_key:
        logger.error("ELASTIC_API_KEY is not configured for Kibana connector execution.")
        raise EmailServiceError("Email delivery service authentication credentials are missing.")

    endpoint = f"{kibana_base_url}/api/actions/connector/{connector_id}/_execute"
    headers = {
        "Content-Type": "application/json",
        "kbn-xsrf": "true",
        "Authorization": f"ApiKey {api_key}",
    }

    payload = {
        "params": {
            "to": clean_recipients,
            "subject": clean_subject,
            "message": plain_text or "Please view the HTML version of this compliance report.",
            "messageHTML": html_body,
        }
    }

    # Bounded retry: 1 retry with short fixed delay on transient network/timeout errors only
    max_attempts = 2
    last_error: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(
                f"[Email] Attempt {attempt}/{max_attempts}: Executing Kibana connector '{connector_id}' "
                f"to {len(clean_recipients)} recipient(s) (domain_class={domain_class})"
            )

            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                response = await client.post(endpoint, headers=headers, json=payload)

            # Check HTTP level status
            if response.status_code != 200:
                logger.error(
                    f"[Email] Kibana connector execute returned HTTP {response.status_code}: {response.text[:500]}"
                )
                # 4xx errors from Kibana are configuration or client issues; do not retry
                if 400 <= response.status_code < 500:
                    raise EmailServiceError(
                        "Email connector request rejected by server.",
                        error_code="EMAIL_SEND_FAILED"
                    )
                raise EmailServiceError(
                    f"Email service returned status {response.status_code}.",
                    error_code="EMAIL_SEND_FAILED"
                )

            res_json = response.json()
            status_val = res_json.get("status")

            if status_val != "ok":
                err_msg = res_json.get("message") or "Unknown connector execution error."
                logger.error(f"[Email] Connector reported error: {err_msg}")
                raise EmailServiceError(
                    "Email provider was unable to dispatch the report.",
                    error_code="EMAIL_SEND_FAILED"
                )

            # Success
            logger.info(
                f"event=rm_report_email recipient_count={len(clean_recipients)} "
                f"domain_class={domain_class} status=SENT"
            )

            return {
                "success": True,
                "recipients": clean_recipients,
                "domain_class": domain_class,
                "connector_id": connector_id,
                "status": "SENT",
                "provider_response": res_json.get("data", {}).get("response", "OK"),
            }

        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as net_err:
            last_error = net_err
            logger.warning(
                f"[Email] Attempt {attempt}/{max_attempts} failed with network/timeout error: {net_err}"
            )
            if attempt < max_attempts:
                await asyncio.sleep(2.0)
                continue
        except EmailServiceError:
            raise
        except Exception as exc:
            logger.exception(f"[Email] Unexpected exception during email dispatch: {exc}")
            raise EmailServiceError("Unexpected error during report email dispatch.")

    # If retries exhausted
    logger.error(
        f"event=rm_report_email status=FAILED error_code=EMAIL_SEND_FAILED error='{last_error}'"
    )
    raise EmailServiceError(
        "Email delivery service was temporarily unreachable after retries.",
        error_code="EMAIL_SEND_FAILED"
    )
