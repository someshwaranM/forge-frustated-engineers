"""
Step 2 — Create the Elasticsearch 'regulations' index.

Creates the index with the exact mapping required by the pipeline,
then validates that the semantic_text field's inference endpoint
actually works by indexing a throwaway test document and running
a real semantic query against it.
"""

import os
import sys
import time
import json
from pathlib import Path
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, NotFoundError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
INDEX_NAME = "regulations"
INFERENCE_ENDPOINT = ".jina-embeddings-v5-text-small"

MAPPING = {
    "mappings": {
        "properties": {
            "chunk_id":             {"type": "keyword"},
            "chunk_level":          {"type": "keyword"},
            "document_id":          {"type": "keyword"},
            "document_name":        {"type": "text",    "fields": {"raw": {"type": "keyword"}}},
            "regulator":            {"type": "keyword"},
            "document_type":        {"type": "keyword"},
            "document_version":     {"type": "keyword"},
            "publication_date":     {"type": "date",    "format": "yyyy-MM-dd"},
            "effective_date":       {"type": "date",    "format": "yyyy-MM-dd"},
            "effective_until":      {"type": "date",    "format": "yyyy-MM-dd"},
            "status":               {"type": "keyword"},
            "priority":             {"type": "integer"},
            "source_url":           {"type": "keyword"},
            "source_file":          {"type": "keyword"},
            "source_file_hash":     {"type": "keyword"},
            "chapter":              {"type": "keyword"},
            "section":              {"type": "keyword"},
            "sub_section":          {"type": "keyword"},
            "regulation_number":    {"type": "keyword"},
            "clause":               {"type": "keyword"},
            "paragraph":            {"type": "keyword"},
            "heading":              {"type": "text",    "fields": {"raw": {"type": "keyword"}}},
            "citation_label":       {"type": "keyword"},
            "clause_text":          {"type": "text"},
            "chunk_text":           {"type": "text"},
            "chunk_text_semantic":  {
                "type": "semantic_text",
                "inference_id": INFERENCE_ENDPOINT,
            },
            "page_number":          {"type": "integer"},
            "indexed_at":           {"type": "date",    "format": "strict_date_time"},
        }
    }
}


def get_es_client() -> Elasticsearch:
    """Return a connected Elasticsearch client from .env."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)
    url = os.getenv("ELASTICSEARCH_URL")
    api_key = os.getenv("ELASTICSEARCH_API_KEY")
    if not url or not api_key:
        raise RuntimeError("ELASTICSEARCH_URL / ELASTICSEARCH_API_KEY not set in .env")
    return Elasticsearch(url, api_key=api_key, request_timeout=120)


def create_index(es: Elasticsearch, *, force: bool = False) -> None:
    """Create the 'regulations' index. Optionally drop first if force=True."""
    if force:
        try:
            es.indices.delete(index=INDEX_NAME)
            print(f"  Deleted existing index '{INDEX_NAME}'.")
        except NotFoundError:
            pass

    if es.indices.exists(index=INDEX_NAME):
        print(f"  Index '{INDEX_NAME}' already exists — skipping creation.")
        return

    es.indices.create(index=INDEX_NAME, body=MAPPING)
    print(f"  Created index '{INDEX_NAME}' with full mapping.")


def validate_semantic_endpoint(es: Elasticsearch) -> None:
    """
    Index a throwaway test document with real text in chunk_text_semantic,
    run a semantic query, confirm it returns a relevant result, then delete.
    """
    test_id = "__semantic_validation_test__"
    test_doc = {
        "chunk_id": test_id,
        "chunk_level": "clause",
        "document_id": "TEST",
        "document_name": "Test Document",
        "regulator": "TEST",
        "document_type": "TEST",
        "document_version": "1.0",
        "publication_date": "2024-01-01",
        "effective_date": "2024-01-01",
        "effective_until": None,
        "status": "current",
        "priority": 1,
        "source_url": "https://example.com",
        "source_file": "test.pdf",
        "source_file_hash": "0" * 64,
        "chapter": "",
        "section": "",
        "sub_section": "",
        "regulation_number": "",
        "clause": "II.4.g",
        "paragraph": "",
        "heading": "Client related obligations",
        "citation_label": "Test §II.4.g",
        "clause_text": "MFDs shall not provide any indicative portfolio or indicative yield or indicative return for any particular scheme or transaction and shall abstain from indicating or assuring returns for any particular scheme or transaction.",
        "chunk_text": "Client related obligations - MFDs shall not provide any indicative portfolio or indicative yield or indicative return.",
        "chunk_text_semantic": "AMFI Code of Conduct for Mutual Fund Distributors. Section II - Obligations. Clause 4.g - Client related obligations. MFDs shall not provide any indicative portfolio or indicative yield or indicative return for any particular scheme or transaction and shall abstain from indicating or assuring returns for any particular scheme or transaction. Mutual fund investments are subject to market risks.",
        "page_number": 5,
        "indexed_at": "2024-01-01T00:00:00Z",
    }

    print("  Indexing throwaway test document…")
    es.index(index=INDEX_NAME, id=test_id, document=test_doc, timeout="120s")

    # Wait for the semantic_text inference to complete and the doc to be searchable
    print("  Waiting for semantic inference to process the document…")
    max_wait = 60
    for i in range(max_wait):
        time.sleep(2)
        try:
            result = es.search(
                index=INDEX_NAME,
                body={
                    "query": {
                        "semantic": {
                            "field": "chunk_text_semantic",
                            "query": "you cannot guarantee returns on mutual funds"
                        }
                    },
                    "size": 1,
                }
            )
            hits = result["hits"]["hits"]
            if hits and hits[0]["_id"] == test_id:
                score = hits[0]["_score"]
                print(f"  [PASS] Semantic query returned test document (score={score:.4f}) — inference endpoint is working.")
                break
        except Exception as e:
            if i >= max_wait - 1:
                raise
            # The document may still be processing
            pass
    else:
        raise RuntimeError(
            "Semantic query did not return the test document within "
            f"{max_wait * 2}s. The inference endpoint "
            f"'{INFERENCE_ENDPOINT}' may not be properly deployed."
        )

    # Clean up
    es.delete(index=INDEX_NAME, id=test_id)
    es.indices.refresh(index=INDEX_NAME)
    print("  Deleted throwaway test document.")


def main():
    print("=" * 60)
    print("STEP 2 — Create Elasticsearch 'regulations' index")
    print("=" * 60)

    es = get_es_client()
    print(f"  Connected to Elasticsearch ({es.info()['version']['number']})")

    create_index(es, force=True)
    validate_semantic_endpoint(es)

    print("\n  [PASS] Step 2 complete — index created and semantic endpoint validated.\n")


if __name__ == "__main__":
    main()
