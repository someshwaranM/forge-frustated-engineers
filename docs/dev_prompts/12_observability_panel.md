# Vigil — Phase 12 Dev Prompt: Observability Panel
`docs/dev_prompts/12_observability_panel.md`

*(Scope, per the Technical Doc's own framing: a simple self-logged
stage-timer, not OpenTelemetry/APM. Reuse Phase 11's real timestamps and
Phase 2's connectivity checks — this phase is mostly wiring existing data
into a visible panel, not building new infrastructure.)*

---

## One gap to close first: there's no true "file arrival" timestamp yet

Phase 11's fix gave you real completion timestamps per stage
(`indexed_at`, `detection_completed_at`, `investigation_completed_at`), and
consecutive differences between those already give valid ingestion/
detection/investigation durations. What's still missing is a timestamp for
when the audio file actually arrived/started processing — needed to report
a true "file arrival → finding confirmed" end-to-end number, not just the
sum of the three stages (which would silently omit any file-watcher/
stability-check delay before Phase 5 even started).

Add `processing_started_at` to the call document in Phase 5's
`process_now.py`/`watch_folder.py` — set it the moment the stability check
passes, before Sarvam is called. This is a one-line addition to existing
code, not a new subsystem.

---

## What this phase builds

1. **Stage-timer aggregation** — per-call and aggregate (mean/median/min/
   max) durations for: ingestion (processing_started_at → indexed_at),
   detection (indexed_at → detection_completed_at), investigation
   (detection_completed_at → investigation_completed_at), and end-to-end
   (processing_started_at → investigation_completed_at).
2. **`GET /api/dashboard/summary`'s `pipeline_latency` field, finally
   real** — Phase 8 explicitly left this as a placeholder pending this
   phase.
3. **`GET /api/system/health`** — live status for MySQL and Elasticsearch,
   and *last-known* status (not live-pinged) for Bedrock/Gemini/Sarvam.
4. **Settings page's "System Health & Pipeline Diagnostics" section**,
   built for real — this was scoped in the Frontend Documentation back at
   Phase 4 but never actually implemented (Phase 10 only wired the
   confidence threshold and provider-status count, not a full panel).
5. **A small per-call processing-timeline touch on Call/Case Detail** —
   cheap, and it's the concrete "we monitor our own system" moment the
   Technical Doc's scope decision was written to deliver.

---

## The prompt (paste this verbatim to Codex / Claude Code / Antigravity)

````
You are running Phase 12 of the Vigil build: the observability panel. Do
NOT build OpenTelemetry, APM, or any third-party monitoring integration —
per the Technical Doc's explicit scope decision, this is a simple
self-logged stage-timer using timestamps this project already produces.

STEP 1 — Add processing_started_at to the call document: set it the moment
Phase 5's stability check passes (backend/ingestion/pipeline.py or
equivalent), before the Sarvam call. This must be a REAL wall-clock
timestamp at actual processing time — never derived from or compared
against the call's fictional date_time field, per Phase 11's explicit
correction. Re-process your existing demo calls (or backfill this field for
already-ingested ones if reprocessing isn't practical) so it's populated
for the benchmark set.

STEP 2 — Build backend/observability/stage_timer.py: for every call with a
complete pipeline run (processing_started_at, indexed_at,
detection_completed_at, investigation_completed_at all present), compute:
    ingestion_duration_seconds      = indexed_at - processing_started_at
    detection_duration_seconds      = detection_completed_at - indexed_at
    investigation_duration_seconds  = investigation_completed_at - detection_completed_at
    end_to_end_duration_seconds     = investigation_completed_at - processing_started_at
Aggregate mean/median/min/max across all such calls, and expose both the
per-call breakdown and the aggregate.

STEP 3 — Wire this into GET /api/dashboard/summary's pipeline_latency
field: replace the Phase 8 placeholder with the real aggregate object
(mean/median per stage, not just one end-to-end number — a stage breakdown
is what actually demonstrates "we monitor our own system," a single number
doesn't).

STEP 4 — Build GET /api/system/health:
- MySQL and Elasticsearch: check LIVE on every call to this endpoint (cheap,
  fast, no cost) — reuse the connection logic already proven in
  scripts/tests/test_mysql.py and test_elasticsearch.py rather than
  reimplementing it.
- Bedrock, Gemini, Sarvam: do NOT live-ping these on every health-check
  request — that wastes real API calls/cost just to render a panel, and
  adds latency to every page load that shows this panel. Instead report
  LAST-KNOWN status derived from actual recent pipeline activity: e.g.
  "Bedrock: last successful call at investigation for CALL_X, N minutes
  ago" / "Gemini fallback: fired N times in the last session." If a
  provider has never been used yet, say so explicitly rather than
  fabricating a status.

STEP 5 — Settings page: build the "System Health & Pipeline Diagnostics"
section using Steps 3-4's data — MySQL/ES live status, Bedrock/Gemini
last-known status and fallback-fire count, and the stage-latency breakdown
(ingestion/detection/investigation/end-to-end, mean and median).

STEP 6 — Add a small "Processing Timeline" element to Call Detail or Case
Detail showing that specific call's own four stage durations (not just the
aggregate) — e.g. a compact horizontal bar or a few labeled numbers:
"Ingested in 8.2s → Detected in 0.4s → Investigated in 11.7s." Keep this
small and secondary to the Evidence Chain, which remains the page's main
focus — this is a nice-to-have detail, not a redesign.

STEP 7 — Verification, with real output:
- Confirm processing_started_at is now populated on your demo calls and
  that end_to_end_duration_seconds produces a sane number (seconds to a
  few minutes, NOT hours or days — if it's showing anything resembling
  Phase 11's original date-confusion bug, stop and check what timestamp is
  actually being diffed).
- Fetch GET /api/dashboard/summary and confirm pipeline_latency shows a
  real per-stage breakdown, not the old placeholder.
- Fetch GET /api/system/health and confirm MySQL/ES report live status,
  and Bedrock/Gemini report last-known status without having made a live
  call to either provider just to answer this health check.
- Load Settings in the browser and confirm the diagnostics section renders
  real numbers.

Report back the actual GET /api/system/health and GET
/api/dashboard/summary (pipeline_latency portion) responses — not
hypothetical ones.
````

---

## What "good" looks like

- `processing_started_at` exists and every latency number derived from it is in the seconds-to-minutes range — this is the direct fix for Phase 11's original date-confusion bug, verified rather than assumed fixed.
- The health endpoint never calls Bedrock/Gemini/Sarvam just to answer "are you healthy" — that would be spending real API budget on a vanity panel, which is exactly the kind of scope creep the Technical Doc's "simple stage-timer, not full APM" decision was meant to prevent.
- The Settings diagnostics panel is the first time in this build that "we monitor our own system" is something a judge can actually see rendered, not just a line in the pitch deck.
- The per-call processing timeline is a small, secondary detail on Case Detail — it doesn't compete with or crowd out the Evidence Chain, which is still the page's one job to protect.
