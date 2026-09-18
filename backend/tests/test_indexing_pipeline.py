"""
Vigil — Test Runner: Indexing Pipeline

Runs the full regulatory indexing pipeline (Steps 3-7):
  1. Clears extracted/ and chunks/ directories
  2. Step 3  — Extracts text from all 5 regulatory PDFs
  3. Steps 4-5 — Chunks all 5 documents
  4. Step 6  — Validation gate (halts on failure)
  5. Step 7  — Wipes and reindexes Elasticsearch

Usage (from the project root d:\\vigil):
    python -m backend.tests.test_indexing_pipeline
  or:
    python backend/tests/test_indexing_pipeline.py
"""

import sys
import logging
from pathlib import Path

# Ensure project root (d:\\vigil) is on sys.path so all backend imports resolve
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.indexing.run_pipeline import run_pipeline


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=" * 70)
    print("  VIGIL — Indexing Pipeline Test Runner")
    print("=" * 70)
    print()
    print("This test runner will:")
    print("  1. Clear extracted/ and chunks/ directories")
    print("  2. Re-extract text from all 5 regulatory PDFs (Step 3)")
    print("  3. Re-chunk all 5 documents (Steps 4-5)")
    print("  4. Run the validation gate — halt if any chunk fails (Step 6)")
    print("  5. Wipe and reindex Elasticsearch 'regulations' index (Step 7)")
    print()

    try:
        summary = run_pipeline()
    except SystemExit as exc:
        print(f"\n[FAIL] Pipeline halted with exit code {exc.code}.")
        sys.exit(exc.code)
    except Exception as exc:
        logging.exception(f"Unexpected error during indexing pipeline: {exc}")
        sys.exit(1)

    # --- Post-run verification summary ---
    print("=" * 70)
    print("  INDEXING PIPELINE TEST — VERIFICATION SUMMARY")
    print("=" * 70)

    total_chunks = sum(info["chunks"] for info in summary.values())
    total_pages  = sum(info["pages_total"] for info in summary.values())
    total_flagged = sum(info["pages_flagged"] for info in summary.values())

    print(f"  Documents processed : {len(summary)}")
    print(f"  Total pages         : {total_pages}")
    print(f"  Pages flagged       : {total_flagged}")
    print(f"  Total chunks indexed: {total_chunks}")
    print()

    for stem, info in summary.items():
        short = stem[:60] + "…" if len(stem) > 60 else stem
        status = "[PASS]" if info["pages_flagged"] == 0 else "[WARN]"
        print(f"  {status} {short}")
        print(f"         pages: {info['pages_total']} total | "
              f"{info['pages_extracted']} extracted | "
              f"{info['pages_flagged']} flagged")
        print(f"         chunks: {info['chunks']}")

    print()
    if total_flagged == 0:
        print("[PASS] All pages passed quality checks. Pipeline completed successfully.")
    else:
        print(f"[WARN] {total_flagged} page(s) were flagged but pipeline continued.")

    print()


if __name__ == "__main__":
    main()
