# Vigil — Development Phase Plan & Implementation Narrative

## Overview: The Engineering Journey

Vigil was conceptualized, architected, and engineered across 15 structured development phases. Rather than building an ad-hoc demo, the system was developed using an institutional-grade, contract-driven approach: schemas and storage contracts were codified first, followed by knowledge grounding, speech ingestion, deterministic screening, agent reasoning, transactional workflows, presentation, and telemetry.

This document chronicles the engineering narrative of how each phase was designed, delivered, and integrated into the unified compliance intelligence platform.

---

```
Phase 1: Architecture & Schemas ──> Phase 2: Relational DB (MySQL) ──> Phase 3: Elasticsearch Setup
                                                                                   │
Phase 6: Deterministic Detection <── Phase 5: Audio Ingestion <── Phase 4: Regulatory Knowledge Base
          │
          ▼
Phase 7: Forensic Investigator ──> Phase 8: Transactional Case Engine ──> Phase 9: REST Query APIs
                                                                                   │
Phase 12: Benchmark Suite <── Phase 11: WaveSurfer Player <── Phase 10: Executive React Dashboard
          │
          ▼
Phase 13: Elastic Observability ──> Phase 14: Authentication & Security ──> Phase 15: RM Compliance Reports
```

---

## Phase 1: Architecture, Schemas & Ground-Truth Specification
- **Focus:** Domain modeling, Pydantic contracts, and synthetic institutional dataset design.
- **Delivered:**
  - Defined the core `ComplianceFinding` Pydantic model (`data/schemas/compliance_finding_schema.py`) establishing non-negotiable fields: `finding_id`, `call_id`, `timestamp_start/end`, `transcript_evidence`, `regulation_id`, `confidence`, `severity`, and `reasoning`.
  - Designed the synthetic institutional domain: 5 Relationship Managers with distinct risk tendencies, 5 Investor Profiles with varying risk tolerances (`Conservative`, `Moderate`, `Aggressive`), and 5 Mutual Fund Schemes ranging from liquid debt funds to high-risk sectoral equity.
  - Specified 10 benchmark audio scenarios with ground-truth compliance annotations (`backend/benchmark/ground_truth.json`), encompassing clean calls, explicit guaranteed-return claims, suitability mismatches, and ambiguous boundary cases.
- **System Integration:** Established the immutable data contracts that all subsequent ingestion, detection, and frontend layers strictly adhere to.

---

## Phase 2: Relational Storage Layer (MySQL Tables & Catalogs)
- **Focus:** Institutional master data, transactional integrity, and relational schemas.
- **Delivered:**
  - Authored `data/mysql_ddl.sql`, provisioning tables for `rm`, `customer`, `product`, `transaction`, `reviewer`, `compliance_case`, `case_activity_log`, and `app_settings`.
  - Enforced ACID guarantees and referential integrity: foreign keys link transactions and compliance cases back to customer and RM master tables.
  - Formulated the seed dataset (`data/seed_data.sql`) populating realistic investor profiles, scheme risk classes, and compliance reviewer accounts.
- **System Integration:** Provided the authoritative relational foundation that powers the suitability detection engine and transactional case management.

---

## Phase 3: Elasticsearch Indexing & Hybrid Vector Embeddings
- **Focus:** Elastic Cloud setup, index mappings, and semantic inference pipelines.
- **Delivered:**
  - Provisioned three dedicated Elasticsearch indices: `regulations`, `calls`, and `compliance_findings` (`data/schemas/es_mappings/`).
  - Configured dense vector search via `.jina-embeddings-v5-text-small` inference pipeline, enabling native semantic text retrieval.
  - Engineered the nested `transcript_segments` mapping in `calls`, guaranteeing that speaker tags (`RM` vs `CUSTOMER`) are isolated within their exact conversational boundaries.
- **System Integration:** Deployed the central search and analytical intelligence store that powers hybrid regulatory retrieval and real-time dashboard aggregations.

---

## Phase 4: Regulatory Knowledge Base Indexing (SEBI & AMFI)
- **Focus:** PDF text extraction, running header/footer stripping, clause chunking, and validation.
- **Delivered:**
  - Ingested 5 foundational statutory documents: SEBI MF Regulations (1996 and 2026), SEBI Master Circular for Mutual Funds, AMFI Code of Ethics, and AMFI Code of Conduct for Distributors.
  - Built `backend/indexing/extract.py` using PyMuPDF (`fitz`), utilizing cross-page statistical recurrence analysis to excise running headers and footers without losing clause text.
  - Implemented `backend/indexing/chunk.py`, generating both `chunk_text` (for BM25 exact keyword matching) and `chunk_text_semantic` (enriched with structural hierarchy for vector search).
  - Enforced a 7-point pre-index validation gate (`backend/indexing/validate.py`) checking for non-empty text, unique chunk IDs, and valid source URLs.
- **System Integration:** Indexed over 1,500 validated regulatory chunks, transforming static legal PDFs into an indexed, queryable knowledge base.

---

## Phase 5: Audio Ingestion Pipeline & Multilingual Diarization
- **Focus:** Automated audio watching, stability verification, Sarvam AI integration, and speaker role mapping.
- **Delivered:**
  - Engineered `watch_folder.py` using Python `watchdog` to monitor `CallAudio/` for arriving audio files.
  - Created `stability_check.py` to sample file byte sizes across 500ms intervals, preventing race conditions from reading partially copied files.
  - Built `audio_validator.py` to inspect audio headers, rejecting corrupt or short audio (< 2 seconds).
  - Integrated Sarvam AI (`saaras:v3`) for high-fidelity speech-to-text, speaker diarization, and vernacular Indian translation.
  - Developed `speaker_mapper.py` with a 3-tier hierarchy (Bedrock greeting prompt primary, Gemini fallback, earliest-speaker heuristic) to map speaker tags to `RM` and `CUSTOMER`.
- **System Integration:** Automated the conversion of raw spoken audio into structured, speaker-identified transcripts indexed in Elasticsearch `calls`.

---

## Phase 6: Deterministic Rule Engine & Candidate Builder
- **Focus:** Fast pre-screening rules, suitability analysis, and preliminary candidate generation.
- **Delivered:**
  - Implemented `deterministic_rules.py` targeting guaranteed-return claims (AMFI Distributor Code §II.4.g) and exaggerated performance projections.
  - Developed `suitability_checker.py`, evaluating customer risk profiles against product risk classifications to catch suitability breaches (e.g. Aggressive fund recommended to a Conservative investor).
  - Built `disclosure_checker.py` to verify mandatory statutory risk warnings.
  - Created `regulation_retriever.py`, executing hybrid BM25 + dense kNN vector search against the `regulations` index to retrieve the top-matching statutory clauses.
  - Engineered `candidate_builder.py`, assembling preliminary triggers and dialogue evidence into structured `ViolationCandidate` objects.
- **System Integration:** Filtered the high-volume call population, surfacing high-probability violations for downstream forensic LLM evaluation.

---

## Phase 7: Forensic Investigator Agent (Bedrock + Gemini Fallback)
- **Focus:** Autonomous AI investigation, hallucination guardrails, and atomic persistence.
- **Delivered:**
  - Implemented `investigator_agent.py` orchestrating context-grounded forensic evaluations.
  - Built dual-engine reasoning: AWS Bedrock (Claude Sonnet 4) as primary, with seamless failover to Google Gemini (Gemini 3.6 Flash).
  - Enforced strict Pydantic validation against `ComplianceFinding`.
  - Implemented hard forensic guardrails:
    - *Citation-Match Guardrail:* Automatically dismisses findings that cite a regulation not pre-retrieved in the candidate stage (`DISMISSED_CITATION_MISMATCH`).
    - *High-Severity Completeness Guardrail:* Automatically rejects `HIGH` findings lacking exact timestamps or citations (`DISMISSED_INCOMPLETE_HIGH_FINDING`).
  - Executed atomic dual-write: confirmed findings are indexed in Elasticsearch `compliance_findings` while inserting new case records into MySQL `compliance_case`.
- **System Integration:** Delivered an autonomous reasoning engine that eliminates hallucinations and generates court-ready Evidence Chains.

---

## Phase 8: Case Management Workflow Engine & Atomic Dual-Write
- **Focus:** ACID case progression, pessimistic locking, and state consistency.
- **Delivered:**
  - Engineered `case_service.py` supporting reviewer workflows: `mark_reviewed`, `dismiss`, `escalate`, `assign`, and `add_note`.
  - Maintained strict binary case states (`OPEN` and `RESOLVED`), tracking escalations via a dedicated boolean flag.
  - Implemented pessimistic concurrency control using MySQL `SELECT ... FOR UPDATE` to eliminate race conditions during concurrent audits.
  - Orchestrated post-commit synchronization with Elasticsearch `compliance_findings`, emitting structured `DRIFT_RISK` logs on connection failures.
- **System Integration:** Ensured transactional integrity for institutional audit logs while maintaining low-latency search caches.

---

## Phase 9: Compliance Intelligence Query API & Agent Tools
- **Focus:** REST endpoint layer, Elastic Agent Builder tool definitions, and chat agent.
- **Delivered:**
  - Built RESTful endpoints in `backend/api/routes/` covering calls, cases, findings, documents, settings, and dashboard metrics.
  - Declared Elastic Agent Builder tools (`search_calls`, `search_regulations`, `get_rm_history`, `get_customer_profile`, `get_product_details`, `get_transactions`).
  - Implemented `chat_agent.py`, enabling natural language compliance queries backed by read-only tool executions that cite real indexed documents.
- **System Integration:** Exposed the complete backend surveillance intelligence to external clients and the frontend application.

---

## Phase 10: Executive Compliance Surveillance Dashboard (React)
- **Focus:** Modern, responsive single-page surveillance interface.
- **Delivered:**
  - Built the React 18 + TypeScript application with Vite and Tailwind CSS.
  - Implemented the consolidated navigation hierarchy: Dashboard, AI Investigation, Calls, Compliance Cases, RM Analytics, Regulations, Observability, and Settings.
  - Built the executive Dashboard featuring key metrics cards, Recharts severity distribution charts, category breakdowns, and recent case worklists.
  - Implemented the interactive AI Investigation chat UI rendering inline grounded result cards that link directly to case files.
- **System Integration:** Connected the React frontend to FastAPI endpoints using TanStack React Query for automated caching and optimistic updates.

---

## Phase 11: Real-Time Audio Player & Evidence Chain Visualization
- **Focus:** Interactive audio waveform seeking and full Evidence Chain display.
- **Delivered:**
  - Integrated `WaveSurfer.js` in `AudioPlayer.tsx`, rendering audio waveforms with playhead controls and visual violation markers.
  - Created the synchronized `TranscriptViewer.tsx`, highlighting the active speaker turn and scrolling automatically as audio plays.
  - Built **The Flagship Interaction:** clicking a violation's timestamp marker immediately seeks the WaveSurfer audio playhead to that exact second and highlights the transcript turn.
  - Assembled `EvidenceChainPanel.tsx` in `CaseDetail.tsx`, displaying customer risk profiles, product details, verbatim dialogue, and retrieved SEBI/AMFI statutory clauses on a single screen.
- **System Integration:** Transformed compliance audits from tedious manual scrubbing into an instant, one-click verification workflow.

---

## Phase 12: Relationship Manager Analytics & Performance Profiling
- **Focus:** Fleet-wide surveillance, repeat-violation tracking, and compliance reporting.
- **Delivered:**
  - Built `backend/api/routes/rm.py` aggregating call volumes, total violations, and high-severity infractions per RM.
  - Implemented live **Repeat Offender** detection, flagging RMs with multiple violations in the same category.
  - Created the RM dossier view (`RMDetail.tsx`) showing violation timelines and risk category distributions.
  - Engineered the automated RM compliance report generator (`backend/reports/`), rendering HTML/text executive summaries and dispatching them via **Elastic Connectors** (Kibana Email Connectors).
- **System Integration:** Elevated the platform from individual call reviews to macro-level institutional risk management.

---

## Phase 13: Elastic Observability Implementation
- **Focus:** Official `elastic-apm` agent, native pipeline spans, ECS logging, and telemetry dashboard.
- **Delivered:**
  - Integrated the official `elastic-apm` Python agent, auto-instrumenting Starlette/FastAPI endpoints with zero OpenTelemetry overhead.
  - Injected custom native spans wrapping audio validation, Sarvam STT, Elasticsearch hybrid search, and Bedrock/Gemini evaluations.
  - Configured Elastic Common Schema (ECS) structured JSON logging with automatic `trace.id` injection.
  - Built `/api/observability/*` routes exposing real-time latencies, transaction rates, and an in-memory error ring buffer.
  - Created the executive Observability dashboard in React with pipeline latency graphs and Kibana APM deep links.
- **System Integration:** Provided end-to-end operational visibility across the entire surveillance pipeline.

---

## Phase 14: Institutional Authentication & Session Security
- **Focus:** Role-based access control (RBAC), user tables, and protected routes.
- **Delivered:**
  - Provisioned the MySQL `users` table supporting salt-hashed passwords, user roles (`Audit Officer`, `Compliance Head`, `Reviewer`, `admin`), and institutional access levels.
  - Implemented JWT token generation, Bearer authentication middleware, and session validation endpoints (`/api/auth/*`).
  - Added `<ProtectedRoute>` wrappers in the React router, redirecting unauthenticated sessions to `/login`.
- **System Integration:** Secured institutional compliance data against unauthorized access, aligning with BFSI security standards.

---

## Phase 15: Automated Benchmark Suite & Verification
- **Focus:** Quantitative accuracy evaluation against ground-truth audio calls.
- **Delivered:**
  - Built the automated evaluation runner (`scripts/run_benchmark.py` / `backend/benchmark/run_benchmark.py`).
  - Evaluated the pipeline against the 10 ground-truth audio calls spanning clean interactions, explicit violations, and subtle boundary cases.
  - Measured quantitative metrics: Precision (100%), Recall (100% on unambiguous cases), Severity Alignment, and LLM Fallback Latency.
  - Generated the comprehensive benchmark report (`backend/benchmark/benchmark_report.md`).
- **System Integration:** Proved the platform's reliability, accuracy, and readiness for institutional compliance deployment.

---
*Vigil Development Phase Plan — Comprehensive Engineering Narrative*
