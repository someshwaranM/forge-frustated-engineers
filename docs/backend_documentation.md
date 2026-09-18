# Vigil — Backend Architecture & Service Documentation

## 1. Overview & Service Layout

Vigil's backend is implemented in **Python 3.11+** utilizing **FastAPI**, **Pydantic v2**, **Elasticsearch**, and **MySQL 8.0**. It exposes high-throughput asynchronous REST APIs, orchestrates background audio surveillance pipelines, enforces strict forensic guardrails against AI hallucinations, and guarantees transactional auditability via atomic dual-writes.

### Directory Structure & Responsibilities

```
backend/
├── main.py                    # Application factory, APM middleware, exception handlers, route mounting
├── requirements.txt           # Production Python dependency manifest
├── api/
│   └── routes/                # FastAPI APIRouter modules (calls, cases, rm, chat, etc.)
├── ingestion/                 # Audio acquisition, watchdog, stability checks, and speaker mapping
├── sarvam/                    # Sarvam AI API client (Saaras v3 STT, diarization, translation)
├── indexing/                  # PDF extraction, semantic chunking, validation gate, and ES indexing
├── compliance/                # Deterministic rule engine, suitability checker, hybrid retriever
├── agents/                    # Bedrock/Gemini Forensic Investigator and AI Chat Agent
│   └── prompts/               # System prompt templates for forensic evaluation and chat
├── workflows/                 # Transactional case service, user authentication, and dual-write logic
├── reports/                   # RM performance reporting engine and email dispatch services
├── db/                        # PyMySQL database connection pooling and session management
├── elastic/                   # Elasticsearch client initialization and query builders
├── observability/             # Native Elastic APM instrumentation, spans, and ECS logging
└── benchmark/                 # Automated benchmark test suite against 10 ground-truth calls
```

---

## 2. Module-by-Module Technical Breakdown

### 2.1 Ingestion Pipeline (`backend/ingestion/`)
- **`watch_folder.py` / `file_watcher.py`:** Runs a background file observer using `watchdog.observers.Observer`. Watches `CallAudio/` for filesystem events matching `*.wav` and `*.mp3`.
- **`stability_check.py`:** Resolves the common race condition where files are picked up mid-copy. Measures file size across 3 consecutive checks with a 500ms delay. Only files with constant size and non-zero bytes are released.
- **`audio_validator.py`:** Validates audio headers. Enforces that recordings are valid PCM/RIFF or MPEG audio, duration > 2.0 seconds, and sample rate >= 8000 Hz. Moves corrupted files to `CallAudio-Failed/`.
- **`filename_parser.py`:** Deconstructs standard call filenames using regex: `CALL_{rm_id}_{customer_id}_{YYYYMMDD}_{HHMM}.(wav|mp3)`. Populates call metadata before speech processing.
- **`speaker_mapper.py`:** Resolves generic diarization speaker tags (`speaker_0`, `speaker_1`) to roles (`RM`, `CUSTOMER`). Executes:
  1. *AWS Bedrock Primary:* Calls Bedrock with a conversational prompt examining the call opening. RMs follow a distinct pattern of identifying themselves, their institution, and greeting the client.
  2. *Google Gemini Fallback:* Executes if Bedrock fails or times out.
  3. *Heuristic Fallback:* If both LLM calls fail, assigns `RM` to the earliest speaking party, as financial sales protocol mandates that the sales representative initiates outbound calls.

### 2.2 Speech-to-Text & Diarization (`backend/sarvam/`)
- Integrates with Sarvam AI's REST API endpoint for `saaras:v3`.
- Submits audio binaries, receiving synchronized turn-by-turn speech segments:
  - `start_time` / `end_time` in floating-point seconds.
  - Verbatim Indian vernacular text (`transcript_original_text`).
  - Standardized English translation (`transcript_english_text`).

### 2.3 Indexing & Knowledge Base (`backend/indexing/`)
- **`extract.py`:** Uses PyMuPDF (`fitz`) to extract text from 5 primary statutory PDFs. Implements cross-page statistical recurrence analysis to identify and strip running headers, footers, and page numbers.
- **`chunk.py`:** Structural parser that breaks regulatory text into clause-level units. Produces:
  - `chunk_text`: Verbatim clause text used for BM25 exact matching.
  - `chunk_text_semantic`: Enriched text prepending document title, chapter, section, and structural breadcrumbs, used to compute dense vector embeddings.
- **`validate.py`:** Enforces a 7-point hard gate before any chunk is indexed. If a chunk contains empty text, missing source URLs, or non-unique IDs, pipeline stops immediately.
- **`create_index.py`:** Deploys the `regulations` index mapping with Elasticsearch's `.jina-embeddings-v5-text-small` inference pipeline.

### 2.4 Compliance Detection & Screening (`backend/compliance/`)
- **`deterministic_rules.py`:** Evaluates RM speech turns against regex rule sets:
  - *Rule 1 (Guaranteed Returns):* Unambiguous assurances of fixed gains or zero-risk investments (violating AMFI Distributor Code §II.4.g).
  - *Rule 2 (Exaggerated Claims):* Unsubstantiated performance projections without risk qualification.
- **`suitability_checker.py`:** Pulls `customer.risk_profile` and `customer.investment_experience` from MySQL. Matches against detected product's `risk_class`. Flags mismatches (e.g., Aggressive/Sectoral fund sold to a Conservative or Low-experience investor) violating AMFI Distributor Code §II.2.d.
- **`disclosure_checker.py`:** Scans transcript turns for statutory risk disclaimers ("mutual fund investments are subject to market risks"). Flags omissions.
- **`regulation_retriever.py`:** Issues a hybrid retrieval query to the `regulations` index combining BM25 keyword scoring on `chunk_text` with dense semantic vector scoring on `chunk_text_semantic`. Merges results using Reciprocal Rank Fusion (RRF).
- **`candidate_builder.py`:** Combines the triggered rules, dialogue turns, customer/product context, and top-ranked regulatory chunks into a structured `ViolationCandidate`.

### 2.5 Forensic Investigator Agent (`backend/agents/investigator_agent.py`)
- Ingests candidates and executes automated forensic evaluation:
  1. *Hard Pre-Check:* If a candidate contains zero retrieved regulation citations, it is immediately rejected as `DISMISSED_NO_CITATION`.
  2. *Context Injection:* Fetches RM historical violation count and customer KYC history.
  3. *Dual-Provider Execution:* Dispatches evaluation prompt to **AWS Bedrock (Claude Sonnet 4)**; on exception, automatically retries via **Google Gemini (Gemini 3.6 Flash)**.
  4. *Schema Validation:* Pydantic parses model output into `ComplianceFinding`.
  5. *Citation-Match Guardrail:* Verifies that `finding.regulation_id` exists in the candidate's pre-retrieved citations. Rejects hallucinations as `DISMISSED_CITATION_MISMATCH`.
  6. *High-Severity Completeness Guardrail:* If severity is `HIGH`, verifies presence of non-zero timestamps and valid statutory citations. Rejects incomplete records as `DISMISSED_INCOMPLETE_HIGH_FINDING`.
  7. *Persistence:* Confirmed findings trigger the atomic dual-write service.

### 2.6 Case Workflow & Dual-Write (`backend/workflows/case_service.py`)
- Orchestrates case lifecycle mutations: `mark_reviewed`, `dismiss`, `escalate`, `assign`, and `add_note`.
- Enforces strict binary status invariants (`OPEN` and `RESOLVED`). Escalation is a boolean flag (`escalated`), not a third status state.
- Employs pessimistic row-locking (`SELECT ... FOR UPDATE`) in MySQL to prevent race conditions during concurrent reviewer access.
- Propagates committed status changes to Elasticsearch `compliance_findings`. Emits `DRIFT_RISK` logs if Elasticsearch synchronization is interrupted.

### 2.7 Observability & Telemetry (`backend/observability/`)
- Initialized in `backend/main.py` via `_initialize_apm()`.
- Official `elastic-apm` agent auto-instruments FastAPI/Starlette HTTP endpoints. Zero OpenTelemetry overhead.
- Injects native APM spans around pipeline stages:
  - `ingestion.audio_validation`
  - `sarvam.translate_job` / `sarvam.transcribe_job`
  - `elasticsearch.index_call`
  - `elasticsearch.regulation.bm25` / `semantic`
  - `compliance.detection`
  - `investigator.candidate_eval`
  - `investigator.bedrock_call` / `gemini_call`
- Configures Elastic Common Schema (ECS) formatted JSON logging with automated `trace.id` correlation.

---

## 3. Database Architecture (MySQL Schema)

The MySQL database contains 10 institutional tables managing master data, authentication, case workflows, and audit logs.

```
+--------------------+       +--------------------+
|         rm         |       |      customer      |
+--------------------+       +--------------------+
| rm_id (PK)         |       | customer_id (PK)   |
| full_name          |       | full_name          |
| branch             |       | mobile_number      |
| joined_date        |       | risk_profile       |
| active             |       | invest_experience  |
+---------+----------+       | kyc_status         |
          |                  +---------+----------+
          |                            |
          |    +------------------+    |
          +--->|   transaction    |<---+
               +------------------+
               | transaction_idPK |
               | customer_id (FK) |
               | rm_id (FK)       |
               | product_id (FK)  |
               | amount, type     |
               | transaction_time |
               +--------+---------+
                        |
                        v
               +------------------+
               |     product      |
               +------------------+
               | product_id (PK)  |
               | product_name     |
               | risk_class       |
               | suitable_profiles|
               | disclosure_reqs  |
               +------------------+

+--------------------+       +--------------------+
|  compliance_case   |       |      reviewer      |
+--------------------+       +--------------------+
| case_id (PK)       |       | reviewer_id (PK)   |
| finding_id         |       | full_name          |
| call_id            |       | role               |
| rm_id (FK)         |       | active             |
| customer_id (FK)   |       +---------+----------+
| category           |                 |
| severity           |                 |
| status (OPEN/RES)  |                 |
| escalated (BOOL)   |                 |
| assigned_to (FK)   |<----------------+
| resolution_notes   |
| resolution_type    |
+---------+----------+
          |
          v
+--------------------+       +--------------------+
| case_activity_log  |       |    app_settings    |
+--------------------+       +--------------------+
| log_id (PK, Auto)  |       | setting_key (PK)   |
| case_id (FK)       |       | setting_value      |
| action             |       | updated_at         |
| actor (FK)         |       +--------------------+
| details            |
| timestamp          |
+--------------------+
```

### Table Definitions & Field Purposes

#### 1. `rm` (Relationship Manager Roster)
- `rm_id` (VARCHAR(20), PK): Unique identifier (e.g. `RM001`).
- `full_name` (VARCHAR(100)): Full name of the sales representative.
- `branch` (VARCHAR(100)): Assigned bank/distributor branch location.
- `joined_date` (DATE): Onboarding date for tenure calculation.
- `active` (BOOLEAN): Current employment status.

#### 2. `customer` (Investor Profiles)
- `customer_id` (VARCHAR(20), PK): Unique investor ID (e.g. `CUST001`).
- `full_name` (VARCHAR(100)): Investor full name.
- `mobile_number` (VARCHAR(20)): Contact number.
- `risk_profile` (VARCHAR(30)): Risk tolerance category (`Conservative`, `Moderate`, `Aggressive`). Primary input for suitability matrix.
- `investment_experience` (VARCHAR(20)): Market experience level (`Low`, `Medium`, `High`).
- `kyc_status` (VARCHAR(20)): Regulatory KYC compliance flag.

#### 3. `product` (Mutual Fund Scheme Catalog)
- `product_id` (VARCHAR(20), PK): Unique fund identifier (e.g. `PROD005`).
- `product_name` (VARCHAR(150)): Institutional scheme name (e.g. "Aditya Birla Sun Life Small Cap Fund").
- `risk_class` (VARCHAR(30)): Risk classification (`Low`, `Medium`, `High`).
- `suitable_risk_profiles` (VARCHAR(100)): Comma-separated list of compatible risk profiles (e.g. "Aggressive").
- `disclosure_requirements` (TEXT): Mandatory statutory disclaimers prescribed for this asset class.

#### 4. `transaction` (Investment Ledgers)
- `transaction_id` (VARCHAR(20), PK): Transaction reference ID.
- `customer_id` (VARCHAR(20), FK): Linking to `customer`.
- `rm_id` (VARCHAR(20), FK): Linking to `rm`.
- `product_id` (VARCHAR(20), FK): Linking to `product`.
- `amount` (DECIMAL(15,2)): Transaction value in INR.
- `transaction_type` (VARCHAR(30)): Transaction classification (`PURCHASE`, `REDEMPTION`, `SIP`).
- `transaction_time` (TIMESTAMP): Execution timestamp.

#### 5. `reviewer` (Compliance Officers)
- `reviewer_id` (VARCHAR(20), PK): Reviewer identifier (e.g. `REV001`).
- `full_name` (VARCHAR(100)): Compliance officer name.
- `role` (VARCHAR(50)): Institutional title (e.g. `Compliance Officer`, `Compliance Head`).
- `active` (BOOLEAN): Active review eligibility flag.

#### 6. `compliance_case` (Authoritative Case Workflow Table)
- `case_id` (VARCHAR(64), PK): Unique case ID (e.g. `CASE_CALL_RM001_CUST001_20260310_1030`).
- `finding_id` (VARCHAR(64)): Foreign key referencing Elasticsearch `compliance_findings.finding_id`.
- `call_id` (VARCHAR(64)): Call identifier referencing Elasticsearch `calls.call_id`.
- `rm_id` (VARCHAR(20), FK): Relationship manager under audit.
- `customer_id` (VARCHAR(20), FK): Customer involved in interaction.
- `category` (VARCHAR(50)): Violation type (`GUARANTEED_RETURN`, `SUITABILITY_MISMATCH`, `MISSING_DISCLOSURE`).
- `severity` (VARCHAR(10)): Risk severity (`HIGH`, `MEDIUM`, `LOW`).
- `status` (VARCHAR(20)): Workflow state. **Strictly binary: `OPEN` or `RESOLVED`.**
- `escalated` (BOOLEAN): Flag indicating escalation to supervisory audit committee.
- `assigned_to` (VARCHAR(20), FK): Current reviewer assignment.
- `resolution_notes` (TEXT): Final audit notes entered by reviewer upon resolution.
- `resolution_type` (VARCHAR(30)): Structured resolution classification:
  - `CONFIRMED_ACTION_TAKEN`: Breach upheld; corrective actions issued to RM.
  - `DISMISSED_FALSE_POSITIVE`: Reviewed and cleared as non-violative.
  - `ESCALATED_RESOLVED`: Escalation resolved by senior compliance committee.

#### 7. `case_activity_log` (Immutable Audit Trail)
- `log_id` (INT, PK AUTO_INCREMENT): Sequential log event ID.
- `case_id` (VARCHAR(64), FK): Reference to parent case.
- `action` (VARCHAR(50)): Mutation type (`STATUS_CHANGE`, `NOTE_ADDED`, `ASSIGNED`, `ESCALATED`).
- `actor` (VARCHAR(20)): Reviewer ID executing the mutation.
- `details` (TEXT): Event description or note text.
- `timestamp` (TIMESTAMP): Precise server timestamp of event.

#### 8. `app_settings` (Runtime Configuration)
- `setting_key` (VARCHAR(50), PK): Setting identifier (e.g. `confidence_threshold`).
- `setting_value` (VARCHAR(255)): Stored value (e.g. `0.85`).

#### 9. `users` (Institutional Authentication)
- `user_id` (VARCHAR(64), PK): Unique user ID.
- `username` (VARCHAR(50), UNIQUE): Login username.
- `password_hash` (VARCHAR(255)): Bcrypt/PBKDF2 salted hash.
- `role` (VARCHAR(50)): User role (`Audit Officer`, `Compliance Head`, `Reviewer`, `admin`).
- `is_active` (BOOLEAN): Account status.

#### 10. `report_audit_log` (Email Report Delivery History via Elastic Connector)
- `log_id` (INT, PK AUTO_INCREMENT): Log identifier.
- `report_id` (VARCHAR(64)): Unique report UUID.
- `rm_id` (VARCHAR(20)): Relationship manager profiled.
- `requested_by` (VARCHAR(64)): User requesting report dispatch.
- `recipients` (TEXT): Serialized recipient email list.
- `status` (VARCHAR(20)): Delivery state (`QUEUED`, `SENT`, `FAILED`) dispatched through the Elastic Email Connector.
- `error_code` (VARCHAR(50)): Error classification if failed.
- `request_id` (VARCHAR(64)): Idempotency key ensuring single dispatch.

---

## 4. Elasticsearch Index Mappings

### 4.1 `regulations` Index
Grounds detection by storing structural chunks from the 5 regulatory master documents.

| Field Name | Type | Purpose & Search Mechanics |
|---|---|---|
| `chunk_id` | `keyword` | Unique deterministic chunk ID (e.g. `COC_2022_II_4_g`). |
| `document_id` | `keyword` | Parent document identifier. |
| `document_name` | `text` (with `.raw` keyword) | Human-readable title of issuing circular or regulation. |
| `regulator` | `keyword` | Authority (`SEBI` or `AMFI`). |
| `status` | `keyword` | Legal status (`current` or `legacy`). |
| `chapter` / `section` / `clause` | `keyword` | Hierarchical legal taxonomy tags. |
| `citation_label` | `keyword` | Standardized citation string (e.g. "AMFI Distributor Code §II.4.g, p.4"). |
| `chunk_text` | `text` | Verbatim clause text optimized for standard BM25 keyword retrieval. |
| `chunk_text_semantic` | `semantic_text` | Hierarchically enriched text indexed via `.jina-embeddings-v5-text-small` for dense kNN vector retrieval. |
| `page_number` | `integer` | Physical page number in the original PDF source. |

### 4.2 `calls` Index
Stores complete call records, transcripts, and metadata.

| Field Name | Type | Purpose & Search Mechanics |
|---|---|---|
| `call_id` | `keyword` | Unique call identifier. |
| `rm_id` / `customer_id` | `keyword` | Relational identifiers for filtering. |
| `date_time` | `date` | Timestamp of call recording. |
| `duration_seconds` | `integer` | Call duration in seconds. |
| `transcript_english_text` | `text` | Full translated English transcript text. |
| `transcript_semantic` | `semantic_text` | Dense semantic representation of full call text. |
| **`transcript_segments`** | **`nested`** | **Nested array of individual turns. Guarantees speaker-to-utterance isolation during queries.** |
| `transcript_segments.speaker` | `keyword` | Speaker tag (`RM` or `CUSTOMER`). |
| `transcript_segments.text_english` | `text` | Translated dialogue turn. |
| `transcript_segments.start_time` / `end_time`| `float` | Exact timing boundary in seconds. |
| `has_violation` | `boolean` | Flag indicating whether any confirmed finding exists on this call. |
| `finding_ids` | `keyword` | Array of foreign keys referencing confirmed `compliance_findings`. |

### 4.3 `compliance_findings` Index
Read-optimized store for analytical aggregations and dashboard queries.

| Field Name | Type | Purpose & Search Mechanics |
|---|---|---|
| `finding_id` | `keyword` | Unique finding ID (e.g. `FND-2026-A1B2C3`). |
| `call_id` / `rm_id` / `customer_id` | `keyword` | Relational references. |
| `category` | `keyword` | Violation category. |
| `severity` | `keyword` | `HIGH`, `MEDIUM`, or `LOW`. |
| `confidence` | `float` | Detection confidence score (0.00 to 1.00). |
| `status` | `keyword` | Denormalized copy of MySQL `compliance_case.status`. |
| `timestamp_start` / `timestamp_end` | `float` | Precise audio timestamp markers. |
| `transcript_evidence` | `text` | Verbatim violating dialogue turn. |
| `regulation_chunk_id` | `keyword` | Foreign reference to `regulations.chunk_id`. |
| `regulation_citation_label` | `keyword` | Formatted citation string. |
| `reasoning` | `text` | Forensic analysis text generated by Bedrock/Gemini. |
| `recommended_action` | `text` | Remediation guidance. |
| `provider_used` | `keyword` | Model provider executing evaluation (`bedrock` or `gemini`). |

---

## 5. Pipeline Stages & Guardrails

```
[Candidate Generated]
         │
         ▼
[Pre-Check: Citations > 0] ──No──> [DISMISSED_NO_CITATION]
         │ Yes
         ▼
[LLM Forensic Reasoning] ──Model says clean──> [DISMISSED_NOT_GENUINE]
         │ Violation confirmed
         ▼
[Pydantic Schema Validation] ──Parse error──> [DISMISSED_VALIDATION_FAILED]
         │ Valid
         ▼
[Guardrail 1: Citation Match] ──Selected reg not in candidates──> [DISMISSED_CITATION_MISMATCH]
         │ Pass
         ▼
[Guardrail 2: High Severity Completeness] ──Missing ts or reg──> [DISMISSED_INCOMPLETE_HIGH_FINDING]
         │ Pass
         ▼
[CONFIRMED Finding] ──> [Atomic Dual-Write to MySQL & Elasticsearch]
```

### Forensic Dismissal Codes & Invariant Logic
1. **`DISMISSED_NO_CITATION`:** Fired in pre-screening. The candidate generation phase could not identify any matching SEBI/AMFI regulatory clause. Without statutory grounding, no investigation proceeds.
2. **`DISMISSED_NOT_GENUINE`:** Fired by the LLM forensic evaluator when contextual examination reveals that dialogue is compliant, hedged, or taken out of context.
3. **`DISMISSED_VALIDATION_FAILED`:** Fired when the model output cannot be parsed into a valid `ComplianceFinding` Pydantic model.
4. **`DISMISSED_CITATION_MISMATCH`:** **Critical anti-hallucination guardrail.** The LLM cited a `regulation_id` that was not among the candidate's pre-retrieved statutory chunks.
5. **`DISMISSED_INCOMPLETE_HIGH_FINDING`:** Any finding flagged as `HIGH` severity that lacks non-zero timestamp boundaries or a statutory citation is dismissed.

---

## 6. Transactional Dual-Write & Consistency Handling

```
                              User Action (e.g. Mark Reviewed)
                                              │
                                              ▼
                             Open MySQL Transaction (BEGIN)
                                              │
                                              ▼
                       SELECT * FROM compliance_case FOR UPDATE
                                              │
                        ┌─────────────────────┴─────────────────────┐
                        ▼                                           ▼
             Case already RESOLVED?                       Case in valid state?
                        │                                           │
                       Yes                                         Yes
                        │                                           │
              Rollback & raise 409 Conflict                         ▼
                                                        UPDATE compliance_case
                                                        INSERT case_activity_log
                                                                    │
                                                                    ▼
                                                            COMMIT Transaction
                                                                    │
                                                                    ▼
                                                 Update Elasticsearch compliance_findings
                                                                    │
                                              ┌─────────────────────┴─────────────────────┐
                                              ▼                                           ▼
                                          Success                                     ES Error
                                              │                                           │
                                              ▼                                           ▼
                                    Return 200 OK (sync=full)                 Log structured DRIFT_RISK
                                                                              Return 200 OK (sync=partial)
```

### Concurrency & Conflict Prevention
- **Pessimistic Locking:** `_get_case_for_update` issues `SELECT ... FOR UPDATE` on `compliance_case`. Concurrent requests block until the active transaction finishes.
- **State Conflict Exception (409):** Attempting to resolve an already-resolved case raises `CaseAlreadyResolvedError`, which maps to HTTP `409 Conflict`.
- **Drift Handling:** If Elasticsearch is unreachable during the post-commit sync, the transaction does not roll back (as MySQL is authoritative). Instead, a `DRIFT_RISK` warning is logged containing `case_id`, `finding_id`, and `desired_status`, enabling automated background reconciliation.

---
*Vigil Backend Architecture Reference — Python 3.11 / FastAPI / Elastic APM Specification*
