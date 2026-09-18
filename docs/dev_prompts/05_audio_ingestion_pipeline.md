# Vigil — Phase 5 Dev Prompt: Audio Ingestion Pipeline
`docs/dev_prompts/05_audio_ingestion_pipeline.md`

*(Prerequisite check before starting: confirm the "calls" Elasticsearch index
from Phase 3.1 actually exists with its mapping applied — this phase writes
into it. You don't need all 10 scripted calls recorded yet; build and test
against 1-2 recorded files first, the rest can follow in parallel.)*

---

## What this phase does, end to end

```
CallAudio/<file>.wav
       ↓
File watcher detects it, waits for it to be fully written
       ↓
Filename validation (pattern + RM/Customer IDs exist in MySQL — also
fetch their full_names now, needed for speaker mapping below)
       ↓
Audio validation (readable, non-zero duration)
       ↓
Sarvam STT + diarization — BOTH transcribe (original language) AND
translate (English) modes, auto language detection
       ↓
Gemini identifies which diarized speaker is RM vs CUSTOMER, using the
RM's and customer's real names as context (fallback: earliest-speaker
timing heuristic if Gemini's response is invalid or low-confidence)
       ↓
Write call document (both transcript_original_text and
transcript_english_text, per-segment too) to the "calls" ES index
       ↓
Move file to CallAudio-Archive/ (success) or CallAudio-Failed/ (any failure)
```

Detection and the Investigator Agent are NOT part of this phase — this phase
stops once a call is transcribed, diarized, and indexed with
`processing_status = "TRANSCRIBED"`. `has_violation` stays `false` and
`finding_ids` stays empty until Phase 6/7 runs.

---

## Speaker-role mapping — Gemini-primary, timing-heuristic fallback

Sarvam's diarization returns anonymous speaker labels, not "RM" or
"CUSTOMER." The primary method here uses Gemini, given the transcript plus
the real RM and customer names (looked up from MySQL by the IDs already
parsed from the filename), to identify which diarized speaker is which —
using actual conversational evidence (who introduces themselves as calling
from Vigil Wealth, whose name the other speaker uses) rather than a
timing assumption. This generalizes far better than "first speaker = RM,"
including to real calls where the customer answers first.

**But don't trust Gemini's output unchecked — validate it, and keep a
fallback:**
- Gemini must return strict structured output:
  `{"speaker_0_role": "RM"|"CUSTOMER", "speaker_1_role": "RM"|"CUSTOMER",
  "confidence": "high"|"medium"|"low", "reasoning": "..."}`.
- Validate this against a small Pydantic schema before using it. Reject any
  response that isn't valid JSON matching this shape, or where both
  speakers get the same role.
- If validation fails, OR confidence is "low", fall back to the timing
  heuristic: the diarized speaker whose first segment starts earliest is
  labeled RM.
- Record which method actually decided the mapping —
  `speaker_mapping_method: "llm"` or `"heuristic_fallback"` — on the call
  document. This is the same transparency pattern already used for
  `provider_used` on findings (Bedrock vs Gemini) — don't silently accept
  whichever method fired; make it auditable.
- State plainly, in code comments and in this phase's report-back, that
  neither method is a solved problem: Gemini can misfire on a very short or
  ambiguous opening exchange where no name gets said; the timing fallback
  can misfire on any real call where the customer speaks first. This is a
  best-effort mapping, not a guarantee — useful to say explicitly if it ever
  comes up with a judge.

---

## The prompt (paste this verbatim to Codex / Claude Code / Antigravity)

````
You are running Phase 5 of the Vigil build: the audio ingestion pipeline.
Build this inside backend/ingestion/ (file watching, filename/audio
validation) and backend/sarvam/ (the Sarvam API client), per the folder
structure already scaffolded in Phase 1. Do NOT implement the detection
engine or Investigator Agent in this phase — this phase stops once a call is
transcribed and indexed with processing_status = "TRANSCRIBED".

STEP 1 — Filename validation (backend/ingestion/filename_parser.py):
Expected pattern: RM<rm_id_digits>_CUST<customer_id_digits>_<YYYYMMDD>_<HHMM>.wav
e.g. RM001_CUST001_20260310_1030.wav
- Parse rm_id, customer_id, and date_time from the filename using this exact
  pattern. Reject (move to CallAudio-Failed/) any file that doesn't match it,
  with a clear reason logged (e.g. "FILENAME_PATTERN_MISMATCH").
- Look up rm_id in the MySQL rm table and customer_id in the customer table.
  If either doesn't exist, reject to CallAudio-Failed/ with reason
  "UNKNOWN_RM_ID" or "UNKNOWN_CUSTOMER_ID" — do not silently proceed with an
  unverifiable ID.
- Fetch and keep rm.full_name and customer.full_name from these same
  lookups — Step 5's Gemini-based speaker mapping needs both names as input.

STEP 2 — File stability check (backend/ingestion/stability_check.py):
Before processing, confirm the file is fully written (not still being
copied/recorded) — check file size twice with a short delay (e.g. 2 seconds)
and confirm it hasn't changed. Only proceed once stable.

STEP 3 — Audio validation (backend/ingestion/audio_validator.py):
Confirm the file opens as valid audio, extract duration_seconds. Reject to
CallAudio-Failed/ with reason "INVALID_AUDIO" if the file can't be read or
has zero duration. Do not enforce a strict duration range (the 30s-2min
target was for the scripted demo calls, not a hard validation rule — a real
call could reasonably run longer).

STEP 4 — Sarvam transcription + diarization (backend/sarvam/sarvam_client.py):
- Call Sarvam's Saarika batch API with language_code="unknown" for automatic
  language detection (the 10 demo calls span English/Hindi/Tamil/code-mixed,
  so don't hardcode a language).
- Request diarized output with per-segment timestamps.
- Request BOTH modes: transcribe (original spoken language, verbatim) AND
  translate (English rendering) — for the full call and per-segment, if
  Sarvam's response structure supports segment-level translation; if it only
  translates at the full-transcript level, translate each segment's original
  text separately as a fallback so per-segment English text is still
  available (needed for the transcript_segments.text_english field).
- Handle API failures with one retry after a short backoff; if it still
  fails, reject to CallAudio-Failed/ with reason "TRANSCRIPTION_FAILED" —
  do not index a call with missing or partial transcript data.

STEP 5 — Speaker role mapping (Gemini-primary, timing-heuristic fallback —
see the design section above for full reasoning):
- Build a Gemini prompt containing: the full diarized transcript (raw
  speaker labels + timestamps + original-language text), rm.full_name, and
  customer.full_name (from Step 1).
- Ask Gemini to identify which raw diarized speaker label is the RM and
  which is the customer, returning ONLY this JSON shape:
      {"speaker_0_role": "RM"|"CUSTOMER",
       "speaker_1_role": "RM"|"CUSTOMER",
       "confidence": "high"|"medium"|"low",
       "reasoning": "..."}
  (adjust speaker label keys to match whatever raw labels Sarvam actually
  returns, e.g. SPEAKER_0/SPEAKER_1).
- Validate this response against a Pydantic schema. If it fails to parse, or
  both speakers get the same role, or confidence is "low", fall back to the
  timing heuristic: the diarized speaker whose first segment starts earliest
  is labeled RM, the other CUSTOMER.
- Record speaker_mapping_method as "llm" or "heuristic_fallback" depending
  on which path actually produced the final mapping — log the raw Gemini
  response (or the fact that it was skipped/failed) for auditability.

STEP 6 — Build the call document matching the "calls" ES index mapping from
Phase 3.1:
    call_id                 deterministic, e.g. "CALL_RM001_CUST001_20260310_1030"
    rm_id                    from Step 1
    customer_id              from Step 1
    date_time                parsed from filename in Step 1
    duration_seconds         from Step 3
    audio_file_path          final path after moving to CallAudio-Archive/
    processing_status        "TRANSCRIBED"
    language                 the language Sarvam auto-detected
    transcript_original_text  all segments' ORIGINAL-language text
                             concatenated in order
    transcript_english_text   all segments' ENGLISH text concatenated in
                             order — this is what transcript_semantic is
                             built from (see the mapping design note: same-
                             language comparison against the English
                             regulations index is more reliable than
                             cross-lingual)
    transcript_semantic       built from transcript_english_text
    transcript_segments       nested array: segment_id, speaker (RM/CUSTOMER
                             per Step 5), text_original, text_english,
                             start_time, end_time, is_violation (false for
                             all — Phase 6/7 sets this later)
    speaker_mapping_method    "llm" or "heuristic_fallback" per Step 5
    has_violation             false
    finding_ids               []
    indexed_at                current timestamp

STEP 7 — Index the call document into the "calls" ES index. Confirm it was
written by reading it back.

STEP 8 — Move the source file: CallAudio-Archive/ on full success,
CallAudio-Failed/ on any rejection from Steps 1-4 or 6-7, each with a
sidecar reason log (e.g. a .txt or .json next to the moved file stating why
it failed, if it failed).

STEP 9 — Build TWO entrypoints, not one:
- backend/ingestion/watch_folder.py — a continuous watcher (using watchdog
  or polling) that processes new files as they land in CallAudio/. This
  supports the "autonomous, continuous monitoring" pitch narrative.
- backend/ingestion/process_now.py — a one-shot script that processes
  whatever is currently sitting in CallAudio/ right now and exits. Use THIS
  one for controlled demo runs and for testing — a live background watcher
  running during an actual presentation is an unnecessary timing risk
  compared to clicking "process now" on demand. Both entrypoints call the
  same underlying ingestion function; don't duplicate the pipeline logic.

STEP 10 — Verification, with real output:
- Process at least 1 real recorded file through process_now.py end to end.
- Confirm it lands in the "calls" ES index with all fields populated
  correctly, including both transcript_original_text and
  transcript_english_text, and a plausible RM/CUSTOMER speaker mapping —
  spot-check against the actual script content (did the labeled "RM"
  segments actually say what the RM was scripted to say?).
- Confirm speaker_mapping_method is set, and check the logged Gemini
  response (or fallback trigger) to see which method actually decided it.
- Confirm the file moved to CallAudio-Archive/.
- Deliberately test one failure path: rename a copy to break the filename
  pattern, confirm it's rejected to CallAudio-Failed/ with a clear reason,
  and that it does NOT get indexed.

Report back: which file(s) you processed, the actual indexed call document
for at least one (including both transcript fields and
speaker_mapping_method), and the result of the deliberate failure-path test.
````

---

## What "good" looks like

- A real recorded call goes from `CallAudio/` to a fully-populated, correctly-mapped document in the `calls` index without manual intervention — both transcript_original_text and transcript_english_text populated, not just one.
- Gemini's speaker mapping is validated before being trusted, and the timing heuristic genuinely fires as a fallback (not dead code) when Gemini's response is invalid or low-confidence — `speaker_mapping_method` makes this visible per call rather than hidden.
- `process_now.py` exists as the demo-safe way to trigger ingestion on command — you are not relying on a live background watcher's timing during an actual presentation.
- A genuinely bad file (bad filename, unknown RM/customer ID) is rejected with a clear, logged reason and never reaches the index — the same "never silently proceed with bad data" principle from Phase 3's validation gate, applied here to real-time ingestion instead of a one-time indexing run.
