"""
Vigil — Phase 7: Investigator Agent.

Forensic compliance investigation agent that evaluates pre-screening candidate violations
flagged by Phase 6. Implements:
- Chronological processing by call date_time ascending
- Full context gathering (MySQL Customer/Product profiles + ES RM prior violation history + candidate evidence)
- Hard pre-check: immediate dismissal of candidates with 0 regulation citations
- Dual-provider reasoning: AWS Bedrock primary with Google Gemini fallback
- Pydantic schema validation against ComplianceFinding
- Hard guardrail checks: citation validation (must match retrieved chunk_ids) & HIGH severity completeness
- Full audit trail logging in backend/agents/investigations/<call_id>.json
- Atomic dual-write: Elasticsearch 'compliance_findings' index + MySQL 'compliance_case' table
- Synchronized update of Elasticsearch 'calls' index has_violation and finding_ids
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import BotoCoreError, ClientError
import dotenv
import pymysql

# Add repository root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agents.gemini_fallback import call_gemini_investigator
from backend.indexing.create_index import get_es_client
from data.schemas.compliance_finding_schema import ComplianceFinding

# Phase 13: Elastic APM spans (no OpenTelemetry)
try:
    from backend.observability.apm import apm_span, report_error
except ImportError:
    from contextlib import contextmanager
    @contextmanager
    def apm_span(*a, **kw): yield
    def report_error(*a, **kw): pass

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Debug logger (enabled via VIGIL_DEBUG_PIPELINE=true)
try:
    from backend.observability.debug_logger import (
        log_investigator_start, log_investigator_context,
        log_investigator_prompt, log_investigator_model_raw,
        log_investigator_parsed, log_investigator_guardrail,
        log_investigator_outcome, log_investigator_dual_write,
        log_investigator_call_summary,
    )
except ImportError:
    def log_investigator_start(*a, **kw): pass
    def log_investigator_context(*a, **kw): pass
    def log_investigator_prompt(*a, **kw): pass
    def log_investigator_model_raw(*a, **kw): pass
    def log_investigator_parsed(*a, **kw): pass
    def log_investigator_guardrail(*a, **kw): pass
    def log_investigator_outcome(*a, **kw): pass
    def log_investigator_dual_write(*a, **kw): pass
    def log_investigator_call_summary(*a, **kw): pass

ENV_PATH = PROJECT_ROOT / "backend" / ".env"
dotenv.load_dotenv(ENV_PATH)

PROMPT_TEMPLATE_PATH = PROJECT_ROOT / "backend" / "agents" / "prompts" / "investigator_prompt.md"
CANDIDATES_DIR = PROJECT_ROOT / "backend" / "compliance" / "candidates"
INVESTIGATIONS_DIR = PROJECT_ROOT / "backend" / "agents" / "investigations"


def get_db_connection():
    """Establish connection to MySQL database."""
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "vigil"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


# ---------------------------------------------------------------------------
# STEP 1: Context Gathering Helpers
# ---------------------------------------------------------------------------

def fetch_customer_profile(customer_id: str) -> Dict[str, Any]:
    """Retrieve customer risk profile and investment experience from MySQL."""
    if not customer_id or customer_id == "UNKNOWN_CUST":
        return {"risk_profile": "Unknown", "investment_experience": "Unknown"}

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT risk_profile, investment_experience FROM customer WHERE customer_id = %s",
                (customer_id,),
            )
            row = cur.fetchone()
            if row:
                return {
                    "risk_profile": row.get("risk_profile") or "Unknown",
                    "investment_experience": row.get("investment_experience") or "Unknown",
                }
    finally:
        conn.close()

    return {"risk_profile": "Unknown", "investment_experience": "Unknown"}


def fetch_product_profile(product_id: Optional[str]) -> Dict[str, Any]:
    """Retrieve product risk class and disclosure requirements from MySQL."""
    if not product_id or product_id == "N/A":
        return {
            "product_name": "N/A",
            "risk_class": "N/A",
            "suitable_risk_profiles": "N/A",
            "disclosure_requirements": "N/A",
        }

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT product_name, risk_class, suitable_risk_profiles, disclosure_requirements "
                "FROM product WHERE product_id = %s",
                (product_id,),
            )
            row = cur.fetchone()
            if row:
                return {
                    "product_name": row.get("product_name") or "N/A",
                    "risk_class": row.get("risk_class") or "N/A",
                    "suitable_risk_profiles": row.get("suitable_risk_profiles") or "N/A",
                    "disclosure_requirements": row.get("disclosure_requirements") or "N/A",
                }
    finally:
        conn.close()

    return {
        "product_name": "N/A",
        "risk_class": "N/A",
        "suitable_risk_profiles": "N/A",
        "disclosure_requirements": "N/A",
    }


def query_rm_history(es, rm_id: str, current_call_date_time: str) -> Tuple[int, List[str]]:
    """
    Query compliance_findings index for prior CONFIRMED findings where rm_id matches,
    from calls with an earlier date_time than current_call_date_time.
    Returns (count, list_of_categories).
    """
    if not rm_id or rm_id == "UNKNOWN_RM":
        return 0, []

    # 1. Find earlier call_ids for this RM from calls index
    try:
        calls_query = {
            "bool": {
                "filter": [
                    {"term": {"rm_id": rm_id}},
                    {"range": {"date_time": {"lt": current_call_date_time}}},
                ]
            }
        }
        res_calls = es.search(index="calls", query=calls_query, size=100, source=["call_id"])
        earlier_call_ids = [hit["_source"]["call_id"] for hit in res_calls["hits"]["hits"] if "call_id" in hit["_source"]]

        if not earlier_call_ids:
            return 0, []

        # 2. Query compliance_findings for findings belonging to these earlier calls
        findings_query = {
            "bool": {
                "filter": [
                    {"term": {"rm_id": rm_id}},
                    {"terms": {"call_id": earlier_call_ids}},
                ]
            }
        }
        findings_aggs = {
            "categories": {
                "terms": {"field": "category", "size": 20}
            }
        }
        res_findings = es.search(
            index="compliance_findings",
            query=findings_query,
            aggregations=findings_aggs,
            size=0,
        )

        total_count = res_findings["hits"]["total"]["value"]
        buckets = res_findings.get("aggregations", {}).get("categories", {}).get("buckets", [])
        categories = [f"{b['key']} ({b['doc_count']})" for b in buckets]
        return total_count, categories

    except Exception as exc:
        logger.warning(f"Error querying RM history for {rm_id}: {exc}")
        return 0, []


def format_dialogue_evidence(evidence: Dict[str, Any]) -> str:
    """Format dialogue evidence into sequential chronological transcript excerpts."""
    segments = []
    for rm_seg in evidence.get("rm_segments", []):
        start = float(rm_seg.get("start_time", 0.0))
        end = float(rm_seg.get("end_time", 0.0))
        text = rm_seg.get("text_english", "")
        segments.append((start, end, "RM", text))

    for cust_seg in evidence.get("customer_segments", []):
        start = float(cust_seg.get("start_time", 0.0))
        end = float(cust_seg.get("end_time", 0.0))
        text = cust_seg.get("text_english", "")
        segments.append((start, end, "Customer", text))

    segments.sort(key=lambda s: s[0])

    if not segments:
        return "No specific verbatim segments isolated in candidate flag."

    lines = []
    for start, end, speaker, text in segments:
        mins_s, secs_s = int(start // 60), int(start % 60)
        mins_e, secs_e = int(end // 60), int(end % 60)
        lines.append(f"[{mins_s:02d}:{secs_s:02d} - {mins_e:02d}:{secs_e:02d}] {speaker}: {text}")

    return "\n".join(lines)


def format_citations_context(citations: List[Dict[str, Any]]) -> str:
    """Format regulation citations for prompt injection."""
    if not citations:
        return "None attached."

    blocks = []
    for idx, cit in enumerate(citations, 1):
        chunk_id = cit.get("chunk_id", "UNKNOWN")
        citation_label = cit.get("citation_label", "N/A")
        clause_text = cit.get("clause_text", "")
        blocks.append(
            f"--- Citation #{idx} ---\n"
            f"chunk_id: {chunk_id}\n"
            f"citation_label: {citation_label}\n"
            f"clause_text:\n{clause_text.strip()}\n"
        )
    return "\n".join(blocks)


# ---------------------------------------------------------------------------
# STEP 3: Model Execution (Bedrock Primary with Gemini Fallback)
# ---------------------------------------------------------------------------

def call_bedrock_investigator(prompt: str) -> Dict[str, Any]:
    """
    Primary LLM caller using AWS Bedrock runtime.
    Raises exception on missing credentials, auth failure, or invocation error.
    """
    aws_access_key = (os.getenv("AWS_ACCESS_KEY_ID") or "").strip().strip("'\"")
    aws_secret_key = (os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip().strip("'\"")
    aws_region = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-west-2").strip().strip("'\"")
    aws_session_token = (os.getenv("AWS_SESSION_TOKEN") or "").strip().strip("'\"")
    model_id = (os.getenv("AWS_BEDROCK_MODEL_ID") or "").strip().strip("'\"")

    # Treat default placeholder values as unconfigured
    if not aws_access_key or "<REPLACE_ME>" in (aws_access_key, aws_secret_key, aws_region, model_id):
        raise ValueError("AWS Bedrock credentials/model_id unconfigured or placeholder in .env")

    client_kwargs = {
        "service_name": "bedrock-runtime",
        "region_name": aws_region,
        "aws_access_key_id": aws_access_key,
        "aws_secret_access_key": aws_secret_key,
    }
    if aws_session_token:
        client_kwargs["aws_session_token"] = aws_session_token
    client = boto3.client(**client_kwargs)

    # Standard Claude 3 Bedrock body
    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": prompt}],
    }

    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(payload),
        contentType="application/json",
        accept="application/json",
    )
    response_body = json.loads(response["body"].read().decode("utf-8"))
    content_text = response_body.get("content", [{}])[0].get("text", "")

    # Store raw response for debug logging before stripping
    _bedrock_raw_response[0] = content_text

    # Strip code block fences if present
    content_text = content_text.strip()
    if content_text.startswith("```"):
        import re
        content_text = re.sub(r"^```[a-zA-Z]*\s*", "", content_text)
        content_text = re.sub(r"\s*```$", "", content_text).strip()

    return json.loads(content_text)


# Thread-local storage for last raw response text (for debug logging)
_bedrock_raw_response: List[str] = [""]


def execute_forensic_evaluation(prompt: str) -> Tuple[Dict[str, Any], str]:
    """
    Executes forensic evaluation: tries Bedrock first; on failure, falls back to Gemini.
    Returns (model_output_dict, provider_used).
    """
    _bedrock_raw_response[0] = ""  # reset
    try:
        logger.info("Attempting primary LLM evaluation via AWS Bedrock...")
        with apm_span("investigator.bedrock_call", span_type="external.ai", span_subtype="bedrock"):
            output = call_bedrock_investigator(prompt)
        return output, "bedrock"
    except (BotoCoreError, ClientError, ValueError, Exception) as exc:
        logger.warning(f"Bedrock primary evaluation unavailable/failed ({exc}). Retrying once via Gemini fallback...")
        with apm_span("investigator.gemini_call", span_type="external.ai", span_subtype="gemini"):
            output = call_gemini_investigator(prompt)
        return output, "gemini"


# ---------------------------------------------------------------------------
# Investigation Engine & Guardrails
# ---------------------------------------------------------------------------

class InvestigatorAgent:
    """Investigator Agent orchestrating context gathering, AI reasoning, guardrails, and dual-write."""

    def __init__(self):
        self.es = get_es_client()
        INVESTIGATIONS_DIR.mkdir(parents=True, exist_ok=True)
        with open(PROMPT_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            self.prompt_template = f.read()

    def build_prompt(
        self,
        call_id: str,
        customer_id: str,
        rm_id: str,
        customer_ctx: Dict[str, Any],
        product_ctx: Dict[str, Any],
        rm_history_ctx: Tuple[int, List[str]],
        candidate: Dict[str, Any],
    ) -> str:
        """Substitute all gathered context into prompt template."""
        dialogue_evidence = format_dialogue_evidence(candidate.get("evidence", {}))
        regulation_citations = format_citations_context(candidate.get("regulation_citations", []))

        finding_id_suggestion = f"FND-2026-{uuid.uuid4().hex[:6].upper()}"
        candidate_details = candidate.get("details", {})
        product_id = candidate_details.get("product_id") or product_ctx.get("product_id", "N/A")

        prompt = self.prompt_template
        replacements = {
            "{customer_id}": customer_id,
            "{customer_risk_profile}": customer_ctx.get("risk_profile", "Unknown"),
            "{customer_investment_experience}": customer_ctx.get("investment_experience", "Unknown"),
            "{product_id}": product_id,
            "{product_name}": product_ctx.get("product_name", "N/A"),
            "{product_risk_class}": product_ctx.get("risk_class", "N/A"),
            "{product_suitable_risk_profiles}": str(product_ctx.get("suitable_risk_profiles", "N/A")),
            "{product_disclosure_requirements}": product_ctx.get("disclosure_requirements", "N/A"),
            "{rm_id}": rm_id,
            "{prior_findings_count}": str(rm_history_ctx[0]),
            "{prior_findings_categories}": ", ".join(rm_history_ctx[1]) if rm_history_ctx[1] else "None (clean record)",
            "{candidate_id}": candidate.get("candidate_id", ""),
            "{candidate_category}": candidate.get("category", ""),
            "{candidate_confidence_signal}": candidate.get("confidence_signal", ""),
            "{candidate_detection_type}": candidate.get("detection_type", ""),
            "{candidate_rule_fired}": candidate.get("rule_fired", ""),
            "{candidate_summary}": candidate.get("summary", ""),
            "{dialogue_evidence}": dialogue_evidence,
            "{regulation_citations}": regulation_citations,
            "{{finding_id}}": finding_id_suggestion,
            "{{call_id}}": call_id,
            "{{category}}": candidate.get("category", ""),
            "{{customer_risk_profile}}": customer_ctx.get("risk_profile", "Unknown"),
            "{{product_risk_class}}": product_ctx.get("risk_class", "N/A"),
        }

        for k, v in replacements.items():
            prompt = prompt.replace(k, str(v))

        return prompt

    def investigate_candidate(
        self,
        call_id: str,
        call_date_time: str,
        customer_id: str,
        rm_id: str,
        candidate: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Investigate a single candidate through all Steps 1 to 5.
        Returns investigation log item dictionary.
        """
        candidate_id = candidate.get("candidate_id", "")
        attached_citations = candidate.get("regulation_citations", [])

        # STEP 2: Hard pre-check — 0 citations attached
        if not attached_citations:
            logger.info(f"Candidate {candidate_id}: DISMISSED_NO_CITATION (0 regulation citations attached)")
            return {
                "candidate_id": candidate_id,
                "outcome": "DISMISSED_NO_CITATION",
                "finding": None,
                "provider_used": None,
                "reasoning": "Pre-check failed: Candidate has zero attached regulation citations from Phase 6.",
            }

        # STEP 1: Gather Context
        customer_ctx = fetch_customer_profile(customer_id)
        product_id = candidate.get("details", {}).get("product_id")
        product_ctx = fetch_product_profile(product_id)
        rm_history = query_rm_history(self.es, rm_id, call_date_time)

        prompt = self.build_prompt(
            call_id=call_id,
            customer_id=customer_id,
            rm_id=rm_id,
            customer_ctx=customer_ctx,
            product_ctx=product_ctx,
            rm_history_ctx=rm_history,
            candidate=candidate,
        )

        # Log context and full prompt
        log_investigator_start(call_id, candidate_id, candidate.get("category", ""))
        log_investigator_context(call_id, candidate_id, customer_ctx, product_ctx, rm_history)
        log_investigator_prompt(call_id, candidate_id, prompt)

        # STEP 3: Model Execution with Fallback
        provider_used = None
        try:
            with apm_span("investigator.candidate_eval", span_type="app.internal", labels={"candidate_id": candidate_id, "call_id": call_id}):
                raw_output, provider_used = execute_forensic_evaluation(prompt)
            # Log raw response text and parsed output
            log_investigator_model_raw(call_id, candidate_id, provider_used, _bedrock_raw_response[0] or json.dumps(raw_output, indent=2))
            log_investigator_parsed(call_id, candidate_id, provider_used, raw_output)
        except Exception as exc:
            logger.error(f"Candidate {candidate_id}: Evaluation execution failure: {exc}")
            return {
                "candidate_id": candidate_id,
                "outcome": "DISMISSED_VALIDATION_FAILED",
                "finding": None,
                "provider_used": provider_used,
                "reasoning": f"LLM execution failed on both primary and fallback: {exc}",
            }

        # Check for explicit dismissal verdict
        verdict = raw_output.get("verdict", "").upper()
        if verdict == "DISMISSED" or raw_output.get("is_violation") is False:
            reasoning = raw_output.get("reasoning", "Model determined dialogue does not constitute a genuine regulatory violation.")
            logger.info(f"Candidate {candidate_id}: DISMISSED_NOT_GENUINE ({reasoning})")
            return {
                "candidate_id": candidate_id,
                "outcome": "DISMISSED_NOT_GENUINE",
                "finding": None,
                "provider_used": provider_used,
                "reasoning": reasoning,
            }

        # STEP 4: Schema Validation against ComplianceFinding
        # Normalize fields for Pydantic instantiation
        finding_data = dict(raw_output)
        if not finding_data.get("finding_id"):
            finding_data["finding_id"] = f"FND-2026-{uuid.uuid4().hex[:6].upper()}"
        finding_data["call_id"] = call_id
        finding_data["rm_id"] = rm_id
        finding_data["customer_id"] = customer_id
        finding_data["provider_used"] = provider_used
        finding_data["status"] = "OPEN"
        finding_data["customer_risk_profile"] = customer_ctx.get("risk_profile", "Unknown")
        finding_data["product_risk_class"] = product_ctx.get("risk_class", "N/A")

        # Fallback timestamps if omitted by model
        rm_segs = candidate.get("evidence", {}).get("rm_segments", [])
        if "timestamp_start" not in finding_data or finding_data["timestamp_start"] is None:
            finding_data["timestamp_start"] = rm_segs[0].get("start_time", 0.0) if rm_segs else 0.0
        if "timestamp_end" not in finding_data or finding_data["timestamp_end"] is None:
            finding_data["timestamp_end"] = rm_segs[-1].get("end_time", 0.0) if rm_segs else 0.0

        if not finding_data.get("transcript_evidence"):
            finding_data["transcript_evidence"] = " ".join(s.get("text_english", "") for s in rm_segs) or candidate.get("summary", "Verbatim evidence")

        if not finding_data.get("recommended_action"):
            finding_data["recommended_action"] = "Conduct compliance review and issue corrective guidance."

        if not finding_data.get("category"):
            finding_data["category"] = candidate.get("category", "SUITABILITY_MISMATCH")

        # Set scores from candidate citation if available
        matched_reg_id = finding_data.get("regulation_id")
        for cit in attached_citations:
            if cit.get("chunk_id") == matched_reg_id:
                finding_data["bm25_score"] = cit.get("bm25_score")
                finding_data["semantic_score"] = cit.get("semantic_score")
                finding_data["regulation_citation_label"] = cit.get("citation_label", "")
                break

        try:
            finding = ComplianceFinding(**finding_data)
        except Exception as exc:
            logger.error(f"Candidate {candidate_id}: Pydantic validation failed: {exc}")
            return {
                "candidate_id": candidate_id,
                "outcome": "DISMISSED_VALIDATION_FAILED",
                "finding": None,
                "provider_used": provider_used,
                "reasoning": f"Pydantic schema validation error: {exc}",
            }

        # STEP 5: Hard Guardrail Checks
        valid_chunk_ids = {cit["chunk_id"] for cit in attached_citations if "chunk_id" in cit}
        if finding.regulation_id not in valid_chunk_ids:
            logger.warning(
                f"Candidate {candidate_id}: DISMISSED_CITATION_MISMATCH. Selected '{finding.regulation_id}' not in {valid_chunk_ids}"
            )
            log_investigator_guardrail(call_id, candidate_id, "CITATION_MATCH", "FAIL",
                f"Model chose '{finding.regulation_id}' not in retrieved set {valid_chunk_ids}")
            log_investigator_outcome(call_id, candidate_id, "DISMISSED_CITATION_MISMATCH", None, provider_used,
                f"Model selected regulation_id '{finding.regulation_id}' which was not in candidate retrieved citations.")
            return {
                "candidate_id": candidate_id,
                "outcome": "DISMISSED_CITATION_MISMATCH",
                "finding": None,
                "provider_used": provider_used,
                "reasoning": f"Model selected regulation_id '{finding.regulation_id}' which was not in candidate retrieved citations.",
            }

        if finding.severity == "HIGH":
            missing_high_fields = []
            if finding.timestamp_start is None or finding.timestamp_end is None or (finding.timestamp_start == 0.0 and finding.timestamp_end == 0.0):
                missing_high_fields.append("timestamp_start/end")
            if not finding.regulation_id:
                missing_high_fields.append("regulation_id")

            if missing_high_fields:
                logger.warning(f"Candidate {candidate_id}: DISMISSED_INCOMPLETE_HIGH_FINDING. Missing {missing_high_fields}")
                log_investigator_guardrail(call_id, candidate_id, "HIGH_SEVERITY_COMPLETENESS", "FAIL",
                    f"Missing mandatory fields: {missing_high_fields}")
                log_investigator_outcome(call_id, candidate_id, "DISMISSED_INCOMPLETE_HIGH_FINDING", None, provider_used,
                    f"HIGH severity finding missing: {', '.join(missing_high_fields)}")
                return {
                    "candidate_id": candidate_id,
                    "outcome": "DISMISSED_INCOMPLETE_HIGH_FINDING",
                    "finding": None,
                    "provider_used": provider_used,
                    "reasoning": f"HIGH severity finding is missing mandatory fields: {', '.join(missing_high_fields)}",
                }

        log_investigator_guardrail(call_id, candidate_id, "CITATION_MATCH", "PASS",
            f"regulation_id='{finding.regulation_id}' is in retrieved set")
        if finding.severity == "HIGH":
            log_investigator_guardrail(call_id, candidate_id, "HIGH_SEVERITY_COMPLETENESS", "PASS", "All mandatory fields present")

        # Candidate successfully confirmed
        logger.info(f"Candidate {candidate_id}: CONFIRMED as {finding.severity} ({finding.category}) via {provider_used}")
        log_investigator_outcome(call_id, candidate_id, "CONFIRMED", finding.finding_id, provider_used, finding.reasoning)
        return {
            "candidate_id": candidate_id,
            "outcome": "CONFIRMED",
            "finding": finding,
            "provider_used": provider_used,
            "reasoning": finding.reasoning,
        }

    def persist_confirmed_finding(self, finding: ComplianceFinding) -> str:
        """
        STEP 7: Execute dual-write for a confirmed finding:
        a) Fetch winning regulation chunk for denormalization
        b) Index finding to compliance_findings in ES
        c) Insert case row into MySQL compliance_case
        d) Update call document in calls index
        """
        # 7a: Denormalize regulation details
        try:
            reg_doc = self.es.get(index="regulations", id=finding.regulation_id)
            source = reg_doc.get("_source", {})
            finding.regulation_citation_label = source.get("citation_label", finding.regulation_citation_label)
            finding.regulation_source_url = source.get("source_url")
            finding.regulation_clause_text = source.get("clause_text") or source.get("chunk_text")
        except Exception as exc:
            logger.warning(f"Could not fetch regulation chunk {finding.regulation_id}: {exc}")

        # 7b: Index into ES compliance_findings
        es_doc = finding.to_es_doc()
        self.es.index(index="compliance_findings", id=finding.finding_id, document=es_doc, refresh="wait_for")
        logger.info(f"Indexed finding {finding.finding_id} into ES compliance_findings")

        # 7c: Dual-write to MySQL compliance_case
        case_id = f"CASE-{finding.finding_id.replace('FND-', '')}"
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO compliance_case (
                        case_id, finding_id, call_id, rm_id, customer_id,
                        category, severity, status, escalated, assigned_to,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        NOW(), NOW()
                    )
                    ON DUPLICATE KEY UPDATE
                        severity = VALUES(severity),
                        status = VALUES(status),
                        updated_at = NOW()
                    """,
                    (
                        case_id,
                        finding.finding_id,
                        finding.call_id,
                        finding.rm_id,
                        finding.customer_id,
                        finding.category,
                        finding.severity,
                        "OPEN",
                        finding.severity in ("HIGH", "CRITICAL"),
                        None,
                    ),
                )
            logger.info(f"Created/updated MySQL compliance_case {case_id} for finding {finding.finding_id}")
        finally:
            conn.close()

        # 7d: Update call document in ES calls index
        try:
            call_res = self.es.get(index="calls", id=finding.call_id)
            existing_findings = call_res.get("_source", {}).get("finding_ids", []) or []
            if finding.finding_id not in existing_findings:
                existing_findings.append(finding.finding_id)

            self.es.update(
                index="calls",
                id=finding.call_id,
                doc={
                    "has_violation": True,
                    "finding_ids": existing_findings,
                },
                refresh="wait_for",
            )
            logger.info(f"Updated call {finding.call_id}: has_violation=True, finding_ids={existing_findings}")
        except Exception as exc:
            logger.error(f"Failed to update call {finding.call_id} in calls index: {exc}")

        return case_id

    def process_call(self, candidate_file_path: Path) -> Dict[str, Any]:
        """
        Process a single candidate file, evaluating all candidates and writing audit log.
        """
        with open(candidate_file_path, "r", encoding="utf-8") as f:
            call_data = json.load(f)

        call_id = call_data["call_id"]
        call_date_time = call_data.get("date_time", datetime.now(timezone.utc).isoformat())
        customer_id = call_data.get("customer_id", "UNKNOWN_CUST")
        rm_id = call_data.get("rm_id", "UNKNOWN_RM")
        candidates = call_data.get("candidates", [])

        logger.info(f"\n{'='*60}\nProcessing Call {call_id} ({call_date_time}) | Candidates: {len(candidates)}\n{'='*60}")

        audit_results = []
        confirmed_findings = []

        for cand in candidates:
            res = self.investigate_candidate(
                call_id=call_id,
                call_date_time=call_date_time,
                customer_id=customer_id,
                rm_id=rm_id,
                candidate=cand,
            )

            finding_obj = res["finding"]
            now_iso = datetime.now(timezone.utc).isoformat()
            res["investigation_completed_at"] = now_iso
            if res["outcome"] == "CONFIRMED" and finding_obj:
                case_id = self.persist_confirmed_finding(finding_obj)
                confirmed_findings.append(finding_obj)
                res["finding"] = finding_obj.to_es_doc()
                res["case_id"] = case_id
            else:
                res["finding"] = None

            audit_results.append(res)
            import time
            time.sleep(1.0)

        # STEP 6: Write audit log to backend/agents/investigations/<call_id>.json
        audit_file = INVESTIGATIONS_DIR / f"{call_id}.json"
        audit_now = datetime.now(timezone.utc).isoformat()
        audit_payload = {
            "call_id": call_id,
            "date_time": call_date_time,
            "rm_id": rm_id,
            "customer_id": customer_id,
            "total_candidates": len(candidates),
            "confirmed_count": len(confirmed_findings),
            "dismissed_count": len(candidates) - len(confirmed_findings),
            "investigations": audit_results,
            "investigation_completed_at": audit_now,
            "generated_at": audit_now,
        }

        with open(audit_file, "w", encoding="utf-8") as f:
            json.dump(audit_payload, f, indent=2)
        logger.info(f"Saved audit trail to {audit_file}")

        try:
            from backend.indexing.create_index import get_es_client
            es_client = get_es_client()
            es_client.update(
                index="calls",
                id=call_id,
                doc={"investigation_completed_at": audit_now},
                doc_as_upsert=True,
            )
        except Exception as exc:
            logger.debug(f"Could not update investigation_completed_at on ES call {call_id}: {exc}")

        return audit_payload


def run_pipeline() -> List[Dict[str, Any]]:
    """
    Run Phase 7 pipeline across all 10 demo calls in chronological date_time order.
    """
    agent = InvestigatorAgent()

    # Discover candidate files (deduplicating by call_id)
    candidate_files = list(CANDIDATES_DIR.glob("CALL_*.json"))
    if not candidate_files:
        candidate_files = list(CANDIDATES_DIR.glob("*.json"))

    # Load metadata to sort by date_time ascending
    calls_to_process = []
    seen_call_ids = set()

    for p in candidate_files:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        cid = data["call_id"]
        if cid in seen_call_ids:
            continue
        seen_call_ids.add(cid)
        calls_to_process.append((data.get("date_time", ""), p))

    # Sort strictly by date_time ascending
    calls_to_process.sort(key=lambda x: x[0])

    print(f"\nDiscovered {len(calls_to_process)} unique calls to process chronologically:")
    for dt, p in calls_to_process:
        print(f"  - {dt} : {p.name}")

    summaries = []
    for dt, p in calls_to_process:
        summary = agent.process_call(p)
        summaries.append(summary)

    return summaries


if __name__ == "__main__":
    run_pipeline()
