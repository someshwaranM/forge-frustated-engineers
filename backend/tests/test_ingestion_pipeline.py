"""
Vigil — Test Runner: Audio Ingestion Pipeline

Scans CallAudio/ for all .wav files and runs each through the full
ingestion pipeline (Phase 5):
  1. Filename validation & MySQL RM/Customer lookup
  2. File stability check
  3. Audio format & duration validation
  4. Sarvam transcription + diarization
  5. Gemini-primary speaker role mapping
  6. Elasticsearch document preparation (calls schema)
  7. Index into 'calls' index + read-back verification
  8. File movement to CallAudio-Archive/ on success, or
     CallAudio-Failed/ with sidecar error log on failure

Usage (from the project root d:\\vigil):
    python -m backend.tests.test_ingestion_pipeline
  or:
    python backend/tests/test_ingestion_pipeline.py

To test a specific file, set the VIGIL_TEST_FILE env var:
    set VIGIL_TEST_FILE=CallAudio/RM001_CUST001_20260310_1030.wav
    python backend/tests/test_ingestion_pipeline.py
"""

import os
import sys
import logging
from pathlib import Path

# Ensure project root (d:\\vigil) is on sys.path so all backend imports resolve
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.ingestion.process_now import process_all_pending
from backend.ingestion.pipeline import (
    process_audio_file,
    CALL_AUDIO_DIR,
    ARCHIVE_DIR,
    FAILED_DIR,
)


def _print_result(result: dict, idx: int = 1, total: int = 1) -> None:
    """Pretty-prints a single pipeline result."""
    status = result.get("status", "UNKNOWN")
    filename = result.get("file", "")

    print(f"\n  [{idx}/{total}] File: {filename}")

    if status == "SUCCESS":
        doc = result.get("document", {})
        print(f"  --> [SUCCESS] Indexed as '{result.get('call_id')}'")
        print(f"       Language        : {doc.get('language')}")
        print(f"       Duration        : {doc.get('duration_seconds')}s")
        print(f"       Speaker Mapping : {doc.get('speaker_mapping_method')}")
        print(f"       Segments        : {len(doc.get('transcript_segments', []))}")
        print(f"       Archived To     : {result.get('archive_path')}")
        print(f"       Mapping Reasoning: {result.get('speaker_reasoning', '')[:120]}")
    else:
        reason = result.get("reason", "UNKNOWN")
        details = result.get("details", "")
        print(f"  --> [REJECTED] Reason : {reason}")
        if details:
            print(f"       Details : {details[:200]}")
        print(f"       Moved To: CallAudio-Failed/")


def run_single_file_test(file_path: str) -> dict:
    """Run the ingestion pipeline against a single specified file."""
    src = Path(file_path)
    if not src.exists():
        print(f"[ERROR] File not found: {src}")
        sys.exit(1)

    print(f"\n  Testing single file: {src.name}")
    result = process_audio_file(src)
    _print_result(result)
    return result


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=" * 70)
    print("  VIGIL — Audio Ingestion Pipeline Test Runner")
    print("=" * 70)
    print()
    print("  CallAudio Dir  :", CALL_AUDIO_DIR)
    print("  Archive Dir    :", ARCHIVE_DIR)
    print("  Failed Dir     :", FAILED_DIR)
    print()

    # Allow targeting a specific file via env var
    test_file = os.environ.get("VIGIL_TEST_FILE", "").strip()

    if test_file:
        # Single-file mode
        print(f"  Mode: Single-file (VIGIL_TEST_FILE={test_file})")
        print()
        result = run_single_file_test(test_file)
        results = [result]
    else:
        # Batch mode — process all .wav files in CallAudio/
        print("  Mode: Batch (all .wav files in CallAudio/)")
        print("  (Set VIGIL_TEST_FILE=<path> to test a specific file instead)")
        print()

        CALL_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        wav_files = sorted(list(CALL_AUDIO_DIR.glob("*.wav")))

        if not wav_files:
            print(f"  [INFO] No .wav files found in '{CALL_AUDIO_DIR}'.")
            print("  Place one or more .wav files in CallAudio/ and re-run.")
            print()
            sys.exit(0)

        print(f"  Found {len(wav_files)} .wav file(s) to process.")
        results = process_all_pending()

    # --- Post-run summary ---
    print()
    print("=" * 70)
    print("  INGESTION PIPELINE TEST — RESULT SUMMARY")
    print("=" * 70)

    success_count = sum(1 for r in results if r.get("status") == "SUCCESS")
    failed_count  = sum(1 for r in results if r.get("status") == "FAILED")

    print(f"  Total processed : {len(results)}")
    print(f"  Successful      : {success_count}")
    print(f"  Failed/Rejected : {failed_count}")
    print()

    if failed_count == 0 and success_count > 0:
        print("[PASS] All files processed successfully.")
    elif success_count == 0 and failed_count > 0:
        print("[FAIL] All files were rejected. Check logs and CallAudio-Failed/.")
    elif failed_count > 0:
        print(f"[PARTIAL] {success_count} succeeded, {failed_count} rejected. "
              "Check CallAudio-Failed/ for sidecar error logs.")

    print()


if __name__ == "__main__":
    main()
