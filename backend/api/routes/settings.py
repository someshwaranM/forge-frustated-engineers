"""
Vigil — Settings API Routes (backend/api/routes/settings.py)
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.db.session import get_db_connection
from backend.elastic.client import get_es_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings"])


class SettingsUpdateRequest(BaseModel):
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    active_ai_provider: str | None = None


def get_current_confidence_threshold() -> float:
    """Read the stored confidence_threshold from MySQL app_settings (default 0.75)."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'confidence_threshold'")
            row = cur.fetchone()
            if row and row.get("setting_value") is not None:
                try:
                    return float(row["setting_value"])
                except (ValueError, TypeError):
                    pass
    except Exception as exc:
        logger.warning(f"Failed to read confidence_threshold from app_settings: {exc}")
    finally:
        conn.close()
    return 0.75


@router.get("", response_model=Dict[str, Any])
def get_settings():
    """Retrieve all configuration settings from app_settings."""
    conn = get_db_connection()
    settings_dict = {}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT setting_key, setting_value, updated_at FROM app_settings")
            rows = cur.fetchall()
            for r in rows:
                key = r["setting_key"]
                val = r["setting_value"]
                # Type conversion for known keys
                if key == "confidence_threshold":
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        pass
                settings_dict[key] = val
    finally:
        conn.close()
    return settings_dict


@router.patch("", response_model=Dict[str, Any])
def update_settings(payload: SettingsUpdateRequest):
    """
    Update app_settings values.
    Validates confidence_threshold is a float between 0.0 and 1.0.
    """
    updates = {}
    if payload.confidence_threshold is not None:
        if not (0.0 <= payload.confidence_threshold <= 1.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="confidence_threshold must be a float between 0.0 and 1.0 inclusive.",
            )
        updates["confidence_threshold"] = str(round(payload.confidence_threshold, 4))

    if payload.active_ai_provider is not None:
        provider = payload.active_ai_provider.strip().lower()
        if provider not in ("bedrock", "gemini"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="active_ai_provider must be either 'bedrock' or 'gemini'.",
            )
        updates["active_ai_provider"] = provider

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid settings provided for update.",
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            for k, v in updates.items():
                cur.execute(
                    """
                    INSERT INTO app_settings (setting_key, setting_value, updated_at)
                    VALUES (%s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        setting_value = VALUES(setting_value),
                        updated_at = NOW()
                    """,
                    (k, v),
                )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error(f"Failed to update app_settings: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database update failed: {exc}",
        )
    finally:
        conn.close()

    return get_settings()


@router.get("/provider-status", response_model=Dict[str, Any])
def get_provider_status():
    """
    Computes real AI inference provider usage from compliance_findings documents.
    Determines whether Bedrock or Gemini (or fallback) executed for recorded findings.
    """
    es = get_es_client()
    bedrock_count = 0
    gemini_count = 0
    total_findings = 0

    try:
        agg = es.search(
            index="compliance_findings",
            size=0,
            aggs={
                "by_provider": {
                    "terms": {"field": "provider_used", "size": 10}
                }
            },
        )
        total_findings = agg.get("hits", {}).get("total", {}).get("value", 0)
        buckets = agg.get("aggregations", {}).get("by_provider", {}).get("buckets", [])
        for b in buckets:
            p_key = b["key"].lower()
            if "bedrock" in p_key or "claude" in p_key:
                bedrock_count += b["doc_count"]
            elif "gemini" in p_key:
                gemini_count += b["doc_count"]
    except Exception as exc:
        logger.warning(f"Failed to query provider_used from compliance_findings: {exc}")

    fallback_triggered = gemini_count > 0

    return {
        "total_findings_analyzed": total_findings,
        "primary_provider": {
            "name": "AWS Bedrock (Claude 3.5 Sonnet)",
            "key": "bedrock",
            "findings_count": bedrock_count,
            "status": "ACTIVE" if bedrock_count > 0 else "STANDBY",
            "description": "Primary acoustic transcription & evidence chain extraction",
        },
        "secondary_provider": {
            "name": "Google Gemini 1.5 Flash / Pro",
            "key": "gemini",
            "findings_count": gemini_count,
            "status": "ACTIVE (FALLBACK FIRED)" if gemini_count > 0 else "STANDBY",
            "description": "Automated circuit-breaker fallback engine",
        },
        "fallback_triggered": fallback_triggered,
        "providers_breakdown": [
            {"provider": "Google Gemini", "key": "gemini", "count": gemini_count, "active": gemini_count > 0},
            {"provider": "AWS Bedrock", "key": "bedrock", "count": bedrock_count, "active": bedrock_count > 0},
        ],
    }
