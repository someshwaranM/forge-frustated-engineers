"""
Run and record all Phase 9 verification queries safely with utf-8 encoding.
"""

import io
import json
import sys
import time
from fastapi.testclient import TestClient
from backend.main import app

# Ensure Windows stdout handles UTF-8 properly
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

client = TestClient(app)
results = {}

print("=== Running Query 1: Show high-severity calls this month ===")
r1 = client.post("/api/chat", json={"session_id": "sess_q1", "message": "Show high-severity calls this month"}).json()
results["query_1"] = r1
print("Q1 tool_calls_made:", r1["tool_calls_made"])
print("Q1 grounded_results count:", len(r1["grounded_results"]))
time.sleep(2)

print("\n=== Running Query 2: Which RM has the most violations? ===")
r2 = client.post("/api/chat", json={"session_id": "sess_q2", "message": "Which RM has the most violations?"}).json()
results["query_2"] = r2
print("Q2 tool_calls_made:", r2["tool_calls_made"])
time.sleep(2)

print("\n=== Running Query 3: Find calls where guaranteed returns were mentioned ===")
r3 = client.post("/api/chat", json={"session_id": "sess_q3", "message": "Find calls where guaranteed returns were mentioned"}).json()
results["query_3"] = r3
print("Q3 tool_calls_made:", r3["tool_calls_made"])
print("Q3 top grounded calls:", [g["id"] for g in r3["grounded_results"] if g["type"] == "call"][:3])
time.sleep(2)

print("\n=== Running Query 4: What regulation applies to guaranteed return findings? ===")
r4 = client.post("/api/chat", json={"session_id": "sess_q4", "message": "What regulation applies to guaranteed returns in mutual funds?"}).json()
results["query_4"] = r4
print("Q4 tool_calls_made:", r4["tool_calls_made"])
print("Q4 regulations grounded:", [g["id"] for g in r4["grounded_results"] if g["type"] == "regulation"][:3])
time.sleep(2)

print("\n=== Running Query 5: Show me all cases for RM001 ===")
r5 = client.post("/api/chat", json={"session_id": "sess_q5", "message": "Show me all cases for RM001"}).json()
results["query_5"] = r5
print("Q5 tool_calls_made:", r5["tool_calls_made"])
print("Q5 grounded_results count:", len(r5["grounded_results"]))
time.sleep(2)

print("\n=== Running Follow-Up Reverification Test in Single Session ===")
# Turn 1:
f_t1 = client.post("/api/chat", json={"session_id": "sess_followup", "message": "What SEBI regulation prohibits promising guaranteed returns?"}).json()
print("Followup Turn 1 tools:", f_t1["tool_calls_made"])
time.sleep(2)
# Turn 2:
f_t2 = client.post("/api/chat", json={"session_id": "sess_followup", "message": "What regulation applies to investor risk profiling and suitability assessment?"}).json()
print("Followup Turn 2 tools:", f_t2["tool_calls_made"])
results["followup_test"] = {"turn_1": f_t1, "turn_2": f_t2}
time.sleep(2)

print("\n=== Running Guardrail Limit Test ===")
from backend.agents.chat_agent import ChatAgent
agent = ChatAgent()
limit_res = agent.chat("sess_limit", "Show all calls and regulations", max_tool_calls=0)
results["limit_test"] = limit_res
print("Limit test response:", limit_res["response_text"])

with open("backend/tests/phase9_verification_output.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("\nAll verification scenarios completed successfully and saved to backend/tests/phase9_verification_output.json!")
