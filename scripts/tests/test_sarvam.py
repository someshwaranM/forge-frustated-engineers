import json
import os
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / "backend" / ".env")

try:
    # Drop a real short, non-production test clip here manually before running this test.
    audio = Path(__file__).parent / "sample_audio" / "test_clip.wav"
    with audio.open("rb") as file:
        response = requests.post(
            "https://api.sarvam.ai/speech-to-text",
            headers={"api-subscription-key": os.environ["SARVAM_API_KEY"]},
            files={"file": (audio.name, file, "audio/wav")},
            data={"model": "saaras:v4", "mode": "transcribe"},
        )
    response.raise_for_status()
    print(json.loads(response.text).get("transcript", response.text))
    print("[PASS] Sarvam connection OK")
except Exception as exc:
    print(f"[FAIL] Sarvam connection failed: {exc}")
