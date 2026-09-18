"""
Vigil — Test Runner: Detection Agent (Phase 6)

Runs the Phase 6 compliance detection engine against calls indexed in
Elasticsearch, producing candidate JSON files in backend/compliance/candidates/.

The detection pipeline for each call:
  1. Deterministic rules scan — guaranteed/hedged return claims in RM segments
  2. Product identification — fuzzy match against MySQL product catalog
  3. Suitability check (Rule 3A: profile mismatch, Rule 3B: experience gap)
  4. Disclosure check — coarse keyword presence for Medium/High-risk products
  5. Hybrid regulation retrieval — BM25 + semantic citations per candidate
  6. Write staged candidate JSON to backend/compliance/candidates/<call_id>.json

After pipeline execution, runs the benchmark verifier against the 10 ground-truth
calls to confirm all detection signals are correctly firing.

Usage (from the project root d:\\vigil):
    python -m backend.tests.test_detection_agent
  or:
    python backend/tests/test_detection_agent.py

To target a specific call ID already in Elasticsearch:
    set VIGIL_TEST_CALL_ID=RM001_CUST001_20260310_1030
    python backend/tests/test_detection_agent.py
"""

import os
import sys
import json
import logging
from pathlib import Path

# Ensure project root (d:\\vigil) is on sys.path so all backend imports resolve
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.compliance.candidate_builder import (
    build_candidates_for_call,
    run_pipeline_on_all_calls,
    CANDIDATES_DIR,
    CALLS_INDEX,
)
from backend.compliance.verify_candidates import run_benchmark_verification
from backend.indexing.create_index import get_es_client


def run_single_call_test(call_id: str) -> dict:
    """
    Fetch a single call from Elasticsearch by call_id and run the full
    Phase 6 detection pipeline against it.
    """
    es = get_es_client()

    # Try direct document get first, then fall back to a term query
    doc = None
    try:
        doc = es.get(index=CALLS_INDEX, id=call_id)["_source"]
    except Exception:
        resp = es.search(
            index=CALLS_INDEX,
            body={"query": {"term": {"call_id": call_id}}},
        )
        hits = resp.get("hits", {}).get("hits", [])
        if hits:
            doc = hits[0]["_source"]

    if not doc:
        print(f"\n[ERROR] Call ID '{call_id}' not found in '{CALLS_INDEX}' index.")
        print("  Make sure the ingestion pipeline has run and indexed this call first.")
        sys.exit(1)

    print(f"\n  Processing single call: {call_id}")
    report = build_candidates_for_call(doc)
    return report


def _print_candidate_report(report: dict) -> None:
    """Pretty-prints a single candidate report."""
    call_id      = report.get("call_id", "")
    prod_status  = report.get("product_identification_status", "")
    product      = report.get("product") or {}
    candidates   = report.get("candidates", [])

    print(f"\n  Call ID : {call_id}")
    print(f"  Product : {product.get('product_id', 'N/A')} — "
          f"{product.get('product_name', '')} "
          f"[{product.get('risk_class', '')}] ({prod_status})")
    print(f"  Candidates found: {len(candidates)}")

    if not candidates:
        print("    --> [CLEAN] No compliance candidates flagged.")
    else:
        for c in candidates:
            print(f"    --> [{c.get('confidence_signal')}] "
                  f"{c.get('category')} : {c.get('summary', '')[:100]}")
            citations = c.get("regulation_citations", [])
            if citations:
                for cit in citations[:2]:
                    print(f"         Citation: {cit.get('citation_label')} "
                          f"({cit.get('chunk_id')})")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=" * 70)
    print("  VIGIL — Detection Agent (Phase 6) Test Runner")
    print("=" * 70)
    print()
    print("  Candidates Output Dir:", CANDIDATES_DIR)
    print("  Elasticsearch Index  :", CALLS_INDEX)
    print()

    test_call_id = os.environ.get("VIGIL_TEST_CALL_ID", "").strip()

    if test_call_id:
        # ---------------------------------------------------------------
        # Single-call mode
        # ---------------------------------------------------------------
        print(f"  Mode: Single-call (VIGIL_TEST_CALL_ID={test_call_id})")
        print()
        report = run_single_call_test(test_call_id)
        _print_candidate_report(report)
        reports = [report]
    else:
        # ---------------------------------------------------------------
        # Batch mode — all TRANSCRIBED calls in Elasticsearch
        # ---------------------------------------------------------------
        print("  Mode: Batch (all calls with processing_status='TRANSCRIBED')")
        print("  (Set VIGIL_TEST_CALL_ID=<id> to test a specific call instead)")
        print()

        try:
            reports = run_pipeline_on_all_calls()
        except Exception as exc:
            logging.exception(f"Detection pipeline failed: {exc}")
            sys.exit(1)

        if not reports:
            print("  [INFO] No TRANSCRIBED calls found in Elasticsearch.")
            print("  Run the ingestion pipeline first to index audio call documents.")
            print()
            sys.exit(0)

    # ---------------------------------------------------------------
    # Per-report pretty summary
    # ---------------------------------------------------------------
    print()
    print("=" * 70)
    print("  DETECTION AGENT — CANDIDATE REPORT SUMMARY")
    print("=" * 70)

    total_candidates = 0
    for r in reports:
        _print_candidate_report(r)
        total_candidates += r.get("candidate_count", 0)

    print()
    print(f"  Total calls processed   : {len(reports)}")
    print(f"  Total candidates flagged: {total_candidates}")
    print(f"  Candidate files written to: {CANDIDATES_DIR}")
    print()

    # ---------------------------------------------------------------
    # Benchmark verification (only meaningful for the 10 ground-truth calls)
    # ---------------------------------------------------------------
    benchmark_files_present = any(
        (CANDIDATES_DIR / f"{stem}.json").exists() or
        (CANDIDATES_DIR / f"CALL_{stem}.json").exists()
        for stem in [
            "RM001_CUST001_20260310_1030",
            "RM001_CUST004_20260405_1145",
            "RM002_CUST002_20260318_0915",
        ]
    )

    if benchmark_files_present:
        print("=" * 70)
        print("  DETECTION AGENT — BENCHMARK VERIFICATION")
        print("=" * 70)
        print()
        run_benchmark_verification()
        print()
    else:
        print("  [INFO] Benchmark ground-truth calls not yet indexed.")
        print("  Index the 10 benchmark calls via the ingestion pipeline to")
        print("  enable benchmark verification.")
        print()


if __name__ == "__main__":
    main()
