"""
Vigil — Phase 6: Candidate Verification & Benchmark Reporter
"""

import json
from pathlib import Path

CANDIDATES_DIR = Path("backend/compliance/candidates")

BENCHMARK_EXPECTATIONS = {
    "RM001_CUST001_20260310_1030": {
        "ground_truth": "HIGH — Suitability Mismatch",
        "expected_product": "PROD005",
        "expected_categories": ["SUITABILITY_MISMATCH"],
        "expect_clean": False
    },
    "RM001_CUST004_20260405_1145": {
        "ground_truth": "MEDIUM — Guaranteed Return (mild/implied)",
        "expected_product": "PROD002",
        "expected_categories": ["GUARANTEED_RETURN"],
        "expect_clean": False
    },
    "RM002_CUST002_20260318_0915": {
        "ground_truth": "HIGH — Guaranteed Return (explicit)",
        "expected_product": "PROD004",
        "expected_categories": ["GUARANTEED_RETURN"],
        "expect_clean": False
    },
    "RM002_CUST005_20260422_1400": {
        "ground_truth": "CLEAN — Compliant Call",
        "expected_product": "PROD001",
        "expected_categories": [],
        "expect_clean": True
    },
    "RM003_CUST003_20260212_1620": {
        "ground_truth": "HIGH — Missing Risk Disclosure",
        "expected_product": "PROD006",
        "expected_categories": ["MISSING_RISK_DISCLOSURE"],
        "expect_clean": False
    },
    "RM003_CUST003_20260630_1330": {
        "ground_truth": "LOW — Borderline / Ambiguous Language",
        "expected_product": "PROD007",
        "expected_categories": ["AMBIGUOUS_RETURN_CLAIM"],
        "expect_clean": False
    },
    "RM004_CUST002_20260701_0930": {
        "ground_truth": "MEDIUM — Missing / Inadequate Risk Disclosure (partial)",
        "expected_product": "PROD003",
        "expected_categories": ["INADEQUATE_RISK_DISCLOSURE"],
        "expect_clean": False
    },
    "RM004_CUST004_20260228_1050": {
        "ground_truth": "CLEAN — Compliant Call (Risk warnings with compliant negations)",
        "expected_product": "PROD002",
        "expected_categories": [],
        "expect_clean": True
    },
    "RM005_CUST001_20260815_1615": {
        "ground_truth": "CLEAN — Compliant Call (Liquid Fund, Low risk exempt from Rule 3B)",
        "expected_product": "PROD001",
        "expected_categories": [],
        "expect_clean": True
    },
    "RM005_CUST005_20260319_1200": {
        "ground_truth": "LOW — Ambiguous Suitability (Low experience in Medium risk fund)",
        "expected_product": "PROD003",
        "expected_categories": ["SUITABILITY_INEXPERIENCE_GAP"],
        "expect_clean": False
    },
}


def run_benchmark_verification():
    print("=" * 115)
    print("  VIGIL PHASE 6 — DETECTION ENGINE BENCHMARK REPORT (10 CALLS)")
    print("=" * 115)
    header = f"{'Call ID':<30} | {'Product':<8} | {'Status':<10} | {'Count':<6} | {'Signals & Categories':<48}"
    print(header)
    print("-" * 115)

    all_passed = True

    for stem, spec in BENCHMARK_EXPECTATIONS.items():
        candidate_file = CANDIDATES_DIR / f"{stem}.json"
        if not candidate_file.exists():
            candidate_file = CANDIDATES_DIR / f"CALL_{stem}.json"

        if not candidate_file.exists():
            print(f"{stem:<30} | MISSING CANDIDATE FILE!")
            all_passed = False
            continue

        with open(candidate_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        prod_id = data.get("product", {}).get("product_id") if data.get("product") else "NONE"
        prod_status = data.get("product_identification_status", "UNKNOWN")
        cand_count = data.get("candidate_count", len(data.get("candidates", [])))
        candidates = data.get("candidates", [])

        signals_str = ", ".join(f"[{c.get('confidence_signal')}] {c.get('category')}" for c in candidates)
        if not signals_str:
            signals_str = "[CLEAN] No candidates flagged"

        # Check product match
        prod_ok = (prod_id == spec["expected_product"])
        # Check clean vs non-clean
        clean_ok = (cand_count == 0) if spec["expect_clean"] else (cand_count > 0)
        # Check expected categories
        actual_categories = [c.get("category") for c in candidates]
        cat_ok = all(ec in actual_categories for ec in spec["expected_categories"])

        status_flag = "[PASS]" if (prod_ok and clean_ok and cat_ok) else "[FAIL]"
        if status_flag == "[FAIL]":
            all_passed = False

        print(f"{stem:<30} | {prod_id:<8} | {status_flag:<10} | {cand_count:<6} | {signals_str:<48}")

    print("=" * 115)
    print(f"  BENCHMARK VERIFICATION RESULT: {'ALL 10 CALLS PASSED VERIFICATION' if all_passed else 'SOME CALLS FAILED'}")
    print("=" * 115)


if __name__ == "__main__":
    run_benchmark_verification()
