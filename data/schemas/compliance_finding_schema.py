"""
Vigil — Compliance Finding Schema.

Defines the authoritative Pydantic model for ComplianceFinding entities across:
- Elasticsearch 'compliance_findings' index (denormalized 23-field document)
- MySQL 'compliance_case' table integration (dual-write status and relational links)
- Investigator Agent output validation (Bedrock / Gemini fallback)
- FastAPI routes and React frontend evidence-chain consumers
"""

from datetime import datetime
from typing import Literal, Optional, Union, Any, Dict
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


def _parse_timestamp(val: Union[float, int, str]) -> float:
    """
    Parse a timestamp representation into float seconds.
    Accepts:
      - float or int: 84.5 -> 84.5
      - str in "MM:SS": "01:24" -> 84.0
      - str in "HH:MM:SS": "01:02:03" -> 3723.0
      - numeric str: "84.5" -> 84.5
    """
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.strip()
        if ":" in val:
            parts = val.split(":")
            if len(parts) == 2:
                return float(int(parts[0]) * 60 + float(parts[1]))
            elif len(parts) == 3:
                return float(int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2]))
        return float(val)
    raise ValueError(f"Invalid timestamp format: {val}")


def _format_seconds(seconds: float) -> str:
    """Format seconds into MM:SS string."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"


class ComplianceFinding(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    # Identifiers
    finding_id: str = Field(..., description="Unique finding ID (e.g. 'FND-2026-8812')")
    call_id: str = Field(..., description="Reference to the call in calls index and MySQL")
    rm_id: str = Field(default="UNKNOWN_RM", description="Reference to rm.rm_id in MySQL")
    customer_id: str = Field(default="UNKNOWN_CUST", description="Reference to customer.customer_id in MySQL")

    # Classification
    category: str = Field(..., description="Violation category, e.g. 'GUARANTEED_RETURNS', 'SUITABILITY_MISMATCH'")
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(..., description="Violation severity level")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score between 0.0 and 1.0")
    status: Literal["OPEN", "RESOLVED"] = Field(
        default="OPEN",
        description="Dual-write status field synchronized with MySQL compliance_case.status",
    )

    # Temporal & dialogue evidence
    timestamp_start: float = Field(..., description="Start timestamp of violation in call (seconds)")
    timestamp_end: float = Field(..., description="End timestamp of violation in call (seconds)")
    transcript_evidence: str = Field(..., description="Verbatim transcript excerpt evidencing the violation")

    # Risk profiling context
    customer_risk_profile: str = Field(..., description="Customer risk classification, e.g. 'Conservative'")
    product_risk_class: str = Field(..., description="Product risk tier, e.g. 'Very High'")

    # Denormalized regulatory link
    regulation_chunk_id: str = Field(
        default="",
        description="Denormalized chunk_id from regulations Elasticsearch index",
    )
    regulation_citation_label: str = Field(
        default="",
        description="Standard citation string, e.g. 'AMFI Distributor Code §II.4.g, p.5'",
    )
    regulation_source_url: Optional[str] = Field(
        default=None,
        description="Direct URL to official regulatory PDF/document",
    )
    regulation_id: Optional[str] = Field(
        default=None,
        description="Backwards-compatible alias or shorthand identifier for regulation",
    )
    regulation_clause_text: Optional[str] = Field(
        default=None,
        description="Verbatim text of the cited regulatory clause from regulations index",
    )

    # LLM forensic reasoning & remedy
    reasoning: str = Field(..., description="Detailed forensic rationale explaining the breach")
    recommended_action: str = Field(..., description="Actionable remediation recommended for compliance team")

    # Audit & pipeline metadata
    provider_used: Optional[str] = Field(
        default=None,
        description="AI provider that generated this finding ('bedrock', 'gemini', 'mock')",
    )
    bm25_score: Optional[float] = Field(default=None, description="BM25 retrieval score against regulations index")
    semantic_score: Optional[float] = Field(default=None, description="Semantic vector similarity score")
    created_at: Optional[Union[datetime, str]] = Field(default=None, description="Timestamp when finding was created")
    updated_at: Optional[Union[datetime, str]] = Field(default=None, description="Timestamp when finding was updated")

    @field_validator("timestamp_start", "timestamp_end", mode="before")
    @classmethod
    def parse_timestamps(cls, v: Any) -> float:
        return _parse_timestamp(v)

    @model_validator(mode="before")
    @classmethod
    def align_regulatory_and_temporal_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Bidirectional sync between regulation_id and regulation_chunk_id
            reg_id = data.get("regulation_id")
            chunk_id = data.get("regulation_chunk_id")

            if reg_id and not chunk_id:
                data["regulation_chunk_id"] = reg_id
            elif chunk_id and not reg_id:
                data["regulation_id"] = chunk_id

            # Default citation label if absent
            if not data.get("regulation_citation_label"):
                data["regulation_citation_label"] = data.get("regulation_chunk_id") or data.get("regulation_id") or ""

            # Ensure timestamps default to 0.0 if not provided in mock stubs
            if "timestamp_start" not in data and "start_time" in data:
                data["timestamp_start"] = data["start_time"]
            if "timestamp_end" not in data and "end_time" in data:
                data["timestamp_end"] = data["end_time"]

        return data

    @property
    def timestamp_display(self) -> str:
        """Return formatted display range, e.g. '01:24 - 01:42'."""
        return f"{_format_seconds(self.timestamp_start)} - {_format_seconds(self.timestamp_end)}"

    def to_es_doc(self) -> Dict[str, Any]:
        """Convert finding into Elasticsearch compliance_findings document dict."""
        created_str = (
            self.created_at.isoformat() if isinstance(self.created_at, datetime)
            else (self.created_at or datetime.utcnow().isoformat() + "Z")
        )
        updated_str = (
            self.updated_at.isoformat() if isinstance(self.updated_at, datetime)
            else (self.updated_at or datetime.utcnow().isoformat() + "Z")
        )

        return {
            "finding_id": self.finding_id,
            "call_id": self.call_id,
            "rm_id": self.rm_id,
            "customer_id": self.customer_id,
            "category": self.category,
            "severity": self.severity,
            "confidence": float(self.confidence),
            "status": self.status,
            "timestamp_start": float(self.timestamp_start),
            "timestamp_end": float(self.timestamp_end),
            "transcript_evidence": self.transcript_evidence,
            "customer_risk_profile": self.customer_risk_profile,
            "product_risk_class": self.product_risk_class,
            "regulation_chunk_id": self.regulation_chunk_id,
            "regulation_citation_label": self.regulation_citation_label,
            "regulation_source_url": self.regulation_source_url,
            "regulation_clause_text": self.regulation_clause_text,
            "reasoning": self.reasoning,
            "recommended_action": self.recommended_action,
            "provider_used": self.provider_used,
            "bm25_score": self.bm25_score,
            "semantic_score": self.semantic_score,
            "created_at": created_str,
            "updated_at": updated_str,
        }

    def to_mysql_case_fields(self, case_id: str, assigned_to: Optional[str] = None) -> Dict[str, Any]:
        """Produce parameters suitable for MySQL compliance_case insert/update."""
        return {
            "case_id": case_id,
            "finding_id": self.finding_id,
            "call_id": self.call_id,
            "rm_id": self.rm_id,
            "customer_id": self.customer_id,
            "category": self.category,
            "severity": self.severity if self.severity in ("LOW", "MEDIUM", "HIGH") else "HIGH",
            "status": self.status,
            "escalated": self.severity in ("HIGH", "CRITICAL"),
            "assigned_to": assigned_to,
        }
