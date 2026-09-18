"""
Step 8 — Single pipeline entrypoint.

Runs Steps 3 through 7 in order for all 5 documents.
Every run is a full, clean rebuild:
  a) Delete everything inside extracted/ and chunks/ (keep folders).
  b) Re-run extraction (Step 3) for all 5 PDFs.
  c) Re-run chunking (Steps 4-5) for all 5 PDFs.
  d) Run validation gate (Step 6) — halt if it fails.
  e) Wipe and reindex Elasticsearch (Step 7).

Usage:
    python -m backend.indexing.run_pipeline
"""

import sys
import shutil
import logging
import time
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.indexing.extract import extract_all, EXTRACTED_DIR
from backend.indexing.chunk import chunk_all, CHUNKS_DIR
from backend.indexing.validate import validate_chunks
from backend.indexing.index_to_es import wipe_and_index


def _clear_directory(dirpath: Path) -> None:
    """Delete all files inside a directory, keeping the directory itself."""
    if dirpath.exists():
        for item in dirpath.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
    dirpath.mkdir(parents=True, exist_ok=True)


def run_pipeline() -> dict:
    """
    Execute the full indexing pipeline.
    Returns a summary dict with counts per document.
    """
    start_time = time.time()

    print("=" * 70)
    print("  VIGIL — Regulatory Indexing Pipeline (Full Rebuild)")
    print("=" * 70)
    print()

    # ---------------------------------------------------------------
    # (a) Clean slate
    # ---------------------------------------------------------------
    print(">> Clearing extracted/ and chunks/ directories…")
    _clear_directory(EXTRACTED_DIR)
    _clear_directory(CHUNKS_DIR)
    print("  Done.\n")

    # ---------------------------------------------------------------
    # (b) Step 3 — Extraction
    # ---------------------------------------------------------------
    print(">> STEP 3 — Extracting text from all 5 PDFs…\n")
    extraction_results = extract_all()  # Raises on flagged pages

    # ---------------------------------------------------------------
    # (c) Steps 4-5 — Chunking
    # ---------------------------------------------------------------
    print("\n>> STEPS 4-5 — Chunking all 5 documents…\n")
    all_chunks = chunk_all(extraction_results)

    # ---------------------------------------------------------------
    # (d) Step 6 — Validation gate
    # ---------------------------------------------------------------
    print("\n>> STEP 6 — Running validation gate…\n")
    passed, validation_results = validate_chunks(all_chunks)
    if not passed:
        print("\n[FAIL] PIPELINE HALTED — validation gate failed.")
        print("   Fix the issues above before re-running.\n")
        raise SystemExit(1)

    # ---------------------------------------------------------------
    # (e) Step 7 — Wipe and reindex
    # ---------------------------------------------------------------
    print("\n>> STEP 7 — Wiping and reindexing Elasticsearch…\n")
    indexed_count = wipe_and_index()

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("  PIPELINE COMPLETE")
    print("=" * 70)
    print(f"  Total documents indexed: {indexed_count}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print()

    summary = {}
    for stem, chunks in all_chunks.items():
        ext_r = extraction_results[stem]
        summary[stem] = {
            "pages_total": ext_r.pages_total,
            "pages_extracted": ext_r.pages_extracted,
            "pages_flagged": ext_r.pages_flagged,
            "chunks": len(chunks),
            "stripped_headers_footers": ext_r.stripped_headers_footers,
        }

    print("  Per-document summary:")
    for stem, info in summary.items():
        short = stem[:55] + "…" if len(stem) > 55 else stem
        print(f"    {short}")
        print(f"      pages: {info['pages_total']} total, "
              f"{info['pages_extracted']} extracted, "
              f"{info['pages_flagged']} flagged")
        print(f"      chunks: {info['chunks']}")
    print()

    return summary


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    run_pipeline()


if __name__ == "__main__":
    main()
