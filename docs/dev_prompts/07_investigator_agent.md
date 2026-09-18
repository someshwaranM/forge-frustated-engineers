# Vigil — Phase 7 Dev Prompt: Investigator Agent
`docs/dev_prompts/07_investigator_agent.md`

*(Scope: turn Phase 6's candidates into validated ComplianceFindings, or
explicitly dismiss them with logged reasoning. This is where AWS Bedrock
(primary) / Gemini (fallback) actually get called for reasoning — nothing
before this phase has called either.)*

---

## What this phase does, end to end

```
backend/compliance/candidates/<call_id>.json  (Phase 6 output)
       ↓
For each candidate, gather full context:
  customer profile (MySQL) + product info (MySQL) +
  RM history (aggregate query on compliance_findings ES index) +
  candidate evidence + retrieved regulation citations (with scores)
       ↓
Bedrock call (Gemini fallback) → structured ComplianceFinding, Pydantic-validated
       ↓
Hard guardrail: regulation_id MUST be one Phase 6 actually retrieved —
never accept an LLM-invented citation not in that list
       ↓
Confirmed finding → compliance_findings ES index + compliance_case (MySQL,
dual-write) + call document's has_violation/finding_ids updated
   OR
Dismissed (insufficient evidence / not a genuine violation) → logged, no
finding or case created
```

---

## Processing order matters — process calls by `date_time` ascending, not ingestion order

RM history context (Step 2 below) is only meaningful if earlier calls have
already been evaluated before later ones. Your 10 demo calls' actual
chronological order is:

```
#5 (2026-02-12) → #7 (2026-02-28) → #1 (2026-03-10) → #3 (2026-03-18) →
#9 (2026-03-19) → #2 (2026-04-05) → #4 (2026-04-22) → #6 (2026-06-30) →
#8 (2026-07-01) → #10 (2026-08-15)
```

This happens to already put every repeat-RM pair in the right order (RM001's
#1 before #2, RM002's #3 before #4, RM003's #5 before #6, RM004's #7 before
#8, RM005's #9 before #10) — but don't rely on that being a coincidence you
can ignore going forward. Process by `date_time`, always, not by whatever
order files happened to get ingested in.

---

## The prompt (paste this verbatim to Codex / Claude Code / Antigravity)

````
You are running Phase 7 of the Vigil build: the Investigator Agent. Read
every backend/compliance/candidates/<call_id>.json produced by Phase 6, for
calls in ascending date_time order (see note above — do not process in
ingestion order or filename order). For each candidate in each file:

STEP 1 — Gather context:
- customer.risk_profile, customer.investment_experience (MySQL, by the
  call's customer_id).
- product.risk_class, product.suitable_risk_profiles,
  product.disclosure_requirements (MySQL, using the product_id Phase 6
  identified, if any).
- RM history: query the compliance_findings ES index (aggregate) for prior
  CONFIRMED findings where rm_id matches this call's RM, from calls with an
  earlier date_time than the current one. Include count and categories of
  prior findings as context — this will be empty for early calls and build
  up as later calls are processed, which is expected, not a bug.
- The candidate's own evidence (transcript segments + timestamps) and its
  attached regulation citations from Phase 6 (chunk_id, citation_label,
  bm25_score, semantic_score, clause_text) — there may be 1-3 of these.

STEP 2 — Hard pre-check: if Phase 6 attached ZERO regulation citations to
this candidate, do NOT call Bedrock/Gemini for it at all — immediately log
it as DISMISSED_NO_CITATION (see Step 6) and move to the next candidate.
This is the literal enforcement of "never invent a regulatory clause" —
if nothing was even retrieved, there is nothing to reason over.

STEP 3 — Bedrock call (primary), Gemini call (fallback): send the gathered
context to a single Bedrock model call. The prompt must instruct the model
to:
  a) Independently assess whether this candidate is a genuine compliance
     concern given the FULL context — not just rubber-stamp Phase 6's flag.
     Phase 6's keyword/retrieval signals are candidates for investigation,
     not pre-confirmed violations; the model can and should conclude "not a
     genuine violation" if the fuller context doesn't support it.
  b) If it IS a genuine concern, select which ONE of the attached regulation
     citations best supports the finding, and explain why in the reasoning
     field — it must pick from the citations actually provided, never
     produce a different chunk_id or clause number.
  c) Return output matching data/schemas/compliance_finding_schema.py
     EXACTLY: finding_id, call_id, category, severity (LOW/MEDIUM/HIGH),
     timestamp_start, timestamp_end, transcript_evidence,
     customer_risk_profile, product_risk_class, regulation_id, reasoning,
     confidence (float), recommended_action.
  d) If it decides this is NOT a genuine violation, return a clear dismissal
     signal instead of a finding (e.g. a `verdict: "DISMISSED"` field with
     reasoning) rather than forcing a low-severity finding just to produce
     output.
- On Bedrock failure (auth/access error, timeout, throttling), retry ONCE
  against Gemini using the identical prompt and context — Gemini's output
  goes through the exact same Pydantic validation as Bedrock's, no relaxed
  rules for the fallback path.
- Record provider_used ("bedrock" or "gemini") on every finding.

STEP 4 — Validate the model's output against the ComplianceFinding Pydantic
schema. If it fails validation (malformed JSON, missing field, wrong type),
this is a hard failure for this candidate — log it as
DISMISSED_VALIDATION_FAILED, do NOT retry indefinitely or accept a partially
valid object.

STEP 5 — Hard guardrail check on every validated finding, enforced in code,
not just prompted for: `regulation_id` MUST exactly match one of the
chunk_ids that were actually in this candidate's Phase 6 citation list. If
the model returns a regulation_id NOT in that list, reject the finding
outright (log as DISMISSED_CITATION_MISMATCH) — this is not a retry
condition, it's a correctness failure to surface, since it means the model
either hallucinated a citation or misunderstood the candidate's actual
options. Also enforce: if severity is "HIGH", timestamp_start,
timestamp_end, and regulation_id must all be non-empty — reject
(DISMISSED_INCOMPLETE_HIGH_FINDING) if a HIGH finding is missing any of
these.

STEP 6 — For every candidate, log an outcome in
backend/agents/investigations/<call_id>.json (create this new folder) —
this is the full audit trail, successes AND dismissals alike:
    {
      "candidate_id": "...",
      "outcome": "CONFIRMED" | "DISMISSED_NO_CITATION" |
                 "DISMISSED_NOT_GENUINE" | "DISMISSED_VALIDATION_FAILED" |
                 "DISMISSED_CITATION_MISMATCH" |
                 "DISMISSED_INCOMPLETE_HIGH_FINDING",
      "finding": {...} or null,
      "provider_used": "bedrock" | "gemini" | null,
      "reasoning": "..."
    }
A candidate being dismissed is a normal, expected outcome for some
candidates (e.g. Call #9's low-experience signal might reasonably be
confirmed as a genuine LOW-severity finding OR dismissed as insufficiently
supported — either is a legitimate model judgment, just make sure it's
logged either way, not silently dropped).

STEP 7 — For every CONFIRMED finding:
  a) Fetch the winning regulation_id's chunk from the regulations index to
     get citation_label and source_url for denormalization.
  b) Write the full finding to the compliance_findings ES index, including
     status: "OPEN", provider_used, and the denormalized
     regulation_citation_label / regulation_source_url.
  c) Create a matching row in MySQL compliance_case: case_id, finding_id,
     call_id, rm_id, customer_id, category, severity, status = "OPEN",
     escalated = false, assigned_to = NULL, created_at = now. This is the
     dual-write point flagged back in Phase 3.1 — both writes must happen
     together, not one without the other.
  d) Update the call document in the calls index: set has_violation = true,
     append this finding_id to finding_ids.

STEP 8 — Run this against all 10 demo calls' candidate files, in date_time
order. Report back:
- Every CONFIRMED finding produced, with its provider_used.
- Every DISMISSED outcome and which reason fired.
- Confirm zero findings were created for your 3 CLEAN calls' (empty
  candidate) files — trivially true since there are no candidates to
  process for those, but confirm it explicitly.
- Confirm at least one RM history aggregate actually returned non-empty
  results for a later call from a repeat-RM pair (e.g. when processing
  Call #2, RM001's Call #1 finding should already be queryable as history).
````

---

## What "good" looks like

- Every CONFIRMED finding's `regulation_id` is traceable to a specific chunk in the regulations index that Phase 6 actually retrieved for that candidate — never a citation invented outside that list. This is the single guardrail that makes "auditable Evidence Chain" true rather than aspirational.
- Dismissals are visible and reasoned, not silent — `backend/agents/investigations/<call_id>.json` shows every candidate's fate, confirmed or dismissed, which is what makes the false-positive side of your benchmark (Section 10 of the Technical Doc) measurable rather than assumed.
- The Gemini fallback path produces output that passes the exact same validation as Bedrock's — if it's ever exercised (Bedrock down, rate-limited), the difference should be invisible to everything downstream except the `provider_used` field.
- RM history genuinely accumulates across calls in the right order — Call #2's context should show RM001 already has one prior confirmed finding when the agent reasons about it, since that's real signal for judging repeat-pattern risk even though this phase doesn't compute the repeat-pattern aggregate itself.
- The dual write (ES finding + MySQL case) happens together for every confirmed finding — a finding that exists in one place but not the other is exactly the drift Phase 3.1 flagged as a risk to avoid.
