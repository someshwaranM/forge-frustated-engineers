"""
Vigil — Phase 5: Speaker Role Mapping.

Hierarchy:
1. Primary: AWS Bedrock (Claude 3 runtime)
2. Fallback: Google Gemini
3. Fallback 2: Earliest-speaker timing heuristic
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from pathlib import Path

# Phase 13: Elastic APM native spans
try:
    from backend.observability.apm import apm_span
except ImportError:
    from contextlib import contextmanager
    @contextmanager
    def apm_span(*a, **kw): yield

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)

logger = logging.getLogger(__name__)

# Debug logger (enabled via VIGIL_DEBUG_PIPELINE=true)
try:
    from backend.observability.debug_logger import (
        log_speaker_mapping_prompt,
        log_speaker_mapping_output,
        log_speaker_mapping_fallback,
    )
except ImportError:
    def log_speaker_mapping_prompt(*a, **kw): pass
    def log_speaker_mapping_output(*a, **kw): pass
    def log_speaker_mapping_fallback(*a, **kw): pass


class SpeakerResponse(BaseModel):
    speaker_1: Optional[str] = None
    speaker_2: Optional[str] = None
    confidence: str = Field(description="high, medium, or low")
    reasoning: Optional[str] = ""

# Backward compatibility alias
GeminiSpeakerResponse = SpeakerResponse


class SpeakerMappingOutput(BaseModel):
    mapping: Dict[str, str]  # e.g. {"speaker_1": "RM", "speaker_2": "CUSTOMER"}
    method: str              # "bedrock", "gemini", or "heuristic_fallback"
    raw_response: Optional[str] = None
    reasoning: Optional[str] = None


def _normalize(text: str) -> str:
    return "".join(c.lower() for c in (text or "") if c.isalnum() or c.isspace()).strip()


def _matches_person(candidate: str, full_name: str, target_role: str) -> bool:
    """Checks if a candidate string corresponds to a person's name or role."""
    cand = _normalize(candidate)
    full = _normalize(full_name)
    role = _normalize(target_role)

    if not cand:
        return False
    if cand == full or cand == role:
        return True
    # Match on first or last name
    for token in full.split():
        if len(token) >= 3 and token in cand:
            return True
    if role in cand:
        return True
    return False


def _timing_heuristic_fallback(segments: List[dict]) -> Dict[str, str]:
    """
    Timing heuristic fallback:
    The diarized speaker whose first segment starts earliest is labeled RM, the other CUSTOMER.
    """
    first_seen = {}
    for seg in sorted(segments, key=lambda s: s.get("start_time", 0.0)):
        spk = seg.get("speaker_raw") or seg.get("speaker")
        if spk and spk not in first_seen:
            first_seen[spk] = seg.get("start_time", 0.0)

    speakers = list(first_seen.keys())
    if not speakers:
        return {"speaker_1": "RM", "speaker_2": "CUSTOMER"}

    earliest_speaker = speakers[0]
    mapping = {earliest_speaker: "RM"}
    for spk in speakers[1:]:
        mapping[spk] = "CUSTOMER"

    # Default safety for 2 speakers
    if "speaker_1" not in mapping:
        mapping["speaker_1"] = "RM" if earliest_speaker != "speaker_1" else "CUSTOMER"
    if "speaker_2" not in mapping:
        mapping["speaker_2"] = "CUSTOMER" if mapping.get("speaker_1") == "RM" else "RM"

    logger.info(f"Timing heuristic fallback applied: {mapping} (earliest: {earliest_speaker})")
    return mapping


def _extract_json_text(text: str) -> str:
    """Strips Markdown code fences if present."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    return text


def _parse_and_resolve_speaker_mapping(
    raw_response_text: str,
    rm_name: str,
    customer_name: str
) -> Tuple[Dict[str, str], str]:
    """
    Parses and validates LLM speaker response.
    Returns (mapping, reasoning) or raises ValueError on validation/confidence failure.
    """
    cleaned = _extract_json_text(raw_response_text)
    data = json.loads(cleaned)
    validated = SpeakerResponse.model_validate(data)

    if validated.confidence.lower() == "low":
        raise ValueError(f"Low confidence ({validated.reasoning})")

    cand1 = validated.speaker_1 or ""
    cand2 = validated.speaker_2 or ""

    spk1_is_rm = _matches_person(cand1, rm_name, "RM")
    spk1_is_cust = _matches_person(cand1, customer_name, "CUSTOMER")

    spk2_is_rm = _matches_person(cand2, rm_name, "RM")
    spk2_is_cust = _matches_person(cand2, customer_name, "CUSTOMER")

    resolved_mapping = {}
    if spk1_is_rm and spk2_is_cust:
        resolved_mapping = {"speaker_1": "RM", "speaker_2": "CUSTOMER"}
    elif spk1_is_cust and spk2_is_rm:
        resolved_mapping = {"speaker_1": "CUSTOMER", "speaker_2": "RM"}
    elif spk1_is_rm and not spk2_is_rm:
        resolved_mapping = {"speaker_1": "RM", "speaker_2": "CUSTOMER"}
    elif spk2_is_rm and not spk1_is_rm:
        resolved_mapping = {"speaker_1": "CUSTOMER", "speaker_2": "RM"}
    elif spk1_is_cust and not spk2_is_cust:
        resolved_mapping = {"speaker_1": "CUSTOMER", "speaker_2": "RM"}
    elif spk2_is_cust and not spk1_is_cust:
        resolved_mapping = {"speaker_1": "RM", "speaker_2": "CUSTOMER"}
    else:
        raise ValueError(f"Ambiguous person name resolution: speaker_1='{cand1}', speaker_2='{cand2}'")

    if resolved_mapping.get("speaker_1") == resolved_mapping.get("speaker_2"):
        raise ValueError("Identical roles assigned to both speakers.")

    return resolved_mapping, validated.reasoning or ""


def _invoke_bedrock(prompt: str) -> str:
    """
    Primary LLM caller using AWS Bedrock runtime.
    Raises exception on missing credentials, auth failure, or invocation error.
    """
    aws_access_key = (os.getenv("AWS_ACCESS_KEY_ID") or "").strip().strip("'\"")
    aws_secret_key = (os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip().strip("'\"")
    aws_region = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-west-2").strip().strip("'\"")
    aws_session_token = (os.getenv("AWS_SESSION_TOKEN") or "").strip().strip("'\"")
    model_id = (os.getenv("AWS_BEDROCK_MODEL_ID") or "").strip().strip("'\"")

    # Treat default placeholder values as unconfigured
    if not aws_access_key or "<REPLACE_ME>" in (aws_access_key, aws_secret_key, aws_region, model_id):
        raise ValueError("AWS Bedrock credentials/model_id unconfigured or placeholder in .env")

    import boto3
    client_kwargs = {
        "service_name": "bedrock-runtime",
        "region_name": aws_region,
        "aws_access_key_id": aws_access_key,
        "aws_secret_access_key": aws_secret_key,
    }
    if aws_session_token:
        client_kwargs["aws_session_token"] = aws_session_token
    client = boto3.client(**client_kwargs)

    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": prompt}],
    }

    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(payload),
        contentType="application/json",
        accept="application/json",
    )
    response_body = json.loads(response["body"].read().decode("utf-8"))
    content_text = response_body.get("content", [{}])[0].get("text", "")
    return content_text


def _invoke_gemini(prompt: str, model_id: Optional[str] = None) -> str:
    """
    Invokes Google Gemini for speaker role identification.
    Raises exception on missing API key, network failure, or rate limits.
    """
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY not configured in .env")

    import google.generativeai as genai
    genai.configure(api_key=gemini_api_key)
    model_name = model_id or os.getenv("GEMINI_MODEL_ID", "gemini-3.5-flash")
    model = genai.GenerativeModel(model_name)

    logger.info(f"Invoking Gemini ({model_name}) for speaker role mapping...")
    res = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    return res.text


def map_speakers(
    segments: List[dict],
    rm_name: str,
    customer_name: str,
    model_id: Optional[str] = None,
    call_id: str = "",
) -> SpeakerMappingOutput:
    """
    Determines whether each speaker is RM or CUSTOMER using a 3-tier cascade:
    1. Primary: AWS Bedrock (Claude 3 runtime)
    2. Fallback: Google Gemini
    3. Fallback 2: Earliest-speaker timing heuristic
    """
    cid = call_id or "SPEAKER_MAPPING"
    # 1. Check if segments are available
    if not segments:
        return SpeakerMappingOutput(
            mapping={"speaker_1": "RM", "speaker_2": "CUSTOMER"},
            method="heuristic_fallback",
            reasoning="No segments provided; default heuristic applied."
        )

    # 2. Build prompt
    lines = []
    for s in segments[:12]:  # First 12 turns provide ample introduction evidence
        spk = s.get("speaker_raw") or s.get("speaker", "unknown")
        start = s.get("start_time", 0.0)
        end = s.get("end_time", 0.0)
        text = s.get("text_english") or s.get("text_original", "")
        lines.append(f"{spk} [{start:.2f}s - {end:.2f}s]: {text}")

    transcript_excerpt = "\n".join(lines)

    prompt = f"""You are analyzing a customer service / wealth management phone call transcript from Vigil Wealth.
Identify the speaker who corresponds to the Relationship Manager (RM) and the speaker who corresponds to the Customer based on conversational introductions, names used, and context.

Context:
- Relationship Manager (RM) Full Name: {rm_name} (from Vigil Wealth)
- Customer Full Name: {customer_name}

Transcript Excerpt:
{transcript_excerpt}

Task:
Return ONLY a valid JSON object identifying which person name corresponds to speaker_1 and speaker_2. Do not include markdown code fences or explanatory text.
Schema:
{{
  "speaker_1": "{rm_name}" or "{customer_name}",
  "speaker_2": "{rm_name}" or "{customer_name}",
  "confidence": "high" or "medium" or "low",
  "reasoning": "brief explanation based on who introduces themselves and who is addressed"
}}
"""
    log_speaker_mapping_prompt(cid, prompt)

    # TIER 1: AWS Bedrock Primary
    raw_bedrock = None
    try:
        logger.info("Attempting primary speaker mapping via AWS Bedrock...")
        with apm_span("speaker_mapping.bedrock", span_type="external.ai", span_subtype="bedrock"):
            raw_bedrock = _invoke_bedrock(prompt)
        mapping, reasoning = _parse_and_resolve_speaker_mapping(raw_bedrock, rm_name, customer_name)
        logger.info(f"Speaker role mapping succeeded via AWS Bedrock: {mapping}")
        log_speaker_mapping_output(cid, raw_bedrock, {"mapping": mapping, "method": "bedrock", "reasoning": reasoning})
        return SpeakerMappingOutput(
            mapping=mapping,
            method="bedrock",
            raw_response=raw_bedrock,
            reasoning=reasoning
        )
    except Exception as exc:
        logger.warning(f"AWS Bedrock speaker mapping unavailable/failed ({exc}). Falling back to Google Gemini...")

    # TIER 2: Google Gemini Fallback
    raw_gemini = None
    try:
        logger.info("Attempting fallback speaker mapping via Google Gemini...")
        with apm_span("speaker_mapping.gemini", span_type="external.ai", span_subtype="gemini"):
            raw_gemini = _invoke_gemini(prompt, model_id=model_id)
        mapping, reasoning = _parse_and_resolve_speaker_mapping(raw_gemini, rm_name, customer_name)
        logger.info(f"Speaker role mapping succeeded via Google Gemini: {mapping}")
        log_speaker_mapping_output(cid, raw_gemini, {"mapping": mapping, "method": "gemini", "reasoning": reasoning})
        return SpeakerMappingOutput(
            mapping=mapping,
            method="gemini",
            raw_response=raw_gemini,
            reasoning=reasoning
        )
    except Exception as exc:
        logger.error(
            f"Gemini speaker mapping failed (timing heuristic fallback applied): {exc}",
            extra={"vigil_stage": "speaker_mapping", "vigil_fallback": "heuristic"},
        )

    # TIER 3: Earliest-speaker timing heuristic
    heuristic_mapping = _timing_heuristic_fallback(segments)
    fallback_reason = "AWS Bedrock and Gemini both failed or were unavailable; timing heuristic fallback applied."
    log_speaker_mapping_fallback(cid, fallback_reason)
    return SpeakerMappingOutput(
        mapping=heuristic_mapping,
        method="heuristic_fallback",
        raw_response=raw_gemini or raw_bedrock,
        reasoning=fallback_reason
    )
