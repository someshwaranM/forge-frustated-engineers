"""
Vigil — Phase 5: Continuous CallAudio/ Folder Watcher.

Continuously watches the CallAudio/ directory using watchdog.
When a new .wav file is created/copied into the directory, it waits for file
stability and triggers the full pipeline automatically:
  Phase 5 (Ingestion) → Phase 6 (Detection) → Phase 7 (Investigation)
"""

import sys
import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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

logger = logging.getLogger("vigil.ingestion.watch_folder")

CANDIDATES_DIR = PROJECT_ROOT / "backend" / "compliance" / "candidates"


def _run_detection(call_doc: dict) -> dict | None:
    """Phase 6: Build violation candidates for a transcribed call document."""
    try:
        from backend.compliance.candidate_builder import build_candidates_for_call
        logger.info(f"[PIPELINE] Phase 6 — Running detection for call: {call_doc.get('call_id')}")
        report = build_candidates_for_call(call_doc, output_dir=CANDIDATES_DIR)
        candidate_count = report.get("candidate_count", 0)
        logger.info(f"[PIPELINE] Phase 6 complete — {candidate_count} candidate(s) found.")
        return report
    except Exception as exc:
        logger.error(f"[PIPELINE] Phase 6 detection failed for {call_doc.get('call_id')}: {exc}")
        return None


def _run_investigation(call_id: str) -> None:
    """Phase 7: Run investigator agent on the candidate file produced by Phase 6."""
    candidate_file = CANDIDATES_DIR / f"{call_id}.json"
    if not candidate_file.exists():
        logger.warning(f"[PIPELINE] Phase 7 skipped — candidate file not found: {candidate_file}")
        return
    try:
        from backend.agents.investigator_agent import InvestigatorAgent
        logger.info(f"[PIPELINE] Phase 7 — Running investigation for call: {call_id}")
        agent = InvestigatorAgent()
        result = agent.process_call(candidate_file)
        confirmed = result.get("confirmed_count", 0)
        dismissed = result.get("dismissed_count", 0)
        logger.info(
            f"[PIPELINE] Phase 7 complete — {confirmed} confirmed finding(s), "
            f"{dismissed} dismissed."
        )
    except Exception as exc:
        logger.error(f"[PIPELINE] Phase 7 investigation failed for {call_id}: {exc}")


class CallAudioFileHandler(FileSystemEventHandler):
    """Handles file creation events in CallAudio/ and runs the full pipeline chain."""

    def __init__(self):
        super().__init__()
        self._processing = set()

    def on_created(self, event):
        if event.is_directory:
            return
        p = Path(event.src_path)
        if p.suffix.lower() != ".wav":
            return

        if str(p) in self._processing:
            return

        self._processing.add(str(p))
        try:
            logger.info(f"[WATCHER EVENT] Detected new audio file: {p.name}")

            # ── Phase 5: Ingestion ────────────────────────────────────────────
            result = process_audio_file(p)

            if result.get("status") != "SUCCESS":
                logger.warning(
                    f"[PIPELINE] Ingestion failed for {p.name} "
                    f"({result.get('reason')}). Skipping detection & investigation."
                )
                return

            call_doc = result.get("document", {})
            call_id = result.get("call_id", call_doc.get("call_id", ""))

            # ── Phase 6: Detection ────────────────────────────────────────────
            detection_report = _run_detection(call_doc)

            if detection_report is None:
                logger.warning(
                    f"[PIPELINE] Detection returned no report for {call_id}. "
                    "Skipping investigation."
                )
                return

            # ── Phase 7: Investigation ────────────────────────────────────────
            # Always run investigation so the call is marked complete even if
            # candidate_count == 0 (produces an audit trail with 0 findings).
            _run_investigation(call_id)

        except Exception as exc:
            logger.error(f"[WATCHER ERROR] Unhandled error processing {p.name}: {exc}")
        finally:
            self._processing.discard(str(p))


def start_watcher():
    """Starts continuous filesystem watcher on CallAudio/."""
    CALL_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("  VIGIL — Continuous Audio Ingestion Watcher")
    print(f"  Monitoring folder: {CALL_AUDIO_DIR.resolve()}")
    print("  Press Ctrl+C to stop.")
    print("=" * 70)

    event_handler = CallAudioFileHandler()
    observer = Observer()
    observer.schedule(event_handler, path=str(CALL_AUDIO_DIR), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping folder watcher...")
        observer.stop()
    observer.join()
    print("Folder watcher stopped.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    start_watcher()
