import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / "backend" / ".env")

try:
    model = os.environ.get("GEMINI_MODEL_ID", "").strip()
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not model or "<REPLACE_ME>" in model:
        raise ValueError("GEMINI_MODEL_ID is missing or still set to <REPLACE_ME>")
    if not api_key or "<REPLACE_ME>" in api_key:
        raise ValueError("GEMINI_API_KEY is missing or still set to <REPLACE_ME>")

    # Accept both "gemini-2.5-flash" and the resource form
    # "models/gemini-2.5-flash" in .env.
    model = model.removeprefix("models/")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = json.dumps({"contents": [{"parts": [{"text": "Reply with the single word: OK"}]}]}).encode()
    request = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
    )
    with urlopen(request) as response:
        result = json.loads(response.read().decode())
    text = result["candidates"][0]["content"]["parts"][0]["text"]
    print(text)
    print("[PASS] Gemini connection OK")
except HTTPError as exc:
    details = exc.read().decode("utf-8", errors="replace").strip()
    print(f"[FAIL] Gemini connection failed: HTTP {exc.code}: {details or exc.reason}")
    print(f"Model used: {os.environ.get('GEMINI_MODEL_ID', '<not set>')}")
except Exception as exc:
    print(f"[FAIL] Gemini connection failed: {exc}")
    print(f"Model used: {os.environ.get('GEMINI_MODEL_ID', '<not set>')}")
