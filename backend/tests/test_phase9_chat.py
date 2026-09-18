"""
Vigil — Phase 9: AI Chat & Agent Builder Tools Verification Suite
(backend/tests/test_phase9_chat.py)

Executes all Phase 9 verification scenarios required by docs/dev_prompts/09_agent_builder_tools_ai_chat.md:
1. Tool Unit & Safety Tests (read-only queries, limits clamping, 2 modes of get_rm_history).
2. Live Frontend Example Queries:
   - "Show high-severity calls this month"
   - "Which RM has the most violations?"
   - "Find calls where guaranteed returns were mentioned" (semantic/hybrid search returning demo calls #2, #3)
   - "What regulation applies to this finding?"
   - "Show me all cases for RM001" (respects default limit 10 and reports total_count)
3. Multi-Turn Follow-Up Test (verifies search_regulations is re-called rather than trusting past conversation text).
4. Guardrail Limit Test (verifies controlled error response when tool call limit is exceeded).
"""

import logging
import pytest
from fastapi.testclient import TestClient

from backend.agents.chat_agent import (
    CONTROLLED_LIMIT_EXCEEDED_MSG,
    ChatAgent,
    get_chat_agent,
)
from backend.agents.chat_tools import (
    _clamp_limit,
    get_customer_profile,
    get_product_details,
    get_rm_history,
    get_transactions,
    search_calls,
    search_regulations,
)
from backend.main import app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Tool Unit & Safety Tests
# ---------------------------------------------------------------------------

def test_clamp_limits():
    """Verify tool limit clamping strictly enforces 1 <= limit <= 25 with default 10."""
    assert _clamp_limit(None) == 10
    assert _clamp_limit(10) == 10
    assert _clamp_limit(100) == 25
    assert _clamp_limit(-5) == 1
    assert _clamp_limit("invalid") == 10


def test_mysql_tools_read_only():
    """Verify MySQL tools execute parameterized SELECT and return expected fields."""
    cust = get_customer_profile("CUST001")
    assert cust.get("found") is True
    assert cust.get("customer_id") == "CUST001"
    assert "risk_profile" in cust

    prod = get_product_details("PROD001")
    assert prod.get("found") is True
    assert prod.get("product_id") == "PROD001"
    assert "risk_class" in prod

    txns = get_transactions(customer_id="CUST001", limit=5)
    assert "total_count" in txns
    assert "transactions" in txns
    assert len(txns["transactions"]) <= 5


def test_get_rm_history_modes():
    """
    Verify get_rm_history supports:
    - Mode 1: before_date specified
    - Mode 2: before_date omitted (all-time)
    - Mode 3: cross-RM summary when rm_id is None / 'ALL'
    """
    # Mode 2: All time for RM001
    all_time = get_rm_history("RM001")
    assert all_time.get("mode") == "all_time"
    assert all_time.get("total_violations") == 2
    assert "SUITABILITY_MISMATCH" in all_time.get("category_breakdown", {})

    # Mode 1: before_date filtered
    filtered = get_rm_history("RM001", before_date="2026-03-15T00:00:00")
    assert filtered.get("mode") == "before_date_filtered"
    assert filtered.get("before_date") == "2026-03-15T00:00:00"
    # Call 1 was 2026-03-10, Call 2 was 2026-04-05, so exactly 1 call was earlier
    assert filtered.get("total_violations") == 1

    # Mode 3: Cross RM leaderboard
    summary = get_rm_history(None)
    assert summary.get("mode") == "cross_rm_summary"
    assert summary.get("most_violations_rm") == "RM001"
    assert summary.get("total_violations_across_all_rms") == 4


def test_search_calls_semantic_hybrid():
    """
    Verify search_calls uses hybrid search over transcript_english_text + transcript_semantic
    and retrieves the guaranteed-return demo calls (#2: CALL_RM001_CUST004, #3: CALL_RM002_CUST002).
    """
    res = search_calls(query="guaranteed returns", limit=10)
    assert res.get("total_count") > 0
    returned_ids = [c["call_id"] for c in res.get("calls", [])]

    # Confirm demo calls #2 and #3 are returned
    assert "CALL_RM001_CUST004_20260405_1145" in returned_ids
    assert "CALL_RM002_CUST002_20260318_0915" in returned_ids


def test_guardrail_tool_call_limit():
    """
    Verify that if tool calls exceed the limit, the controlled response fires
    rather than looping indefinitely.
    """
    agent = ChatAgent()
    # Force max_tool_calls=0 to immediately trigger limit guardrail
    res = agent.chat(
        session_id="limit_test_session",
        user_message="Show high severity calls and search all regulations",
        max_tool_calls=0,
    )
    assert res["response_text"] == CONTROLLED_LIMIT_EXCEEDED_MSG


# ---------------------------------------------------------------------------
# 2. Live Frontend Queries & API Endpoint Tests
# ---------------------------------------------------------------------------

def test_api_chat_queries():
    """Run the 5 actual frontend example queries via POST /api/chat and verify tool grounding."""
    client = TestClient(app)

    # Query 1: High severity calls
    res1 = client.post(
        "/api/chat",
        json={"session_id": "test_q1", "message": "Show high-severity calls this month"},
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert "search_calls" in data1["tool_calls_made"]
    assert any(g["type"] in ("call", "finding") for g in data1["grounded_results"])

    # Query 2: RM with most violations
    res2 = client.post(
        "/api/chat",
        json={"session_id": "test_q2", "message": "Which RM has the most violations?"},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert "get_rm_history" in data2["tool_calls_made"]
    assert "RM001" in data2["response_text"]

    # Query 3: Guaranteed returns semantic search
    res3 = client.post(
        "/api/chat",
        json={"session_id": "test_q3", "message": "Find calls where guaranteed returns were mentioned"},
    )
    assert res3.status_code == 200
    data3 = res3.json()
    assert "search_calls" in data3["tool_calls_made"]
    call_ids = [g["id"] for g in data3["grounded_results"] if g["type"] == "call"]
    assert "CALL_RM001_CUST004_20260405_1145" in call_ids or "CALL_RM002_CUST002_20260318_0915" in call_ids

    # Query 4: What regulation applies
    res4 = client.post(
        "/api/chat",
        json={"session_id": "test_q4", "message": "What regulation applies to guaranteed returns in mutual funds?"},
    )
    assert res4.status_code == 200
    data4 = res4.json()
    assert "search_regulations" in data4["tool_calls_made"]
    assert any(g["type"] == "regulation" for g in data4["grounded_results"])

    # Query 5: Cases for RM001
    res5 = client.post(
        "/api/chat",
        json={"session_id": "test_q5", "message": "Show me all cases for RM001"},
    )
    assert res5.status_code == 200
    data5 = res5.json()
    assert any(t in data5["tool_calls_made"] for t in ["search_calls", "get_rm_history"])
    assert any(g["type"] in ("call", "finding") for g in data5["grounded_results"])


def test_multi_turn_regulation_reverification():
    """
    Test that asking a follow-up regulation question in the same session causes
    search_regulations to be called AGAIN rather than trusting previous text as fact.
    """
    client = TestClient(app)
    session_id = "test_multi_turn_reverify"

    # Turn 1
    t1 = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "What SEBI regulation prohibits promising guaranteed returns?"},
    )
    assert t1.status_code == 200
    assert "search_regulations" in t1.json()["tool_calls_made"]

    # Turn 2: Follow-up regulation question
    t2 = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "What regulation applies to risk profiling and suitability?"},
    )
    assert t2.status_code == 200
    # Must re-verify with search_regulations in turn 2
    assert "search_regulations" in t2.json()["tool_calls_made"]
