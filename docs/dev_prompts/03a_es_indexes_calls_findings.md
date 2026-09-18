# Vigil — Phase 3.1 Dev Prompt: Calls & Compliance Findings Indices
`docs/dev_prompts/03a_es_indexes_calls_findings.md`

*(Scope: create the "calls" and "compliance_findings" Elasticsearch index
mappings only. No data is indexed into either in this phase — "calls" gets
populated by the ingestion pipeline (Phase 5), "compliance_findings" gets
populated by detection (Phase 6/7). This phase exists so both schemas are
locked and correct before those phases need to write to them, exactly the
way Phase 3 locked the regulations schema before any text existed to index.)*

---

## The two mappings

### `calls` index

```json
{
  "mappings": {
    "properties": {
      "call_id": { "type": "keyword" },
      "rm_id": { "type": "keyword" },
      "customer_id": { "type": "keyword" },
      "date_time": { "type": "date" },
      "duration_seconds": { "type": "integer" },
      "audio_file_path": { "type": "keyword" },
      "processing_status": { "type": "keyword" },
      "language": { "type": "keyword" },

      "transcript_full_text": { "type": "text" },
      "transcript_semantic": { "type": "semantic_text" },

      "transcript_segments": {
        "type": "nested",
        "properties": {
          "segment_id": { "type": "keyword" },
          "speaker": { "type": "keyword" },
          "text": { "type": "text" },
          "start_time": { "type": "float" },
          "end_time": { "type": "float" },
          "is_violation": { "type": "boolean" }
        }
      },

      "has_violation": { "type": "boolean" },
      "finding_ids": { "type": "keyword" },
      "indexed_at": { "type": "date" }
    }
  }
}
```

**Why `transcript_segments` is `nested`, not a plain object array:** a plain
object/array field in Elasticsearch flattens all values across array
elements, so a query for "speaker=RM AND text contains guaranteed return"
could match a document where the RM said something unrelated on one segment
and the customer said "guaranteed return" on a different one — Elasticsearch
would still consider it a match because it lost track of which values
belonged to which array element. `nested` keeps each segment's fields bound
together for querying, which matters directly for `search_calls` (a later
phase's Agent Builder tool) needing to find "calls where the RM specifically
said X," not "calls where X appears somewhere."

**Why both `transcript_full_text` and `transcript_semantic` exist:**
mirrors the regulations index's BM25/semantic split — exact phrase search
("guaranteed return") uses `transcript_full_text`; paraphrase-tolerant
search ("you don't have to worry about losing money") uses
`transcript_semantic`, bound to the same `.multilingual-e5-small-elasticsearch`
inference endpoint used for regulations — chosen there specifically because
it's multilingual, which matters even more here since these are the actual
Hindi/English/code-mixed RM call transcripts, not English legal text.

### `compliance_findings` index

```json
{
  "mappings": {
    "properties": {
      "finding_id": { "type": "keyword" },
      "call_id": { "type": "keyword" },
      "rm_id": { "type": "keyword" },
      "customer_id": { "type": "keyword" },

      "category": { "type": "keyword" },
      "severity": { "type": "keyword" },
      "confidence": { "type": "float" },
      "status": { "type": "keyword" },

      "timestamp_start": { "type": "float" },
      "timestamp_end": { "type": "float" },
      "transcript_evidence": { "type": "text" },

      "customer_risk_profile": { "type": "keyword" },
      "product_risk_class": { "type": "keyword" },

      "regulation_chunk_id": { "type": "keyword" },
      "regulation_citation_label": { "type": "keyword" },
      "regulation_source_url": { "type": "keyword" },

      "reasoning": { "type": "text" },
      "recommended_action": { "type": "text" },

      "provider_used": { "type": "keyword" },
      "bm25_score": { "type": "float" },
      "semantic_score": { "type": "float" },

      "created_at": { "type": "date" },
      "updated_at": { "type": "date" }
    }
  }
}
```

**Field notes:**
- `status` is denormalized from MySQL's `compliance_case.status` (still the
  authoritative source for case workflow state) — this copy exists purely so
  a query like "show all OPEN high-severity findings" doesn't need a MySQL
  join on every search/dashboard load. Whichever phase implements case
  status changes (Phase 8) must write to BOTH MySQL and this field, or the
  two will drift — flag this explicitly as a dual-write point, not an
  afterthought.
- `regulation_citation_label` and `regulation_source_url` are denormalized
  from the matched regulations-index chunk at the moment a finding is
  created — this is deliberate: the Evidence Chain UI needs to display the
  citation instantly without a runtime cross-index lookup, and it also
  means a finding's citation stays fixed to what was actually true when the
  finding was made, even if the regulations index is later rebuilt.
- `bm25_score` / `semantic_score` are retained for internal/debugging use
  (e.g. understanding why a finding cited a particular clause) — not
  necessarily surfaced in the UI, but useful for Phase 7's Investigator
  Agent and for explaining retrieval behavior if a judge asks how a citation
  was chosen.
- `provider_used` ("bedrock" or "gemini") is where the fallback logging from
  Section 9.2 of the Technical Doc actually lands — this is what lets you
  later check whether the Gemini fallback ever fired during the real run.

---

## The prompt (paste this verbatim to Codex / Claude Code / Antigravity)

````
You are creating two Elasticsearch index mappings for Vigil: "calls" and
"compliance_findings". Use the exact mappings given above — do not add or
remove fields without flagging the change. Do NOT index any real data into
either index in this phase, and do NOT implement the ingestion pipeline,
detection engine, or Investigator Agent — those are later phases. This
phase only creates and verifies the two index schemas.

STEP 1 — Create backend/indexing/create_calls_index.py and
backend/indexing/create_findings_index.py, each creating its respective
index with the mapping given above.

STEP 2 — Verify the "calls" index's nested transcript_segments field works
as intended: index one throwaway test document with 2 segments — one where
speaker="RM" and text contains "guaranteed return", one where speaker=
"CUSTOMER" and text contains an unrelated phrase. Run a nested query for
speaker=RM AND text matches "guaranteed return" and confirm it matches.
Run the same nested query for speaker=CUSTOMER AND text matches "guaranteed
return" and confirm it does NOT match (this is the cross-contamination
nested is specifically preventing — verify it, don't just assume the
mapping type alone is sufficient). Delete the throwaway document once
confirmed.

STEP 3 — Verify transcript_semantic on "calls" binds to the same
.multilingual-e5-small-elasticsearch inference endpoint used for the
regulations index in Phase 3: index one throwaway test document with a
paraphrased Hindi-English code-mixed style statement in
transcript_full_text/transcript_semantic (e.g. an English rendering of "is
mein paisa doobne ka koi risk nahi hai" — "there's no risk of losing money
in this"), run a semantic query for a differently-worded English risk
statement, and confirm it matches. Delete the throwaway document once
confirmed.

STEP 4 — Verify the compliance_findings index accepts a fully-populated
throwaway test document with every field from the mapping present,
including a realistic regulation_citation_label and regulation_source_url
copied from an actual chunk already indexed in the "regulations" index
(Phase 3) — this confirms the denormalization pattern is wired correctly
before any real detection logic depends on it. Delete the throwaway
document once confirmed.

STEP 5 — Do not build any indexing/writer code for real call or finding
data yet. That belongs to Phase 5 (ingestion) and Phase 6/7 (detection)
respectively. This phase stops once both indices exist, empty, with their
mappings verified as described above.

Report back: confirmation both indices were created with the exact mappings
given, and the actual results of all three verification tests (nested
segment isolation, calls semantic binding, findings denormalization
round-trip).
````

---

## What "good" looks like

- Both indices exist, empty, with zero data — this phase produces schemas, not content.
- The nested-segment isolation test genuinely proves cross-contamination doesn't happen — this is the exact failure mode a plain object array would have silently allowed, and it's cheap to verify now versus discovering it once `search_calls` starts returning wrong results in a later phase.
- The `calls` index's semantic field is confirmed working against the same multilingual model already validated for regulations — one less thing to debug when Phase 5 starts writing real transcripts to it.
- The dual-write flag on `status` (MySQL `compliance_case.status` ↔ ES `compliance_findings.status`) is written down now, in code comments and in this doc, so whoever builds Phase 8's case-workflow logic doesn't discover the drift risk by accident.
