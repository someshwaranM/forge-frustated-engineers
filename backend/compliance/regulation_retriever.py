"""
Vigil — Phase 6: Hybrid Regulation Retriever (backend/compliance/regulation_retriever.py)

Retrieves candidate regulatory citations from the Elasticsearch 'regulations' index using
hybrid search:
- BM25 on chunk_text (exact keyword & terminology matching)
- Semantic on chunk_text_semantic (bound to jina-embeddings-v5-text-small for paraphrase matching)

Returns top 1-3 candidate chunks per violation category with both bm25_score and semantic_score
so Phase 7's Investigator Agent can reason over multiple retrieved options rather than having
Phase 6 prematurely collapse the citation choice.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from elasticsearch import Elasticsearch
from backend.indexing.create_index import get_es_client

# Phase 13: Elastic APM spans (no OpenTelemetry)
try:
    from backend.observability.apm import apm_span
except ImportError:
    from contextlib import contextmanager
    @contextmanager
    def apm_span(*a, **kw): yield

logger = logging.getLogger(__name__)

# Debug logger (enabled via VIGIL_DEBUG_PIPELINE=true)
try:
    from backend.observability.debug_logger import log_regulation_retrieval
except ImportError:
    def log_regulation_retrieval(*a, **kw): pass

REGULATIONS_INDEX = "regulations"


@dataclass
class RegulationCitationCandidate:
    chunk_id: str
    citation_label: str
    bm25_score: float
    semantic_score: float
    clause_text: str
    heading: str
    source_file: str
    page_number: int


# Pre-configured query strategies per candidate category
CATEGORY_QUERY_STRATEGIES = {
    "GUARANTEED_RETURN": {
        "bm25_query": "guaranteed return indicative yield assuring returns fixed profit",
        "semantic_query": "guaranteed returns or assuring fixed profit to investors",
    },
    "AMBIGUOUS_RETURN_CLAIM": {
        "bm25_query": "indicative return future performance projection indicative yield",
        "semantic_query": "indicating or projecting future performance returns to clients",
    },
    "SUITABILITY_MISMATCH": {
        "bm25_query": "investor risk profile suitability assessment client category investment experience",
        "semantic_query": "investor risk profile suitability assessment before recommendation",
    },
    "SUITABILITY_INEXPERIENCE_GAP": {
        "bm25_query": "client investment experience knowledge suitability risk profile",
        "semantic_query": "investor investment experience knowledge assessment suitability",
    },
    "AMBIGUOUS_SUITABILITY": {
        "bm25_query": "client investment experience knowledge suitability risk profile",
        "semantic_query": "investor investment experience knowledge assessment suitability",
    },
    "MISSING_RISK_DISCLOSURE": {
        "bm25_query": "mandatory risk disclosure risk-o-meter product risk category scheme information document",
        "semantic_query": "mandatory risk disclosure risk-o-meter scheme document to client",
    },
    "INADEQUATE_RISK_DISCLOSURE": {
        "bm25_query": "risk disclosure risk-o-meter hybrid allocation scheme document",
        "semantic_query": "mandatory product risk disclosure and risk-o-meter requirements",
    },
    "MISSING_DISCLOSURE": {
        "bm25_query": "mandatory risk disclosure risk-o-meter hybrid allocation product risk scheme information document",
        "semantic_query": "mandatory risk disclosure risk-o-meter scheme document to client",
    },
}


class RegulationRetriever:
    """Handles hybrid BM25 + semantic retrieval from Elasticsearch regulations index."""

    def __init__(self, es_client: Optional[Elasticsearch] = None):
        self.es = es_client or get_es_client()

    def retrieve_citations_for_category(
        self,
        category: str,
        top_k: int = 3,
        call_id: str = "N/A"
    ) -> List[Dict[str, Any]]:
        """
        Executes hybrid retrieval (BM25 + Semantic) for a candidate category.
        
        Returns:
            List of 1 to top_k candidate citation dictionaries with chunk_id, citation_label,
            bm25_score, semantic_score, and clause_text.
        """
        strategy = CATEGORY_QUERY_STRATEGIES.get(
            category,
            CATEGORY_QUERY_STRATEGIES["SUITABILITY_MISMATCH"]
        )

        bm25_query_text = strategy["bm25_query"]
        semantic_query_text = strategy["semantic_query"]

        # 1. Run BM25 search
        bm25_hits: Dict[str, Dict[str, Any]] = {}
        try:
            with apm_span("elasticsearch.regulation.bm25", span_type="db.elasticsearch", span_subtype="search", labels={"category": category}):
                bm25_resp = self.es.search(
                    index=REGULATIONS_INDEX,
                    body={
                        "query": {
                            "match": {
                                "chunk_text": bm25_query_text
                            }
                        },
                        "size": top_k * 2
                    }
                )
                for h in bm25_resp.get("hits", {}).get("hits", []):
                    cid = h["_source"]["chunk_id"]
                    bm25_hits[cid] = {
                        "score": float(h["_score"]),
                        "source": h["_source"]
                    }
        except Exception as exc:
            logger.warning(f"BM25 search error for category '{category}': {exc}")

        # 2. Run Semantic search
        semantic_hits: Dict[str, Dict[str, Any]] = {}
        try:
            with apm_span("elasticsearch.regulation.semantic", span_type="db.elasticsearch", span_subtype="search", labels={"category": category}):
                sem_resp = self.es.search(
                    index=REGULATIONS_INDEX,
                    body={
                        "query": {
                            "semantic": {
                                "field": "chunk_text_semantic",
                                "query": semantic_query_text
                            }
                        },
                        "size": top_k * 2
                    }
                )
                for h in sem_resp.get("hits", {}).get("hits", []):
                    cid = h["_source"]["chunk_id"]
                    semantic_hits[cid] = {
                        "score": float(h["_score"]),
                        "source": h["_source"]
                    }
        except Exception as exc:
            logger.warning(f"Semantic search error for category '{category}': {exc}")

        # 3. Fuse scores and rank candidates (Reciprocal Rank Fusion with score weight)
        all_ids = set(bm25_hits.keys()) | set(semantic_hits.keys())
        scored_candidates = []

        for cid in all_ids:
            bm25_data = bm25_hits.get(cid)
            sem_data = semantic_hits.get(cid)

            b_score = round(bm25_data["score"], 4) if bm25_data else 0.0
            s_score = round(sem_data["score"], 4) if sem_data else 0.0

            source = (bm25_data or sem_data)["source"]

            # Combined hybrid ranking score
            # Normalize BM25 roughly into [0, 1] range (assuming max bm25 ~ 25) + semantic score
            hybrid_score = (b_score / 25.0) + s_score

            # Boost current regulations over historical
            if source.get("status") == "current":
                hybrid_score *= 1.1

            scored_candidates.append({
                "chunk_id": cid,
                "citation_label": source.get("citation_label", ""),
                "bm25_score": b_score,
                "semantic_score": s_score,
                "hybrid_score": hybrid_score,
                "clause_text": source.get("clause_text", ""),
                "heading": source.get("heading", ""),
                "source_file": source.get("source_file", ""),
                "page_number": source.get("page_number", 1)
            })

        # Sort descending by hybrid_score
        scored_candidates.sort(key=lambda x: x["hybrid_score"], reverse=True)

        # Return top_k without the temporary hybrid_score field
        results = []
        for c in scored_candidates[:top_k]:
            results.append({
                "chunk_id": c["chunk_id"],
                "citation_label": c["citation_label"],
                "bm25_score": c["bm25_score"],
                "semantic_score": c["semantic_score"],
                "clause_text": c["clause_text"],
                "heading": c["heading"],
                "source_file": c["source_file"],
                "page_number": c["page_number"]
            })

        # Emit debug log with full retrieval detail
        log_regulation_retrieval(
            call_id=call_id,
            candidate_id=category,
            category=category,
            bm25_query=bm25_query_text,
            semantic_query=semantic_query_text,
            bm25_hits=bm25_hits,
            semantic_hits=semantic_hits,
            final_chunks=results,
        )

        return results
