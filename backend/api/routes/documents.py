"""
Vigil — Regulations Documents API Route (backend/api/routes/documents.py)

Exposes:
- GET /api/documents: Aggregated regulation documents from the Elasticsearch 'regulations' index
"""

import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, status

from backend.elastic.client import get_es_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("", response_model=Dict[str, Any])
def list_documents():
    """
    Aggregate the regulations ES index by document_id and return document metadata,
    chunk count, and synthetic indexed_status: "INDEXED".
    """
    es = get_es_client()
    try:
        res = es.search(
            index="regulations",
            size=0,
            aggs={
                "documents": {
                    "terms": {"field": "document_id", "size": 100},
                    "aggs": {
                        "doc_name": {"terms": {"field": "document_name.raw", "size": 1}},
                        "regulator": {"terms": {"field": "regulator", "size": 1}},
                        "status": {"terms": {"field": "status", "size": 1}},
                    },
                }
            },
        )

        buckets = res.get("aggregations", {}).get("documents", {}).get("buckets", [])
        documents = []
        for b in buckets:
            doc_id = b["key"]
            chunk_count = b["doc_count"]

            doc_name_buckets = b.get("doc_name", {}).get("buckets", [])
            doc_name = doc_name_buckets[0]["key"] if doc_name_buckets else doc_id

            regulator_buckets = b.get("regulator", {}).get("buckets", [])
            regulator = regulator_buckets[0]["key"] if regulator_buckets else "Unknown"

            status_buckets = b.get("status", {}).get("buckets", [])
            doc_status = status_buckets[0]["key"] if status_buckets else "current"

            documents.append({
                "document_id": doc_id,
                "document_name": doc_name,
                "regulator": regulator,
                "status": doc_status,
                "chunk_count": chunk_count,
                "indexed_status": "INDEXED",
            })

        return {
            "total": len(documents),
            "items": documents,
        }
    except Exception as exc:
        logger.error(f"Failed to aggregate regulations from ES: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to aggregate regulations from ES: {exc}",
        )
