"""
Vigil — Phase 6: Deterministic Rules Engine (backend/compliance/deterministic_rules.py)

Scans RM transcript segments for guaranteed-return claims and ambiguous return promises:
- Explicit guaranteed-return claims (AMFI Code of Conduct §II.4.g/h): HIGH/MEDIUM confidence
- Soft/hedged ambiguous language ("should perform well", "I think this should"): LOW confidence
- Negation exception handling: compliant disclosures like "cannot guarantee", "no guarantee"
  are specifically recognized and excluded so they do NOT trigger false positives.
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class RuleViolationCandidate:
    category: str              # GUARANTEED_RETURN or AMBIGUOUS_RETURN_CLAIM
    confidence_signal: str     # HIGH, MEDIUM, LOW
    detection_type: str        # DETERMINISTIC_RULES
    matched_phrase: str
    segment_id: str
    start_time: float
    end_time: float
    text_english: str
    summary: str


# =============================================================================
# 1. Negation & Compliant Disclosure Patterns
# When these appear around or in place of guarantee words, they represent
# compliant regulatory disclosure (e.g. "I cannot guarantee returns"), NOT a violation.
# =============================================================================
COMPLIANT_NEGATION_PATTERNS = [
    r"\b(?:cannot|can't|cant|could\s+not|couldn't)\s+(?:guarantee|assure|promise)\b",
    r"\b(?:no|not\s+a|without\s+any)\s+(?:guarantee|guaranteed\s+return|assured\s+return)\b",
    r"\b(?:not|never)\s+guaranteed\b",
    r"\b(?:do\s+not|don't)\s+(?:guarantee|assure|promise)\b",
    r"\b(?:subject\s+to\s+market\s+risks?|no\s+fixed\s+return)\b",
    r"\b(?:cannot\s+tell\s+you\s+any\s+fixed\s+or\s+guaranteed\s+return)\b",
    r"\b(?:no|not|neither|never|is\s+no|there\s+is\s+no)\s+zero\s+risk\b",
]
_COMPILED_NEGATIONS = [re.compile(p, re.IGNORECASE) for p in COMPLIANT_NEGATION_PATTERNS]


# =============================================================================
# 2. Explicit Guaranteed-Return Patterns (AMFI Code of Conduct §II.4.g / §II.4.h)
# Reuses the exact regulatory indexing terminology established in Phase 3.
# =============================================================================
EXPLICIT_GUARANTEE_PATTERNS = [
    # Direct guarantee / assurance terms
    (r"\bguaranteed\s+returns?\b", "guaranteed return"),
    (r"\bguarantee\s+(?:a\s+|the\s+)?returns?\b", "guarantee return"),
    (r"\bguaranteed\s+profits?\b", "guaranteed profit"),
    (r"\bguaranteed\s+yields?\b", "guaranteed yield"),
    (r"\bassured\s+returns?\b", "assured return"),
    (r"\bassuring\s+returns?\b", "assuring return"),
    (r"\bassure\s+(?:you\s+of\s+)?(?:a\s+)?returns?\b", "assure return"),
    (r"\bindicative\s+yields?\b", "indicative yield"),
    (r"\bindicative\s+returns?\b", "indicative return"),
    (r"\bdefinitely\s+(?:get|receive|give)\b.*?\breturn\b", "definitely get return"),
    (r"\bdefinitely\s+\d+%\s+return\b", "definitely percentage return"),
    (r"\bwill\s+definitely\s+get\b", "will definitely get"),
    (r"\bassuring\s+you\b.*?\b(?:definitely|guarantee|return)\b", "assuring you return"),
    (r"\bpromise\s+(?:you\s+)?(?:a\s+)?returns?\b", "promise return"),
    (r"\bpromising\s+(?:a\s+)?returns?\b", "promising return"),
    (r"\bno\s+chance\s+of\s+(?:any\s+|you\s+having\s+a\s+)?loss\b", "no chance of loss"),
    (r"\bcannot\s+lose\s+money\b", "cannot lose money"),
    (r"\bcan't\s+lose\s+money\b", "can't lose money"),
    (r"\bwon't\s+lose\s+money\b", "won't lose money"),
    (r"\bzero\s+risk\b", "zero risk"),
    (r"\bcompletely\s+safe\b", "completely safe"),
    (r"\bfully\s+safe\b", "fully safe"),
]
_COMPILED_EXPLICIT = [(re.compile(p, re.IGNORECASE), label) for p, label in EXPLICIT_GUARANTEE_PATTERNS]


# =============================================================================
# 3. Soft, Hedged Language Patterns (Call #6 test case)
# Produces LOW confidence candidates — deliberately ambiguous language that
# must NOT be auto-confirmed as HIGH, but should not be ignored either.
# =============================================================================
HEDGED_LANGUAGE_PATTERNS = [
    (r"\bshould\s+perform\s+well\b", "should perform well"),
    (r"\bexpect\s+to\s+perform\s+well\b", "expect to perform well"),
    (r"\bi\s+think\s+this\s+should\b", "i think this should"),
    (r"\bi\s+think\s+this\s+will\b", "i think this will"),
    (r"\bexpect\s+to\s+give\b", "expect to give"),
    (r"\blikely\s+to\s+perform\b", "likely to perform"),
    (r"\blean\s+towards\s+it\s+doing\s+reasonably\s+well\b", "lean towards doing well"),
    (r"\bought\s+to\s+perform\b", "ought to perform"),
]
_COMPILED_HEDGED = [(re.compile(p, re.IGNORECASE), label) for p, label in HEDGED_LANGUAGE_PATTERNS]


def is_negated_or_compliant(text: str, match_span: tuple) -> bool:
    """
    Checks if a matched pattern occurs within a compliant disclaimer / negation context.
    e.g. 'I cannot guarantee future performance' should NOT be flagged as a guarantee claim.
    """
    for neg_regex in _COMPILED_NEGATIONS:
        for neg_match in neg_regex.finditer(text):
            # If the negation overlaps or encompasses the sentence/clause of the match
            start_dist = abs(neg_match.start() - match_span[0])
            end_dist = abs(neg_match.end() - match_span[1])
            if start_dist < 60 or end_dist < 60 or (neg_match.start() <= match_span[0] and neg_match.end() >= match_span[1]):
                return True
    return False


def scan_rm_segments(segments: List[Dict[str, Any]]) -> List[RuleViolationCandidate]:
    """
    Scans a call's transcript segments where speaker == 'RM'.
    Evaluates text_english for deterministic compliance violations.

    Returns:
        List of RuleViolationCandidate objects.
    """
    candidates: List[RuleViolationCandidate] = []

    for seg in segments:
        speaker = seg.get("speaker", "").upper()
        if speaker != "RM":
            continue

        text = seg.get("text_english", "") or seg.get("text_original", "")
        if not text.strip():
            continue

        seg_id = str(seg.get("segment_id", ""))
        start_t = float(seg.get("start_time", 0.0))
        end_t = float(seg.get("end_time", 0.0))

        # Check explicit guaranteed-return patterns first
        matched_explicit = False
        for regex, label in _COMPILED_EXPLICIT:
            for match in regex.finditer(text):
                if is_negated_or_compliant(text, match.span()):
                    continue

                matched_phrase = match.group(0)
                # Assign confidence based on explicit strength
                confidence = "HIGH"
                if label in ("no chance of loss", "completely safe", "fully safe"):
                    confidence = "MEDIUM"  # Implied/soft assurance (e.g. Call #2)

                candidates.append(
                    RuleViolationCandidate(
                        category="GUARANTEED_RETURN",
                        confidence_signal=confidence,
                        detection_type="DETERMINISTIC_RULES",
                        matched_phrase=matched_phrase,
                        segment_id=seg_id,
                        start_time=start_t,
                        end_time=end_t,
                        text_english=text,
                        summary=f"RM made return assurance / guaranteed return claim ({label}): '{matched_phrase}'."
                    )
                )
                matched_explicit = True
                break
            if matched_explicit:
                break

        # If no explicit guarantee was found, check for soft/hedged language (Call #6)
        if not matched_explicit:
            for regex, label in _COMPILED_HEDGED:
                matched_hedged = False
                for match in regex.finditer(text):
                    if is_negated_or_compliant(text, match.span()):
                        continue

                    matched_phrase = match.group(0)
                    candidates.append(
                        RuleViolationCandidate(
                            category="AMBIGUOUS_RETURN_CLAIM",
                            confidence_signal="LOW",
                            detection_type="DETERMINISTIC_RULES",
                            matched_phrase=matched_phrase,
                            segment_id=seg_id,
                            start_time=start_t,
                            end_time=end_t,
                            text_english=text,
                            summary=f"RM used soft/hedged return prediction language ({label}): '{matched_phrase}'."
                        )
                    )
                    matched_hedged = True
                    break
                if matched_hedged:
                    break

    return candidates
