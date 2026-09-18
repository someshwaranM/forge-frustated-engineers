"""
Vigil — Phase 13: Elastic APM Core (backend/observability/apm.py)

Provides:
- Singleton Elastic APM client initialization from environment variables
- apm_span(): context manager for wrapping pipeline operations with APM spans
- report_error(): captures exceptions into Elastic APM
- is_apm_enabled(): check whether APM is active

Technology: elastic-apm (official Elastic Python APM agent)
Do NOT use OpenTelemetry, OTel SDKs, or OTEL_* variables.

Configuration (env vars):
  ELASTIC_APM_SERVER_URL    - APM Server endpoint (from Kibana > APM > Add Data)
  ELASTIC_APM_SECRET_TOKEN  - APM Secret Token
  ELASTIC_APM_SERVICE_NAME  - Service name (default: vigil-backend)
  ELASTIC_APM_ENVIRONMENT   - Environment label (default: production)
  ELASTIC_APM_ENABLED       - Set to "false" to disable APM (default: true)

All APM operations are wrapped in try/except.
APM failure NEVER propagates to the core compliance pipeline.
"""

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Optional

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy singleton — module-level reference only
# ---------------------------------------------------------------------------
_apm_client = None
_apm_initialized = False


def _initialize_apm():
    """Initialize the Elastic APM client once. Safely no-ops if not configured."""
    global _apm_client, _apm_initialized
    if _apm_initialized:
        return

    _apm_initialized = True

    enabled_str = os.getenv("ELASTIC_APM_ENABLED", "true").lower()
    if enabled_str in ("false", "0", "no", "off"):
        logger.info("[APM] Elastic APM disabled via ELASTIC_APM_ENABLED=false")
        return

    server_url = os.getenv("ELASTIC_APM_SERVER_URL", "")
    # Respect explicit env var names — do NOT guess from token format.
    # ELASTIC_APM_API_KEY  → send as api_key  (Elastic Cloud serverless / API key auth)
    # ELASTIC_APM_SECRET_TOKEN → send as secret_token (managed APM server / on-prem)
    explicit_api_key = os.getenv("ELASTIC_APM_API_KEY", "").strip()
    explicit_secret_token = os.getenv("ELASTIC_APM_SECRET_TOKEN", "").strip()
    service_name = os.getenv("ELASTIC_APM_SERVICE_NAME", "vigil-backend")
    environment = os.getenv("ELASTIC_APM_ENVIRONMENT", "production")

    if not server_url or (not explicit_api_key and not explicit_secret_token):
        logger.warning(
            "[APM] ELASTIC_APM_SERVER_URL or auth token not set. "
            "Elastic APM is disabled. Core pipeline will function normally."
        )
        return

    try:
        import elasticapm  # noqa: F401 — ensure package available

        # Explicit var priority: ELASTIC_APM_API_KEY takes precedence over ELASTIC_APM_SECRET_TOKEN.
        use_api_key = bool(explicit_api_key)

        # Pre-flight check: verify APM credentials to prevent background transport retry loop on 401
        try:
            import urllib.request
            import urllib.error
            check_req = urllib.request.Request(server_url)
            auth_val = f"ApiKey {explicit_api_key}" if use_api_key else f"Bearer {explicit_secret_token}"
            check_req.add_header("Authorization", auth_val)
            with urllib.request.urlopen(check_req, timeout=2.0) as _:
                pass
        except urllib.error.HTTPError as he:
            if he.code == 401:
                logger.warning(
                    "[APM] Elastic APM endpoint returned HTTP 401 (Unauthenticated). "
                    "APM is disabled to prevent background retry logs. "
                    "Update ELASTIC_APM_API_KEY in backend/.env to re-enable."
                )
                return
        except Exception:
            pass

        # Silence elasticapm background retry transport spam
        logging.getLogger("elasticapm.transport").setLevel(logging.CRITICAL)
        logging.getLogger("elasticapm.errors").setLevel(logging.ERROR)

        client_kwargs = {
            "service_name": service_name,
            "server_url": server_url,
            "environment": environment,
            "service_version": "1.0.0",
            "capture_body": "errors",
            "capture_headers": False,
        }
        if use_api_key:
            client_kwargs["api_key"] = explicit_api_key
        else:
            client_kwargs["secret_token"] = explicit_secret_token

        _apm_client = elasticapm.Client(**client_kwargs)
        logger.info(
            f"[APM] Elastic APM initialized: service='{service_name}' "
            f"env='{environment}' server='{server_url[:40]}...' "
            f"auth={'api_key' if use_api_key else 'secret_token'}"
        )
    except ImportError:
        logger.warning(
            "[APM] elastic-apm package not installed. Run: pip install elastic-apm"
        )
    except Exception as exc:
        logger.warning(f"[APM] Failed to initialize Elastic APM client: {exc}")


def get_apm_client():
    """Return the initialized Elastic APM Client, or None if APM is not available."""
    if not _apm_initialized:
        _initialize_apm()
    return _apm_client


def is_apm_enabled() -> bool:
    """Return True if Elastic APM is active."""
    return get_apm_client() is not None


@contextmanager
def apm_span(
    name: str,
    span_type: str = "app",
    span_subtype: str = "",
    labels: Optional[Dict[str, Any]] = None,
) -> Generator[None, None, None]:
    """
    Context manager that creates an Elastic APM span around a block of code.

    Usage:
        with apm_span("sarvam.transcription", "external", labels={"call_id": call_id}):
            result = client.process_audio(path)

    - If APM is not configured, this is a transparent no-op.
    - APM errors never propagate to the calling code.
    - Only safe labels are passed — never PII, never API keys.
    """
    client = get_apm_client()
    if client is None:
        yield
        return

    try:
        import elasticapm

        span_kwargs: Dict[str, Any] = {
            "name": name,
            "span_type": span_type,
        }
        if span_subtype:
            span_kwargs["span_subtype"] = span_subtype

        with elasticapm.capture_span(**span_kwargs):
            if labels:
                try:
                    elasticapm.label(**labels)
                except Exception:
                    pass
            yield
    except Exception as span_exc:
        # Last-resort: if APM span setup itself fails, still run the code
        logger.debug(f"[APM] span setup failed for '{name}': {span_exc}")
        yield


def report_error(exc: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None) -> None:
    """
    Capture an exception into Elastic APM.

    - Safe no-op if APM is not configured.
    - context: optional dict of safe labels (call_id, stage, etc.) — no PII.
    """
    client = get_apm_client()
    if client is None:
        return
    try:
        import elasticapm
        if context:
            for key, val in context.items():
                try:
                    elasticapm.label(**{key: str(val)})
                except Exception:
                    pass
        client.capture_exception()
    except Exception as cap_exc:
        logger.debug(f"[APM] error capture failed: {cap_exc}")


def set_transaction_labels(labels: Dict[str, Any]) -> None:
    """Set safe labels on the current APM transaction."""
    client = get_apm_client()
    if client is None:
        return
    try:
        import elasticapm
        elasticapm.label(**labels)
    except Exception:
        pass
