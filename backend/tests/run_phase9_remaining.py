"""
Run the remaining Phase 9 verification scenarios (follow-up reverification + guardrail limit).
Queries 1-5 already passed in the previous run.
"""

import io
import json
import sys
import time

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient
from backend.main import app
from backend.agents.chat_agent import ChatAgent, CONTROLLED_LIMIT_EXCEEDED_MSG

client = TestClient(app)
results = {}

print("=== Running Follow-Up Reverification Test ===")
# Turn 1:
t1 = client.post("/api/chat", json={
    "session_id": "sess_followup_v2",
    "message": "What SEBI regulation prohibits promising guaranteed returns?"
})
if t1.status_code == 200:
    t1_data = t1.json()
    print("Turn 1 tools:", t1_data["tool_calls_made"])
    print("Turn 1 has search_regulations:", "search_regulations" in t1_data["tool_calls_made"])
    results["followup_turn_1"] = t1_data
else:
    print("Turn 1 FAILED with status:", t1.status_code)
    results["followup_turn_1"] = {"error": t1.status_code}

# Wait for quota replenishment before Turn 2
print("Waiting 65s for quota replenishment before Turn 2...")
time.sleep(65)

# Turn 2: Follow-up in SAME session
t2 = client.post("/api/chat", json={
    "session_id": "sess_followup_v2",
    "message": "What regulation applies to investor risk profiling and suitability assessment?"
})
if t2.status_code == 200:
    t2_data = t2.json()
    print("Turn 2 tools:", t2_data["tool_calls_made"])
    print("Turn 2 has search_regulations:", "search_regulations" in t2_data["tool_calls_made"])
    print("REVERIFICATION PASSED:", "search_regulations" in t2_data["tool_calls_made"])
    results["followup_turn_2"] = t2_data
else:
    print("Turn 2 FAILED with status:", t2.status_code)
    results["followup_turn_2"] = {"error": t2.status_code}

print("\n=== Running Guardrail Limit Test (no LLM call needed) ===")
agent = ChatAgent()
limit_res = agent.chat("sess_limit_v2", "Show all calls and regulations", max_tool_calls=0)
print("Limit test response:", limit_res["response_text"])
print("GUARDRAIL PASSED:", limit_res["response_text"] == CONTROLLED_LIMIT_EXCEEDED_MSG)
results["limit_test"] = limit_res

with open("backend/tests/phase9_remaining_output.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("\nRemaining verification scenarios completed!")
