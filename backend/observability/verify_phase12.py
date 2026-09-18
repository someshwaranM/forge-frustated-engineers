"""Phase 12 verification script."""
import time
import json
import sys
sys.path.insert(0, ".")

from backend.api.routes.system import get_system_health
from backend.api.routes.dashboard import get_dashboard_summary
from backend.observability.stage_timer import get_pipeline_latency_summary

print("=== VERIFICATION 1: GET /api/system/health ===")
t0 = time.perf_counter()
health = get_system_health()
elapsed = time.perf_counter() - t0
svc = health["services"]
print(json.dumps(health, indent=2))
print(f"\nCompleted in {elapsed:.2f}s")
print(f"Bedrock type: {svc['bedrock']['type']} (must be last_known)")
print(f"Gemini type:  {svc['gemini']['type']} (must be last_known)")
print(f"Sarvam type:  {svc['sarvam']['type']} (must be last_known)")
assert svc["bedrock"]["type"] == "last_known", "FAIL: bedrock live-pinged!"
assert svc["gemini"]["type"] == "last_known", "FAIL: gemini live-pinged!"
assert svc["sarvam"]["type"] == "last_known", "FAIL: sarvam live-pinged!"
assert elapsed < 3.0, f"FAIL: health check took {elapsed:.2f}s — possible LLM call!"
print("PASS: all providers last_known, no live LLM ping, under 3s")

print("\n=== VERIFICATION 2: GET /api/dashboard/summary pipeline_latency ===")
summary = get_dashboard_summary()
latency = summary["pipeline_latency"]
print(json.dumps(latency, indent=2))
assert latency["status"] == "active", "FAIL: still showing placeholder status!"
assert latency.get("stages") is not None, "FAIL: no stage breakdown!"
inv = latency["stages"]["investigation"]
assert inv["count"] == 10, f"FAIL: investigation count={inv['count']}, want 10"
assert inv["mean_seconds"] is not None, "FAIL: investigation mean is null!"
assert 30 < inv["mean_seconds"] < 600, f"FAIL: investigation mean={inv['mean_seconds']}s, not sane!"
print(f"PASS: Investigation mean={inv['mean_seconds']}s, median={inv['median_seconds']}s, min={inv['min_seconds']}s, max={inv['max_seconds']}s")

print("\n=== VERIFICATION 3: pipeline_started_at field exists in pipeline.py ===")
import inspect
from backend.ingestion import pipeline
src = inspect.getsource(pipeline.process_audio_file)
assert "processing_started_at" in src, "FAIL: processing_started_at not found in pipeline!"
print("PASS: processing_started_at recorded in pipeline.py")

print("\n=== VERIFICATION 4: Sane investigation durations for all 10 demo calls ===")
timings = get_pipeline_latency_summary()
for call in timings.get("per_call", []):
    inv_dur = call["durations"]["investigation_duration_seconds"]
    if inv_dur is not None:
        assert 1 < inv_dur < 700, f"FAIL: {call['call_id']} investigation={inv_dur}s — not sane!"
        print(f"  {call['call_id']}: investigation={inv_dur}s")
print("PASS: all investigation durations sane (seconds range, not hours)")

print("\nAll verification checks passed.")
