"""
Vigil — Findings API Routes (backend/api/routes/findings.py)

Exposes:
- GET /api/findings: Filterable findings list from Elasticsearch 'compliance_findings'
- GET /api/findings/{finding_id}: Single finding lookup
"""

import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, status
from elasticsearch import NotFoundError

from backend.elastic.client import get_es_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/findings", tags=["Findings"])


@router.get("", response_model=Dict[str, Any])
def list_findings(
    rm_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    call_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List findings from compliance_findings index with filtering."""
    es = get_es_client()
    must_clauses: List[Dict[str, Any]] = []

    if rm_id:
        must_clauses.append({"term": {"rm_id": rm_id}})
    if customer_id:
        must_clauses.append({"term": {"customer_id": customer_id}})
    if category:
        must_clauses.append({"term": {"category": category}})
    if severity:
        must_clauses.append({"term": {"severity": severity.upper()}})
    if status_filter:
        must_clauses.append({"term": {"status": status_filter.upper()}})
    if call_id:
        must_clauses.append({"term": {"call_id": call_id}})

    query = {"bool": {"must": must_clauses}} if must_clauses else {"match_all": {}}

    try:
        res = es.search(
            index="compliance_findings",
            query=query,
            sort=[{"created_at": {"order": "desc", "unmapped_type": "date"}}],
            from_=offset,
            size=limit,
        )
        total = res["hits"]["total"]["value"]
        items = [h["_source"] for h in res["hits"]["hits"]]
        return {"total": total, "items": items}
    except Exception as exc:
        logger.error(f"Failed to query compliance_findings: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query compliance_findings: {exc}",
        )


@router.get("/{finding_id}", response_model=Dict[str, Any])
def get_finding(finding_id: str):
    """Retrieve single finding document by finding_id."""
    es = get_es_client()
    try:
        res = es.get(index="compliance_findings", id=finding_id)
        return res["_source"]
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "FINDING_NOT_FOUND", "message": f"Finding '{finding_id}' not found."},
        )
    except Exception as exc:
        logger.error(f"Failed to retrieve finding {finding_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve finding {finding_id}: {exc}",
        )
