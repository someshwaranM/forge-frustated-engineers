"""
Unit tests for 3-tier Speaker Role Mapping:
1. Primary: AWS Bedrock
2. Fallback: Google Gemini
3. Fallback 2: Earliest speaker timing heuristic
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.ingestion.speaker_mapper import (
    map_speakers,
    _timing_heuristic_fallback,
    _parse_and_resolve_speaker_mapping,
    SpeakerMappingOutput,
)


@pytest.fixture
def sample_segments():
    return [
        {
            "segment_id": "seg_1",
            "speaker_raw": "speaker_1",
            "text_english": "Good morning Mr. Patel, this is Rahul Sharma calling from Vigil Wealth.",
            "text_original": "Good morning Mr. Patel, this is Rahul Sharma calling from Vigil Wealth.",
            "start_time": 0.5,
            "end_time": 4.2,
        },
        {
            "segment_id": "seg_2",
            "speaker_raw": "speaker_2",
            "text_english": "Hello Rahul, thank you for returning my call.",
            "text_original": "Hello Rahul, thank you for returning my call.",
            "start_time": 4.5,
            "end_time": 7.1,
        },
    ]


def test_timing_heuristic_earliest_speaker(sample_segments):
    """Timing heuristic assigns earliest speaker to RM and secondary to CUSTOMER."""
    mapping = _timing_heuristic_fallback(sample_segments)
    assert mapping["speaker_1"] == "RM"
    assert mapping["speaker_2"] == "CUSTOMER"

    # Reverse timing: speaker_2 speaks first
    reversed_segments = [
        {
            "segment_id": "seg_1",
            "speaker_raw": "speaker_2",
            "text_english": "Hello?",
            "start_time": 0.2,
            "end_time": 1.0,
        },
        {
            "segment_id": "seg_2",
            "speaker_raw": "speaker_1",
            "text_english": "Hello, this is RM calling.",
            "start_time": 1.5,
            "end_time": 3.0,
        },
    ]
    mapping_rev = _timing_heuristic_fallback(reversed_segments)
    assert mapping_rev["speaker_2"] == "RM"
    assert mapping_rev["speaker_1"] == "CUSTOMER"


def test_primary_bedrock_success(sample_segments):
    """When AWS Bedrock succeeds, map_speakers returns method='bedrock'."""
    bedrock_response = """
    {
        "speaker_1": "Rahul Sharma",
        "speaker_2": "Amit Patel",
        "confidence": "high",
        "reasoning": "speaker_1 introduces themselves as Rahul Sharma from Vigil Wealth"
    }
    """
    with patch("backend.ingestion.speaker_mapper._invoke_bedrock", return_value=bedrock_response):
        with patch("backend.ingestion.speaker_mapper._invoke_gemini") as mock_gemini:
            res = map_speakers(sample_segments, rm_name="Rahul Sharma", customer_name="Amit Patel")
            assert res.method == "bedrock"
            assert res.mapping == {"speaker_1": "RM", "speaker_2": "CUSTOMER"}
            mock_gemini.assert_not_called()


def test_bedrock_fallback_to_gemini_success(sample_segments):
    """When AWS Bedrock fails, system falls back to Gemini and returns method='gemini'."""
    gemini_response = """
    {
        "speaker_1": "Rahul Sharma",
        "speaker_2": "Amit Patel",
        "confidence": "high",
        "reasoning": "speaker_1 introduces themselves as Rahul Sharma"
    }
    """
    with patch("backend.ingestion.speaker_mapper._invoke_bedrock", side_effect=RuntimeError("Bedrock auth failure")):
        with patch("backend.ingestion.speaker_mapper._invoke_gemini", return_value=gemini_response) as mock_gemini:
            res = map_speakers(sample_segments, rm_name="Rahul Sharma", customer_name="Amit Patel")
            mock_gemini.assert_called_once()
            assert res.method == "gemini"
            assert res.mapping == {"speaker_1": "RM", "speaker_2": "CUSTOMER"}


def test_both_llms_fail_fallback_to_heuristic(sample_segments):
    """When both Bedrock and Gemini fail, system falls back to timing heuristic."""
    with patch("backend.ingestion.speaker_mapper._invoke_bedrock", side_effect=RuntimeError("Bedrock unavailable")):
        with patch("backend.ingestion.speaker_mapper._invoke_gemini", side_effect=RuntimeError("Gemini quota 429")):
            res = map_speakers(sample_segments, rm_name="Rahul Sharma", customer_name="Amit Patel")
            assert res.method == "heuristic_fallback"
            assert res.mapping == {"speaker_1": "RM", "speaker_2": "CUSTOMER"}


def test_low_confidence_triggers_fallback(sample_segments):
    """Low confidence response from Bedrock triggers Gemini fallback, and low confidence from Gemini triggers heuristic."""
    low_conf_json = """
    {
        "speaker_1": "Rahul Sharma",
        "speaker_2": "Amit Patel",
        "confidence": "low",
        "reasoning": "unclear introduction"
    }
    """
    with patch("backend.ingestion.speaker_mapper._invoke_bedrock", return_value=low_conf_json):
        with patch("backend.ingestion.speaker_mapper._invoke_gemini", return_value=low_conf_json):
            res = map_speakers(sample_segments, rm_name="Rahul Sharma", customer_name="Amit Patel")
            assert res.method == "heuristic_fallback"
            assert res.mapping == {"speaker_1": "RM", "speaker_2": "CUSTOMER"}
