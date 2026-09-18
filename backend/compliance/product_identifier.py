"""
Vigil — Phase 6: Product Identification Engine (backend/compliance/product_identifier.py)

Identifies mutual fund products mentioned in call transcripts:
- Queries MySQL product table for authoritative product catalog.
- Uses robust fuzzy/substring and conversational alias matching across transcript_english
  (RM segments prioritized).
- Fetches product_id, product_name, risk_class, suitable_risk_profiles, disclosure_requirements.
- If NO product can be identified, returns None with status PRODUCT_NOT_IDENTIFIED.
  Explicitly rejects guessing from transaction dates as a primary method.
- Secondary cross-check: verifies against customer transactions in MySQL if a match is found.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from backend.ingestion.filename_parser import get_mysql_connection

logger = logging.getLogger(__name__)


@dataclass
class IdentifiedProduct:
    product_id: str
    product_name: str
    risk_class: str
    suitable_risk_profiles: List[str]
    disclosure_requirements: str
    matched_term: str
    match_score: float
    confirmed_in_transactions: bool = False


# Canonical product aliases mapped to product_id
# Built dynamically from MySQL, with conversational aliases
CANONICAL_ALIASES: Dict[str, List[str]] = {
    "PROD001": [
        "vigil liquid fund",
        "liquid fund",
        "liquid scheme",
    ],
    "PROD002": [
        "vigil short duration debt fund",
        "short duration debt fund",
        "short duration fund",
        "short duration debt",
        "debt fund",
    ],
    "PROD003": [
        "vigil balanced hybrid fund",
        "balanced hybrid fund",
        "hybrid fund",
        "balanced hybrid",
    ],
    "PROD004": [
        "vigil large cap equity fund",
        "large cap equity fund",
        "large cap fund",
        "large cap equity",
        "large cap",
    ],
    "PROD005": [
        "vigil small cap equity fund",
        "small cap equity fund",
        "small cap fund",
        "small cap equity",
        "small cap",
    ],
    "PROD006": [
        "vigil sectoral thematic fund",
        "sectoral thematic fund",
        "thematic fund",
        "sectoral fund",
    ],
    "PROD007": [
        "vigil multi asset allocation fund",
        "multi asset allocation fund",
        "multi asset fund",
        "multi-asset fund",
        "multi asset allocation",
        "multi asset",
    ],
}


def load_products_from_db() -> Dict[str, Dict[str, Any]]:
    """Loads all products from the MySQL product table."""
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT product_id, product_name, risk_class, suitable_risk_profiles, "
                "disclosure_requirements FROM product"
            )
            rows = cur.fetchall()
            return {r["product_id"]: r for r in rows}
    finally:
        conn.close()


def check_customer_transaction(customer_id: str, product_id: str) -> bool:
    """
    Secondary cross-check: checks if customer has an actual transaction in this product.
    Note: Used purely as corroborating confirmation, NEVER as primary identification.
    """
    if not customer_id or not product_id:
        return False
    try:
        conn = get_mysql_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM transaction WHERE customer_id = %s AND product_id = %s LIMIT 1",
                    (customer_id, product_id)
                )
                return cur.fetchone() is not None
        finally:
            conn.close()
    except Exception as exc:
        logger.warning(f"Error checking transaction for customer {customer_id}: {exc}")
        return False


def _normalize_text(text: str) -> str:
    """Normalizes text by replacing hyphens, underscores, and extra whitespace."""
    t = re.sub(r"[-_]", " ", text)
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.lower().split())


def identify_product_from_call(
    call_doc: Dict[str, Any],
    products_db: Optional[Dict[str, Dict[str, Any]]] = None
) -> Optional[IdentifiedProduct]:
    """
    Searches call transcript (RM segments prioritized, then full text) for product mentions.
    
    Returns:
        IdentifiedProduct if a product is identified with high confidence,
        or None if no product can be reliably identified from the transcript.
    """
    if products_db is None:
        products_db = load_products_from_db()

    # Gather RM transcript text
    rm_texts = []
    all_texts = []
    segments = call_doc.get("transcript_segments", [])
    for s in segments:
        text = s.get("text_english", "") or s.get("text_original", "")
        if not text:
            continue
        all_texts.append(text)
        if s.get("speaker", "").upper() == "RM":
            rm_texts.append(text)

    # Fallback to top-level transcript_english_text if segments empty
    if not all_texts and call_doc.get("transcript_english_text"):
        all_texts.append(call_doc["transcript_english_text"])
        rm_texts.append(call_doc["transcript_english_text"])

    rm_blob = _normalize_text(" ".join(rm_texts))
    full_blob = _normalize_text(" ".join(all_texts))

    # Search candidates with specificity scoring: longer alias match = higher specificity
    matches: List[Tuple[float, str, str]] = []  # (score, product_id, matched_alias)

    for pid, pdata in products_db.items():
        aliases = CANONICAL_ALIASES.get(pid, []).copy()
        # Also include formal product name without "Vigil"
        formal_name = _normalize_text(pdata["product_name"])
        if formal_name not in aliases:
            aliases.append(formal_name)
        unbranded = formal_name.replace("vigil", "").strip()
        if unbranded and unbranded not in aliases:
            aliases.append(unbranded)

        # Sort aliases by descending length so most specific phrase matches first
        sorted_aliases = sorted([_normalize_text(a) for a in aliases], key=len, reverse=True)

        for alias in sorted_aliases:
            pattern = r"\b" + re.escape(alias) + r"\b"
            # Prioritize matches in RM segments (weight 1.0) over customer segments (weight 0.8)
            if re.search(pattern, rm_blob):
                # Specificity score based on alias length (longer alias = more specific)
                score = 1.0 + (len(alias) / 100.0)
                matches.append((score, pid, alias))
                break
            elif re.search(pattern, full_blob):
                score = 0.8 + (len(alias) / 100.0)
                matches.append((score, pid, alias))
                break

    if not matches:
        logger.info(f"Call {call_doc.get('call_id')}: PRODUCT_NOT_IDENTIFIED from transcript.")
        return None

    # Pick the highest scoring match
    matches.sort(key=lambda x: x[0], reverse=True)
    best_score, best_pid, best_alias = matches[0]
    pdata = products_db[best_pid]

    # Parse suitable risk profiles
    profiles_raw = pdata.get("suitable_risk_profiles", "")
    suitable_profiles = [p.strip() for p in profiles_raw.split(",") if p.strip()]

    # Secondary transaction check
    cust_id = call_doc.get("customer_id", "")
    has_txn = check_customer_transaction(cust_id, best_pid)

    return IdentifiedProduct(
        product_id=best_pid,
        product_name=pdata["product_name"],
        risk_class=pdata["risk_class"],
        suitable_risk_profiles=suitable_profiles,
        disclosure_requirements=pdata.get("disclosure_requirements", ""),
        matched_term=best_alias,
        match_score=best_score,
        confirmed_in_transactions=has_txn
    )
