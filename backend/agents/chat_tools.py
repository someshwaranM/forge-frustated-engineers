"""
Vigil — Phase 9: AI Chat & Agent Builder Tools (backend/agents/chat_tools.py)

Strictly read-only tools for investigative compliance chat:
1. search_calls: Hybrid BM25 + semantic text search and filtering over ES 'calls' index.
2. search_regulations: Hybrid BM25 + semantic search over ES 'regulations' index.
3. get_rm_history: Prior violation history & aggregations from ES 'compliance_findings' index.
4. get_customer_profile: Fixed parameterized SELECT from MySQL 'customer' table.
5. get_product_details: Fixed parameterized SELECT from MySQL 'product' table.
6. get_transactions: Fixed parameterized SELECT from MySQL 'transaction' table.

Guardrails:
- Strictly read-only: No case creation, no notifications, no calls to mutating services.
- Deterministic limits: Default 10, max 25.
- Deterministic sorting & total_count reporting.
"""

import logging
from typing import Any, Dict, List, Optional
from backend.indexing.create_index import get_es_client
from backend.db.session import db_connection

logger = logging.getLogger(__name__)

CALLS_INDEX = "calls"
REGULATIONS_INDEX = "regulations"
FINDINGS_INDEX = "compliance_findings"

DEFAULT_LIMIT = 10
MAX_LIMIT = 25


def _clamp_limit(limit: Optional[int]) -> int:
    """Clamp result limit between 1 and MAX_LIMIT."""
    if limit is None:
        return DEFAULT_LIMIT
    try:
        lim = int(limit)
        return max(1, min(lim, MAX_LIMIT))
    except (ValueError, TypeError):
        return DEFAULT_LIMIT


# ---------------------------------------------------------------------------
# Tool 1: search_calls
# ---------------------------------------------------------------------------

def search_calls(
    query: Optional[str] = None,
    rm_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    severity: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Search recorded RM-customer calls in Elasticsearch. Supports free-text / semantic search
    over transcripts as well as structured filters by RM ID, Customer ID, severity, or date range.

    Args:
        query: Free-text search terms or semantic concepts (e.g. 'guaranteed returns', 'pushed small cap fund').
        rm_id: Specific Relationship Manager ID to filter by (e.g. 'RM001').
        customer_id: Specific Customer ID to filter by (e.g. 'CUST001').
        severity: Filter by finding severity ('HIGH', 'MEDIUM', 'LOW').
        date_from: ISO date string for start of call range (e.g. '2026-03-01').
        date_to: ISO date string for end of call range (e.g. '2026-04-30').
        limit: Max results to return (default 10, max 25).

    Returns:
        Dict with total_count and list of call summaries.
    """
    effective_limit = _clamp_limit(limit)
    es = get_es_client()

    filter_clauses: List[Dict[str, Any]] = []

    if rm_id:
        filter_clauses.append({"term": {"rm_id": rm_id}})
    if customer_id:
        filter_clauses.append({"term": {"customer_id": customer_id}})

    # Severity filter: lookup call_ids from compliance_findings
    if severity:
        try:
            f_res = es.search(
                index=FINDINGS_INDEX,
                query={"term": {"severity": severity.upper()}},
                source=["call_id"],
                size=500,
            )
            matching_call_ids = list({
                h["_source"]["call_id"]
                for h in f_res["hits"]["hits"]
                if "call_id" in h["_source"]
            })
            if not matching_call_ids:
                return {"total_count": 0, "limit": effective_limit, "calls": []}
            filter_clauses.append({"terms": {"call_id": matching_call_ids}})
        except Exception as exc:
            logger.warning(f"Error querying severity filter from {FINDINGS_INDEX}: {exc}")

    # Date range filter
    if date_from or date_to:
        range_clause: Dict[str, Any] = {}
        if date_from:
            range_clause["gte"] = date_from
        if date_to:
            range_clause["lte"] = date_to
        filter_clauses.append({"range": {"date_time": range_clause}})

    # Search query
    sort_criteria = [{"date_time": {"order": "desc", "unmapped_type": "date"}}]

    if query and query.strip():
        q_text = query.strip()
        should_clauses = [
            {"match": {"transcript_english_text": {"query": q_text, "boost": 1.5}}},
            {"semantic": {"field": "transcript_semantic", "query": q_text, "boost": 2.0}},
        ]

        # Also boost call_ids if query matches confirmed compliance findings
        try:
            f_match = es.search(
                index=FINDINGS_INDEX,
                query={
                    "multi_match": {
                        "query": q_text,
                        "fields": ["category^2", "reasoning", "transcript_evidence"],
                    }
                },
                source=["call_id"],
                size=20,
            )
            finding_call_ids = list({
                h["_source"]["call_id"]
                for h in f_match["hits"]["hits"]
                if "call_id" in h.get("_source", {})
            })
            if finding_call_ids:
                should_clauses.append({"terms": {"call_id": finding_call_ids, "boost": 3.0}})
        except Exception as exc:
            logger.debug(f"Finding-boost lookup non-fatal error: {exc}")

        bool_query: Dict[str, Any] = {
            "should": should_clauses,
            "minimum_should_match": 1,
        }
        if filter_clauses:
            bool_query["filter"] = filter_clauses

        final_query = {"bool": bool_query}
        sort_criteria = ["_score", {"date_time": {"order": "desc", "unmapped_type": "date"}}]
    else:
        final_query = {"bool": {"filter": filter_clauses}} if filter_clauses else {"match_all": {}}

    try:
        res = es.search(
            index=CALLS_INDEX,
            query=final_query,
            sort=sort_criteria,
            size=effective_limit,
            source=[
                "call_id",
                "rm_id",
                "customer_id",
                "date_time",
                "duration_seconds",
                "has_violation",
                "finding_ids",
                "transcript_english_text",
            ],
        )
        total = res["hits"]["total"]["value"]
        calls = []
        for h in res["hits"]["hits"]:
            src = h["_source"]
            transcript = src.get("transcript_english_text", "")
            summary = (transcript[:280] + "...") if len(transcript) > 280 else transcript
            calls.append({
                "call_id": src.get("call_id"),
                "rm_id": src.get("rm_id"),
                "customer_id": src.get("customer_id"),
                "date_time": src.get("date_time"),
                "duration_seconds": src.get("duration_seconds"),
                "has_violation": src.get("has_violation", False),
                "finding_ids": src.get("finding_ids", []),
                "transcript_excerpt": summary,
            })

        return {
            "total_count": total,
            "returned_count": len(calls),
            "limit": effective_limit,
            "calls": calls,
        }
    except Exception as exc:
        logger.error(f"search_calls ES query failed: {exc}")
        return {"total_count": 0, "returned_count": 0, "limit": effective_limit, "calls": [], "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool 2: search_regulations
# ---------------------------------------------------------------------------

def search_regulations(query: str, limit: int = 10) -> Dict[str, Any]:
    """
    Search regulatory requirements and circular clauses from SEBI and AMFI using hybrid
    BM25 and semantic search against indexed regulatory documents.

    Args:
        query: Specific regulatory query or violation topic (e.g. 'guaranteed returns SEBI', 'risk disclosure').
        limit: Max results to return (default 10, max 25).

    Returns:
        Dict with total_count and list of regulatory clause chunks.
    """
    effective_limit = _clamp_limit(limit)
    es = get_es_client()
    q_clean = (query or "").strip()
    if not q_clean:
        return {"total_count": 0, "returned_count": 0, "limit": effective_limit, "regulations": []}

    fetch_size = min(effective_limit * 2, 50)

    # 1. BM25 Search
    bm25_hits: Dict[str, Dict[str, Any]] = {}
    try:
        bm25_res = es.search(
            index=REGULATIONS_INDEX,
            query={"match": {"chunk_text": q_clean}},
            size=fetch_size,
        )
        for h in bm25_res.get("hits", {}).get("hits", []):
            cid = h["_source"].get("chunk_id")
            if cid:
                bm25_hits[cid] = {"score": float(h["_score"]), "source": h["_source"]}
    except Exception as exc:
        logger.warning(f"BM25 search error in search_regulations: {exc}")

    # 2. Semantic Search
    sem_hits: Dict[str, Dict[str, Any]] = {}
    try:
        sem_res = es.search(
            index=REGULATIONS_INDEX,
            query={"semantic": {"field": "chunk_text_semantic", "query": q_clean}},
            size=fetch_size,
        )
        for h in sem_res.get("hits", {}).get("hits", []):
            cid = h["_source"].get("chunk_id")
            if cid:
                sem_hits[cid] = {"score": float(h["_score"]), "source": h["_source"]}
    except Exception as exc:
        logger.warning(f"Semantic search error in search_regulations: {exc}")

    # 3. Fuse scores (normalized BM25 + semantic score with current-status boost)
    all_cids = set(bm25_hits.keys()) | set(sem_hits.keys())
    scored = []
    for cid in all_cids:
        b_data = bm25_hits.get(cid)
        s_data = sem_hits.get(cid)
        b_score = round(b_data["score"], 4) if b_data else 0.0
        s_score = round(s_data["score"], 4) if s_data else 0.0
        src = (b_data or s_data)["source"]

        hybrid_score = (b_score / 25.0) + s_score
        if src.get("status") == "current":
            hybrid_score *= 1.1

        scored.append({
            "chunk_id": cid,
            "citation_label": src.get("citation_label", "N/A"),
            "heading": src.get("heading", ""),
            "clause_text": src.get("clause_text", src.get("chunk_text", "")),
            "source_file": src.get("source_file", ""),
            "page_number": src.get("page_number", 1),
            "score": round(hybrid_score, 4),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    results = scored[:effective_limit]

    return {
        "total_count": len(scored),
        "returned_count": len(results),
        "limit": effective_limit,
        "regulations": results,
    }


# ---------------------------------------------------------------------------
# Tool 3: get_rm_history
# ---------------------------------------------------------------------------

def get_rm_history(
    rm_id: Optional[str] = None,
    before_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve prior confirmed compliance findings and violation history for Relationship Managers.

    Supports two distinct modes:
    1. rm_id provided + before_date provided: prior confirmed findings strictly before that date_time.
    2. rm_id provided + before_date omitted: ALL confirmed findings across that RM's history.
    3. rm_id omitted or 'ALL': aggregate cross-RM violation leaderboard/statistics.

    Args:
        rm_id: The RM identifier (e.g. 'RM001'). If omitted or 'ALL', returns cross-RM leaderboard.
        before_date: Optional cutoff date_time string. If supplied, only findings before this date are included.

    Returns:
        Dict with total_violations count, category breakdown, and list of finding items.
    """
    es = get_es_client()

    # Mode 3: Cross-RM aggregate leaderboard
    if not rm_id or rm_id.strip().upper() in ("ALL", "ANY", "*"):
        try:
            res = es.search(
                index=FINDINGS_INDEX,
                size=0,
                aggs={
                    "by_rm": {"terms": {"field": "rm_id", "size": 25}},
                    "by_category": {"terms": {"field": "category", "size": 20}},
                },
            )
            total = res["hits"]["total"]["value"]
            rm_buckets = res.get("aggregations", {}).get("by_rm", {}).get("buckets", [])
            cat_buckets = res.get("aggregations", {}).get("by_category", {}).get("buckets", [])

            leaderboard = [
                {"rm_id": b["key"], "violations_count": b["doc_count"]}
                for b in rm_buckets
            ]
            most_violations_rm = leaderboard[0]["rm_id"] if leaderboard else "None"

            return {
                "mode": "cross_rm_summary",
                "total_violations_across_all_rms": total,
                "most_violations_rm": most_violations_rm,
                "rm_leaderboard": leaderboard,
                "category_breakdown": {b["key"]: b["doc_count"] for b in cat_buckets},
            }
        except Exception as exc:
            logger.error(f"Error querying cross-RM findings summary: {exc}")
            return {"error": str(exc), "rm_leaderboard": []}

    target_rm = rm_id.strip()

    # Mode 1 & Mode 2: Specific RM
    must_clauses: List[Dict[str, Any]] = [{"term": {"rm_id": target_rm}}]

    if before_date:
        # Phase 7 semantics: calls with date_time < before_date
        try:
            calls_res = es.search(
                index=CALLS_INDEX,
                query={
                    "bool": {
                        "filter": [
                            {"term": {"rm_id": target_rm}},
                            {"range": {"date_time": {"lt": before_date}}},
                        ]
                    }
                },
                size=100,
                source=["call_id"],
            )
            earlier_call_ids = [
                h["_source"]["call_id"]
                for h in calls_res["hits"]["hits"]
                if "call_id" in h["_source"]
            ]
            if not earlier_call_ids:
                return {
                    "rm_id": target_rm,
                    "mode": "before_date_filtered",
                    "before_date": before_date,
                    "total_violations": 0,
                    "category_breakdown": {},
                    "findings": [],
                }
            must_clauses.append({"terms": {"call_id": earlier_call_ids}})
        except Exception as exc:
            logger.warning(f"Error resolving prior calls before {before_date}: {exc}")

    query = {"bool": {"filter": must_clauses}}
    aggs = {"categories": {"terms": {"field": "category", "size": 20}}}

    try:
        res = es.search(
            index=FINDINGS_INDEX,
            query=query,
            aggregations=aggs,
            size=MAX_LIMIT,
            sort=[{"created_at": {"order": "desc", "unmapped_type": "date"}}],
        )
        total = res["hits"]["total"]["value"]
        buckets = res.get("aggregations", {}).get("categories", {}).get("buckets", [])
        findings_list = []
        for h in res["hits"]["hits"]:
            src = h["_source"]
            findings_list.append({
                "finding_id": src.get("finding_id"),
                "call_id": src.get("call_id"),
                "category": src.get("category"),
                "severity": src.get("severity"),
                "customer_id": src.get("customer_id"),
                "regulation_citation_label": src.get("regulation_citation_label"),
                "reasoning": (src.get("reasoning", "")[:240] + "...") if len(src.get("reasoning", "")) > 240 else src.get("reasoning", ""),
                "created_at": src.get("created_at"),
            })

        return {
            "rm_id": target_rm,
            "mode": "before_date_filtered" if before_date else "all_time",
            "before_date": before_date,
            "total_violations": total,
            "category_breakdown": {b["key"]: b["doc_count"] for b in buckets},
            "findings": findings_list,
        }
    except Exception as exc:
        logger.error(f"Error executing get_rm_history for {target_rm}: {exc}")
        return {
            "rm_id": target_rm,
            "total_violations": 0,
            "category_breakdown": {},
            "findings": [],
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Tool 4: get_customer_profile
# ---------------------------------------------------------------------------

def get_customer_profile(customer_id: str) -> Dict[str, Any]:
    """
    Retrieve customer profile, risk category, investment experience, and KYC status from MySQL.

    Args:
        customer_id: Customer ID (e.g. 'CUST001').

    Returns:
        Dict with customer record or error if not found.
    """
    cid = (customer_id or "").strip()
    if not cid:
        return {"error": "customer_id is required"}

    with db_connection() as cur:
        cur.execute(
            "SELECT customer_id, full_name, mobile_number, risk_profile, investment_experience, kyc_status "
            "FROM customer WHERE customer_id = %s",
            (cid,),
        )
        row = cur.fetchone()

    if not row:
        return {"customer_id": cid, "found": False, "message": f"Customer '{cid}' not found"}

    return {
        "found": True,
        "customer_id": row["customer_id"],
        "full_name": row.get("full_name"),
        "risk_profile": row.get("risk_profile"),
        "investment_experience": row.get("investment_experience"),
        "kyc_status": row.get("kyc_status"),
    }


# ---------------------------------------------------------------------------
# Tool 5: get_product_details
# ---------------------------------------------------------------------------

def get_product_details(product_id: str) -> Dict[str, Any]:
    """
    Retrieve investment product details, risk classification, suitable risk profiles,
    and mandatory disclosure requirements from MySQL.

    Args:
        product_id: Product ID (e.g. 'PROD001').

    Returns:
        Dict with product record or error if not found.
    """
    pid = (product_id or "").strip()
    if not pid:
        return {"error": "product_id is required"}

    with db_connection() as cur:
        cur.execute(
            "SELECT product_id, product_name, risk_class, suitable_risk_profiles, disclosure_requirements "
            "FROM product WHERE product_id = %s",
            (pid,),
        )
        row = cur.fetchone()

    if not row:
        return {"product_id": pid, "found": False, "message": f"Product '{pid}' not found"}

    return {
        "found": True,
        "product_id": row["product_id"],
        "product_name": row.get("product_name"),
        "risk_class": row.get("risk_class"),
        "suitable_risk_profiles": row.get("suitable_risk_profiles"),
        "disclosure_requirements": row.get("disclosure_requirements"),
    }


# ---------------------------------------------------------------------------
# Tool 6: get_transactions
# ---------------------------------------------------------------------------

def get_transactions(
    customer_id: Optional[str] = None,
    rm_id: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Retrieve customer and RM transactions from MySQL with deterministic sorting and limit bounds.

    Args:
        customer_id: Optional customer ID to filter by.
        rm_id: Optional RM ID to filter by.
        limit: Max transactions to return (default 10, max 25).

    Returns:
        Dict with total_count and list of transactions.
    """
    effective_limit = _clamp_limit(limit)
    conditions = []
    params: List[Any] = []

    if customer_id and customer_id.strip():
        conditions.append("customer_id = %s")
        params.append(customer_id.strip())

    if rm_id and rm_id.strip():
        conditions.append("rm_id = %s")
        params.append(rm_id.strip())

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with db_connection() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM transaction {where_sql}", tuple(params))
        count_res = cur.fetchone()
        total = count_res["total"] if count_res else 0

        query_params = list(params) + [effective_limit]
        cur.execute(
            f"SELECT transaction_id, customer_id, rm_id, product_id, amount, transaction_type, transaction_time "
            f"FROM transaction {where_sql} ORDER BY transaction_time DESC LIMIT %s",
            tuple(query_params),
        )
        rows = cur.fetchall()

    txns = []
    for r in rows:
        t_time = r.get("transaction_time")
        txns.append({
            "transaction_id": r.get("transaction_id"),
            "customer_id": r.get("customer_id"),
            "rm_id": r.get("rm_id"),
            "product_id": r.get("product_id"),
            "amount": float(r.get("amount")) if r.get("amount") is not None else 0.0,
            "transaction_type": r.get("transaction_type"),
            "transaction_time": t_time.isoformat() if hasattr(t_time, "isoformat") else str(t_time),
        })

    return {
        "total_count": total,
        "returned_count": len(txns),
        "limit": effective_limit,
        "transactions": txns,
    }


# ---------------------------------------------------------------------------
# Tool Dispatcher & Grounded Results Extractor
# ---------------------------------------------------------------------------

TOOL_REGISTRY = {
    "search_calls": search_calls,
    "search_regulations": search_regulations,
    "get_rm_history": get_rm_history,
    "get_customer_profile": get_customer_profile,
    "get_product_details": get_product_details,
    "get_transactions": get_transactions,
}

ALL_TOOLS = [
    search_calls,
    search_regulations,
    get_rm_history,
    get_customer_profile,
    get_product_details,
    get_transactions,
]


def execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a tool execution by name safely with argument unpacking."""
    fn = TOOL_REGISTRY.get(tool_name)
    if not fn:
        return {"error": f"Tool '{tool_name}' not found in registry"}
    try:
        return fn(**tool_args)
    except Exception as exc:
        logger.error(f"Error executing tool '{tool_name}' with args {tool_args}: {exc}")
        return {"error": str(exc), "tool_name": tool_name}


def extract_grounded_ids_from_tool_output(tool_name: str, output: Any) -> List[Dict[str, str]]:
    """
    Extract grounded identifiers directly from tool outputs.
    Guarantees grounded_results are built strictly from real returned entities,
    not from parsing model text.
    """
    results: List[Dict[str, str]] = []
    if not isinstance(output, dict):
        return results

    if tool_name == "search_calls":
        for call in output.get("calls", []):
            if cid := call.get("call_id"):
                results.append({"type": "call", "id": cid})
            for fid in call.get("finding_ids", []):
                if fid:
                    results.append({"type": "finding", "id": fid})

    elif tool_name == "search_regulations":
        for reg in output.get("regulations", []):
            if cid := reg.get("chunk_id"):
                results.append({"type": "regulation", "id": cid})

    elif tool_name == "get_rm_history":
        for fnd in output.get("findings", []):
            if fid := fnd.get("finding_id"):
                results.append({"type": "finding", "id": fid})
            if cid := fnd.get("call_id"):
                results.append({"type": "call", "id": cid})

    elif tool_name == "get_customer_profile":
        if output.get("found") and (cid := output.get("customer_id")):
            results.append({"type": "customer", "id": cid})

    elif tool_name == "get_product_details":
        if output.get("found") and (pid := output.get("product_id")):
            results.append({"type": "product", "id": pid})

    elif tool_name == "get_transactions":
        for txn in output.get("transactions", []):
            if tid := txn.get("transaction_id"):
                results.append({"type": "transaction", "id": tid})
            if cid := txn.get("customer_id"):
                results.append({"type": "customer", "id": cid})

    return results


# ---------------------------------------------------------------------------
# Bedrock Converse Tool Specifications
# ---------------------------------------------------------------------------

BEDROCK_TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "search_calls",
                "description": "Search recorded RM-customer calls in Elasticsearch by text/semantic query, RM ID, Customer ID, severity, or date range.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search terms or semantic query (e.g. 'guaranteed returns')"},
                            "rm_id": {"type": "string", "description": "Relationship Manager ID (e.g. 'RM001')"},
                            "customer_id": {"type": "string", "description": "Customer ID (e.g. 'CUST001')"},
                            "severity": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"], "description": "Violation severity"},
                            "date_from": {"type": "string", "description": "Start date in ISO format"},
                            "date_to": {"type": "string", "description": "End date in ISO format"},
                            "limit": {"type": "integer", "description": "Max results (default 10, max 25)"},
                        },
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "search_regulations",
                "description": "Search regulatory requirements and clauses from SEBI and AMFI using hybrid BM25 + semantic search.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Topic or keyword query for regulations (e.g. 'guaranteed return prohibition')"},
                            "limit": {"type": "integer", "description": "Max results (default 10, max 25)"},
                        },
                        "required": ["query"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_rm_history",
                "description": "Retrieve prior confirmed violation history and category breakdown for Relationship Managers.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "rm_id": {"type": "string", "description": "RM identifier (e.g. 'RM001'). Omit or set to 'ALL' for cross-RM leaderboard."},
                            "before_date": {"type": "string", "description": "Optional ISO date_time cutoff to only retrieve violations prior to this timestamp."},
                        },
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_customer_profile",
                "description": "Retrieve customer risk profile, investment experience, and KYC status from MySQL database.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Customer identifier (e.g. 'CUST001')"},
                        },
                        "required": ["customer_id"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_product_details",
                "description": "Retrieve investment product details, risk class, suitable risk profiles, and disclosures from MySQL database.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string", "description": "Product identifier (e.g. 'PROD001')"},
                        },
                        "required": ["product_id"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_transactions",
                "description": "Retrieve investment transaction records from MySQL database filtered by customer ID or RM ID.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Customer ID to filter by"},
                            "rm_id": {"type": "string", "description": "RM ID to filter by"},
                            "limit": {"type": "integer", "description": "Max transactions (default 10, max 25)"},
                        },
                    }
                },
            }
        },
    ]
}
