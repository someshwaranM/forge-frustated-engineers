# Vigil — Phase 11 Dev Prompt: Benchmark Run
`docs/dev_prompts/11_benchmark_run.md`

*(Scope: measure the system against ground truth, comparing the full
pipeline (Phase 6+7) against a rule-only baseline (Phase 6 alone). This is
what turns "Vigil is accurate" from a claim into a number.)*

---

## The two systems being compared

- **Baseline ("rule-only/keyword-only detector")** = Phase 6's raw output,
  treated naively: ANY non-empty candidate array for a call = a confirmed
  violation for that call, with severity taken directly from the
  candidate's `confidence_signal` and no LLM judgment applied at all. This
  is deliberately the "dumb" comparison point — it's expected to have worse
  precision than the full pipeline, since it can't tell a genuine violation
  from a spurious keyword match.
- **Full pipeline ("the real system")** = Phase 7's output — Phase 6's
  candidates AFTER Investigator Agent reasoning, citation validation, and
  the dismissal guardrails.

**Important ceiling to state explicitly in the report, not discover by
surprise:** the full pipeline's RECALL can never exceed the baseline's
recall, because Phase 7 only refines/filters what Phase 6 already flagged —
it never independently discovers a violation Phase 6 missed entirely (e.g.
if `PRODUCT_NOT_IDENTIFIED` caused Phase 6 to skip suitability/disclosure
checks for a call, no amount of good reasoning in Phase 7 recovers that).
If recall is capped by Phase 6, say so plainly in the report as an expected
property of the pipeline design, not an anomaly to explain away.

---

## Ground truth

`backend/benchmark/ground_truth.json` is provided (see attached) — sourced
directly from the 10 call scripts' metadata headers. Use it as-is; do not
regenerate or infer labels from the pipeline's own output. Note the
explicit instruction embedded in Call #9's entry: its outcome is a
legitimate judgment call either way and should be reported separately from
the strict precision/recall numbers, not folded in as a hard pass/fail.

---

## The prompt (paste this verbatim to Codex / Claude Code / Antigravity)

````
You are running Phase 11 of the Vigil build: the benchmark harness. Place
the provided ground_truth.json at backend/benchmark/ground_truth.json. Do
NOT modify its labels — if you believe a label is wrong, flag it in your
report rather than silently changing it.

STEP 1 — Add lightweight timestamp capture to existing staging files (do
NOT build a new observability system — that's Phase 12's job; this is the
minimum needed for THIS phase's own latency numbers):
- In Phase 5's call document (calls ES index): confirm `indexed_at` already
  captures when transcription completed — if not already precise, add it.
- In Phase 6's backend/compliance/candidates/<call_id>.json: add a
  `detection_completed_at` timestamp when the file is written.
- In Phase 7's backend/agents/investigations/<call_id>.json: add an
  `investigation_completed_at` timestamp per candidate outcome.
- Latency per call = investigation_completed_at - date_time (the call's
  actual recorded timestamp) for the full pipeline; detection_completed_at
  - date_time for the baseline. Report both, not just one.

STEP 2 — Build backend/benchmark/run_benchmark.py:
For each of the 10 calls in ground_truth.json:
  a) Baseline prediction: read backend/compliance/candidates/<call_id>.json.
     If the candidates array is non-empty, baseline_severity = the highest
     confidence_signal among all candidates for that call (HIGH > MEDIUM >
     LOW), baseline_category = the category of whichever candidate produced
     that severity. If empty, baseline_severity = "CLEAN".
  b) Full-pipeline prediction: read
     backend/agents/investigations/<call_id>.json. If any candidate's
     outcome is "CONFIRMED", pipeline_severity = the highest severity among
     CONFIRMED findings for that call, pipeline_category = that finding's
     category. If all outcomes are DISMISSED_* or the file shows no
     candidates at all, pipeline_severity = "CLEAN".
  c) Compare both predictions against ground_truth_severity and
     ground_truth_category for that call_id. Treat Call #9
     (CALL_RM005_CUST005_20260319_1200) specially per its ground_truth note
     — report its outcome separately, do not fold it into the aggregate
     precision/recall/F1 computation either way.

STEP 3 — Compute, for BOTH baseline and full pipeline, across the remaining
9 calls:
  - Precision: of calls predicted as a violation (non-CLEAN), what fraction
    actually are one per ground truth.
  - Recall: of calls that ARE violations per ground truth, what fraction
    were predicted as one.
  - F1: harmonic mean of the two.
  - Category accuracy: of the calls correctly identified as a violation,
    what fraction also got the right category.
  - Latency: mean and per-call, from Step 1's timestamps.
  - Evidence coverage (full pipeline only — the baseline has no citations
    to check): of all CONFIRMED findings, what fraction have a non-empty
    timestamp_start, timestamp_end, AND regulation_id. This should be at or
    near 100% by construction (Phase 7's guardrails already require this)
    — verify it's actually true rather than assuming the guardrails worked
    perfectly; report any gap if found.

STEP 4 — Write backend/benchmark/benchmark_report.md with:
  - A results table: Precision / Recall / F1 / Category Accuracy / Mean
    Latency, one row for baseline, one row for full pipeline.
  - A per-category breakdown (guaranteed-return, suitability, disclosure,
    ambiguous) showing how each system did specifically on that category.
  - Call #9's outcome reported separately with its judgment-call context,
    not silently included or excluded from the headline numbers without
    explanation.
  - The explicit statement that full-pipeline recall is capped by baseline
    recall by design, with the actual numbers showing whether that ceiling
    was reached or whether the LLM reasoning step lost recall it didn't
    need to (i.e. did Phase 7 ever DISMISS a candidate that Phase 6 flagged
    and ground truth confirms IS real, for a call other than #9 — that
    would be a real precision-for-recall tradeoff worth calling out, not
    just the expected ceiling).
  - Evidence coverage's actual measured percentage, not an assumed 100%.

STEP 5 — Run it for real and report back the actual completed table and
report content — not a template with placeholder numbers.
````

---

## What "good" looks like

- The full pipeline's precision is visibly higher than the baseline's — this is the concrete number that proves the Investigator Agent's reasoning step is adding real value, not just extra latency.
- Evidence coverage is measured, not assumed — if it's below 100%, that's a real bug in Phase 7's guardrails worth fixing before it's worth presenting.
- Call #9's ambiguous outcome is reported honestly as a judgment call, not silently absorbed into either a flattering or unflattering aggregate number.
- The recall-ceiling relationship between baseline and full pipeline is stated as an expected design property in the report — this is exactly the kind of thing a judge might ask about, and having the answer already written down beats explaining it live for the first time.
- Latency numbers exist and are real, filling the gap Phase 8 explicitly deferred, using timestamps added to files that already existed rather than new infrastructure.
