#!/usr/bin/env python3
"""
Bedrock Connectivity & Diagnostic Tool
Tests AWS Bedrock runtime connectivity, credentials, region, and model invocation.
"""

import os
import sys
import time
import json
from pathlib import Path
from dotenv import load_dotenv

# Load backend/.env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

def mask_key(val: str, prefix_len: int = 4, suffix_len: int = 4) -> str:
    if not val:
        return "(empty)"
    if len(val) <= prefix_len + suffix_len:
        return "***"
    return f"{val[:prefix_len]}...{val[-suffix_len:]}"

def test_connectivity():
    print("=" * 60)
    print("  AWS Bedrock Connectivity & Configuration Diagnostic")
    print("=" * 60)
    print(f"Loaded .env from: {env_path}\n")

    access_key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    region = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "").strip()
    model_id = os.getenv("AWS_BEDROCK_MODEL_ID", "").strip()
    session_token = os.getenv("AWS_SESSION_TOKEN", "").strip()

    print("[1] Configuration Summary:")
    print(f"  - AWS_REGION / AWS_DEFAULT_REGION : {region or '(NOT SET)'}")
    print(f"  - AWS_BEDROCK_MODEL_ID             : {model_id or '(NOT SET)'}")
    print(f"  - AWS_ACCESS_KEY_ID               : {mask_key(access_key)} (length: {len(access_key)})")
    print(f"  - AWS_SECRET_ACCESS_KEY           : {'[SET]' if secret_key else '(NOT SET)'} (length: {len(secret_key)})")
    print(f"  - AWS_SESSION_TOKEN               : {'[SET]' if session_token else '(NOT SET)'} (length: {len(session_token)})")
    print()

    # Pre-check credential type
    if access_key.startswith("ASIA"):
        print("[!] NOTICE: AWS_ACCESS_KEY_ID starts with 'ASIA', indicating TEMPORARY STS credentials.")
        if not session_token:
            print("  CRITICAL: Temporary credentials (ASIA...) REQUIRE 'AWS_SESSION_TOKEN'.")
            print("  Without AWS_SESSION_TOKEN, AWS rejects requests with UnrecognizedClientException / InvalidClientTokenId.")
            print()

    if not access_key or not secret_key:
        print("[FAIL] Missing AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY in .env.")
        return False

    if not region:
        print("[FAIL] Neither AWS_REGION nor AWS_DEFAULT_REGION is configured in .env.")
        return False

    if not model_id:
        print("[FAIL] AWS_BEDROCK_MODEL_ID is not configured in .env.")
        return False

    import boto3

    client_kwargs = {
        "region_name": region,
        "aws_access_key_id": access_key,
        "aws_secret_access_key": secret_key,
    }
    if session_token:
        client_kwargs["aws_session_token"] = session_token

    # Step 2: STS Caller Identity check
    print("[2] Testing AWS STS Authentication...")
    try:
        sts = boto3.client("sts", **client_kwargs)
        caller = sts.get_caller_identity()
        print("  [SUCCESS] AWS Identity Verified:")
        print(f"    - Account : {caller.get('Account')}")
        print(f"    - UserId  : {caller.get('UserId')}")
        print(f"    - Arn     : {caller.get('Arn')}")
    except Exception as e:
        print(f"  [FAIL] STS authentication error: {type(e).__name__} - {e}")
        if access_key.startswith("ASIA") and not session_token:
            print("\n  -> Solution: Add your 'AWS_SESSION_TOKEN' from the AWS CLI/Console to backend/.env")
        return False

    # Step 3: Bedrock Model Invocation check
    print(f"\n[3] Testing Bedrock Runtime Invocation with '{model_id}' in region '{region}'...")
    try:
        bedrock = boto3.client("bedrock-runtime", **client_kwargs)
        start_time = time.time()

        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 50,
            "temperature": 0.0,
            "messages": [{"role": "user", "content": "Respond with only: Bedrock connectivity verified."}],
        }

        resp = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps(payload),
            contentType="application/json",
            accept="application/json",
        )
        latency = round((time.time() - start_time) * 1000, 2)
        resp_body = json.loads(resp["body"].read().decode("utf-8"))
        text = resp_body.get("content", [{}])[0].get("text", "").strip()

        print(f"  [SUCCESS] Bedrock Model Invocation succeeded in {latency} ms!")
        print(f"  - Model response: \"{text}\"")
        print("\n" + "=" * 60)
        print("  ALL BEDROCK CONNECTIVITY CHECKS PASSED")
        print("=" * 60)
        return True
    except Exception as e:
        print(f"  [FAIL] Bedrock invoke_model error: {type(e).__name__} - {e}")
        
        # Test if Claude 3 Haiku works on this account
        fallback_model = "us.anthropic.claude-3-haiku-20240307-v1:0"
        fallback_region = "us-east-1"
        print(f"\n[4] Probing alternative model access ('{fallback_model}' in '{fallback_region}')...")
        try:
            fb_client = boto3.client(
                "bedrock-runtime",
                region_name=fallback_region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
            )
            fb_resp = fb_client.invoke_model(
                modelId=fallback_model,
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json",
            )
            fb_body = json.loads(fb_resp["body"].read().decode("utf-8"))
            fb_text = fb_body.get("content", [{}])[0].get("text", "").strip()
            print(f"  [SUCCESS] '{fallback_model}' in {fallback_region} responded: \"{fb_text}\"")
            print(f"  -> NOTICE: Bedrock connectivity itself is working! The error on '{model_id}' is due to AWS Marketplace subscription permissions on this role.")
        except Exception as fb_err:
            print(f"  [FAIL] Probing fallback also failed: {fb_err}")

        print("\n" + "=" * 60)
        print("  BEDROCK CONNECTIVITY CHECK FINISHED")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = test_connectivity()
    sys.exit(0 if success else 1)
