"""
Vigil — Phase 3.1: Create & Verify Elasticsearch 'compliance_findings' index.

Defines the exact schema for the 'compliance_findings' index, including:
- finding, call, RM, customer identifiers
- classification: category, severity, confidence, status
- temporal evidence: timestamp_start, timestamp_end, transcript_evidence
- risk profiling: customer_risk_profile, product_risk_class
- denormalized regulation link: regulation_chunk_id, regulation_citation_label, regulation_source_url
- LLM reasoning & recommendations: reasoning, recommended_action
- audit trail: provider_used ("bedrock" or "gemini"), bm25_score, semantic_score, timestamps

DUAL-WRITE WARNING:
  The 'status' field is denormalized from MySQL's compliance_case.status table.
  Phase 8 case status transitions MUST write to BOTH MySQL and this field,
  or the two systems will drift.

Verification performed:
- Full round-trip test with a fully-populated finding document copying real
  denormalized fields from the regulations index (AMFI Distributor Code §II.4.g, p.5).
  Document is deleted afterwards so the index remains empty.
"""

import os
import sys
import logging
from pathlib import Path
from elasticsearch import Elasticsearch, NotFoundError

# Ensure project root is on sys.path for direct script execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.indexing.create_index import get_es_client

logger = logging.getLogger(__name__)

INDEX_NAME = "compliance_findings"

FINDINGS_MAPPING = {
    "mappings": {
        "properties": {
            "finding_id":                 {"type": "keyword"},
            "call_id":                    {"type": "keyword"},
            "rm_id":                      {"type": "keyword"},
            "customer_id":                {"type": "keyword"},

            "category":                   {"type": "keyword"},
            "severity":                   {"type": "keyword"},
            "confidence":                 {"type": "float"},
            # DUAL-WRITE WARNING: status is denormalized from MySQL compliance_case.status.
            # Any update to case status in Phase 8 MUST update both MySQL and this field.
            "status":                     {"type": "keyword"},

            "timestamp_start":            {"type": "float"},
            "timestamp_end":              {"type": "float"},
            "transcript_evidence":        {"type": "text"},

            "customer_risk_profile":      {"type": "keyword"},
            "product_risk_class":         {"type": "keyword"},

            # Denormalized from 'regulations' index at detection time
            "regulation_chunk_id":        {"type": "keyword"},
            "regulation_citation_label":  {"type": "keyword"},
            "regulation_source_url":      {"type": "keyword"},

            "reasoning":                  {"type": "text"},
            "recommended_action":         {"type": "text"},

            "provider_used":              {"type": "keyword"},
            "bm25_score":                 {"type": "float"},
            "semantic_score":             {"type": "float"},

            "created_at":                 {"type": "date"},
            "updated_at":                 {"type": "date"},
        }
    }
}


def create_findings_index(es: Elasticsearch, *, force: bool = False) -> None:
    """Create the 'compliance_findings' index. If force=True, delete existing index first."""
    if es.indices.exists(index=INDEX_NAME):
        if force:
            logger.info(f"Deleting existing '{INDEX_NAME}' index...")
            es.indices.delete(index=INDEX_NAME)
            print(f"  Deleted existing index '{INDEX_NAME}'.")
        else:
            print(f"  Index '{INDEX_NAME}' already exists. Use force=True to recreate.")
            return

    logger.info(f"Creating index '{INDEX_NAME}' with mapping...")
    es.indices.create(index=INDEX_NAME, body=FINDINGS_MAPPING)
    print(f"  Created index '{INDEX_NAME}' with exact schema.")


def verify_findings_denormalization_roundtrip(es: Elasticsearch) -> bool:
    """
    STEP 4 Verification:
    Verify the compliance_findings index accepts a fully-populated throwaway test
    document with EVERY field from the mapping present, including realistic
    denormalized regulation metadata from an actual chunk in the regulations index.
    Deletes throwaway document upon completion.
    """
    print("\n--- STEP 4: Verifying Findings Denormalization Round-Trip ---")
    test_finding_id = "__test_finding_denorm_001__"

    # Fully populated finding with real regulatory citation from Phase 3 regulations index
    test_doc = {
        "finding_id": test_finding_id,
        "call_id": "CALL_TEST_20260325_001",
        "rm_id": "RM_1042",
        "customer_id": "CUST_8831",
        "category": "GUARANTEED_RETURNS",
        "severity": "CRITICAL",
        "confidence": 0.96,
        "status": "OPEN",  # Dual-write field with MySQL
        "timestamp_start": 142.5,
        "timestamp_end": 158.0,
        "transcript_evidence": "Sir, aap bilkul chinta mat kijiye, is fund mein 15% guaranteed return milega bina kisi risk ke.",
        "customer_risk_profile": "CONSERVATIVE",
        "product_risk_class": "VERY_HIGH",
        # Denormalized fields verified against real Phase 3 regulations index chunk
        "regulation_chunk_id": "AMFI_MFD_COC_2022_II_4_g",
        "regulation_citation_label": "AMFI Distributor Code §II.4.g, p.5",
        "regulation_source_url": "https://www.amfiindia.com/uploads/Revised_Codeof_Conductfor_Mutual_Fund_Distributors_April2022_57d91fe1c4.pdf",
        "reasoning": "The RM explicitly assured a fixed 15% return and claimed the investment carried zero risk. This constitutes an outright breach of AMFI Distributor Code Clause II.4.g.",
        "recommended_action": "Issue formal compliance violation notice to RM. Flag client account for advisory review.",
        "provider_used": "bedrock",
        "bm25_score": 14.82,
        "semantic_score": 0.9412,
        "created_at": "2026-03-25T14:30:00Z",
        "updated_at": "2026-03-25T14:30:00Z",
    }

    try:
        # Index document and refresh
        es.index(index=INDEX_NAME, id=test_finding_id, document=test_doc, refresh=True)

        # Retrieve document
        fetched = es.get(index=INDEX_NAME, id=test_finding_id)
        source = fetched["_source"]

        # Validate that all fields match exactly
        all_fields_present = True
        for key, expected_val in test_doc.items():
            if key not in source:
                print(f"  [FAIL] Missing field: {key}")
                all_fields_present = False
            elif source[key] != expected_val:
                print(f"  [FAIL] Value mismatch for {key}: expected {expected_val}, got {source[key]}")
                all_fields_present = False

        if all_fields_present:
            print(f"  [PASS] All {len(test_doc)} fields correctly indexed and retrieved:")
            print(f"    Finding ID:               {source['finding_id']}")
            print(f"    Category / Severity:      {source['category']} / {source['severity']}")
            print(f"    Status (Dual-write):      {source['status']}")
            print(f"    Regulation Citation:      {source['regulation_citation_label']}")
            print(f"    Regulation Source URL:    {source['regulation_source_url']}")
            print(f"    Provider Used:            {source['provider_used']}")
            print(f"    Scores (BM25 / Semantic): {source['bm25_score']} / {source['semantic_score']}")
        return all_fields_present

    finally:
        # Clean up test document
        try:
            es.delete(index=INDEX_NAME, id=test_finding_id, refresh=True)
            print("  Cleaned up throwaway test document for compliance findings.")
        except NotFoundError:
            pass


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("=" * 65)
    print("  PHASE 3.1 — Create & Verify 'compliance_findings' Index")
    print("=" * 65)

    es = get_es_client()
    create_findings_index(es, force=True)

    passed_roundtrip = verify_findings_denormalization_roundtrip(es)

    final_count = es.count(index=INDEX_NAME)["count"]
    print(f"\nFinal document count in '{INDEX_NAME}': {final_count} (must be 0)")

    if passed_roundtrip and final_count == 0:
        print(f"\n[PASS] All verifications passed for '{INDEX_NAME}' index. Schema locked and empty.\n")
    else:
        print(f"\n[FAIL] Verification failed for '{INDEX_NAME}'.\n")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
