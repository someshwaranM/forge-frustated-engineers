"""
Vigil — Phase 13: Structured Logging for Elastic Observability (backend/observability/logging_config.py)

Configures Python logging to emit JSON-structured log records in a format
compatible with Elastic Common Schema (ECS). When Elastic APM is active,
APM trace/transaction/span IDs are automatically injected into each log record,
enabling log-to-trace correlation in Elastic Observability.

Usage:
    from backend.observability.logging_config import configure_logging
    configure_logging()   # Call once at application startup (in main.py)
"""

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional


SERVICE_NAME = os.getenv("ELASTIC_APM_SERVICE_NAME", "vigil-backend")
SERVICE_ENVIRONMENT = os.getenv("ELASTIC_APM_ENVIRONMENT", "production")


class ECSFormatter(logging.Formatter):
    """
    JSON log formatter compatible with Elastic Common Schema (ECS).

    Emitted fields per log record:
      @timestamp        ISO-8601 UTC
      log.level         DEBUG / INFO / WARNING / ERROR / CRITICAL
      log.logger        logger name
      message           log message
      service.name      from ELASTIC_APM_SERVICE_NAME
      service.environment
      error.message     (only on ERROR/CRITICAL with exc_info)
      error.stack_trace (only on ERROR/CRITICAL with exc_info)
      transaction.id    Injected by elastic-apm if an active transaction exists
      trace.id          Injected by elastic-apm if an active transaction exists
      span.id           Injected by elastic-apm if an active span exists
    """

    def format(self, record: logging.LogRecord) -> str:
        doc: Dict[str, Any] = {
            "@timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "log": {
                "level": record.levelname,
                "logger": record.name,
            },
            "message": record.getMessage(),
            "service": {
                "name": SERVICE_NAME,
                "environment": SERVICE_ENVIRONMENT,
            },
        }

        # APM correlation IDs — injected by elastic-apm automatically if active
        for apm_field in ("transaction.id", "trace.id", "span.id"):
            val = getattr(record, apm_field.replace(".", "_"), None)
            if val:
                doc[apm_field] = val

        # Exception info
        if record.exc_info and record.exc_info[0] is not None:
            exc_type, exc_value, exc_tb = record.exc_info
            doc["error"] = {
                "message": str(exc_value),
                "type": exc_type.__name__ if exc_type else "Exception",
                "stack_trace": "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
            }

        # Extra fields attached via logger.info(..., extra={...})
        for key in record.__dict__:
            if key.startswith("vigil_") or key.startswith("labels_"):
                doc.setdefault("labels", {})[key] = record.__dict__[key]

        return json.dumps(doc, ensure_ascii=False)


def configure_logging(level: int = logging.INFO, client: Any = None) -> None:
    """
    Configure the root logger with ECS JSON output.
    Call once at application startup.

    If Elastic APM is enabled, the apm logging handler is also attached
    which injects trace IDs and forwards ERROR+ records to the APM server.
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Remove any default handlers
    for h in root.handlers[:]:
        root.removeHandler(h)

    # Stdout JSON handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(ECSFormatter())
    root.addHandler(stdout_handler)

    # Elastic APM log handler (injects trace IDs + ships errors to APM)
    try:
        from elasticapm.handlers.logging import LoggingHandler as APMLoggingHandler
        if client is None:
            from backend.observability.apm import get_apm_client
            client = get_apm_client()
        
        if client is not None:
            apm_log_handler = APMLoggingHandler(client=client)
        else:
            apm_log_handler = APMLoggingHandler()
        apm_log_handler.setLevel(logging.ERROR)
        root.addHandler(apm_log_handler)
        logging.getLogger(__name__).info("[Logging] Elastic APM logging handler attached (ERROR+)")
    except ImportError:
        pass  # elastic-apm not installed — fine
    except Exception as exc:
        logging.getLogger(__name__).debug(f"[Logging] APM handler attach failed: {exc}")

    logging.getLogger(__name__).info(
        f"[Logging] Structured JSON logging configured: service={SERVICE_NAME}, env={SERVICE_ENVIRONMENT}"
    )


def log_pipeline_event(
    logger_instance: logging.Logger,
    event: str,
    call_id: Optional[str] = None,
    stage: Optional[str] = None,
    status: Optional[str] = None,
    duration_ms: Optional[float] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
    level: int = logging.INFO,
    exc_info: bool = False,
) -> None:
    """
    Emit a structured pipeline event log with standard safe fields.

    Parameters
    ----------
    logger_instance : Logger to use
    event           : Event action name, e.g. "sarvam.transcription.completed"
    call_id         : Safe call identifier (no PII)
    stage           : Pipeline stage name
    status          : "success" | "failed" | "started"
    duration_ms     : Duration in milliseconds if completed
    extra_fields    : Additional safe fields (no PII)
    level           : logging level
    exc_info        : Whether to attach exc_info
    """
    extra: Dict[str, Any] = {}
    if call_id:
        extra["labels_call_id"] = call_id
    if stage:
        extra["labels_stage"] = stage
    if status:
        extra["labels_status"] = status
    if duration_ms is not None:
        extra["labels_duration_ms"] = round(duration_ms, 2)
    if extra_fields:
        for k, v in extra_fields.items():
            extra[f"labels_{k}"] = v

    msg = f"[{event}]"
    if call_id:
        msg += f" call_id={call_id}"
    if status:
        msg += f" status={status}"
    if duration_ms is not None:
        msg += f" duration={duration_ms:.0f}ms"

    logger_instance.log(level, msg, exc_info=exc_info, extra=extra)
