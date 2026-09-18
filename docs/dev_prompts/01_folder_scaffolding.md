# Vigil — Phase 1 Dev Prompt: Folder Scaffolding
`docs/dev_prompts/01_folder_scaffolding.md`

---

## Why this phase matters more than it looks like it should

This is the first thing that runs, and it's also the first thing a judge sees when they open the repo — before a single detection, agent call, or UI screen exists. A clean, purposeful tree signals "this team knew exactly what they were building before they wrote a line of code." A messy one undercuts every later claim about the system being reliable and auditable, no matter how good the actual pipeline is.

Two things this phase must get right, because everything after it depends on them:
1. **Every folder name maps to one real responsibility in the architecture** — no `misc/`, no `utils2/`, no folder whose purpose you'd have to explain out loud.
2. **The locked contracts (Section 21 of the Technical Doc) exist as real files from minute one** — the `ComplianceFinding` schema, the Elasticsearch mappings, and the MySQL DDL are not TODOs to fill in later; they're pasted in now, verbatim, so every subsequent track and every subsequent agent session works against the same fixed shapes.

---

## The prompt (paste this verbatim to Codex / Claude Code / Antigravity)

````
You are scaffolding the repository structure for "Vigil" — an autonomous,
explainable compliance intelligence platform for BFSI that monitors RM sales
calls and produces an auditable Evidence Chain for each compliance finding.

Your ONLY job in this phase is to create the folder structure, placeholder
files, and the three locked data contracts below. Do NOT write business logic,
do NOT implement the ingestion pipeline, detection engine, agents, or API
routes yet — those are later phases. Every file you create in this phase is
either a directory placeholder, a stub with a purpose-comment header, or one
of the three locked contract files (which must be complete and correct, not
stubs).

Create exactly this structure:

vigil/
├── README.md
├── ARCHITECTURE.md
├── .env.example
├── .gitignore
│
├── docs/
│   ├── phase_plan.md
│   ├── pitch.md
│   ├── techstack.md
│   └── dev_prompts/
│       ├── 01_folder_scaffolding.md          (this file, already provided)
│       ├── 02_connectivity_dry_test.md
│       ├── 03_es_indexes_regulation_indexing.md
│       ├── 04_frontend_scaffolding.md
│       ├── 05_audio_ingestion_pipeline.md
│       ├── 06_detection_engine.md
│       ├── 07_investigator_agent.md
│       ├── 08_backend_api_case_workflow.md
│       ├── 09_agent_builder_tools_ai_chat.md
│       ├── 10_frontend_integration.md
│       ├── 11_benchmark_run.md
│       ├── 12_observability_panel.md
│       ├── 13_guardrails_hardening.md
│       └── 14_integration_testing_bugfixing.md
│       (create these 13 remaining files as empty placeholders with a single
│        line: "# Phase N — <title from the filename>. Not yet written.")
│
├── data/
│   ├── schemas/                               ← THE LOCKED CONTRACTS (see below)
│   │   ├── compliance_finding_schema.py
│   │   ├── mysql_ddl.sql
│   │   └── es_mappings/
│   │       ├── calls_mapping.json
│   │       ├── regulations_mapping.json
│   │       └── compliance_findings_mapping.json
│   └── sample/                                ← placeholders only, populated in
│       ├── rm_roster.csv                        pre-event setup, not this phase
│       ├── customers.csv
│       ├── products.csv
│       └── transactions.csv
│
├── CallAudio/                                  (empty dir + .gitkeep — new
│                                                 recordings land here)
├── CallAudio-Archive/                          (empty dir + .gitkeep)
├── CallAudio-Failed/                           (empty dir + .gitkeep)
│
├── RegulatoryDocs/                             ← the 5 source regulation files
│   ├── SEBI/
│   │   ├── sebi_mf_regulations_1996_amended_2023.pdf   (placeholder — real
│   │   ├── sebi_mf_regulations_2026.pdf                 file dropped in during
│   │   └── sebi_master_circular_2026.pdf                pre-event setup)
│   └── AMFI/
│       ├── amfi_code_of_ethics_2026.pdf
│       └── amfi_distributor_code_of_conduct_2022.pdf
│
├── backend/
│   ├── main.py                                 (stub: FastAPI app entrypoint)
│   ├── requirements.txt
│   ├── .env.example
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── calls.py
│   │       ├── findings.py
│   │       ├── cases.py
│   │       ├── documents.py
│   │       ├── chat.py
│   │       ├── dashboard.py
│   │       └── benchmark.py
│   ├── agents/
│   │   ├── agent_builder_tools.py              (search_calls, search_regulations,
│   │   │                                         get_customer_profile, etc.)
│   │   ├── investigator_agent.py               (Bedrock — primary)
│   │   ├── gemini_fallback.py                  (Gemini — same-schema fallback)
│   │   └── prompts/
│   │       └── investigator_prompt.md
│   ├── ingestion/
│   │   ├── file_watcher.py
│   │   ├── filename_parser.py
│   │   ├── stability_check.py
│   │   └── audio_validator.py
│   ├── sarvam/
│   │   └── sarvam_client.py                    (STT + diarization wrapper)
│   ├── elastic/
│   │   ├── client.py
│   │   ├── indexer.py
│   │   └── queries/
│   │       ├── hybrid_search.py
│   │       ├── semantic_search.py
│   │       └── esql_queries.py
│   ├── compliance/
│   │   ├── deterministic_rules.py              (regex/keyword layer)
│   │   ├── semantic_matcher.py                 (semantic_text candidate matching)
│   │   └── candidate_builder.py
│   ├── db/
│   │   ├── models.py                           (SQLAlchemy models — rm,
│   │   │                                         customer, product,
│   │   │                                         compliance_case, transaction)
│   │   ├── session.py
│   │   └── migrations/
│   ├── workflows/
│   │   ├── case_service.py                     (case creation/status transitions)
│   │   ├── notification_service.py
│   │   └── guardrails.py                       (no HIGH finding without
│   │                                             timestamp + regulation;
│   │                                             confidence threshold routing)
│   └── tests/
│       ├── unit/
│       └── integration/
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── router.tsx
│       ├── pages/
│       │   ├── Dashboard/
│       │   ├── AIInvestigation/
│       │   ├── Calls/
│       │   ├── ComplianceCases/
│       │   │   └── CaseDetail/
│       │   ├── RMAnalytics/
│       │   ├── Regulations/
│       │   └── Settings/
│       ├── components/
│       │   ├── shared/
│       │   │   ├── SeverityBadge/
│       │   │   ├── CaseCallTable/
│       │   │   ├── AudioPlayer/               (WaveSurfer.js wrapper)
│       │   │   ├── TranscriptViewer/
│       │   │   ├── EvidenceChainPanel/
│       │   │   ├── TrendChart/
│       │   │   └── ChatMessageCard/
│       │   └── layout/
│       │       ├── Sidebar/
│       │       ├── Topbar/
│       │       └── AppShell/
│       ├── services/                          (typed API clients — one file
│       │   ├── callsService.ts                 per FastAPI route group above)
│       │   ├── findingsService.ts
│       │   ├── casesService.ts
│       │   ├── documentsService.ts
│       │   ├── chatService.ts
│       │   ├── dashboardService.ts
│       │   └── benchmarkService.ts
│       ├── types/                              (TS types mirroring
│       │   └── complianceFinding.ts             compliance_finding_schema.py —
│       │                                        keep these two in sync by hand
│       │                                        until codegen is worth the time)
│       ├── hooks/
│       └── styles/
│
└── scripts/
    ├── seed_mysql.py                           (loads data/sample/* into MySQL)
    ├── create_es_indices.py                    (applies data/schemas/es_mappings/*)
    ├── run_benchmark.py
    └── poc/                                     (throwaway pre-event spike
        ├── sarvam_poc.py                         scripts — not reused as-is)
        ├── elasticsearch_poc.py
        ├── bedrock_poc.py
        └── gemini_poc.py

NAMING RULES — follow these exactly, no exceptions, no mixing conventions
within the same layer:
- Python files and folders: snake_case (e.g. `investigator_agent.py`,
  `case_service.py`).
- React component folders: PascalCase, matching the component name exactly
  (e.g. `AudioPlayer/`, `CaseDetail/`) — the folder name IS the component name.
- React service/hook/type files: camelCase (e.g. `callsService.ts`,
  `useAudioSeek.ts`).
- Markdown docs: snake_case (e.g. `phase_plan.md`), except files this
  convention already fixes (`README.md`, `ARCHITECTURE.md`).
- Dev prompt files: always `NN_short_description.md` with a zero-padded
  two-digit phase number — this is what keeps `docs/dev_prompts/` sorted in
  build order in every file browser and in the repo history.
- Regulatory source files: `<regulator>_<document_short_name>_<year>.pdf`,
  lowercase, underscores only — never the original messy download filename.
  This alone is a small, visible signal of care when a judge browses
  `RegulatoryDocs/`.

FOR EVERY STUB FILE (i.e. everything except the three locked contracts below):
write only a short header comment stating the file's single responsibility
and which phase will implement it, e.g.:

    # investigator_agent.py
    # Combines call evidence + customer context + product context + RM
    # history + matched regulation into one ComplianceFinding via a single
    # AWS Bedrock call (Gemini fallback in gemini_fallback.py).
    # Implemented in Phase 7 — see docs/dev_prompts/07_investigator_agent.md.

Do not write any actual logic in these stub files yet.

NOW CREATE THE THREE LOCKED CONTRACTS WITH REAL, COMPLETE CONTENT (not stubs):

1. data/schemas/compliance_finding_schema.py — the exact Pydantic model:

from pydantic import BaseModel
from typing import Literal

class ComplianceFinding(BaseModel):
    finding_id: str
    call_id: str
    category: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    timestamp_start: str
    timestamp_end: str
    transcript_evidence: str
    customer_risk_profile: str
    product_risk_class: str
    regulation_id: str
    reasoning: str
    confidence: float
    recommended_action: str

2. data/schemas/mysql_ddl.sql — the exact schema (rm, customer, product,
   compliance_case, transaction tables) as defined in the Technical Doc,
   Section 4.5. Copy it verbatim.

3. data/schemas/es_mappings/ — three JSON mapping files derived from the
   Technical Doc Section 7.1 document shapes (calls, regulations,
   compliance_findings), written as valid Elasticsearch index mapping JSON
   (not just example documents — actual `"mappings": {"properties": {...}}`
   structures), including a `semantic_text` field type on `transcript_semantic`
   and `content_semantic` respectively.

Finally:
- README.md: a short top-level summary (one-line pitch, link to
  ARCHITECTURE.md and docs/pitch.md, and a "Data Disclosure" section stating
  plainly that customer/RM/product/transaction data is synthetic and the
  regulatory documents are real public SEBI/AMFI material).
- ARCHITECTURE.md: paste the high-level architecture diagram from the
  Technical Doc Section 5, unmodified.
- .gitignore: standard Python + Node ignores, plus explicit entries for
  `CallAudio/*`, `!CallAudio/.gitkeep` (same pattern for the other two audio
  folders) so the folder structure is preserved in git without committing
  real or synthetic audio files.
- .env.example (root and backend/): placeholder keys for AWS Bedrock, Gemini,
  Sarvam, Elasticsearch, and MySQL — values as `<REPLACE_ME>`, never real
  credentials.

Do not proceed to implement any route, model, agent, or pipeline stage beyond
what's listed above. Stop once the tree, stubs, and three locked contracts
exist and report back the full tree you created.
````

---

## What "good" looks like when this phase is done

- `git log` shows one clean commit: "Phase 1: repository scaffolding + locked contracts" — nothing implemented, nothing half-wired.
- The three locked contract files under `data/schemas/` are real and correct, not placeholders — every later phase and every parallel AI-agent track pastes these in as fixed context per Section 21.2 of the Technical Doc, so getting them right here is what prevents integration pain at Hour-equivalent checkpoints later.
- Every stub file's one-line header comment is, by itself, a legible table of contents for the whole system — a judge (or a teammate) should be able to understand what Vigil does just by running `find backend frontend -name "*.py" -o -name "*.ts" | xargs head -1`.
- `RegulatoryDocs/SEBI/` and `RegulatoryDocs/AMFI/` are visibly organized by regulator with clean, consistent filenames — this is a cheap, visible signal of the same care the Evidence Chain claims to bring to the actual detection logic.
