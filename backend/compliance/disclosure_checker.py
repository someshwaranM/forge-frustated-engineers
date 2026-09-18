"""
Vigil — Phase 6: Disclosure Keyword Checker (backend/compliance/disclosure_checker.py)

========================================================================================
METHODOLOGY & AUDIT DISCLAIMER (KNOWN STATED LIMITATION):
This check performs a deterministic keyword-presence scan, NOT true NLU comprehension.
Known limitations:
- Can false-negative: RM may discuss risks using colloquial phrasing outside the keyword list.
- Can false-positive: RM may say the word "risk" in an unrelated or dismissive sense
  (e.g., "there is no risk").
This is a coarse preliminary filter designed to produce candidates for Phase 7's
Investigator Agent, which applies LLM reasoning over the full context.
========================================================================================

Scope:
- Applies only to products with risk_class in ("Medium", "High"). Low-risk products are exempt.
- Total absence of disclosure language -> MISSING_RISK_DISCLOSURE (HIGH for High-risk, MEDIUM for Medium-risk).
- Partial disclosure (generic risk mentioned, but product-specific mandatory requirements like
  'risk-o-meter' or 'hybrid-allocation' completely missing) -> INADEQUATE_RISK_DISCLOSURE (MEDIUM).
"""

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from backend.compliance.product_identifier import IdentifiedProduct

logger = logging.getLogger(__name__)


@dataclass
class DisclosureCandidate:
    category: str              # MISSING_DISCLOSURE
    confidence_signal: str     # HIGH or MEDIUM
    detection_type: str        # DISCLOSURE_CHECK
    product_id: str
    product_name: str
    product_risk_class: str
    mandatory_requirements: str
    missing_elements: List[str]
    summary: str
    rm_segments_evaluated: int
    matched_generic_keywords: List[str] = field(default_factory=list)
    rm_evidence_segments: List[Dict[str, Any]] = field(default_factory=list)


# Generic risk disclosure keywords
GENERIC_DISCLOSURE_KEYWORDS = [
    r"\brisk\b",
    r"\brisks\b",
    r"\bdisclosure\b",
    r"\brisk-o-meter\b",
    r"\briskometer\b",
    r"\bvolatil\w*\b",
    r"\bno\s+guarantee\b",
    r"\bcannot\s+guarantee\b",
    r"\bmarket\s+risk\b",
    r"\bscheme\s+(?:information\s+)?document\b",
    r"\b(?:fund|scheme)\s+details\b",
    r"\b(?:nothing(?:'s|\s+is)?\s+certain|not\s+certain|uncertain)\b",
    r"\bfluctuat\w*\b",
]
_COMPILED_GENERIC = [re.compile(p, re.IGNORECASE) for p in GENERIC_DISCLOSURE_KEYWORDS]

# Product-specific mandatory disclosure terms extracted from product table
SPECIFIC_REQUIREMENT_PATTERNS = {
    "risk-o-meter": re.compile(r"\b(?:risk-o-meter|riskometer)\b", re.IGNORECASE),
    "hybrid-allocation": re.compile(r"\b(?:hybrid[- ]allocation|equity\s+and\s+debt\s+allocation)\b", re.IGNORECASE),
    "concentration-risk": re.compile(r"\b(?:concentration[- ]risk|sector[- ]specific\s+risk)\b", re.IGNORECASE),
    "high-volatility": re.compile(r"\b(?:high[- ]volatility|volatile\s+nature)\b", re.IGNORECASE),
    "market-risk": re.compile(r"\bmarket[- ]risk\b", re.IGNORECASE),
}


def check_disclosure(
    call_doc: Dict[str, Any],
    product: Optional[IdentifiedProduct]
) -> List[DisclosureCandidate]:
    """
    Checks if RM delivered mandatory risk disclosures for Medium/High risk products.
    
    Returns:
        List of DisclosureCandidate objects (empty if compliant).
    """
    if not product:
        return []

    # Only Medium and High risk products require risk disclosures
    if product.risk_class.lower() not in ("medium", "high"):
        return []

    # Gather RM segment texts and metadata
    rm_texts = []
    rm_segs = []
    segments = call_doc.get("transcript_segments", [])
    for s in segments:
        if s.get("speaker", "").upper() == "RM":
            text = s.get("text_english", "") or s.get("text_original", "")
            if text.strip():
                rm_texts.append(text)
                rm_segs.append({
                    "segment_id": s.get("segment_id", f"seg_{len(rm_segs)+1}"),
                    "start_time": s.get("start_time", 0.0),
                    "end_time": s.get("end_time", 0.0),
                    "text_english": text,
                    "text_original": s.get("text_original", "")
                })

    # Fallback to transcript_english_text if segments missing
    if not rm_texts and call_doc.get("transcript_english_text"):
        fallback_text = call_doc["transcript_english_text"]
        rm_texts.append(fallback_text)
        rm_segs.append({
            "segment_id": "seg_full_transcript",
            "start_time": 0.0,
            "end_time": float(call_doc.get("duration_seconds", 60.0)),
            "text_english": fallback_text,
            "text_original": fallback_text
        })

    combined_rm_text = " ".join(rm_texts).lower()

    # 1. Check for ANY generic risk / disclosure language
    matched_generic = []
    for pattern in _COMPILED_GENERIC:
        m = pattern.search(combined_rm_text)
        if m:
            matched_generic.append(m.group(0))

    # Case A: Complete Absence of ANY risk disclosure
    if not matched_generic:
        confidence = "HIGH" if product.risk_class.lower() == "high" else "MEDIUM"
        summary = (
            f"Missing Risk Disclosure: RM recommended {product.product_name} ({product.product_id}, "
            f"Risk Class: '{product.risk_class}') without providing ANY risk disclosure, risk-o-meter explanation, "
            f"or market volatility warnings. Mandatory requirements: '{product.disclosure_requirements}'."
        )
        return [
            DisclosureCandidate(
                category="MISSING_DISCLOSURE",
                confidence_signal=confidence,
                detection_type="DISCLOSURE_CHECK",
                product_id=product.product_id,
                product_name=product.product_name,
                product_risk_class=product.risk_class,
                mandatory_requirements=product.disclosure_requirements,
                missing_elements=["All risk disclosures (zero risk keywords detected in RM speech)"],
                summary=summary,
                rm_segments_evaluated=len(rm_texts),
                matched_generic_keywords=[],
                rm_evidence_segments=rm_segs
            )
        ]

    # Case B: Partial / Inadequate Disclosure
    # RM mentioned generic risk (e.g. "market risk hota hai"), but omitted specific requirements
    # stated in product.disclosure_requirements (e.g. risk-o-meter or hybrid-allocation)
    missing_specific = []
    req_text = (product.disclosure_requirements or "").lower()

    if "risk-o-meter" in req_text and not SPECIFIC_REQUIREMENT_PATTERNS["risk-o-meter"].search(combined_rm_text):
        missing_specific.append("risk-o-meter")
    if "hybrid-allocation" in req_text and not SPECIFIC_REQUIREMENT_PATTERNS["hybrid-allocation"].search(combined_rm_text):
        missing_specific.append("hybrid-allocation disclosure")
    if "concentration-risk" in req_text and not SPECIFIC_REQUIREMENT_PATTERNS["concentration-risk"].search(combined_rm_text):
        missing_specific.append("concentration-risk disclosure")

    if missing_specific:
        summary = (
            f"Inadequate / Partial Risk Disclosure: RM mentioned general risk keywords "
            f"({', '.join(set(matched_generic))}) for {product.product_name} ({product.product_id}), "
            f"but omitted mandatory product-specific disclosures: [{', '.join(missing_specific)}]. "
            f"Required: '{product.disclosure_requirements}'."
        )
        return [
            DisclosureCandidate(
                category="MISSING_DISCLOSURE",
                confidence_signal="MEDIUM",
                detection_type="DISCLOSURE_CHECK",
                product_id=product.product_id,
                product_name=product.product_name,
                product_risk_class=product.risk_class,
                mandatory_requirements=product.disclosure_requirements,
                missing_elements=missing_specific,
                summary=summary,
                rm_segments_evaluated=len(rm_texts),
                matched_generic_keywords=list(set(matched_generic)),
                rm_evidence_segments=rm_segs
            )
        ]

    # Full compliance
    return []
