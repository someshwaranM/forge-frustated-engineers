"""
Step 6 — Validation gate.

Hard gate that runs BEFORE indexing on every chunk in every
backend/indexing/chunks/*.json file. If any check fails, the
pipeline STOPS and reports exactly which chunk(s) failed which check.

Checks:
  - clause_text is non-empty wherever clause is non-empty
  - Every CoC chunk has a non-empty clause field
  - page_number is present and >= 1
  - source_url is present and non-empty
  - chunk_id is unique (within and across all documents)
  - All required metadata fields present (no null except effective_until)
  - chunk_text and chunk_text_semantic are not garbage
"""

import re
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

CHUNKS_DIR = Path(__file__).resolve().parent / "chunks"

# The CoC document stem that requires non-empty clause on every chunk
COC_STEM = "Revised_Codeof_Conductfor_Mutual_Fund_Distributors_April2022"

# Required fields that must not be null/empty
REQUIRED_FIELDS = [
    "chunk_id", "chunk_level", "document_id", "document_name",
    "regulator", "document_type", "status", "source_url",
    "source_file", "source_file_hash", "indexed_at",
]

# Fields that must be non-null (but can be empty string)
REQUIRED_PRESENT = [
    "document_version", "publication_date", "effective_date",
    "priority",
]

# Nullable fields
NULLABLE_FIELDS = ["effective_until"]


@dataclass
class ValidationResult:
    """Holds validation results for a single document."""
    pdf_stem: str
    total_chunks: int
    passed: int
    failed: int
    failures: list  # list of (chunk_id, check_name, detail)


def _is_garbage_text(text: str) -> bool:
    """Check if text is obvious extraction garbage."""
    if not text or len(text.strip()) < 5:
        return True
    # Check alphanumeric ratio
    non_ws = re.sub(r'\s+', '', text)
    if len(non_ws) == 0:
        return True
    alnum_count = sum(1 for c in non_ws if c.isalnum())
    ratio = alnum_count / len(non_ws)
    return ratio < 0.25


def validate_chunks(chunks_by_stem: dict = None) -> tuple:
    """
    Validate all chunks. Can accept a dict of {stem: chunk_list} directly,
    or will read from chunks/*.json files.

    Returns (all_passed: bool, results: list[ValidationResult]).
    """
    if chunks_by_stem is None:
        # Read from JSON files
        chunks_by_stem = {}
        for json_path in sorted(CHUNKS_DIR.glob("*.json")):
            stem = json_path.stem
            with open(json_path, "r", encoding="utf-8") as f:
                chunks_by_stem[stem] = json.load(f)

    all_chunk_ids = set()
    results = []
    total_failures = 0

    for stem, chunks in chunks_by_stem.items():
        is_coc = (stem == COC_STEM)
        vr = ValidationResult(
            pdf_stem=stem,
            total_chunks=len(chunks),
            passed=0,
            failed=0,
            failures=[],
        )

        for chunk in chunks:
            chunk_id = chunk.get("chunk_id", "<missing>")
            chunk_failures = []

            # 1. Required fields not null/empty
            for fld in REQUIRED_FIELDS:
                val = chunk.get(fld)
                if val is None or (isinstance(val, str) and not val.strip()):
                    chunk_failures.append(
                        (fld, f"required field '{fld}' is missing or empty")
                    )

            # 2. Required-present fields (not null, can be empty string for strings)
            for fld in REQUIRED_PRESENT:
                val = chunk.get(fld)
                if val is None:
                    chunk_failures.append(
                        (fld, f"field '{fld}' is null (must be present)")
                    )

            # 3. clause_text non-empty when clause is non-empty
            clause_val = chunk.get("clause", "")
            clause_text_val = chunk.get("clause_text", "")
            if clause_val and isinstance(clause_val, str) and clause_val.strip():
                if not clause_text_val or not clause_text_val.strip():
                    chunk_failures.append(
                        ("clause_text",
                         f"clause='{clause_val}' but clause_text is empty")
                    )

            # 4. CoC: every chunk must have non-empty clause
            if is_coc:
                if not clause_val or (isinstance(clause_val, str) and not clause_val.strip()):
                    chunk_failures.append(
                        ("clause",
                         "CoC chunk missing required clause field")
                    )

            # 5. page_number present and >= 1
            page_num = chunk.get("page_number")
            if page_num is None or (isinstance(page_num, int) and page_num < 1):
                chunk_failures.append(
                    ("page_number",
                     f"page_number is {page_num} (must be >= 1)")
                )

            # 6. source_url present and non-empty
            src_url = chunk.get("source_url", "")
            if not src_url or not src_url.strip():
                chunk_failures.append(
                    ("source_url", "source_url is missing or empty")
                )

            # 7. chunk_id uniqueness
            if chunk_id in all_chunk_ids:
                chunk_failures.append(
                    ("chunk_id", f"duplicate chunk_id '{chunk_id}'")
                )
            all_chunk_ids.add(chunk_id)

            # 8. chunk_text and chunk_text_semantic not garbage
            chunk_text = chunk.get("chunk_text", "")
            if _is_garbage_text(chunk_text):
                chunk_failures.append(
                    ("chunk_text",
                     f"chunk_text appears to be garbage (len={len(chunk_text)})")
                )

            chunk_text_sem = chunk.get("chunk_text_semantic", "")
            if _is_garbage_text(chunk_text_sem):
                chunk_failures.append(
                    ("chunk_text_semantic",
                     f"chunk_text_semantic appears to be garbage (len={len(chunk_text_sem)})")
                )

            if chunk_failures:
                vr.failed += 1
                for check, detail in chunk_failures:
                    vr.failures.append((chunk_id, check, detail))
            else:
                vr.passed += 1

        results.append(vr)
        total_failures += vr.failed

    # Report
    print("\n" + "=" * 60)
    print("VALIDATION GATE RESULTS")
    print("=" * 60)
    all_passed = True
    for vr in results:
        short = vr.pdf_stem[:60] + "…" if len(vr.pdf_stem) > 60 else vr.pdf_stem
        status = "[PASS] PASS" if vr.failed == 0 else "[FAIL] FAIL"
        print(f"  {short}")
        print(f"    {status} — {vr.passed}/{vr.total_chunks} passed, {vr.failed} failed")
        if vr.failures:
            all_passed = False
            for chunk_id, check, detail in vr.failures[:20]:
                print(f"      x [{chunk_id}] {check}: {detail}")
            if len(vr.failures) > 20:
                print(f"      ... and {len(vr.failures) - 20} more failures")
        print()

    if all_passed:
        print("[PASS] Validation gate PASSED — all chunks valid.\n")
    else:
        print(f"[FAIL] Validation gate FAILED — {total_failures} chunk(s) with errors.\n")
        print("Pipeline will NOT proceed to indexing.\n")

    return all_passed, results


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("=" * 60)
    print("STEP 6 — Validation Gate")
    print("=" * 60)
    passed, _ = validate_chunks()
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
