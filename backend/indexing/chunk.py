"""
Steps 4-5 — Document-specific chunking with full field population.

Five document-type-specific chunking strategies:
  1. SEBI MF Regulations (1996 & 2026): Chapter → Regulation → Sub-regulation → Paragraph
  2. Master Circular: Chapter/Topic → Sub-topic → Requirement/paragraph
  3. AMFI Code of Ethics: Section → Subsection → Paragraph/Clause
  4. AMFI Distributor Code of Conduct: Clause-level (e.g. II.4.g)

Every chunk gets full metadata populated per the ES mapping.
Output: one .json file per PDF in backend/indexing/chunks/.
"""

import re
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EXTRACTED_DIR = Path(__file__).resolve().parent / "extracted"
CHUNKS_DIR = Path(__file__).resolve().parent / "chunks"

# ---------------------------------------------------------------------------
# Document metadata registry  (from docs/regulatory_corpus.md)
# ---------------------------------------------------------------------------
DOC_REGISTRY = {
    "securities-and-exchange-board-of-india-mutual-funds-regulations-1996-last-amended-on-february-07-2023": {
        "document_id": "SEBI_MF_REGS_1996",
        "document_name": "SEBI (Mutual Funds) Regulations, 1996 (last amended February 07, 2023)",
        "regulator": "SEBI",
        "document_type": "REGULATION",
        "document_version": "February 2023",
        "publication_date": "2023-02-07",
        "effective_date": "2023-02-07",
        "effective_until": None,
        "status": "historical",
        "priority": 1,
        "source_url": "https://www.sebi.gov.in/legal/regulations/feb-2023/securities-and-exchange-board-of-india-mutual-funds-regulations-1996-last-amended-on-february-07-2023-_69213.html",
        "source_file": "RegulatoryDocs/SEBI/securities-and-exchange-board-of-india-mutual-funds-regulations-1996-last-amended-on-february-07-2023.pdf",
        "chunker": "sebi_regulation",
        "citation_prefix": "SEBI MF Regs 1996",
    },
    "securities-and-exchange-board-of-india-mutual-funds-regulations-2026-last-amended-on-july-7-2026": {
        "document_id": "SEBI_MF_REGS_2026",
        "document_name": "SEBI (Mutual Funds) Regulations, 2026 (last amended July 7, 2026)",
        "regulator": "SEBI",
        "document_type": "REGULATION",
        "document_version": "2026",
        "publication_date": "2026-07-07",
        "effective_date": "2026-07-07",
        "effective_until": None,
        "status": "current",
        "priority": 10,
        "source_url": "https://www.sebi.gov.in/legal/regulations/jul-2026/securities-and-exchange-board-of-india-mutual-funds-regulations-2026-last-amended-on-july-7-2026-_102780.html",
        "source_file": "RegulatoryDocs/SEBI/securities-and-exchange-board-of-india-mutual-funds-regulations-2026-last-amended-on-july-7-2026.pdf",
        "chunker": "sebi_regulation",
        "citation_prefix": "SEBI MF Regs 2026",
    },
    "master-circular-for-mutual-funds": {
        "document_id": "SEBI_MASTER_CIRCULAR_MF",
        "document_name": "Master Circular for Mutual Funds (March 20, 2026)",
        "regulator": "SEBI",
        "document_type": "MASTER_CIRCULAR",
        "document_version": "March 2026",
        "publication_date": "2026-03-20",
        "effective_date": "2026-03-20",
        "effective_until": None,
        "status": "current",
        "priority": 10,
        "source_url": "https://www.sebi.gov.in/legal/master-circulars/mar-2026/master-circular-for-mutual-funds_100491.html",
        "source_file": "RegulatoryDocs/SEBI/master-circular-for-mutual-funds.pdf",
        "chunker": "master_circular",
        "citation_prefix": "SEBI Master Circular MF",
    },
    "AMFI_Codeof_Ethics_2026": {
        "document_id": "AMFI_CODE_OF_ETHICS_2026",
        "document_name": "AMFI Code of Ethics, 2026",
        "regulator": "AMFI",
        "document_type": "CODE_OF_ETHICS",
        "document_version": "2026",
        "publication_date": "2026-01-01",
        "effective_date": "2026-01-01",
        "effective_until": None,
        "status": "current",
        "priority": 10,
        "source_url": "https://www.amfiindia.com/uploads/AMFI_Codeof_Ethics_2026_c9e1d12ba1.pdf",
        "source_file": "RegulatoryDocs/AMFI/AMFI_Codeof_Ethics_2026.pdf",
        "chunker": "amfi_ethics",
        "citation_prefix": "AMFI Code of Ethics",
    },
    "Revised_Codeof_Conductfor_Mutual_Fund_Distributors_April2022": {
        "document_id": "AMFI_MFD_COC_2022",
        "document_name": "AMFI Code of Conduct for Mutual Fund Distributors (April 2022)",
        "regulator": "AMFI",
        "document_type": "CODE_OF_CONDUCT",
        "document_version": "April 2022",
        "publication_date": "2022-04-01",
        "effective_date": "2022-04-01",
        "effective_until": None,
        "status": "current",
        "priority": 10,
        "source_url": "https://www.amfiindia.com/uploads/Revised_Codeof_Conductfor_Mutual_Fund_Distributors_April2022_57d91fe1c4.pdf",
        "source_file": "RegulatoryDocs/AMFI/Revised_Codeof_Conductfor_Mutual_Fund_Distributors_April2022.pdf",
        "chunker": "amfi_coc",
        "citation_prefix": "AMFI Distributor Code",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sha256_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_page_number(char_offset: int, page_boundaries: list) -> int:
    """Given a character offset, determine the physical page number from boundaries."""
    page_num = 1
    for pb in page_boundaries:
        if char_offset >= pb.char_offset:
            page_num = pb.page_number
        else:
            break
    return page_num


def _make_chunk_id(doc_id: str, *parts: str) -> str:
    """Build a deterministic chunk ID from document ID and structural parts."""
    clean_parts = []
    for p in parts:
        if p:
            # Replace dots, spaces, parens with underscores, collapse
            cleaned = re.sub(r'[^A-Za-z0-9]+', '_', str(p)).strip('_')
            if cleaned:
                clean_parts.append(cleaned)
    chunk_id = doc_id + "_" + "_".join(clean_parts) if clean_parts else doc_id + "_root"
    return chunk_id


def _build_citation_label(prefix: str, structural_ref: str, page_num: int) -> str:
    """Build a human-readable citation label."""
    if structural_ref:
        return f"{prefix} §{structural_ref}, p.{page_num}"
    return f"{prefix}, p.{page_num}"


def _build_chunk_text(heading: str, clause_text: str, context: str = "") -> str:
    """Build chunk_text: heading + clause_text + short surrounding context."""
    parts = []
    if heading:
        parts.append(heading)
    if clause_text:
        parts.append(clause_text)
    if context:
        parts.append(context)
    return "\n\n".join(parts)


def _build_chunk_text_semantic(
    doc_name: str, chapter: str, section: str, regulation: str,
    clause: str, heading: str, clause_text: str, broader_context: str = ""
) -> str:
    """Build chunk_text_semantic: richer, retrieval-oriented composition."""
    parts = [doc_name]
    if chapter:
        parts.append(f"Chapter: {chapter}")
    if section:
        parts.append(f"Section: {section}")
    if regulation:
        parts.append(f"Regulation: {regulation}")
    if clause:
        parts.append(f"Clause: {clause}")
    if heading:
        parts.append(heading)
    if clause_text:
        parts.append(clause_text)
    if broader_context:
        parts.append(broader_context)
    return "\n\n".join(parts)


def _make_base_doc(meta: dict, source_hash: str, indexed_at: str) -> dict:
    """Build the base metadata fields common to all chunks."""
    return {
        "document_id": meta["document_id"],
        "document_name": meta["document_name"],
        "regulator": meta["regulator"],
        "document_type": meta["document_type"],
        "document_version": meta["document_version"],
        "publication_date": meta["publication_date"],
        "effective_date": meta["effective_date"],
        "effective_until": meta["effective_until"],
        "status": meta["status"],
        "priority": meta["priority"],
        "source_url": meta["source_url"],
        "source_file": meta["source_file"],
        "source_file_hash": source_hash,
        "indexed_at": indexed_at,
    }


# ---------------------------------------------------------------------------
# SEBI Regulation chunker (1996 & 2026)
# ---------------------------------------------------------------------------
# Regex patterns for structural elements in SEBI regulations
RE_CHAPTER = re.compile(r'^CHAPTER\s+([IVXLCDM]+(?:\s*[A-Z])?)\s*[-–—:]?\s*(.*)', re.IGNORECASE)
RE_REGULATION = re.compile(r'^(?:Regulation\s+)?(\d+[A-Z]?)\.\s*(.*)', re.IGNORECASE)
RE_SUB_REG = re.compile(r'^\((\d+[a-z]?)\)\s*(.*)')
RE_CLAUSE_LETTER = re.compile(r'^\(([a-z])\)\s*(.*)')
RE_SCHEDULE = re.compile(r'^SCHEDULE\s+([IVXLCDM]+)', re.IGNORECASE)


def _chunk_sebi_regulation(text: str, meta: dict, page_boundaries: list,
                            source_hash: str, indexed_at: str) -> list:
    """Chunk SEBI Regulation by Chapter → Regulation → Sub-regulation → Paragraph."""
    doc_id = meta["document_id"]
    prefix = meta["citation_prefix"]
    chunks = []
    lines = text.split('\n')

    current_chapter = ""
    current_chapter_title = ""
    current_regulation = ""
    current_regulation_title = ""
    current_sub_reg = ""
    current_clause = ""
    current_heading = ""

    # Accumulate text for current chunk
    chunk_lines = []
    chunk_start_offset = 0
    prev_offset = 0

    def _flush_chunk():
        nonlocal chunk_lines
        if not chunk_lines:
            return
        clause_text_str = '\n'.join(chunk_lines).strip()
        if not clause_text_str:
            chunk_lines = []
            return

        # Determine structural reference
        struct_ref = ""
        if current_regulation:
            struct_ref = f"Reg.{current_regulation}"
            if current_sub_reg:
                struct_ref += f"({current_sub_reg})"
            if current_clause:
                struct_ref += f"({current_clause})"

        page_num = _get_page_number(chunk_start_offset, page_boundaries)

        # Build chunk ID
        cid = _make_chunk_id(doc_id, current_chapter, current_regulation,
                             current_sub_reg, current_clause)

        # Determine chunk level
        if current_clause:
            level = "clause"
        elif current_sub_reg:
            level = "sub_regulation"
        elif current_regulation:
            level = "paragraph"
        else:
            level = "paragraph"

        heading = current_heading or current_regulation_title or current_chapter_title

        # Broader context for semantic field
        context_start = max(0, chunk_start_offset - 500)
        context_end = min(len(text), chunk_start_offset + len(clause_text_str) + 500)
        broader_context = text[context_start:context_end].strip()

        # Short context for chunk_text
        short_context_start = max(0, chunk_start_offset - 200)
        short_context_end = min(len(text), chunk_start_offset + len(clause_text_str) + 200)
        short_context = text[short_context_start:short_context_end].strip()

        chunk_doc = _make_base_doc(meta, source_hash, indexed_at)
        chunk_doc.update({
            "chunk_id": cid,
            "chunk_level": level,
            "chapter": current_chapter,
            "section": "",
            "sub_section": "",
            "regulation_number": current_regulation,
            "clause": current_clause,
            "paragraph": current_sub_reg,
            "heading": heading,
            "citation_label": _build_citation_label(prefix, struct_ref, page_num),
            "clause_text": clause_text_str,
            "chunk_text": _build_chunk_text(heading, clause_text_str, short_context),
            "chunk_text_semantic": _build_chunk_text_semantic(
                meta["document_name"], current_chapter_title, "", current_regulation,
                current_clause, heading, clause_text_str, broader_context
            ),
            "page_number": page_num,
        })
        chunks.append(chunk_doc)
        chunk_lines = []

    current_offset = 0
    for line in lines:
        line_len = len(line) + 1  # +1 for the newline

        # Check for chapter heading
        m = RE_CHAPTER.match(line.strip())
        if m:
            _flush_chunk()
            current_chapter = m.group(1).strip()
            current_chapter_title = m.group(2).strip() if m.group(2) else f"Chapter {current_chapter}"
            current_regulation = ""
            current_regulation_title = ""
            current_sub_reg = ""
            current_clause = ""
            current_heading = current_chapter_title
            chunk_start_offset = current_offset
            current_offset += line_len
            continue

        # Check for regulation heading
        m = RE_REGULATION.match(line.strip())
        if m and not line.strip().startswith('('):
            _flush_chunk()
            current_regulation = m.group(1).strip()
            current_regulation_title = m.group(2).strip() if m.group(2) else ""
            current_sub_reg = ""
            current_clause = ""
            current_heading = current_regulation_title
            chunk_start_offset = current_offset
            current_offset += line_len
            continue

        # Check for sub-regulation
        m = RE_SUB_REG.match(line.strip())
        if m and current_regulation:
            _flush_chunk()
            current_sub_reg = m.group(1).strip()
            current_clause = ""
            chunk_start_offset = current_offset
            chunk_lines.append(line.strip())
            current_offset += line_len
            continue

        # Check for clause letter
        m = RE_CLAUSE_LETTER.match(line.strip())
        if m and current_regulation:
            _flush_chunk()
            current_clause = m.group(1).strip()
            chunk_start_offset = current_offset
            chunk_lines.append(line.strip())
            current_offset += line_len
            continue

        # Regular line — accumulate
        if not chunk_lines:
            chunk_start_offset = current_offset
        chunk_lines.append(line)
        current_offset += line_len

    # Flush remaining
    _flush_chunk()

    return chunks


# ---------------------------------------------------------------------------
# Master Circular chunker
# ---------------------------------------------------------------------------
RE_MC_CHAPTER = re.compile(r'^(?:Chapter|CHAPTER)\s+([IVXLCDM\d]+)\s*[-–—:]?\s*(.*)', re.IGNORECASE)
RE_MC_SECTION = re.compile(r'^(\d+(?:\.\d+)*)\s+(.*)')
RE_MC_SUBSECTION = re.compile(r'^(\d+\.\d+(?:\.\d+)*)\s+(.*)')
RE_MC_ANNEXURE = re.compile(r'^Annexure\s+(\S+)', re.IGNORECASE)

# Master Circular has very large text — we set a max chunk size
MC_MAX_CHUNK_CHARS = 3000
MC_MIN_CHUNK_CHARS = 200


def _chunk_master_circular(text: str, meta: dict, page_boundaries: list,
                            source_hash: str, indexed_at: str) -> list:
    """Chunk Master Circular by Chapter/Topic → Sub-topic → Requirement/paragraph."""
    doc_id = meta["document_id"]
    prefix = meta["citation_prefix"]
    chunks = []

    current_chapter = ""
    current_chapter_title = ""
    current_section = ""
    current_section_title = ""
    current_subsection = ""
    current_heading = ""

    chunk_lines = []
    chunk_start_offset = 0
    chunk_counter = 0

    def _flush_chunk():
        nonlocal chunk_lines, chunk_counter
        if not chunk_lines:
            return
        clause_text_str = '\n'.join(chunk_lines).strip()
        if not clause_text_str or len(clause_text_str) < 10:
            chunk_lines = []
            return

        chunk_counter += 1
        page_num = _get_page_number(chunk_start_offset, page_boundaries)

        struct_ref = current_section or current_chapter
        if current_subsection:
            struct_ref = current_subsection

        cid = _make_chunk_id(doc_id, current_chapter, current_section,
                             current_subsection, str(chunk_counter))

        heading = current_heading or current_section_title or current_chapter_title

        # Broader context
        context_start = max(0, chunk_start_offset - 800)
        context_end = min(len(text), chunk_start_offset + len(clause_text_str) + 800)
        broader_context = text[context_start:context_end].strip()

        short_context_start = max(0, chunk_start_offset - 300)
        short_context_end = min(len(text), chunk_start_offset + len(clause_text_str) + 300)
        short_context = text[short_context_start:short_context_end].strip()

        level = "requirement" if current_subsection else "paragraph"

        chunk_doc = _make_base_doc(meta, source_hash, indexed_at)
        chunk_doc.update({
            "chunk_id": cid,
            "chunk_level": level,
            "chapter": current_chapter,
            "section": current_section,
            "sub_section": current_subsection,
            "regulation_number": "",
            "clause": "",
            "paragraph": "",
            "heading": heading,
            "citation_label": _build_citation_label(prefix, struct_ref, page_num),
            "clause_text": clause_text_str,
            "chunk_text": _build_chunk_text(heading, clause_text_str, short_context),
            "chunk_text_semantic": _build_chunk_text_semantic(
                meta["document_name"], current_chapter_title, current_section_title,
                "", "", heading, clause_text_str, broader_context
            ),
            "page_number": page_num,
        })
        chunks.append(chunk_doc)
        chunk_lines = []

    lines = text.split('\n')
    current_offset = 0

    for line in lines:
        line_len = len(line) + 1
        stripped = line.strip()

        # Chapter heading
        m = RE_MC_CHAPTER.match(stripped)
        if m:
            _flush_chunk()
            current_chapter = m.group(1).strip()
            current_chapter_title = m.group(2).strip() if m.group(2) else f"Chapter {current_chapter}"
            current_section = ""
            current_section_title = ""
            current_subsection = ""
            current_heading = current_chapter_title
            chunk_start_offset = current_offset
            current_offset += line_len
            continue

        # Annexure
        m = RE_MC_ANNEXURE.match(stripped)
        if m:
            _flush_chunk()
            current_chapter = f"Annexure {m.group(1)}"
            current_chapter_title = stripped
            current_section = ""
            current_section_title = ""
            current_subsection = ""
            current_heading = stripped
            chunk_start_offset = current_offset
            current_offset += line_len
            continue

        # Sub-section (e.g. 1.2.3)
        m = RE_MC_SUBSECTION.match(stripped)
        if m and '.' in m.group(1) and m.group(1).count('.') >= 2:
            _flush_chunk()
            current_subsection = m.group(1)
            current_heading = m.group(2).strip()
            chunk_start_offset = current_offset
            chunk_lines.append(stripped)
            current_offset += line_len
            continue

        # Section (e.g. 1.2)
        m = RE_MC_SECTION.match(stripped)
        if m and '.' in m.group(1):
            _flush_chunk()
            current_section = m.group(1)
            current_section_title = m.group(2).strip()
            current_subsection = ""
            current_heading = current_section_title
            chunk_start_offset = current_offset
            chunk_lines.append(stripped)
            current_offset += line_len
            continue

        # Accumulate — but respect max chunk size for master circular
        current_text_len = sum(len(l) + 1 for l in chunk_lines)
        if current_text_len > MC_MAX_CHUNK_CHARS and len(stripped) > 0:
            # Check if this is a "natural" break (blank line or numbered item)
            if not stripped or re.match(r'^[a-z]\)', stripped) or re.match(r'^\d+\.', stripped):
                _flush_chunk()
                chunk_start_offset = current_offset

        if not chunk_lines:
            chunk_start_offset = current_offset
        chunk_lines.append(line)
        current_offset += line_len

    _flush_chunk()
    return chunks


# ---------------------------------------------------------------------------
# AMFI Code of Ethics chunker
# ---------------------------------------------------------------------------
RE_ETHICS_SECTION = re.compile(r'^(\d+)\.\s+(.*)', re.MULTILINE)
RE_ETHICS_SUBSECTION = re.compile(r'^(\d+\.\d+)\s*(.*)')
RE_ETHICS_CLAUSE = re.compile(r'^\(([a-z])\)\s*(.*)')


def _chunk_amfi_ethics(text: str, meta: dict, page_boundaries: list,
                        source_hash: str, indexed_at: str) -> list:
    """Chunk AMFI Code of Ethics by Section → Subsection → Paragraph/Clause."""
    doc_id = meta["document_id"]
    prefix = meta["citation_prefix"]
    chunks = []

    current_section = ""
    current_section_title = ""
    current_subsection = ""
    current_clause = ""
    current_heading = ""

    chunk_lines = []
    chunk_start_offset = 0
    chunk_counter = 0

    def _flush_chunk():
        nonlocal chunk_lines, chunk_counter
        if not chunk_lines:
            return
        clause_text_str = '\n'.join(chunk_lines).strip()
        if not clause_text_str or len(clause_text_str) < 10:
            chunk_lines = []
            return

        chunk_counter += 1
        page_num = _get_page_number(chunk_start_offset, page_boundaries)

        struct_ref = ""
        if current_section:
            struct_ref = current_section
            if current_subsection:
                struct_ref = current_subsection
            if current_clause:
                struct_ref += f"({current_clause})"

        cid = _make_chunk_id(doc_id, current_section, current_subsection,
                             current_clause, str(chunk_counter))

        heading = current_heading or current_section_title
        level = "clause" if current_clause else ("paragraph" if current_subsection else "paragraph")

        context_start = max(0, chunk_start_offset - 500)
        context_end = min(len(text), chunk_start_offset + len(clause_text_str) + 500)
        broader_context = text[context_start:context_end].strip()

        short_context_start = max(0, chunk_start_offset - 200)
        short_context_end = min(len(text), chunk_start_offset + len(clause_text_str) + 200)
        short_context = text[short_context_start:short_context_end].strip()

        chunk_doc = _make_base_doc(meta, source_hash, indexed_at)
        chunk_doc.update({
            "chunk_id": cid,
            "chunk_level": level,
            "chapter": "",
            "section": current_section,
            "sub_section": current_subsection,
            "regulation_number": "",
            "clause": current_clause,
            "paragraph": "",
            "heading": heading,
            "citation_label": _build_citation_label(prefix, struct_ref, page_num),
            "clause_text": clause_text_str,
            "chunk_text": _build_chunk_text(heading, clause_text_str, short_context),
            "chunk_text_semantic": _build_chunk_text_semantic(
                meta["document_name"], "", current_section_title, "",
                current_clause, heading, clause_text_str, broader_context
            ),
            "page_number": page_num,
        })
        chunks.append(chunk_doc)
        chunk_lines = []

    lines = text.split('\n')
    current_offset = 0

    for line in lines:
        line_len = len(line) + 1
        stripped = line.strip()

        # Subsection (e.g. 6.4)
        m = RE_ETHICS_SUBSECTION.match(stripped)
        if m and '.' in m.group(1):
            _flush_chunk()
            current_subsection = m.group(1)
            current_clause = ""
            title = m.group(2).strip() if m.group(2) else ""
            current_heading = title
            chunk_start_offset = current_offset
            chunk_lines.append(stripped)
            current_offset += line_len
            continue

        # Section (e.g. 6. Professional Selling Practices)
        m = RE_ETHICS_SECTION.match(stripped)
        if m and not '.' in m.group(1):
            _flush_chunk()
            current_section = m.group(1)
            current_section_title = m.group(2).strip() if m.group(2) else ""
            current_subsection = ""
            current_clause = ""
            current_heading = current_section_title
            chunk_start_offset = current_offset
            current_offset += line_len
            continue

        # Clause letter
        m = RE_ETHICS_CLAUSE.match(stripped)
        if m:
            _flush_chunk()
            current_clause = m.group(1)
            chunk_start_offset = current_offset
            chunk_lines.append(stripped)
            current_offset += line_len
            continue

        if not chunk_lines:
            chunk_start_offset = current_offset
        chunk_lines.append(line)
        current_offset += line_len

    _flush_chunk()
    return chunks


# ---------------------------------------------------------------------------
# AMFI Code of Conduct chunker  (clause-level granularity)
# ---------------------------------------------------------------------------
# Pattern: Roman numeral sections (I, II, III, IV, V)
RE_COC_SECTION = re.compile(r'^(I{1,3}|IV|V)\.\s*(.*)')
# Pattern: numbered subsections (1., 2., 3., etc.)
RE_COC_NUMBERED = re.compile(r'^(\d+)\.\s*(.*)')
# Pattern: lettered clauses (a., b., c., etc. OR a), b), c))
RE_COC_CLAUSE = re.compile(r'^([a-z])[\.\)]\s*(.*)')
# Pattern: Roman sub-items (i., ii., iii., iv., v.)
RE_COC_ROMAN_SUB = re.compile(r'^(i{1,3}|iv|vi{0,3}|ix|x)[\.\)]\s*(.*)', re.IGNORECASE)


def _chunk_amfi_coc(text: str, meta: dict, page_boundaries: list,
                     source_hash: str, indexed_at: str) -> list:
    """
    Chunk AMFI Distributor Code of Conduct at clause level.
    e.g. II.4.g as its own chunk — this document has the most precisely
    citable language for Vigil's core detection categories.
    """
    doc_id = meta["document_id"]
    prefix = meta["citation_prefix"]
    chunks = []

    current_roman = ""
    current_roman_title = ""
    current_number = ""
    current_number_title = ""
    current_letter = ""
    current_sub_roman = ""
    current_heading = ""

    chunk_lines = []
    chunk_start_offset = 0

    def _flush_chunk():
        nonlocal chunk_lines
        if not chunk_lines:
            return
        # If no roman section yet (e.g. top document title), do not produce an un-citable root chunk
        if not current_roman:
            chunk_lines = []
            return

        clause_text_str = '\n'.join(chunk_lines).strip()
        if not clause_text_str or len(clause_text_str) < 5:
            chunk_lines = []
            return

        page_num = _get_page_number(chunk_start_offset, page_boundaries)

        # Build structural reference
        struct_parts = []
        if current_roman:
            struct_parts.append(current_roman)
        if current_number:
            struct_parts.append(current_number)
        if current_letter:
            struct_parts.append(current_letter)
        if current_sub_roman:
            struct_parts.append(current_sub_roman)
        struct_ref = ".".join(struct_parts)

        # The clause field for this document
        clause_field = struct_ref

        cid = _make_chunk_id(doc_id, current_roman, current_number,
                             current_letter, current_sub_roman)

        heading = current_heading or current_number_title or current_roman_title

        if current_sub_roman:
            level = "clause"
        elif current_letter:
            level = "clause"
        elif current_number:
            level = "sub_regulation"
        else:
            level = "paragraph"

        context_start = max(0, chunk_start_offset - 500)
        context_end = min(len(text), chunk_start_offset + len(clause_text_str) + 500)
        broader_context = text[context_start:context_end].strip()

        short_context_start = max(0, chunk_start_offset - 200)
        short_context_end = min(len(text), chunk_start_offset + len(clause_text_str) + 200)
        short_context = text[short_context_start:short_context_end].strip()

        chunk_doc = _make_base_doc(meta, source_hash, indexed_at)
        chunk_doc.update({
            "chunk_id": cid,
            "chunk_level": level,
            "chapter": "",
            "section": current_roman,
            "sub_section": current_number,
            "regulation_number": "",
            "clause": clause_field,
            "paragraph": "",
            "heading": heading,
            "citation_label": _build_citation_label(prefix, struct_ref, page_num),
            "clause_text": clause_text_str,
            "chunk_text": _build_chunk_text(heading, clause_text_str, short_context),
            "chunk_text_semantic": _build_chunk_text_semantic(
                meta["document_name"], "", current_roman_title, "",
                clause_field, heading, clause_text_str, broader_context
            ),
            "page_number": page_num,
        })
        chunks.append(chunk_doc)
        chunk_lines = []

    lines = text.split('\n')
    current_offset = 0

    for line in lines:
        line_len = len(line) + 1
        stripped = line.strip()

        # Roman section (I., II., III., etc.)
        m = RE_COC_SECTION.match(stripped)
        if m:
            _flush_chunk()
            current_roman = m.group(1)
            current_roman_title = m.group(2).strip() if m.group(2) else ""
            current_number = ""
            current_number_title = ""
            current_letter = ""
            current_sub_roman = ""
            current_heading = current_roman_title
            chunk_start_offset = current_offset
            current_offset += line_len
            continue

        # If we have a Roman section but no title yet, check if this line is the title
        if current_roman and not current_roman_title and not current_number and not current_letter:
            if not RE_COC_NUMBERED.match(stripped) and not RE_COC_CLAUSE.match(stripped):
                current_roman_title = stripped
                current_heading = stripped
                current_offset += line_len
                continue

        # Numbered subsection (1., 2., etc.)
        m = RE_COC_NUMBERED.match(stripped)
        if m and current_roman:
            _flush_chunk()
            current_number = m.group(1)
            current_number_title = m.group(2).strip() if m.group(2) else ""
            current_letter = ""
            current_sub_roman = ""
            current_heading = current_number_title
            chunk_start_offset = current_offset
            chunk_lines.append(stripped)
            current_offset += line_len
            continue

        # Letter clause (a., b., c., etc.)
        m = RE_COC_CLAUSE.match(stripped)
        if m and (current_number or current_roman):
            _flush_chunk()
            current_letter = m.group(1)
            current_sub_roman = ""
            chunk_start_offset = current_offset
            chunk_lines.append(stripped)
            current_offset += line_len
            continue

        # Roman sub-item (i., ii., iii.)
        m = RE_COC_ROMAN_SUB.match(stripped)
        if m and current_letter:
            _flush_chunk()
            current_sub_roman = m.group(1).lower()
            chunk_start_offset = current_offset
            chunk_lines.append(stripped)
            current_offset += line_len
            continue

        if not chunk_lines:
            chunk_start_offset = current_offset
        chunk_lines.append(line)
        current_offset += line_len

    _flush_chunk()
    return chunks


# ---------------------------------------------------------------------------
# Dispatch + main
# ---------------------------------------------------------------------------
CHUNKERS = {
    "sebi_regulation": _chunk_sebi_regulation,
    "master_circular": _chunk_master_circular,
    "amfi_ethics": _chunk_amfi_ethics,
    "amfi_coc": _chunk_amfi_coc,
}


def chunk_document(pdf_stem: str, extraction_result) -> list:
    """Chunk a single extracted document and return list of chunk dicts."""
    if pdf_stem not in DOC_REGISTRY:
        raise ValueError(f"Unknown document: {pdf_stem}")

    meta = DOC_REGISTRY[pdf_stem]
    chunker_name = meta["chunker"]
    chunker_fn = CHUNKERS[chunker_name]

    # Compute source file hash
    source_path = PROJECT_ROOT / meta["source_file"]
    source_hash = _sha256_file(source_path)

    indexed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    text = extraction_result.clean_text
    page_boundaries = extraction_result.page_boundaries

    chunks = chunker_fn(text, meta, page_boundaries, source_hash, indexed_at)

    logger.info(f"  Chunked {pdf_stem}: {len(chunks)} chunks")
    return chunks


def chunk_all(extraction_results: dict) -> dict:
    """
    Chunk all 5 documents. Returns dict mapping pdf_stem -> chunk list.
    Also writes JSON files to backend/indexing/chunks/.
    """
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    all_chunks = {}
    for pdf_stem, ext_result in extraction_results.items():
        chunks = chunk_document(pdf_stem, ext_result)
        all_chunks[pdf_stem] = chunks

        # Deduplicate chunk IDs within this document
        seen_ids = {}
        for i, chunk in enumerate(chunks):
            cid = chunk["chunk_id"]
            if cid in seen_ids:
                # Append counter to make unique
                counter = 2
                while f"{cid}_{counter}" in seen_ids:
                    counter += 1
                new_cid = f"{cid}_{counter}"
                chunk["chunk_id"] = new_cid
                cid = new_cid
            seen_ids[cid] = i

        # Write JSON
        out_path = CHUNKS_DIR / f"{pdf_stem}.json"
        out_path.write_text(
            json.dumps(chunks, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"  Written: {out_path.name} ({len(chunks)} chunks)")

    # Summary
    print("\n" + "=" * 60)
    print("CHUNKING SUMMARY")
    print("=" * 60)
    total = 0
    for stem, chunks in all_chunks.items():
        short = stem[:60] + "…" if len(stem) > 60 else stem
        print(f"  {short}: {len(chunks)} chunks")
        total += len(chunks)
    print(f"\n  Total: {total} chunks across {len(all_chunks)} documents\n")

    return all_chunks


def main():
    """Standalone run — requires extraction results. Use run_pipeline.py instead."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("=" * 60)
    print("STEPS 4-5 — Chunking (requires extraction first)")
    print("=" * 60)
    print("Run via run_pipeline.py for the full pipeline.")


if __name__ == "__main__":
    main()
