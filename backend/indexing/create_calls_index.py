"""
Vigil — Phase 3.1: Create & Verify Elasticsearch 'calls' index.

Defines the exact schema for the 'calls' index, including:
- transcript_original_text & transcript_english_text
- transcript_semantic (bound to jina-embeddings-v5-text-small for English paraphrase queries)
- nested transcript_segments with text_original and text_english (for speaker-isolated text queries)
- speaker_mapping_method ("bedrock" vs "gemini" vs "heuristic_fallback")
- call metadata and violation flags

Verifications performed:
1. Nested segment isolation test: proves cross-contamination does NOT happen between speakers.
2. Semantic binding test: proves paraphrase search works via jina-embeddings-v5-text-small.
All test documents are deleted afterwards so the index remains empty.
"""

import os
import sys
import logging
import time
from pathlib import Path
from elasticsearch import Elasticsearch, NotFoundError

# Ensure project root is on sys.path for direct script execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.indexing.create_index import get_es_client

logger = logging.getLogger(__name__)

INDEX_NAME = "calls"
INFERENCE_ENDPOINT = ".jina-embeddings-v5-text-small"

CALLS_MAPPING = {
    "mappings": {
        "properties": {
            "call_id":                  {"type": "keyword"},
            "rm_id":                    {"type": "keyword"},
            "customer_id":              {"type": "keyword"},
            "date_time":                {"type": "date"},
            "duration_seconds":         {"type": "integer"},
            "audio_file_path":          {"type": "keyword"},
            "processing_status":        {"type": "keyword"},
            "language":                 {"type": "keyword"},

            "transcript_original_text": {"type": "text"},
            "transcript_english_text":  {"type": "text"},
            "transcript_semantic":      {
                "type": "semantic_text",
                "inference_id": INFERENCE_ENDPOINT,
            },

            "transcript_segments": {
                "type": "nested",
                "properties": {
                    "segment_id":    {"type": "keyword"},
                    "speaker":       {"type": "keyword"},
                    "text_original": {"type": "text"},
                    "text_english":  {"type": "text"},
                    "start_time":    {"type": "float"},
                    "end_time":      {"type": "float"},
                    "is_violation":  {"type": "boolean"},
                },
            },

            "speaker_mapping_method":   {"type": "keyword"},
            "has_violation":            {"type": "boolean"},
            "finding_ids":              {"type": "keyword"},
            "indexed_at":               {"type": "date"},
            "processing_started_at":    {"type": "date"},
            "detection_completed_at":   {"type": "date"},
            "investigation_completed_at": {"type": "date"},
        }
    }
}


def create_calls_index(es: Elasticsearch, *, force: bool = False) -> None:
    """Create the 'calls' index. If force=True, delete existing index first."""
    if es.indices.exists(index=INDEX_NAME):
        if force:
            logger.info(f"Deleting existing '{INDEX_NAME}' index...")
            es.indices.delete(index=INDEX_NAME)
            print(f"  Deleted existing index '{INDEX_NAME}'.")
        else:
            print(f"  Index '{INDEX_NAME}' already exists. Use force=True to recreate.")
            return

    logger.info(f"Creating index '{INDEX_NAME}' with mapping...")
    es.indices.create(index=INDEX_NAME, body=CALLS_MAPPING)
    print(f"  Created index '{INDEX_NAME}' with exact schema.")


def verify_nested_segment_isolation(es: Elasticsearch) -> bool:
    """
    STEP 2 Verification:
    Index a throwaway document with 2 segments:
      - speaker='RM', text_english contains 'guaranteed return'
      - speaker='CUSTOMER', text_english contains an unrelated phrase ('Okay that sounds good to me')
    
    Test A: Nested query for speaker='RM' AND text_english matches 'guaranteed return' -> MUST MATCH.
    Test B: Nested query for speaker='CUSTOMER' AND text_english matches 'guaranteed return' -> MUST NOT MATCH.
    
    Deletes throwaway document upon completion.
    """
    print("\n--- STEP 2: Verifying Nested Transcript Segments Isolation ---")
    test_doc_id = "__test_nested_call_isolation__"
    test_doc = {
        "call_id": test_doc_id,
        "rm_id": "RM_TEST_001",
        "customer_id": "CUST_TEST_001",
        "date_time": "2026-03-25T10:00:00Z",
        "duration_seconds": 120,
        "audio_file_path": "CallAudio/test.mp3",
        "processing_status": "COMPLETED",
        "language": "en-IN",
        "transcript_original_text": "RM: We can provide a guaranteed return on this mutual fund scheme. Customer: Okay that sounds good to me, what is the process?",
        "transcript_english_text": "RM: We can provide a guaranteed return on this mutual fund scheme. Customer: Okay that sounds good to me, what is the process?",
        "transcript_semantic": "We can provide a guaranteed return on this mutual fund scheme. Okay that sounds good to me, what is the process?",
        "transcript_segments": [
            {
                "segment_id": "seg_1",
                "speaker": "RM",
                "text_original": "We can provide a guaranteed return on this mutual fund scheme.",
                "text_english": "We can provide a guaranteed return on this mutual fund scheme.",
                "start_time": 0.0,
                "end_time": 5.2,
                "is_violation": True,
            },
            {
                "segment_id": "seg_2",
                "speaker": "CUSTOMER",
                "text_original": "Okay that sounds good to me, what is the process?",
                "text_english": "Okay that sounds good to me, what is the process?",
                "start_time": 5.5,
                "end_time": 9.8,
                "is_violation": False,
            },
        ],
        "speaker_mapping_method": "llm",
        "has_violation": True,
        "finding_ids": ["F_TEST_001"],
        "indexed_at": "2026-03-25T10:05:00Z",
    }

    try:
        # Index document and refresh
        es.index(index=INDEX_NAME, id=test_doc_id, document=test_doc, refresh=True)

        # Test A: speaker=RM AND text_english="guaranteed return"
        query_rm = {
            "nested": {
                "path": "transcript_segments",
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"transcript_segments.speaker": "RM"}},
                            {"match": {"transcript_segments.text_english": "guaranteed return"}},
                        ]
                    }
                },
            }
        }
        res_rm = es.search(index=INDEX_NAME, query=query_rm)
        rm_matched = res_rm["hits"]["total"]["value"] > 0
        print(f"  Test A (speaker='RM' AND text_english='guaranteed return'): "
              f"{'[PASS] MATCHED' if rm_matched else '[FAIL] NO MATCH'} (hits={res_rm['hits']['total']['value']})")

        # Test B: speaker=CUSTOMER AND text_english="guaranteed return"
        query_cust = {
            "nested": {
                "path": "transcript_segments",
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"transcript_segments.speaker": "CUSTOMER"}},
                            {"match": {"transcript_segments.text_english": "guaranteed return"}},
                        ]
                    }
                },
            }
        }
        res_cust = es.search(index=INDEX_NAME, query=query_cust)
        cust_isolated = res_cust["hits"]["total"]["value"] == 0
        print(f"  Test B (speaker='CUSTOMER' AND text_english='guaranteed return'): "
              f"{'[PASS] NO MATCH (ISOLATED)' if cust_isolated else '[FAIL] CROSS-CONTAMINATION DETECTED'} (hits={res_cust['hits']['total']['value']})")

        success = rm_matched and cust_isolated
        return success

    finally:
        # Clean up test document
        try:
            es.delete(index=INDEX_NAME, id=test_doc_id, refresh=True)
            print("  Cleaned up throwaway test document for nested isolation.")
        except NotFoundError:
            pass


def verify_calls_semantic_binding(es: Elasticsearch) -> bool:
    """
    STEP 3 Verification:
    Verify transcript_semantic binds to jina-embeddings-v5-text-small inference endpoint.
    Index a throwaway test document with paraphrased statement in transcript_english_text/transcript_semantic:
      'There is no risk of losing money in this mutual fund, your principal is completely safe.'
    (an English rendering of 'is mein paisa doobne ka koi risk nahi hai').
    Run a semantic query for a differently-worded English risk statement:
      'Is there any danger of losing invested capital or principal?'
    Confirm it matches and produces a relevance score.
    Deletes throwaway document upon completion.
    """
    print("\n--- STEP 3: Verifying Calls Semantic Inference Binding ---")
    test_doc_id = "__test_semantic_call_binding__"
    test_original = "is mein paisa doobne ka koi risk nahi hai, bilkul tension mat lijiye"
    test_english = "There is no risk of losing money in this mutual fund, your principal is completely safe."
    test_doc = {
        "call_id": test_doc_id,
        "rm_id": "RM_TEST_002",
        "customer_id": "CUST_TEST_002",
        "date_time": "2026-03-25T11:00:00Z",
        "duration_seconds": 90,
        "audio_file_path": "CallAudio/test2.mp3",
        "processing_status": "COMPLETED",
        "language": "hi-en",
        "transcript_original_text": test_original,
        "transcript_english_text": test_english,
        "transcript_semantic": test_english,
        "transcript_segments": [
            {
                "segment_id": "seg_1",
                "speaker": "RM",
                "text_original": test_original,
                "text_english": test_english,
                "start_time": 0.0,
                "end_time": 4.5,
                "is_violation": True,
            }
        ],
        "speaker_mapping_method": "heuristic_fallback",
        "has_violation": True,
        "finding_ids": ["F_TEST_002"],
        "indexed_at": "2026-03-25T11:05:00Z",
    }

    try:
        # Index document with inference
        es.index(index=INDEX_NAME, id=test_doc_id, document=test_doc, refresh=True)

        # Allow inference endpoint to process if needed
        time.sleep(1)

        query_semantic = {
            "semantic": {
                "field": "transcript_semantic",
                "query": "Is there any danger of losing invested capital or principal?",
            }
        }
        res_sem = es.search(index=INDEX_NAME, query=query_semantic)
        hits = res_sem["hits"]["hits"]
        matched = len(hits) > 0 and hits[0]["_id"] == test_doc_id

        if matched:
            score = hits[0]["_score"]
            print(f"  [PASS] Semantic query matched test document! (score={score:.4f})")
            print(f"    English text in transcript_semantic: '{test_english}'")
            print(f"    Query text:                          'Is there any danger of losing invested capital or principal?'")
        else:
            print(f"  [FAIL] Semantic query did not match. (hits={len(hits)})")

        return matched

    finally:
        # Clean up test document
        try:
            es.delete(index=INDEX_NAME, id=test_doc_id, refresh=True)
            print("  Cleaned up throwaway test document for semantic binding.")
        except NotFoundError:
            pass


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("=" * 65)
    print("  PHASE 3.1 — Create & Verify 'calls' Index")
    print("=" * 65)

    es = get_es_client()
    create_calls_index(es, force=True)

    passed_nested = verify_nested_segment_isolation(es)
    passed_semantic = verify_calls_semantic_binding(es)

    final_count = es.count(index=INDEX_NAME)["count"]
    print(f"\nFinal document count in '{INDEX_NAME}': {final_count} (must be 0)")

    if passed_nested and passed_semantic and final_count == 0:
        print(f"\n[PASS] All verifications passed for '{INDEX_NAME}' index. Schema locked and empty.\n")
    else:
        print(f"\n[FAIL] One or more verifications failed for '{INDEX_NAME}'.\n")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
