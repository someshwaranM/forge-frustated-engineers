# Vigil — Phase 3 Dev Prompt: Regulatory Indexing
`docs/dev_prompts/03_es_indexes_regulation_indexing.md`

*(Scope: everything in this phase lives inside `backend/`. Extraction,
cleaning, chunking, and indexing only — no retrieval/query strategy, no
detection engine, no agent logic. Those come in later phases.)*

*(Revision note: the mapping below is NOT externally fixed — we own the
index design. Because of that, source_url, page_number, and every other
piece of metadata a citation needs live directly on the ES document itself.
There is no separate mapping.json lookup file in this version — it's
unnecessary now that the index can hold everything.)*

---

## The Elasticsearch mapping this phase creates

```json
{
  "mappings": {
    "properties": {
      "chunk_id": { "type": "keyword" },
      "chunk_level": { "type": "keyword" },

      "document_id": { "type": "keyword" },
      "document_name": {
        "type": "text",
        "fields": { "keyword": { "type": "keyword" } }
      },
      "regulator": { "type": "keyword" },
      "document_type": { "type": "keyword" },
      "document_version": { "type": "keyword" },
      "publication_date": { "type": "date" },
      "effective_date": { "type": "date" },
      "effective_until": { "type": "date" },
      "status": { "type": "keyword" },
      "priority": { "type": "integer" },
      "source_url": { "type": "keyword" },
      "source_file": { "type": "keyword" },
      "source_file_hash": { "type": "keyword" },

      "chapter": { "type": "keyword" },
      "section": { "type": "keyword" },
      "sub_section": { "type": "keyword" },
      "regulation_number": { "type": "keyword" },
      "clause": { "type": "keyword" },
      "paragraph": { "type": "keyword" },
      "heading": { "type": "text" },
      "citation_label": { "type": "keyword" },

      "clause_text": { "type": "text" },
      "chunk_text": { "type": "text" },
      "chunk_text_semantic": { "type": "semantic_text" },
      "page_number": { "type": "integer" },
      "indexed_at": { "type": "date" }
    }
  }
}
```

**Field groups, and why each exists:**
- **Document-level** — everything needed to identify, cite, and rank the source document itself. `priority` is a RANKING/BOOST signal only — it is NOT the authoritative legal precedence mechanism. `status`, `effective_date`, and `effective_until` are what represent actual legal applicability; `priority` just biases retrieval toward the currently-applicable version so it surfaces first. A later phase's Investigator Agent must reason from `status`/`effective_date`, never treat `priority=10` as itself meaning "this is legally superior." `source_file_hash` is stored now (one line to compute) purely as a future-proofing value — this phase does NOT build any hash-based change-detection or incremental-reindex logic on top of it; that's infrastructure for a problem this fixed, 5-document corpus doesn't have.
- **Structural** — the exact identifiers (chapter/section/clause/etc.) as `keyword` fields, since these are looked up and filtered on exactly, never full-text searched. `citation_label` is a precomputed, ready-to-display string (e.g. `"AMFI Distributor Code §II.4.g, p.12"`) so the Investigator Agent in a later phase never has to reconstruct a citation from parts — it just reads this field.
- **Content/retrieval** — `chunk_text` is the BM25 field: heading + `clause_text` + short immediate context, tuned for precise phrase/keyword matching. `chunk_text_semantic` is a deliberately RICHER, retrieval-oriented composition — not a blind copy of `chunk_text` — built from document_name + chapter/section + regulation number + clause + heading + `clause_text` + broader surrounding context, giving semantic retrieval more of the context a paraphrased query needs, while `clause_text` alone stays the exact, minimal citation text. This is the genuine hybrid capability the earlier fixed-schema version couldn't have.

---

## The folder structure this phase creates (all inside `backend/`)

```
backend/
└── indexing/
    ├── extract.py                  (PDF → cleaned text, one function per doc type)
    ├── chunk.py                    (cleaned text → chunk JSON, per doc-type strategy)
    ├── index_to_es.py              (wipes + reindexes Elasticsearch from chunks/)
    ├── run_pipeline.py             (single entrypoint: runs everything below in order)
    ├── extracted/
    │   ├── AMFI_Codeof_Ethics_2026.txt
    │   ├── Revised_Codeof_Conductfor_Mutual_Fund_Distributors_April2022.txt
    │   ├── master-circular-for-mutual-funds.txt
    │   ├── securities-and-exchange-board-of-india-mutual-funds-regulations-1996-last-amended-on-february-07-2023.txt
    │   └── securities-and-exchange-board-of-india-mutual-funds-regulations-2026-last-amended-on-july-7-2026.txt
    └── chunks/
        ├── AMFI_Codeof_Ethics_2026.json
        ├── Revised_Codeof_Conductfor_Mutual_Fund_Distributors_April2022.json
        ├── master-circular-for-mutual-funds.json
        ├── securities-and-exchange-board-of-india-mutual-funds-regulations-1996-last-amended-on-february-07-2023.json
        └── securities-and-exchange-board-of-india-mutual-funds-regulations-2026-last-amended-on-july-7-2026.json
```

Each `extracted/<pdf_stem>.txt` and `chunks/<pdf_stem>.json` is named after the
actual source PDF's filename (stem only). Each `chunks/<pdf_stem>.json` now
contains the FULL ES document shape per chunk (all fields from the mapping
above, including `source_url` and `page_number` directly) — it's not a
partial record anymore, it's exactly what gets bulk-indexed.

---

## The prompt (paste this verbatim to Codex / Claude Code / Antigravity)

````
You are running Phase 3 of the Vigil build: extracting, cleaning, chunking,
and indexing the 5 regulatory source PDFs into Elasticsearch. Everything in
this phase lives inside backend/indexing/ — do not create files outside
backend/ for this phase. Do NOT implement retrieval/query logic, hybrid
search ranking, the detection engine, or the Investigator Agent — this phase
only produces clean staging files and a correctly populated Elasticsearch
index.

Before starting, read docs/regulatory_corpus.md for document-specific detail
(which sections/clauses matter per document, the real source URLs).

STEP 1 — Create backend/indexing/ with the extracted/ and chunks/
subfolders (empty initially).

STEP 2 — Create the Elasticsearch "regulations" index using the mapping
below exactly as given:

{full mapping JSON from above}

Verify the semantic_text field actually binds to a working inference
endpoint before moving on — do this by indexing one throwaway test document
with real text in chunk_text_semantic, then running a real semantic query
against it and confirming it returns a relevant result. A semantic_text
field can accept the mapping successfully while its backing inference
endpoint is not properly deployed, and this only surfaces later as silently
empty semantic query results if not caught now. Delete the throwaway test
document once confirmed.

STEP 3 — Extraction (backend/indexing/extract.py), per PDF, using PyMuPDF
(fitz):

For each of the 5 PDFs in RegulatoryDocs/SEBI/ and RegulatoryDocs/AMFI/:

a) Open with fitz and iterate pages using page.number (PyMuPDF's own
   zero-indexed physical page counter). Convert to a 1-indexed PHYSICAL page
   number (page.number + 1) and use ONLY this physical page number
   throughout the entire pipeline — never rely on a printed/logical page
   number from the document's own text. These documents are inconsistent
   about printed numbering (some restart per chapter, some front-matter
   pages are unnumbered); physical page number is the only value guaranteed
   to exist and be unambiguous for every page.

b) For each page, extract text preserving reading order and block/line
   structure (use page.get_text("blocks") or page.get_text("dict") — NOT a
   flat page.get_text() string dump, since block/line boundaries are needed
   to detect headers/footers and headings).

c) Header/footer detection and removal (before writing the cleaned .txt):
   - Collect the first 1-2 lines and last 1-2 lines of every page.
   - Any line (after normalizing whitespace and stripping page-number
     digits) recurring on more than ~60% of pages is a header or footer —
     strip it everywhere it appears.
   - Do not strip a genuine section heading that spans several CONSECUTIVE
     pages. A true header/footer recurs near-verbatim across NON-adjacent
     pages (e.g. page 4 and page 47); only strip lines with that
     non-adjacent-page recurrence pattern.
   - Log which lines were stripped as headers/footers per document, so this
     is auditable, not silent.

d) Reconstruct cleaned full document text in reading order, embedding a
   page-boundary marker at each physical page transition internally so the
   chunker in Step 4 can determine which physical page any chunk's text
   started on. Strip these markers back out before writing the final
   human-readable .txt (keep the page-boundary offsets separately, e.g. as
   a parallel list your chunker consults) — the .txt files must read as
   clean continuous text with no marker artifacts.

e) Write the cleaned text to backend/indexing/extracted/<pdf_stem>.txt,
   where <pdf_stem> is the PDF's filename without its .pdf extension,
   exactly matching the real filenames in RegulatoryDocs/.

f) Extraction quality check (detection only — NOT an OCR pipeline; these are
   official born-digital SEBI/AMFI PDFs, already spot-checked as clean text,
   so building a full OCR fallback is disproportionate infrastructure for a
   fixed 5-document corpus with no scanned pages. What's still worth having
   cheaply is the safety property: never silently index a blank or garbled
   page). For every page, check extracted character count and alphabetic
   character ratio. If a page's extracted text falls below a low threshold
   (e.g. under 20 characters, or under 50% alphabetic characters after
   stripping whitespace/punctuation), flag that page as FAILED rather than
   silently including its near-empty content. Track and report per document:
       pages_total
       pages_extracted   (extracted cleanly, above threshold)
       pages_flagged     (below threshold — did not meet quality check)
   If any page is flagged, the pipeline must STOP for that document and
   report exactly which physical page number(s) failed and why, rather than
   proceeding to index a gap silently. Do not attempt OCR — surface the flag
   so a human can inspect that specific page.

STEP 4 — Chunking (backend/indexing/chunk.py), per-document-type — do NOT
use one generic fixed-size chunker for all 5:

1. securities-and-exchange-board-of-india-mutual-funds-regulations-2026-last-amended-on-july-7-2026
   securities-and-exchange-board-of-india-mutual-funds-regulations-1996-last-amended-on-february-07-2023
   → Chunk by: Chapter → Regulation → Sub-regulation → Paragraph.
   → status: "current" for the 2026 file, "historical" for the 1996 file.
   → priority: 10 for the 2026 file, 1 for the 1996 file.
   → document_type: "REGULATION".

2. master-circular-for-mutual-funds
   → Chunk by: Chapter/Topic → Sub-topic → Requirement/paragraph. Largest,
     most operationally detailed document — do not let a requirement get
     separated from the context paragraph it depends on; prefer slightly
     larger chunks over splitting a requirement in half.
   → status: "current", priority: 10, document_type: "MASTER_CIRCULAR".

3. AMFI_Codeof_Ethics_2026
   → Chunk by: Section → Subsection → Paragraph/Clause.
   → status: "current", priority: 10, document_type: "CODE_OF_ETHICS".

4. Revised_Codeof_Conductfor_Mutual_Fund_Distributors_April2022
   → Chunk by clause-level wherever the document's own numbering allows it
     (e.g. II.4.g as its own chunk) — this document has the most precisely
     citable language for Vigil's core detection categories, so clause-level
     granularity matters more here than for any other document.
   → status: "current", priority: 10, document_type: "CODE_OF_CONDUCT".

For every chunk, determine its originating physical page number from the
page-boundary offsets recorded in Step 3(d) — if a chunk spans more than one
physical page, use the page where the chunk STARTS.

STEP 5 — Populate every field in the mapping for each chunk, and write the
full array of chunk documents for each PDF to
backend/indexing/chunks/<pdf_stem>.json (this file IS the exact bulk-index
payload — every field below must be present, using null only for
effective_until when genuinely unknown):

    chunk_id            deterministic, e.g. "AMFI_MFD_COC_2022_II_4_g" —
                         same clause → same ID every run, for debugging and
                         citation stability (NOT for deduplication — see
                         Step 7).
    chunk_level          "clause" | "sub_regulation" | "requirement" |
                         "paragraph" — whichever granularity this chunk is.
    document_id          a stable slug, e.g. "AMFI_MFD_COC_2022".
    document_name        full document title.
    regulator            "SEBI" or "AMFI".
    document_type        per Step 4 above.
    document_version     e.g. "April 2022", "2026".
    publication_date     from docs/regulatory_corpus.md.
    effective_date       from docs/regulatory_corpus.md (use publication_date
                         if no distinct effective date is documented).
    effective_until      ONLY set with a real, confirmed date — null
                         otherwise, never guessed.
    status               "current" or "historical" per Step 4.
    priority             10 or 1 per Step 4.
    source_url           the real URL from docs/regulatory_corpus.md — never
                         invented.
    source_file          relative path, e.g.
                         "RegulatoryDocs/AMFI/Revised_Codeof_Conductfor_Mutual_Fund_Distributors_April2022.pdf".
    source_file_hash     SHA-256 of the source PDF file (compute and store
                         only — no reindex/versioning logic built on this
                         value in this phase).
    chapter/section/
    sub_section/
    regulation_number/
    clause/paragraph     whichever apply to this document type and chunk —
                         leave any that don't apply as empty string, not null.
    heading              the structural heading immediately above this chunk.
    citation_label        precomputed display string, e.g.
                         "AMFI Distributor Code §II.4.g, p.12" — build this
                         from document_name/clause/page_number so later
                         phases never reconstruct a citation string by hand.
    clause_text          exact clause wording only.
    chunk_text           heading + clause_text + short surrounding context,
                         concatenated — the BM25 field, tuned for precise
                         phrase/keyword matching.
    chunk_text_semantic  a RICHER, retrieval-oriented composition — NOT a
                         blind copy of chunk_text. Build it from:
                         document_name + chapter/section + regulation_number
                         + clause + heading + clause_text + broader
                         surrounding context (more than chunk_text's short
                         context window). This gives semantic retrieval the
                         fuller context a paraphrased query benefits from,
                         while clause_text alone stays the exact, minimal
                         citation text.
    page_number          physical page number per Step 3/4.
    indexed_at           timestamp of this indexing run (ISO 8601).

STEP 6 — Validation gate (backend/indexing/validate.py) — run this BEFORE
indexing, on every chunk in every backend/indexing/chunks/*.json file. This
is a hard gate: if any check fails, the pipeline STOPS and reports exactly
which chunk(s) failed which check — it does NOT proceed to indexing with bad
data just because extraction/chunking technically completed. Checks:
    - clause_text is non-empty wherever clause is non-empty.
    - Every chunk from Revised_Codeof_Conductfor_Mutual_Fund_Distributors_April2022
      has a non-empty clause field — this document's whole value is precise
      clause-level citation, so a missing clause number here is a hard
      failure, not a warning.
    - page_number is present and >= 1 on every chunk.
    - source_url is present and non-empty on every chunk.
    - chunk_id is unique — no duplicates within a single document's chunk
      array, and no duplicates across all 5 documents combined.
    - All required metadata fields are present (document_id, document_name,
      regulator, document_type, status, priority) — no missing/null values
      outside the explicitly-nullable effective_until.
    - chunk_text and chunk_text_semantic are not obvious extraction garbage
      (e.g. mostly non-alphanumeric characters, or a leftover stripped
      header/footer fragment that slipped through Step 3(c)).
Report a pass/fail count per document and a full list of any failures found.

STEP 7 — Indexing (backend/indexing/index_to_es.py): wipe the "regulations"
index completely (delete all documents, or drop and recreate using the Step
2 mapping), then bulk-index every chunk document from every
backend/indexing/chunks/*.json file, unmodified — the JSON files ARE the
payload. Only run this step if Step 6 passed with zero failures. Every run
starts from a clean, empty index — do not rely on upsert-by-chunk_id to
prevent duplicates; the clean wipe is what prevents them.

STEP 8 — Build backend/indexing/run_pipeline.py as the single entrypoint
that runs Steps 3 through 7 in order for all 5 documents. Running it must be
a full, clean rebuild every time:
    a) Delete everything inside backend/indexing/extracted/ and
       backend/indexing/chunks/ (keep the folders themselves).
    b) Re-run extraction (Step 3) for all 5 PDFs → repopulates extracted/.
    c) Re-run chunking (Step 4-5) for all 5 PDFs → repopulates chunks/.
    d) Run the validation gate (Step 6) — halt here if it fails.
    e) Wipe and reindex Elasticsearch (Step 7) from the fresh chunks/.
This is the command to run any time chunking logic changes — it guarantees
extracted/, chunks/, and the ES index are always in sync with current code,
with nothing stale left over from a previous version of the chunking logic.

STEP 9 — Verification. Confirm, for real, with actual output:
- backend/indexing/extracted/ contains exactly 5 .txt files, correctly
  named, with header/footer lines actually removed (spot check: grep a
  known repeated header string across a couple of the .txt files and
  confirm it appears 0 times, or only where genuinely part of clause
  content).
- backend/indexing/chunks/ contains exactly 5 .json files, each a valid
  JSON array of complete chunk documents (every mapping field present, no
  unexpected nulls beyond effective_until where genuinely unknown).
- Elasticsearch document count matches the total chunk count across all 5
  chunks/*.json files.
- Every chunk from Revised_Codeof_Conductfor_Mutual_Fund_Distributors_April2022
  has a non-empty clause field and a correctly built citation_label.
- Run a real semantic query against chunk_text_semantic using a paraphrased,
  non-matching-keyword statement — "you don't have to worry about losing
  money" — and confirm it returns a relevant guaranteed-return/risk-
  disclosure clause. Report the actual top result.
- Run a real BM25 query against chunk_text for "guaranteed return" and
  confirm it surfaces AMFI Distributor Code §II.4.g and/or §II.4.h. Report
  the actual top result.
- Run an exact-metadata query for clause = "II.4.g" and confirm the returned
  document has: document_id = the AMFI Distributor Code's document_id,
  clause = "II.4.g", non-empty clause_text, a correctly-built citation_label
  (e.g. "AMFI Distributor Code §II.4.g, p.12"), the correct page_number, and
  the correct source_url. This test checks the citation chain end to end,
  not just that retrieval returns something plausible.
- Run run_pipeline.py twice in a row and confirm both runs produce the same
  total chunk count per document — validates extraction/chunking is
  deterministic; the wipe-and-rebuild already guarantees no duplicates
  regardless.

Report back: total chunk count per document, pages_total/pages_extracted/
pages_flagged per document from Step 3(f), 2-3 example header/footer lines
stripped per document, the validation gate's pass/fail summary from Step 6,
the actual results of all three verification queries (semantic, BM25, exact
clause/citation), and the two-run consistency check output.
````

---

## What "good" looks like

- Every chunk document in `chunks/*.json` has every mapping field populated correctly — this file is now the literal bulk-index payload, so what's in it is exactly what's in Elasticsearch. The validation gate (Step 6) is what makes this a guarantee rather than a hope — bad chunks never reach the index in the first place.
- The semantic query test actually returns a relevant clause for a paraphrased statement — this is the real proof that `chunk_text_semantic`'s richer context composition is doing genuine embedding-based retrieval, not just present in the mapping.
- The exact-clause query returns a document whose `citation_label`, `page_number`, and `source_url` all check out correctly — this is the test that validates the full citation chain end to end, not just that retrieval returns something plausible.
- `citation_label` reads correctly on inspection (e.g. `"AMFI Distributor Code §II.4.g, p.12"`) — this is what a later phase's Investigator Agent drops straight into a finding's citation, with zero string-assembly logic of its own.
- Running `run_pipeline.py` twice back-to-back gives identical chunk counts both times, and the Elasticsearch document count always matches the sum of `chunks/*.json` — the whole staging-to-index chain stays in sync every time you rerun it.
- `pages_flagged` is reported and, ideally, zero across all 5 documents — confirming the extraction-quality check ran and found nothing to worry about, without having built a full OCR pipeline for a risk this corpus doesn't carry.
- `source_file_hash` is present on every document but nothing in this phase reads or acts on it yet — it's stored for future use, not wired into any change-detection logic, which is the right amount of investment for a corpus of 5 fixed files that won't change this week.
