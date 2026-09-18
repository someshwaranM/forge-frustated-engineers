"""
Vigil — Backend API Application Entrypoint (backend/main.py)

Phase 13: Elastic Observability
- Elastic APM middleware attached (elasticapm.contrib.starlette.ElasticAPM)
  auto-instruments all HTTP transactions. No OpenTelemetry.
- Structured ECS JSON logging configured at startup.
- Observability API routes registered under /api/observability/*
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Load environment
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)

# ---------------------------------------------------------------------------
# Phase 13: Initialize Elastic APM client & structured logging
# ---------------------------------------------------------------------------
from backend.observability.apm import _initialize_apm, get_apm_client
_initialize_apm()

from backend.observability.logging_config import configure_logging
configure_logging(client=get_apm_client())

# Phase 13: Attach ring-buffer handler so every logger.error() is auto-captured
# into the Observability Error Stream tab (no manual instrumentation needed)
from backend.api.routes.observability import configure_errors_log_capture
configure_errors_log_capture()

# Import routes
from backend.api.routes import (
    dashboard, calls, cases, benchmark, documents,
    settings, findings, chat, system, observability,
    auth, rm,
)
from backend.workflows.case_service import (
    CaseNotFoundError,
    CaseAlreadyResolvedError,
    CaseAlreadyEscalatedError,
    ReviewerNotFoundError,
)

logger = logging.getLogger("vigil.api")

app = FastAPI(
    title="Vigil Compliance Engine API",
    description="Backend API and case management workflow engine for Vigil",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Phase 13: Elastic APM Middleware
# Automatically creates APM transactions for every HTTP request.
# Must be added BEFORE CORS and other middleware.
# Uses elasticapm.contrib.starlette — native Elastic APM, NOT OpenTelemetry.
# ---------------------------------------------------------------------------
try:
    from elasticapm.contrib.starlette import ElasticAPM
    from backend.observability.apm import get_apm_client

    _apm_client = get_apm_client()
    if _apm_client is not None:
        app.add_middleware(ElasticAPM, client=_apm_client)
        logger.info("[APM] ElasticAPM Starlette middleware attached — all HTTP requests will be traced")
    else:
        logger.info("[APM] APM client not active — skipping ElasticAPM middleware")
except ImportError:
    logger.warning("[APM] elasticapm package not found. Run: pip install elastic-apm")
except Exception as exc:
    logger.warning(f"[APM] Failed to attach ElasticAPM middleware: {exc}")

# ---------------------------------------------------------------------------
# CORS Configuration
# Explicit origin list for browser dev environments without contradictory wildcard *
# ---------------------------------------------------------------------------
env_origins = os.getenv("CORS_ORIGINS", "")
if env_origins.strip():
    allowed_origins = [o.strip() for o in env_origins.split(",") if o.strip()]
else:
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Structured Exception Handlers
# ---------------------------------------------------------------------------

@app.exception_handler(CaseAlreadyResolvedError)
async def case_already_resolved_handler(request: Request, exc: CaseAlreadyResolvedError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error": "CASE_ALREADY_RESOLVED",
            "message": str(exc),
            "case_id": exc.case_id,
        },
    )


@app.exception_handler(CaseAlreadyEscalatedError)
async def case_already_escalated_handler(request: Request, exc: CaseAlreadyEscalatedError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error": "CASE_ALREADY_ESCALATED",
            "message": str(exc),
            "case_id": exc.case_id,
        },
    )


@app.exception_handler(CaseNotFoundError)
async def case_not_found_handler(request: Request, exc: CaseNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "CASE_NOT_FOUND",
            "message": str(exc),
            "case_id": exc.case_id,
        },
    )


@app.exception_handler(ReviewerNotFoundError)
async def reviewer_not_found_handler(request: Request, exc: ReviewerNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "REVIEWER_NOT_FOUND",
            "message": str(exc),
            "reviewer_id": exc.reviewer_id,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "message": exc.detail,
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid request parameters or payload.",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    # Phase 13: Report unhandled exceptions to Elastic APM
    from backend.observability.apm import report_error
    report_error(exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected server error occurred.",
        },
    )


# ---------------------------------------------------------------------------
# API Routes Inclusion
# ---------------------------------------------------------------------------

API_PREFIX = "/api"

app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(calls.router, prefix=API_PREFIX)
app.include_router(cases.router, prefix=API_PREFIX)
app.include_router(benchmark.router, prefix=API_PREFIX)
app.include_router(documents.router, prefix=API_PREFIX)
app.include_router(settings.router, prefix=API_PREFIX)
app.include_router(findings.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(system.router, prefix=API_PREFIX)
# Phase 13: Elastic Observability endpoints
app.include_router(observability.router, prefix=API_PREFIX)
# Authentication endpoints
app.include_router(auth.router, prefix=API_PREFIX)
# Phase 15: RM Analytics and compliance report endpoints
app.include_router(rm.router, prefix=API_PREFIX)


@app.on_event("startup")
def on_startup():
    """Ensure database tables and initial user credentials are ready on startup."""
    from backend.workflows.user_service import init_user_table_and_seed
    from backend.reports.rm_report_service import init_report_audit_table
    try:
        init_user_table_and_seed()
        logger.info("[Auth] Users table initialized and default credentials verified.")
    except Exception as exc:
        logger.warning(f"[Auth] Could not initialize users table on startup: {exc}")

    try:
        init_report_audit_table()
        logger.info("[Reports] Report audit log table verified.")
    except Exception as exc:
        logger.warning(f"[Reports] Could not initialize report audit table on startup: {exc}")


@app.get("/api/health", tags=["Health"])
def health_check():
    """Service health and connectivity probe."""
    from backend.observability.apm import is_apm_enabled
    return {
        "status": "ok",
        "service": "vigil-api",
        "version": "1.0.0",
        "apm_enabled": is_apm_enabled(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
