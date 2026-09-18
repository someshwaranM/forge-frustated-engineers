"""
Vigil — Phase 5: One-Shot Audio Ingestion Processor.

Processes all .wav files currently present in CallAudio/ and exits.
Safe for live demos, predictable testing, and batch processing.
"""

import sys
import logging
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.ingestion.pipeline import (
    process_audio_file,
    CALL_AUDIO_DIR,
    ARCHIVE_DIR,
    FAILED_DIR,
)

logger = logging.getLogger("vigil.ingestion.process_now")


def process_all_pending() -> list:
    """Scans CallAudio/ for .wav files and processes each through the pipeline."""
    CALL_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)

    wav_files = sorted(list(CALL_AUDIO_DIR.glob("*.wav")))
    if not wav_files:
        print(f"No .wav files found in '{CALL_AUDIO_DIR}'. Nothing to process.")
        return []

    print("=" * 70)
    print(f"  VIGIL — Phase 5: Processing {len(wav_files)} Pending File(s)")
    print("=" * 70)

    results = []
    for idx, audio_file in enumerate(wav_files, start=1):
        print(f"\n[{idx}/{len(wav_files)}] Processing: {audio_file.name}...")
        try:
            res = process_audio_file(audio_file)
            results.append(res)
            if res.get("status") == "SUCCESS":
                doc = res["document"]
                print(f"  --> [SUCCESS] Indexed as '{res['call_id']}'")
                print(f"      Language:         {doc['language']}")
                print(f"      Duration:         {doc['duration_seconds']}s")
                print(f"      Speaker Mapping:  {doc['speaker_mapping_method']}")
                print(f"      Segments:         {len(doc['transcript_segments'])}")
                print(f"      Archived To:      {res['archive_path']}")
            else:
                print(f"  --> [REJECTED] Reason: {res.get('reason')}")
                print(f"      Details:  {res.get('details')}")
                print(f"      Moved To: CallAudio-Failed/")
        except Exception as exc:
            logger.exception(f"Unhandled error processing {audio_file.name}: {exc}")
            print(f"  --> [ERROR] Unhandled exception: {exc}")
            results.append({"status": "FAILED", "file": audio_file.name, "reason": "UNHANDLED_EXCEPTION", "details": str(exc)})

    print("\n" + "=" * 70)
    print("  BATCH PROCESSING COMPLETE")
    print("=" * 70)
    success_count = sum(1 for r in results if r.get("status") == "SUCCESS")
    failed_count = sum(1 for r in results if r.get("status") == "FAILED")
    print(f"  Successful: {success_count}")
    print(f"  Failed:     {failed_count}")
    print("=" * 70)

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    process_all_pending()
