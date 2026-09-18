"""
Vigil — Calls API Routes (backend/api/routes/calls.py)

Exposes:
- GET /api/calls: Filterable call list (rm_id, customer_id, severity, status, date range)
- GET /api/calls/{call_id}: Full call detail incl. transcript_segments
- GET /api/calls/{call_id}/audio: Streams the archived WAV audio recording
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from elasticsearch import NotFoundError

from backend.elastic.client import get_es_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calls", tags=["Calls"])


@router.get("", response_model=Dict[str, Any])
def list_calls(
    rm_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    has_violation: Optional[bool] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Retrieve paginated calls from Elasticsearch 'calls' index with filtering.
    """
    es = get_es_client()
    must_clauses: List[Dict[str, Any]] = []

    if rm_id:
        must_clauses.append({"term": {"rm_id": rm_id}})
    if customer_id:
        must_clauses.append({"term": {"customer_id": customer_id}})
    if has_violation is not None:
        must_clauses.append({"term": {"has_violation": has_violation}})

    if status_filter:
        s_upper = status_filter.upper()
        if s_upper in ("COMPLETED", "PROCESSED", "PENDING", "FAILED"):
            must_clauses.append({"term": {"processing_status": s_upper}})
        elif s_upper == "VIOLATION":
            must_clauses.append({"term": {"has_violation": True}})
        elif s_upper == "CLEAN":
            must_clauses.append({"term": {"has_violation": False}})

    # If severity filter provided, look up call_ids from compliance_findings
    if severity:
        try:
            f_res = es.search(
                index="compliance_findings",
                query={"term": {"severity": severity.upper()}},
                source=["call_id"],
                size=500,
            )
            matching_call_ids = list({h["_source"]["call_id"] for h in f_res["hits"]["hits"] if "call_id" in h["_source"]})
            if matching_call_ids:
                must_clauses.append({"terms": {"call_id": matching_call_ids}})
            else:
                return {"total": 0, "items": []}
        except Exception as exc:
            logger.warning(f"Error querying severity from compliance_findings: {exc}")

    # Date range filtering
    if start_date or end_date:
        range_clause: Dict[str, Any] = {}
        if start_date:
            range_clause["gte"] = start_date
        if end_date:
            range_clause["lte"] = end_date
        must_clauses.append({"range": {"date_time": range_clause}})

    query = {"bool": {"must": must_clauses}} if must_clauses else {"match_all": {}}

    try:
        res = es.search(
            index="calls",
            query=query,
            sort=[{"date_time": {"order": "desc", "unmapped_type": "date"}}],
            from_=offset,
            size=limit,
            source={
                "excludes": ["transcript_semantic", "transcript_segments.text_original", "transcript_segments.text_english"]
            },
        )
        total = res["hits"]["total"]["value"]
        hits = [h["_source"] for h in res["hits"]["hits"]]
        return {"total": total, "items": hits}
    except Exception as exc:
        logger.error(f"Failed to query calls index: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query calls index: {exc}",
        )


@router.get("/{call_id}", response_model=Dict[str, Any])
def get_call_detail(call_id: str):
    """
    Retrieve full call document from Elasticsearch 'calls' index,
    including transcript_segments, findings, and associated compliance cases.
    """
    es = get_es_client()
    try:
        res = es.get(index="calls", id=call_id)
        call_doc = res["_source"]
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "CALL_NOT_FOUND", "message": f"Call '{call_id}' not found."},
        )
    except Exception as exc:
        logger.error(f"Failed to retrieve call {call_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve call {call_id}: {exc}",
        )

    # Enrich with associated cases from MySQL compliance_case table
    try:
        from backend.db.session import get_db_connection
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT case_id, finding_id, call_id, category, severity, status, created_at, updated_at
                FROM compliance_case
                WHERE call_id = %s
                ORDER BY created_at ASC
                """,
                (call_id,)
            )
            cases = cur.fetchall()
            for c in cases:
                if c.get("created_at"):
                    c["created_at"] = str(c["created_at"])
                if c.get("updated_at"):
                    c["updated_at"] = str(c["updated_at"])
            call_doc["cases"] = cases
            if cases:
                call_doc["case_id"] = cases[0]["case_id"]
        conn.close()
    except Exception as exc:
        logger.warning(f"Could not fetch cases from MySQL for call {call_id}: {exc}")

    # Fallback derivation if case_id still missing but finding_ids present
    if not call_doc.get("case_id") and call_doc.get("finding_ids"):
        f_id = call_doc["finding_ids"][0]
        derived = f_id.replace("FND-", "CASE-") if f_id.startswith("FND-") else f"CASE-{f_id}"
        call_doc["case_id"] = derived
        if not call_doc.get("cases"):
            call_doc["cases"] = [{"case_id": derived, "finding_id": f_id, "status": "OPEN"}]

    # Also enrich findings list from compliance_findings index if not populated
    if not call_doc.get("findings") and (call_doc.get("finding_ids") or call_doc.get("has_violation")):
        try:
            f_res = es.search(
                index="compliance_findings",
                query={"term": {"call_id": call_id}},
                size=20,
            )
            findings = [h["_source"] for h in f_res["hits"]["hits"]]
            if findings:
                call_doc["findings"] = findings
                if not call_doc.get("case_id"):
                    f0 = findings[0].get("finding_id", "")
                    call_doc["case_id"] = f0.replace("FND-", "CASE-") if f0.startswith("FND-") else f"CASE-{f0}"
        except Exception as exc:
            logger.warning(f"Could not fetch findings for call {call_id}: {exc}")

    return call_doc


@router.get("/{call_id}/audio")
def get_call_audio(call_id: str):
    """
    Stream the WAV audio recording for a call.
    Resolves the audio file path from Elasticsearch and verifies file existence.
    """
    es = get_es_client()
    try:
        res = es.get(index="calls", id=call_id)
        call_doc = res["_source"]
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "CALL_NOT_FOUND", "message": f"Call '{call_id}' not found."},
        )
    except Exception as exc:
        logger.error(f"Failed to retrieve call {call_id} for audio streaming: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve call {call_id}: {exc}",
        )

    audio_file_path = call_doc.get("audio_file_path")
    if not audio_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "AUDIO_NOT_FOUND", "message": f"No audio file path recorded for call '{call_id}'."},
        )

    # Resolve path defensively: direct path or within CallAudio-Archive / CallAudio
    candidate_path = Path(audio_file_path)
    if not candidate_path.is_file():
        # Check relative to vigil root archive
        repo_root = Path(__file__).resolve().parents[3]
        fallback_archive = repo_root / "CallAudio-Archive" / candidate_path.name
        fallback_active = repo_root / "CallAudio" / candidate_path.name

        if fallback_archive.is_file():
            candidate_path = fallback_archive
        elif fallback_active.is_file():
            candidate_path = fallback_active
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "AUDIO_FILE_MISSING",
                    "message": f"Audio file not found on disk: {audio_file_path}",
                },
            )

    return FileResponse(
        path=str(candidate_path),
        media_type="audio/wav",
        filename=candidate_path.name,
    )
