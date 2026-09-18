# Vigil — Phase 6 Dev Prompt: Detection Engine
`docs/dev_prompts/06_detection_engine.md`

*(Scope: produce CANDIDATES, not final findings. This phase reads calls +
regulations + MySQL and outputs staged candidate files. The Investigator
Agent (Phase 7) is what turns a candidate into a validated ComplianceFinding
with AI reasoning — this phase does the deterministic/retrieval groundwork
that feeds it, and does NOT call Bedrock or Gemini for reasoning.)*

---

## What this phase does, end to end

```
calls index (RM-speaker segments, English text)
       ↓
1. Deterministic keyword/pattern scan (guaranteed-return language)
2. Product identification (product name mentioned in transcript → MySQL)
3. Suitability check (customer.risk_profile vs product.risk_class)
4. Disclosure-keyword-presence check (for Medium/High risk products)
       ↓
For each flagged candidate: hybrid regulation retrieval (BM25 + semantic
against the regulations index) → attach candidate citation
       ↓
Write backend/detection/candidates/<call_id>.json
```

**Explicitly OUT of scope for this phase:** the "repeated RM pattern"
category is NOT a per-call candidate — it's an aggregate computed later
(RM Analytics / dashboard) over multiple `compliance_case` rows, not
something this scanner produces per call. Don't try to detect it here.

---

## Folder structure (inside `backend/compliance/`, per Phase 1 scaffolding)

```
backend/compliance/
├── deterministic_rules.py    (keyword/pattern scan — reuses Phase 3's synonym list)
├── product_identifier.py     (match product names mentioned in transcript → MySQL)
├── suitability_checker.py    (customer.risk_profile vs product.risk_class)
├── disclosure_checker.py     (keyword-presence check for Medium/High risk products)
├── regulation_retriever.py   (hybrid BM25+semantic query against regulations index)
├── candidate_builder.py      (assembles + writes candidate JSON per call)
└── candidates/
    └── <call_id>.json        (one file per call with any candidates found)
```

---

## The prompt (paste this verbatim to Codex / Claude Code / Antigravity)

````
You are running Phase 6 of the Vigil build: the detection engine. This phase
reads calls from the "calls" ES index (populated by Phase 5), cross-
references MySQL and the "regulations" ES index, and produces CANDIDATE
detections only — staged JSON files, not final ComplianceFindings. Do NOT
call AWS Bedrock or Gemini for reasoning in this phase — that's Phase 7. Do
NOT implement repeated-RM-pattern detection here — that's a later aggregate
computed from compliance_case history, not a per-call candidate.

For each call document in the "calls" index with processing_status =
"TRANSCRIBED", run the following against its transcript_segments where
speaker = "RM" (RM statements are what's being evaluated for compliance —
customer segments are read only as corroborating context, e.g. if a customer
explicitly states risk discomfort or inexperience, capture that as
supporting evidence text alongside a suitability candidate, but don't scan
customer segments for violations of their own).

STEP 1 — Deterministic keyword/pattern scan (backend/compliance/
deterministic_rules.py): scan each RM segment's text_english for
guaranteed-return language. Reuse the exact synonym/keyword list already
built during Phase 3's regulatory indexing (the guaranteed-return synonym
mappings) as the source of these patterns — don't build a second,
inconsistent keyword list. Also flag softer, hedged language ("should
perform well", "I think", "expect to") as a separate, lower-priority
candidate type — this is the deliberately ambiguous case your Call #6 script
was written to test, and it should produce a LOW-confidence candidate, not
get ignored or treated as equally severe as explicit guarantee language.

STEP 2 — Product identification (backend/compliance/product_identifier.py):
For each call, search all of the call's transcript_english text (RM segments
primarily) for any product_name from the MySQL product table — use a
fuzzy/substring match, not exact-string-only, since spoken language won't
always say a product's full formal name. If a product is identified, fetch
its risk_class and suitable_risk_profiles. If NO product can be identified
from the transcript, log this explicitly (e.g. "PRODUCT_NOT_IDENTIFIED" on
the call's candidate file) and skip Steps 3-4 for this call — do NOT guess a
product from transaction-date proximity as a primary method; that's a weak
signal only, and generating a suitability/disclosure candidate against a
guessed product risks a false positive built on a false premise. If you want
to use transaction-date proximity as a secondary cross-check once a product
IS identified from the transcript (e.g. to confirm it against a real
transaction), that's fine — just never as the primary identification method.

STEP 3 — Suitability check (backend/compliance/suitability_checker.py): if a
product was identified in Step 2, fetch the call's customer_id → look up
customer.risk_profile in MySQL. If customer.risk_profile is NOT in the
product's suitable_risk_profiles list, flag a suitability-mismatch
candidate. Attach as evidence: the transcript segment(s) where the product
was mentioned/pitched, AND any customer segment where they expressed their
own risk comfort/experience level, if present (this strengthens the
candidate's evidence beyond just a database lookup).

STEP 4 — Disclosure-keyword-presence check (backend/compliance/
disclosure_checker.py): if a product was identified in Step 2 with
risk_class Medium or High, check whether the RM's segments contain ANY
disclosure-related language (e.g. "risk", "disclosure", "risk-o-meter",
"volatil", "no guarantee", "market risk" — build this list from
product.disclosure_requirements text for the specific product where
possible). If none of these appear anywhere in the RM's segments for that
call, flag a missing-disclosure candidate. State explicitly in code comments
and in this phase's report-back that this is a coarse keyword-presence
check, not true NLU comprehension — it can false-negative (RM discussed risk
using phrasing outside the keyword list) or false-positive (RM said "risk"
in an unrelated sense) — this is a known, stated limitation, not a hidden
one.

STEP 5 — Regulation retrieval for every candidate produced by Steps 1, 3,
and 4 (backend/compliance/regulation_retriever.py): run a hybrid query
(BM25 on chunk_text + semantic on chunk_text_semantic) against the
regulations index, using the candidate's category as the query basis (e.g.
a guaranteed-return candidate queries for guaranteed-return language; a
suitability candidate queries for "investment experience suitability"; a
disclosure candidate queries for risk disclosure requirements for the
relevant product risk class). Attach the top 1-3 candidate regulation
chunks (chunk_id, citation_label, bm25_score, semantic_score) to the
candidate — do NOT pick just one and discard the rest; Phase 7's
Investigator Agent needs to see the retrieved options to reason over, not
have this phase silently decide the citation for it.

STEP 6 — Write backend/compliance/candidates/<call_id>.json containing an
array of every candidate found for that call (empty array if none — this is
the expected, correct output for your CLEAN demo calls). Each candidate
object should carry: category, confidence_signal (based on which check
produced it and how strong the match was — this is a raw signal, NOT the
final LLM confidence score Phase 7 will produce), evidence (transcript
segment(s) + timestamps), and the attached regulation candidates from Step 5.

STEP 7 — Run this against all 10 demo calls once they're ingested (or
whichever are ingested so far) and report back: the actual candidates.json
content for at least one HIGH-severity call (e.g.
RM001_CUST001_20260310_1030 — should show a suitability-mismatch candidate),
one CLEAN call (should show an empty candidates array), and confirm
PRODUCT_NOT_IDENTIFIED did not fire on any call where your script explicitly
named a product.
````

---

## What "good" looks like

- Every candidate carries multiple retrieved regulation options (not a single pre-picked citation) — this is what lets Phase 7's Investigator Agent do real reasoning over the evidence instead of just rubber-stamping this phase's guess.
- `PRODUCT_NOT_IDENTIFIED` never fires on a call where your script explicitly named a product — if it does, the fuzzy-match logic in Step 2 needs work before Phase 7 can run at all for that call.
- A CLEAN demo call produces a genuinely empty candidates array — this is the direct evidence your benchmark run (Section 10 of the Technical Doc) needs to show low false-positive rate, not just high true-positive rate.
- Call #6's deliberately soft "should perform well" language produces a LOW-confidence candidate, not a HIGH one and not silence — this is the specific test case that distinguishes a well-tuned detector from an overly aggressive or overly lax one.
- The disclosure check's keyword-only limitation is stated plainly, not glossed over — useful to have ready if a judge asks how disclosure detection works.
