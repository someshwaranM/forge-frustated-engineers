"""
Vigil — Phase 3.1: Runner and orchestrator for Calls & Compliance Findings indices.
Executes creation, all 3 verification checks, and confirms both indices are empty.
"""

import os
import sys
import logging
from pathlib import Path

# Ensure project root is on sys.path for direct script execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.indexing.create_index import get_es_client
from backend.indexing.create_calls_index import (
    create_calls_index,
    verify_nested_segment_isolation,
    verify_calls_semantic_binding,
    INDEX_NAME as CALLS_INDEX,
)
from backend.indexing.create_findings_index import (
    create_findings_index,
    verify_findings_denormalization_roundtrip,
    INDEX_NAME as FINDINGS_INDEX,
)

logger = logging.getLogger(__name__)


def run_phase3_1():
    es = get_es_client()

    print("=" * 70)
    print("  VIGIL — Phase 3.1: Calls & Compliance Findings Indices")
    print("=" * 70)

    # 1. Calls Index
    print(f"\n>> Step 1A: Creating '{CALLS_INDEX}' index...")
    create_calls_index(es, force=True)

    print("\n>> Step 2: Testing nested transcript_segments isolation on 'calls'...")
    passed_nested = verify_nested_segment_isolation(es)

    print("\n>> Step 3: Testing transcript_semantic multilingual inference on 'calls'...")
    passed_semantic = verify_calls_semantic_binding(es)

    # 2. Compliance Findings Index
    print(f"\n>> Step 1B: Creating '{FINDINGS_INDEX}' index...")
    create_findings_index(es, force=True)

    print("\n>> Step 4: Testing denormalization round-trip on 'compliance_findings'...")
    passed_findings = verify_findings_denormalization_roundtrip(es)

    # Check zero counts
    calls_count = es.count(index=CALLS_INDEX)["count"]
    findings_count = es.count(index=FINDINGS_INDEX)["count"]

    print("\n" + "=" * 70)
    print("  PHASE 3.1 VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"  [PASS] 'calls' schema created and locked")
    print(f"  [{'PASS' if passed_nested else 'FAIL'}] Step 2: Nested segment isolation (RM matched, CUSTOMER isolated)")
    print(f"  [{'PASS' if passed_semantic else 'FAIL'}] Step 3: Semantic inference binding (jina-embeddings-v5-text-small)")
    print(f"  [PASS] 'compliance_findings' schema created and locked")
    print(f"  [{'PASS' if passed_findings else 'FAIL'}] Step 4: Full 23-field denormalization round-trip")
    print(f"  [PASS] Final index counts:")
    print(f"         - '{CALLS_INDEX}': {calls_count} documents")
    print(f"         - '{FINDINGS_INDEX}': {findings_count} documents")
    print("=" * 70)

    all_passed = passed_nested and passed_semantic and passed_findings and (calls_count == 0) and (findings_count == 0)
    if not all_passed:
        raise SystemExit(1)
    print("\n  All Phase 3.1 checks passed successfully!\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_phase3_1()
