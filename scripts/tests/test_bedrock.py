import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / "backend" / ".env")

try:
    required = {
        "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID"),
        "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY"),
        "AWS_REGION": os.environ.get("AWS_REGION"),
        "AWS_BEDROCK_MODEL_ID": os.environ.get("AWS_BEDROCK_MODEL_ID"),
    }
    placeholder = {key: value for key, value in required.items() if value is None or str(value).strip() == "<REPLACE_ME>"}
    if placeholder:
        raise ValueError(f"Placeholder AWS config detected: {placeholder}")

    import boto3
    client = boto3.client("bedrock-runtime", region_name=os.environ["AWS_REGION"])
    response = client.converse(
        modelId=os.environ["AWS_BEDROCK_MODEL_ID"],
        messages=[{"role": "user", "content": [{"text": "Reply with the single word: OK"}]}],
    )
    print(response["output"]["message"]["content"][0]["text"])
    print("[PASS] Bedrock connection OK")
except Exception as exc:
    reason = str(exc)
    if any(word in reason.lower() for word in ("auth", "accessdenied", "credential", "unauthorized", "forbidden")):
        reason = f"authentication or access error: {reason}"
    print(f"[FAIL] Bedrock connection failed: {reason}")
