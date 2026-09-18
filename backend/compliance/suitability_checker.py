"""
Vigil — Phase 6: Suitability Checker (backend/compliance/suitability_checker.py)

Evaluates customer suitability against identified mutual fund products using a dual-rule model:
1. Rule 3A (Risk Profile Mismatch):
   - Triggered if customer.risk_profile is NOT in product.suitable_risk_profiles.
   - Confidence: HIGH if Conservative customer pitched High-risk product (e.g. Call #1);
     MEDIUM for other mismatches.
2. Rule 3B (Experience-Based Inadequacy Gap):
   - Triggered if customer.investment_experience == "Low" AND product.risk_class in ("Medium", "High"),
     independent of whether risk_profile is technically on the suitable list.
   - Confidence: LOW (deliberately ambiguous test case e.g. Call #9).
   - Low-risk products (risk_class == "Low") are strictly EXEMPT from this rule (e.g. Call #10 clean call).

Attaches corroborating customer risk-comfort/experience statements and RM pitch segments as evidence.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from backend.ingestion.filename_parser import get_mysql_connection
from backend.compliance.product_identifier import IdentifiedProduct

logger = logging.getLogger(__name__)


@dataclass
class SuitabilityCandidate:
    category: str                   # SUITABILITY_MISMATCH or SUITABILITY_INEXPERIENCE_GAP
    confidence_signal: str          # HIGH, MEDIUM, LOW
    detection_type: str             # SUITABILITY_CHECK
    customer_id: str
    customer_name: str
    customer_risk_profile: str
    customer_investment_experience: str
    product_id: str
    product_name: str
    product_risk_class: str
    suitable_risk_profiles: List[str]
    rule_fired: str                 # RULE_3A_PROFILE_MISMATCH or RULE_3B_EXPERIENCE_GAP
    summary: str
    rm_evidence_segments: List[Dict[str, Any]] = field(default_factory=list)
    customer_evidence_segments: List[Dict[str, Any]] = field(default_factory=list)


# Keywords indicating customer expressing risk preference, inexperience, or discomfort
CUSTOMER_RISK_KEYWORDS = [
    r"\brisky\b",
    r"\bsafer?\b",
    r"\bfixed\s+deposits?\b",
    r"\bliquid\s+funds?\b",
    r"\bnever\s+(?:really\s+)?invested\b",
    r"\bnervous\b",
    r"\bups\s+and\s+downs\b",
    r"\bfluctuation\b",
    r"\bcomplicated\b",
    r"\bcomfort\b",
    r"\bstart\s+small\b",
    r"\brisk\s+nahi\s+lena\b",
    r"\bsafe\s+investment\b",
    r"\bprefer\b",
    r"\bhesitant\b",
    r"\bfirst\s+time\b",
    r"\bloss\b",
]
_COMPILED_CUST_KEYWORDS = [re.compile(p, re.IGNORECASE) for p in CUSTOMER_RISK_KEYWORDS]


def load_customer_from_db(customer_id: str) -> Optional[Dict[str, Any]]:
    """Fetches customer details from MySQL customer table."""
    if not customer_id:
        return None
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT customer_id, full_name, risk_profile, investment_experience, "
                "kyc_status FROM customer WHERE customer_id = %s",
                (customer_id,)
            )
            return cur.fetchone()
    finally:
        conn.close()


def find_customer_evidence_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extracts customer segments where they expressed risk discomfort or experience level."""
    evidence = []
    for seg in segments:
        if seg.get("speaker", "").upper() != "CUSTOMER":
            continue
        text = seg.get("text_english", "") or seg.get("text_original", "")
        for pattern in _COMPILED_CUST_KEYWORDS:
            if pattern.search(text):
                evidence.append({
                    "segment_id": seg.get("segment_id"),
                    "start_time": seg.get("start_time"),
                    "end_time": seg.get("end_time"),
                    "text_english": text,
                    "matched_keyword": pattern.pattern
                })
                break
    return evidence


def find_rm_pitch_segments(segments: List[Dict[str, Any]], product: IdentifiedProduct) -> List[Dict[str, Any]]:
    """Extracts RM segments where the identified product was pitched or recommended."""
    evidence = []
    term = product.matched_term.lower()
    for seg in segments:
        if seg.get("speaker", "").upper() != "RM":
            continue
        text = seg.get("text_english", "") or seg.get("text_original", "")
        if term in text.lower() or "fund" in text.lower() or "invest" in text.lower() or "recommend" in text.lower():
            evidence.append({
                "segment_id": seg.get("segment_id"),
                "start_time": seg.get("start_time"),
                "end_time": seg.get("end_time"),
                "text_english": text
            })
    return evidence


def check_suitability(
    call_doc: Dict[str, Any],
    product: Optional[IdentifiedProduct]
) -> List[SuitabilityCandidate]:
    """
    Runs the suitability check against MySQL customer profile and product specifications.
    
    Returns:
        List of SuitabilityCandidate objects (empty if compliant).
    """
    if not product:
        return []

    customer_id = call_doc.get("customer_id", "")
    customer = load_customer_from_db(customer_id)
    if not customer:
        logger.warning(f"Customer '{customer_id}' not found in MySQL customer table.")
        return []

    candidates: List[SuitabilityCandidate] = []
    segments = call_doc.get("transcript_segments", [])
    cust_evidence = find_customer_evidence_segments(segments)
    rm_evidence = find_rm_pitch_segments(segments, product)

    cust_risk_profile = customer.get("risk_profile", "").strip()
    cust_experience = customer.get("investment_experience", "").strip()
    cust_name = customer.get("full_name", "")

    # -------------------------------------------------------------------------
    # RULE 3A: Risk Profile Mismatch
    # -------------------------------------------------------------------------
    # Check if customer's risk profile is accepted by the product
    if cust_risk_profile and cust_risk_profile not in product.suitable_risk_profiles:
        # High severity if Conservative pitched High-risk
        if cust_risk_profile.lower() == "conservative" and product.risk_class.lower() == "high":
            confidence = "HIGH"
        else:
            confidence = "MEDIUM"

        summary = (
            f"Suitability Mismatch: Customer {cust_name} ({customer_id}) has a '{cust_risk_profile}' "
            f"risk profile, but {product.product_name} ({product.product_id}) is risk class '{product.risk_class}' "
            f"and only suitable for [{', '.join(product.suitable_risk_profiles)}]."
        )

        candidates.append(
            SuitabilityCandidate(
                category="SUITABILITY_MISMATCH",
                confidence_signal=confidence,
                detection_type="SUITABILITY_CHECK",
                customer_id=customer_id,
                customer_name=cust_name,
                customer_risk_profile=cust_risk_profile,
                customer_investment_experience=cust_experience,
                product_id=product.product_id,
                product_name=product.product_name,
                product_risk_class=product.risk_class,
                suitable_risk_profiles=product.suitable_risk_profiles,
                rule_fired="RULE_3A_PROFILE_MISMATCH",
                summary=summary,
                rm_evidence_segments=rm_evidence,
                customer_evidence_segments=cust_evidence
            )
        )

    # -------------------------------------------------------------------------
    # RULE 3B: Experience-Based Inadequacy Gap (Call #9 vs Call #10)
    # -------------------------------------------------------------------------
    # If customer has Low investment experience and product is Medium or High risk:
    # Flag a LOW-confidence suitability candidate independent of whether risk_profile matches.
    # Exemption: Low risk products (risk_class == "Low") are strictly EXEMPT.
    is_medium_or_high = product.risk_class.lower() in ("medium", "high")
    has_low_experience = cust_experience.lower() == "low"

    if is_medium_or_high and has_low_experience:
        # If Rule 3A did NOT already fire, emit this experience gap candidate
        if not any(c.rule_fired == "RULE_3A_PROFILE_MISMATCH" for c in candidates):
            summary = (
                f"Suitability Inexperience Gap: Customer {cust_name} ({customer_id}) has 'Low' investment experience "
                f"while {product.product_name} ({product.product_id}) is a '{product.risk_class}' risk product. "
                f"Pitch made without adequately addressing investor inexperience."
            )
            candidates.append(
                SuitabilityCandidate(
                    category="AMBIGUOUS_SUITABILITY",
                    confidence_signal="LOW",
                    detection_type="SUITABILITY_CHECK",
                    customer_id=customer_id,
                    customer_name=cust_name,
                    customer_risk_profile=cust_risk_profile,
                    customer_investment_experience=cust_experience,
                    product_id=product.product_id,
                    product_name=product.product_name,
                    product_risk_class=product.risk_class,
                    suitable_risk_profiles=product.suitable_risk_profiles,
                    rule_fired="RULE_3B_EXPERIENCE_GAP",
                    summary=summary,
                    rm_evidence_segments=rm_evidence,
                    customer_evidence_segments=cust_evidence
                )
            )

    return candidates
