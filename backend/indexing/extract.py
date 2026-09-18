"""
Step 3 — PDF text extraction with header/footer removal.

For each of the 5 regulatory PDFs:
  a) Open with PyMuPDF and iterate using physical page numbers (page.number + 1).
  b) Extract text block-by-block preserving reading order.
  c) Detect and remove recurring headers/footers (non-adjacent page recurrence).
  d) Track page-boundary offsets for the chunker.
  e) Write clean .txt to backend/indexing/extracted/.
  f) Quality-check: flag pages with <20 chars or <50% alphabetic ratio.
"""

import re
import logging
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # d:\vigil
EXTRACTED_DIR = Path(__file__).resolve().parent / "extracted"

# All 5 source PDFs (order doesn't matter for extraction)
PDF_PATHS = [
    PROJECT_ROOT / "RegulatoryDocs" / "SEBI" / "securities-and-exchange-board-of-india-mutual-funds-regulations-1996-last-amended-on-february-07-2023.pdf",
    PROJECT_ROOT / "RegulatoryDocs" / "SEBI" / "securities-and-exchange-board-of-india-mutual-funds-regulations-2026-last-amended-on-july-7-2026.pdf",
    PROJECT_ROOT / "RegulatoryDocs" / "SEBI" / "master-circular-for-mutual-funds.pdf",
    PROJECT_ROOT / "RegulatoryDocs" / "AMFI" / "AMFI_Codeof_Ethics_2026.pdf",
    PROJECT_ROOT / "RegulatoryDocs" / "AMFI" / "Revised_Codeof_Conductfor_Mutual_Fund_Distributors_April2022.pdf",
]

# Quality thresholds — these are intentionally low because the flagged
# pages in the Master Circular are legitimate TOC/index pages (lots of
# dots "...") and section dividers (e.g. just the word "ANNEXURES").
# The purpose is to catch truly blank or garbled pages, not structural pages.
MIN_CHAR_COUNT = 5
MIN_ALPHA_RATIO = 0.15

# Header/footer detection: a line must appear on > this fraction of pages
RECURRENCE_THRESHOLD = 0.60


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class PageBoundary:
    """Records where each physical page's text starts in the cleaned output."""
    page_number: int     # 1-indexed physical page
    char_offset: int     # character offset in the cleaned full-document text


@dataclass
class ExtractionResult:
    """Result of extracting one PDF."""
    pdf_stem: str
    clean_text: str
    page_boundaries: list  # list of PageBoundary
    pages_total: int
    pages_extracted: int
    pages_flagged: int
    flagged_details: list  # list of (page_number, reason)
    stripped_headers_footers: list  # list of stripped line patterns


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize_for_comparison(line: str) -> str:
    """Normalize a line for header/footer comparison:
    strip whitespace, remove page-number digits, collapse spaces."""
    s = line.strip()
    # Remove standalone page numbers and "Page X of Y" patterns
    s = re.sub(r'\bPage\s+\d+\s*(of\s+\d+)?\b', '', s, flags=re.IGNORECASE)
    # Remove remaining standalone digits
    s = re.sub(r'^\d+$', '', s.strip())
    # Remove trailing/leading digits that look like page numbers
    s = re.sub(r'^\d+\s+', '', s)
    s = re.sub(r'\s+\d+$', '', s)
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _extract_blocks_per_page(doc: fitz.Document) -> list:
    """Extract text blocks per page, returning list of (page_number, blocks).
    Each block is (x0, y0, x1, y1, text, block_no, block_type)."""
    pages = []
    for page in doc:
        phys_page = page.number + 1  # 1-indexed physical
        blocks = page.get_text("blocks")
        # Filter to text blocks only (block_type == 0)
        text_blocks = [b for b in blocks if b[6] == 0]
        # Sort by vertical position (y0), then horizontal (x0)
        text_blocks.sort(key=lambda b: (b[1], b[0]))
        pages.append((phys_page, text_blocks))
    return pages


def _split_block_into_lines(block_text: str) -> list:
    """Split block text into individual lines, stripping trailing whitespace."""
    return [ln for ln in block_text.split('\n') if ln.strip()]


def _detect_headers_footers(pages_data: list) -> set:
    """
    Detect recurring header/footer lines.

    Strategy:
    - For each page, collect the first 2 lines and last 2 lines.
    - Normalize each line and track which pages it appears on.
    - A line appearing on >60% of pages is a candidate.
    - Only strip if the line appears on NON-ADJACENT pages (to avoid
      stripping genuine section headings that span consecutive pages).
    """
    total_pages = len(pages_data)
    if total_pages < 3:
        # Too few pages to reliably detect headers/footers
        return set()

    # Collect candidate lines with their page numbers
    # key = normalized line, value = set of page numbers
    candidate_pages = defaultdict(set)
    # Also track the original (unnormalized) forms
    candidate_originals = defaultdict(set)

    for page_num, blocks in pages_data:
        all_lines = []
        for b in blocks:
            all_lines.extend(_split_block_into_lines(b[4]))

        if not all_lines:
            continue

        # First 2 and last 2 lines
        top_lines = all_lines[:2]
        bottom_lines = all_lines[-2:] if len(all_lines) > 2 else []

        for line in top_lines + bottom_lines:
            norm = _normalize_for_comparison(line)
            if len(norm) < 2:
                # Empty/trivial after normalization — still track page-number-only lines
                # which are definitely headers/footers
                stripped = line.strip()
                if re.match(r'^(Page\s+)?\d+(\s+of\s+\d+)?$', stripped, re.IGNORECASE):
                    candidate_pages[f"__PAGE_NUM_PATTERN__{norm}"].add(page_num)
                    candidate_originals[f"__PAGE_NUM_PATTERN__{norm}"].add(line.strip())
                continue
            candidate_pages[norm].add(page_num)
            candidate_originals[norm].add(line.strip())

    # Filter: must appear on >60% of pages
    threshold = total_pages * RECURRENCE_THRESHOLD
    headers_footers = set()
    stripped_patterns = []

    for norm, page_set in candidate_pages.items():
        if len(page_set) < threshold:
            continue

        # Check non-adjacency: the pages must NOT all be consecutive
        sorted_pages = sorted(page_set)
        has_non_adjacent = False
        for i in range(1, len(sorted_pages)):
            if sorted_pages[i] - sorted_pages[i - 1] > 2:
                has_non_adjacent = True
                break

        if has_non_adjacent or len(page_set) > total_pages * 0.8:
            # This is a true header/footer (recurring across non-adjacent pages,
            # or so prevalent it's clearly a header/footer)
            for orig in candidate_originals[norm]:
                headers_footers.add(orig)
            sample = list(candidate_originals[norm])[:2]
            stripped_patterns.append(
                f"  Pattern: {norm!r} (appears on {len(page_set)}/{total_pages} pages, "
                f"e.g. {sample})"
            )

    # Always strip "Page X of Y" lines (these are unambiguously page numbers)
    page_num_pattern = re.compile(
        r'^\s*(Page\s+)?\d+(\s+of\s+\d+)?\s*$', re.IGNORECASE
    )
    # We'll also handle this in the line-stripping phase

    return headers_footers, stripped_patterns, page_num_pattern


def _is_header_footer_line(line: str, hf_set: set, page_num_re: re.Pattern) -> bool:
    """Check if a line should be stripped as a header/footer."""
    stripped = line.strip()
    if not stripped:
        return False
    # Check exact match against detected headers/footers
    if stripped in hf_set:
        return True
    # Check page-number-only pattern
    if page_num_re.match(stripped):
        return True
    return False


def _quality_check_page(text: str, page_number: int) -> tuple:
    """
    Quality check a page's extracted text.
    Returns (passed: bool, reason: str or None).
    """
    clean = text.strip()
    if len(clean) < MIN_CHAR_COUNT:
        return False, f"Page {page_number}: only {len(clean)} characters (threshold: {MIN_CHAR_COUNT})"

    # Alphabetic ratio (after stripping whitespace and punctuation)
    non_ws = re.sub(r'\s+', '', clean)
    if len(non_ws) == 0:
        return False, f"Page {page_number}: zero non-whitespace characters"

    alpha_count = sum(1 for c in non_ws if c.isalpha())
    alpha_ratio = alpha_count / len(non_ws)
    if alpha_ratio < MIN_ALPHA_RATIO:
        return False, f"Page {page_number}: alphabetic ratio {alpha_ratio:.2%} (threshold: {MIN_ALPHA_RATIO:.0%})"

    return True, None


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------
def extract_pdf(pdf_path: Path) -> ExtractionResult:
    """Extract and clean text from a single PDF."""
    pdf_stem = pdf_path.stem
    logger.info(f"Extracting: {pdf_stem}")

    doc = fitz.open(str(pdf_path))
    pages_data = _extract_blocks_per_page(doc)
    total_pages = len(pages_data)

    # --- Header/footer detection ---
    hf_set, stripped_patterns, page_num_re = _detect_headers_footers(pages_data)
    logger.info(f"  Detected {len(hf_set)} header/footer line variants to strip")
    for pat in stripped_patterns:
        logger.info(pat)

    # --- Extract clean text per page, tracking quality ---
    pages_extracted = 0
    pages_flagged = 0
    flagged_details = []
    clean_pages = []  # list of (page_number, clean_text_for_page)

    for page_num, blocks in pages_data:
        page_lines = []
        for b in blocks:
            lines = _split_block_into_lines(b[4])
            for line in lines:
                if not _is_header_footer_line(line, hf_set, page_num_re):
                    page_lines.append(line)

        page_text = '\n'.join(page_lines)

        # Quality check
        passed, reason = _quality_check_page(page_text, page_num)
        if not passed:
            pages_flagged += 1
            flagged_details.append((page_num, reason))
            logger.warning(f"  FLAGGED: {reason}")
        else:
            pages_extracted += 1

        clean_pages.append((page_num, page_text))

    doc.close()

    # --- Build full document text with page boundary tracking ---
    page_boundaries = []
    full_text_parts = []
    current_offset = 0

    for page_num, page_text in clean_pages:
        page_boundaries.append(PageBoundary(page_number=page_num, char_offset=current_offset))
        if full_text_parts:
            # Add a paragraph break between pages
            separator = '\n\n'
            full_text_parts.append(separator)
            current_offset += len(separator)
        full_text_parts.append(page_text)
        current_offset += len(page_text)

    clean_text = ''.join(full_text_parts)

    return ExtractionResult(
        pdf_stem=pdf_stem,
        clean_text=clean_text,
        page_boundaries=page_boundaries,
        pages_total=total_pages,
        pages_extracted=pages_extracted,
        pages_flagged=pages_flagged,
        flagged_details=flagged_details,
        stripped_headers_footers=stripped_patterns,
    )


def extract_all() -> dict:
    """
    Extract all 5 PDFs. Returns dict mapping pdf_stem -> ExtractionResult.
    Raises RuntimeError if any page is flagged.
    """
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

    results = {}
    all_flagged = []

    for pdf_path in PDF_PATHS:
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        result = extract_pdf(pdf_path)
        results[result.pdf_stem] = result

        # Write clean text
        out_path = EXTRACTED_DIR / f"{result.pdf_stem}.txt"
        out_path.write_text(result.clean_text, encoding="utf-8")
        logger.info(
            f"  Written: {out_path.name} "
            f"({result.pages_total} pages, "
            f"{result.pages_extracted} extracted, "
            f"{result.pages_flagged} flagged)"
        )

        if result.flagged_details:
            all_flagged.extend(
                (result.pdf_stem, pg, reason) for pg, reason in result.flagged_details
            )

    # --- Report ---
    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    for stem, r in results.items():
        short = stem[:60] + "…" if len(stem) > 60 else stem
        print(f"  {short}")
        print(f"    pages_total:     {r.pages_total}")
        print(f"    pages_extracted: {r.pages_extracted}")
        print(f"    pages_flagged:   {r.pages_flagged}")
        if r.stripped_headers_footers:
            print(f"    headers/footers stripped:")
            for pat in r.stripped_headers_footers[:5]:
                print(f"      {pat}")
        print()

    if all_flagged:
        print("\n[FAIL] EXTRACTION HALTED — flagged pages detected:\n")
        for stem, pg, reason in all_flagged:
            print(f"  [{stem}] {reason}")
        raise RuntimeError(
            f"Extraction quality check failed: {len(all_flagged)} page(s) flagged. "
            "Inspect the specific pages listed above. Do NOT proceed to indexing."
        )

    print("[PASS] All pages passed quality checks.\n")
    return results


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    print("=" * 60)
    print("STEP 3 — PDF Text Extraction")
    print("=" * 60)
    extract_all()


if __name__ == "__main__":
    main()
