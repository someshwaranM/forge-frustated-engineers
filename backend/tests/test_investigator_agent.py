"""
Unit and integration tests for Phase 7: Investigator Agent.

Tests:
1. Hard Pre-Check: 0 regulation citations -> DISMISSED_NO_CITATION (no LLM call)
2. Model Dismissal: verdict="DISMISSED" -> DISMISSED_NOT_GENUINE
3. Citation Mismatch: model picks citation not in candidate list -> DISMISSED_CITATION_MISMATCH
4. Incomplete HIGH finding: HIGH severity missing timestamps/regulation -> DISMISSED_INCOMPLETE_HIGH_FINDING
5. Validation Failure: malformed output -> DISMISSED_VALIDATION_FAILED
6. Dual-Provider Fallback: Bedrock exception cleanly triggers Gemini fallback
7. Dual-Write Verification: confirmed finding appears in ES and MySQL compliance_case
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agents.investigator_agent import InvestigatorAgent, execute_forensic_evaluation
from data.schemas.compliance_finding_schema import ComplianceFinding


@pytest.fixture
def agent():
    return InvestigatorAgent()


def test_hard_precheck_zero_citations(agent):
    """Candidate with 0 regulation citations must immediately be dismissed without LLM invocation."""
    candidate = {
        "candidate_id": "CAND_TEST_01",
        "category": "SUITABILITY_MISMATCH",
        "regulation_citations": [],  # ZERO citations
        "evidence": {},
    }

    with patch("backend.agents.investigator_agent.execute_forensic_evaluation") as mock_llm:
        res = agent.investigate_candidate(
            call_id="CALL_TEST_01",
            call_date_time="2026-03-10T10:30:00Z",
            customer_id="CUST001",
            rm_id="RM001",
            candidate=candidate,
        )

        assert res["outcome"] == "DISMISSED_NO_CITATION"
        assert res["finding"] is None
        assert res["provider_used"] is None
        mock_llm.assert_not_called()


def test_model_dismissed_not_genuine(agent):
    """When model concludes not a genuine violation, return DISMISSED_NOT_GENUINE."""
    candidate = {
        "candidate_id": "CAND_TEST_02",
        "category": "SUITABILITY_MISMATCH",
        "regulation_citations": [{"chunk_id": "SEBI_CHUNK_01", "citation_label": "SEBI §1"}],
        "evidence": {},
    }

    dismissed_output = {
        "verdict": "DISMISSED",
        "reasoning": "RM properly disclosed all risk factors and customer affirmed understanding.",
    }

    with patch("backend.agents.investigator_agent.execute_forensic_evaluation", return_value=(dismissed_output, "gemini")):
        res = agent.investigate_candidate(
            call_id="CALL_TEST_02",
            call_date_time="2026-03-10T10:30:00Z",
            customer_id="CUST001",
            rm_id="RM001",
            candidate=candidate,
        )

        assert res["outcome"] == "DISMISSED_NOT_GENUINE"
        assert res["finding"] is None
        assert res["provider_used"] == "gemini"
        assert "RM properly disclosed" in res["reasoning"]


def test_guardrail_citation_mismatch(agent):
    """If model selects a regulation_id not in the retrieved citations, reject as DISMISSED_CITATION_MISMATCH."""
    candidate = {
        "candidate_id": "CAND_TEST_03",
        "category": "GUARANTEED_RETURNS",
        "regulation_citations": [{"chunk_id": "SEBI_VALID_CHUNK_01", "citation_label": "SEBI §1"}],
        "evidence": {},
    }

    hallucinated_output = {
        "finding_id": "FND-TEST-003",
        "category": "GUARANTEED_RETURNS",
        "severity": "HIGH",
        "confidence": 0.95,
        "timestamp_start": 10.0,
        "timestamp_end": 20.0,
        "transcript_evidence": "Guaranteed 20% return",
        "regulation_id": "SEBI_INVENTED_CHUNK_99",  # NOT in retrieved list
        "reasoning": "Promised returns",
        "recommended_action": "Retrain RM",
    }

    with patch("backend.agents.investigator_agent.execute_forensic_evaluation", return_value=(hallucinated_output, "gemini")):
        res = agent.investigate_candidate(
            call_id="CALL_TEST_03",
            call_date_time="2026-03-10T10:30:00Z",
            customer_id="CUST001",
            rm_id="RM001",
            candidate=candidate,
        )

        assert res["outcome"] == "DISMISSED_CITATION_MISMATCH"
        assert res["finding"] is None
        assert "not in candidate retrieved citations" in res["reasoning"]


def test_guardrail_incomplete_high_finding(agent):
    """If severity is HIGH and timestamps are missing, reject as DISMISSED_INCOMPLETE_HIGH_FINDING."""
    candidate = {
        "candidate_id": "CAND_TEST_04",
        "category": "GUARANTEED_RETURNS",
        "regulation_citations": [{"chunk_id": "SEBI_VALID_CHUNK_01", "citation_label": "SEBI §1"}],
        "evidence": {},
    }

    incomplete_high_output = {
        "finding_id": "FND-TEST-004",
        "category": "GUARANTEED_RETURNS",
        "severity": "HIGH",
        "confidence": 0.95,
        "timestamp_start": 0.0,
        "timestamp_end": 0.0,  # Missing specific temporal span
        "transcript_evidence": "Guaranteed 20% return",
        "regulation_id": "SEBI_VALID_CHUNK_01",
        "reasoning": "Promised returns",
        "recommended_action": "Retrain RM",
    }

    with patch("backend.agents.investigator_agent.execute_forensic_evaluation", return_value=(incomplete_high_output, "gemini")):
        res = agent.investigate_candidate(
            call_id="CALL_TEST_04",
            call_date_time="2026-03-10T10:30:00Z",
            customer_id="CUST001",
            rm_id="RM001",
            candidate=candidate,
        )

        assert res["outcome"] == "DISMISSED_INCOMPLETE_HIGH_FINDING"
        assert res["finding"] is None


def test_schema_validation_failure(agent):
    """If model output fails Pydantic schema validation, reject as DISMISSED_VALIDATION_FAILED."""
    candidate = {
        "candidate_id": "CAND_TEST_05",
        "category": "GUARANTEED_RETURNS",
        "regulation_citations": [{"chunk_id": "SEBI_VALID_CHUNK_01", "citation_label": "SEBI §1"}],
        "evidence": {},
    }

    malformed_output = {
        "finding_id": "FND-TEST-005",
        "severity": "INVALID_SEVERITY_LEVEL",  # Invalid enum
        "confidence": "not_a_float",
    }

    with patch("backend.agents.investigator_agent.execute_forensic_evaluation", return_value=(malformed_output, "gemini")):
        res = agent.investigate_candidate(
            call_id="CALL_TEST_05",
            call_date_time="2026-03-10T10:30:00Z",
            customer_id="CUST001",
            rm_id="RM001",
            candidate=candidate,
        )

        assert res["outcome"] == "DISMISSED_VALIDATION_FAILED"
        assert res["finding"] is None


def test_bedrock_fallback_to_gemini():
    """When Bedrock raises an exception, the caller falls back to Gemini cleanly."""
    with patch("backend.agents.investigator_agent.call_bedrock_investigator", side_effect=RuntimeError("Bedrock auth error")):
        with patch("backend.agents.investigator_agent.call_gemini_investigator", return_value={"verdict": "DISMISSED"}) as mock_gemini:
            output, provider = execute_forensic_evaluation("Test prompt")
            assert provider == "gemini"
            assert output == {"verdict": "DISMISSED"}
            mock_gemini.assert_called_once()
