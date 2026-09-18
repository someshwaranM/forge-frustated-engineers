"""
Vigil — Phase 6: Candidate Builder & Orchestrator (backend/compliance/candidate_builder.py)

Orchestrates the Phase 6 Detection Engine pipeline:
1. Deterministic rules scan for guaranteed-return and hedged return claims
2. Product identification against MySQL catalog (fuzzy/conversational alias matching)
3. Dual-rule suitability check (Rule 3A profile mismatch + Rule 3B experience gap)
4. Coarse keyword-presence disclosure check for Medium/High risk products
5. Hybrid regulation retrieval (BM25 + semantic) attaching top 1-3 citations per candidate
6. Outputs staged candidate JSON files to backend/compliance/candidates/<call_id>.json

Produces CANDIDATES only — does NOT call AWS Bedrock or Gemini for reasoning (that is Phase 7).
"""

import os
import sys
import json
import logging
import argparse
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.indexing.create_index import get_es_client
from backend.compliance.deterministic_rules import scan_rm_segments, RuleViolationCandidate
from backend.compliance.product_identifier import identify_product_from_call, IdentifiedProduct
from backend.compliance.suitability_checker import check_suitability, SuitabilityCandidate
from backend.compliance.disclosure_checker import check_disclosure, DisclosureCandidate
from backend.compliance.regulation_retriever import RegulationRetriever

# Phase 13: Elastic APM instrumentation (native elastic-apm, NOT OpenTelemetry)
try:
    from backend.observability.apm import apm_span, report_error
    from backend.observability.logging_config import log_pipeline_event
    _APM_AVAILABLE = True
except ImportError:
    _APM_AVAILABLE = False
    from contextlib import contextmanager
    @contextmanager
    def apm_span(*a, **kw): yield
    def report_error(*a, **kw): pass
    def log_pipeline_event(*a, **kw): pass

logger = logging.getLogger("vigil.compliance.candidate_builder")

# Debug logger (enabled via VIGIL_DEBUG_PIPELINE=true)
try:
    from backend.observability.debug_logger import (
        log_detection_start, log_candidate_built, log_detection_summary,
        log_deterministic_rule_fired,
    )
    _DBG = True
except ImportError:
    _DBG = False
    def log_detection_start(*a, **kw): pass
    def log_candidate_built(*a, **kw): pass
    def log_detection_summary(*a, **kw): pass
    def log_deterministic_rule_fired(*a, **kw): pass

CANDIDATES_DIR = PROJECT_ROOT / "backend" / "compliance" / "candidates"
CALLS_INDEX = "calls"


def build_candidates_for_call(
    call_doc: Dict[str, Any],
    retriever: Optional[RegulationRetriever] = None,
    output_dir: Path = CANDIDATES_DIR
) -> Dict[str, Any]:
    """
    Runs the full Phase 6 detection pipeline against a single transcribed call document.
    Phase 13: Instrumented with Elastic APM spans.

    Returns:
        The complete candidate report dict written to <call_id>.json.
    """
    if retriever is None:
        retriever = RegulationRetriever()

    call_id = call_doc.get("call_id", "")
    segments = call_doc.get("transcript_segments", [])
    _detect_start_ms = time.perf_counter() * 1000
    log_pipeline_event(logger, "compliance.detection.started", call_id=call_id,
                       stage="detection", status="started")
    log_detection_start(call_id, len(segments))

    candidates_list: List[Dict[str, Any]] = []
    candidate_counter = 1

    # -------------------------------------------------------------------------
    # STEP 1: Deterministic Rules Scan (RM segments)
    # -------------------------------------------------------------------------
    rule_hits: List[RuleViolationCandidate] = scan_rm_segments(segments)
    for rh in rule_hits:
        cand_id = f"CAND_{call_id}_{candidate_counter:02d}"
        candidate_counter += 1

        # Hybrid regulation retrieval for this category
        citations = retriever.retrieve_citations_for_category(rh.category, top_k=3, call_id=call_id)

        candidates_list.append({
            "candidate_id": cand_id,
            "category": rh.category,
            "confidence_signal": rh.confidence_signal,
            "detection_type": rh.detection_type,
            "summary": rh.summary,
            "evidence": {
                "matched_phrase": rh.matched_phrase,
                "rm_segments": [{
                    "segment_id": rh.segment_id,
                    "start_time": rh.start_time,
                    "end_time": rh.end_time,
                    "text_english": rh.text_english
                }],
                "customer_segments": []
            },
            "regulation_citations": citations
        })
        log_candidate_built(call_id, candidates_list[-1])

    # -------------------------------------------------------------------------
    # STEP 2: Product Identification
    # -------------------------------------------------------------------------
    product: Optional[IdentifiedProduct] = identify_product_from_call(call_doc)

    product_status = "IDENTIFIED" if product else "PRODUCT_NOT_IDENTIFIED"
    product_meta = None

    if product:
        product_meta = {
            "product_id": product.product_id,
            "product_name": product.product_name,
            "risk_class": product.risk_class,
            "suitable_risk_profiles": product.suitable_risk_profiles,
            "matched_term": product.matched_term,
            "confirmed_in_transactions": product.confirmed_in_transactions
        }

        # ---------------------------------------------------------------------
        # STEP 3: Suitability Check (Dual Rules: 3A Mismatch + 3B Inexperience)
        # ---------------------------------------------------------------------
        suit_hits: List[SuitabilityCandidate] = check_suitability(call_doc, product)
        for sh in suit_hits:
            cand_id = f"CAND_{call_id}_{candidate_counter:02d}"
            candidate_counter += 1

            citations = retriever.retrieve_citations_for_category(sh.category, top_k=3, call_id=call_id)

            candidates_list.append({
                "candidate_id": cand_id,
                "category": sh.category,
                "confidence_signal": sh.confidence_signal,
                "detection_type": sh.detection_type,
                "rule_fired": sh.rule_fired,
                "summary": sh.summary,
                "details": {
                    "customer_id": sh.customer_id,
                    "customer_name": sh.customer_name,
                    "customer_risk_profile": sh.customer_risk_profile,
                    "customer_investment_experience": sh.customer_investment_experience,
                    "product_id": sh.product_id,
                    "product_name": sh.product_name,
                    "product_risk_class": sh.product_risk_class,
                    "suitable_risk_profiles": sh.suitable_risk_profiles
                },
                "evidence": {
                    "rm_segments": sh.rm_evidence_segments,
                    "customer_segments": sh.customer_evidence_segments
                },
                "regulation_citations": citations
            })
            log_candidate_built(call_id, candidates_list[-1])

        # ---------------------------------------------------------------------
        # STEP 4: Disclosure Check (Medium / High Risk Products)
        # ---------------------------------------------------------------------
        disc_hits: List[DisclosureCandidate] = check_disclosure(call_doc, product)
        for dh in disc_hits:
            cand_id = f"CAND_{call_id}_{candidate_counter:02d}"
            candidate_counter += 1

            citations = retriever.retrieve_citations_for_category(dh.category, top_k=3, call_id=call_id)

            candidates_list.append({
                "candidate_id": cand_id,
                "category": dh.category,
                "confidence_signal": dh.confidence_signal,
                "detection_type": dh.detection_type,
                "summary": dh.summary,
                "details": {
                    "product_id": dh.product_id,
                    "product_name": dh.product_name,
                    "product_risk_class": dh.product_risk_class,
                    "mandatory_requirements": dh.mandatory_requirements,
                    "missing_elements": dh.missing_elements,
                    "matched_generic_keywords": dh.matched_generic_keywords
                },
                "evidence": {
                    "rm_segments": dh.rm_evidence_segments,
                    "rm_segments_evaluated": dh.rm_segments_evaluated,
                    "customer_segments": []
                },
                "regulation_citations": citations
            })
            log_candidate_built(call_id, candidates_list[-1])

    else:
        logger.info(
            f"Call {call_id}: No product identified from transcript. "
            f"Explicitly logging PRODUCT_NOT_IDENTIFIED and skipping suitability/disclosure checks."
        )

    # -------------------------------------------------------------------------
    # STEP 6: Assemble and Write Candidate JSON
    # -------------------------------------------------------------------------
    output_dir.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(timezone.utc).isoformat()
    report = {
        "call_id": call_id,
        "customer_id": call_doc.get("customer_id", ""),
        "rm_id": call_doc.get("rm_id", ""),
        "date_time": call_doc.get("date_time", ""),
        "product_identification_status": product_status,
        "product": product_meta,
        "candidate_count": len(candidates_list),
        "candidates": candidates_list,
        "detection_completed_at": now_iso,
        "generated_at": now_iso
    }

    # Write authoritative JSON file
    out_file = output_dir / f"{call_id}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Also write alias without 'CALL_' prefix if applicable (e.g. RM001_CUST001_20260310_1030.json)
    if call_id.startswith("CALL_"):
        alias_stem = call_id[5:]
        alias_file = output_dir / f"{alias_stem}.json"
        with open(alias_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(
        f"Wrote candidates for {call_id} to {out_file.name} "
        f"({len(candidates_list)} candidates found)."
    )

    try:
        es_client = get_es_client()
        es_client.update(
            index=CALLS_INDEX,
            id=call_id,
            doc={"detection_completed_at": now_iso},
            doc_as_upsert=True,
        )
    except Exception as exc:
        logger.debug(f"Could not update detection_completed_at on ES call {call_id}: {exc}")

    _detect_ms = (time.perf_counter() * 1000) - _detect_start_ms
    log_pipeline_event(logger, "compliance.detection.completed", call_id=call_id,
                       stage="detection", status="success", duration_ms=_detect_ms,
                       extra_fields={"candidate_count": len(candidates_list)})
    log_detection_summary(call_id, len(candidates_list))
    return report


def run_pipeline_on_all_calls(output_dir: Path = CANDIDATES_DIR) -> List[Dict[str, Any]]:
    """
    Runs the detection pipeline on all calls with processing_status = 'TRANSCRIBED'
    in the Elasticsearch 'calls' index.
    """
    es = get_es_client()
    retriever = RegulationRetriever(es)

    resp = es.search(
        index=CALLS_INDEX,
        body={
            "query": {
                "term": {"processing_status": "TRANSCRIBED"}
            },
            "size": 100
        }
    )

    hits = resp.get("hits", {}).get("hits", [])
    logger.info(f"Found {len(hits)} transcribed call(s) in '{CALLS_INDEX}' index.")

    results = []
    for hit in hits:
        call_doc = hit["_source"]
        call_id = call_doc.get("call_id", hit["_id"])
        print(f"\nProcessing call: {call_id}...")
        report = build_candidates_for_call(call_doc, retriever=retriever, output_dir=output_dir)
        results.append(report)
        print(f"  --> Product:    {report.get('product_identification_status')}")
        print(f"  --> Candidates: {report.get('candidate_count')}")
        for c in report.get("candidates", []):
            print(f"      - [{c['confidence_signal']}] {c['category']}: {c['summary'][:80]}...")

    return results


def main():
    parser = argparse.ArgumentParser(description="Vigil Phase 6 Detection Engine")
    parser.add_argument("--all", action="store_true", help="Process all transcribed calls in ES")
    parser.add_argument("--call_id", type=str, help="Process a specific call_id")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if args.call_id:
        es = get_es_client()
        # Try exact ID or term query
        doc = None
        try:
            doc = es.get(index=CALLS_INDEX, id=args.call_id)["_source"]
        except Exception:
            # Query by call_id field
            resp = es.search(index=CALLS_INDEX, body={"query": {"term": {"call_id": args.call_id}}})
            hits = resp.get("hits", {}).get("hits", [])
            if hits:
                doc = hits[0]["_source"]

        if not doc:
            print(f"Call ID '{args.call_id}' not found in '{CALLS_INDEX}' index.")
            sys.exit(1)

        report = build_candidates_for_call(doc)
        print(json.dumps(report, indent=2))
    else:
        run_pipeline_on_all_calls()


if __name__ == "__main__":
    main()
