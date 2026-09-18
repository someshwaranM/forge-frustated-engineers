# Vigil System Architecture & Technical Design

## 1. High-Level Architecture & End-to-End Data Flow

Vigil is architected as an event-driven, forensic compliance surveillance system for financial services. The pipeline processes spoken audio, grounds conversational dialogue in regulatory law, enforces strict schema validation, and exposes audit trails to human reviewers.

```
+---------------------------------------------------------------------------------------------------------+
|                                        CALL INGESTION & SPEECH                                          |
+---------------------------------------------------------------------------------------------------------+
  CallAudio/*.wav ──> Watchdog (file_watcher.py) ──> Stability Check (stability_check.py)
                                                              │
                                                              ▼
                                                   Audio Validator (audio_validator.py)
                                                              │
                                                              ▼
                                                   Sarvam AI API (Saaras v3)
                                                   - Speech-to-Text (multilingual Indian vernacular)
                                                   - Speaker Diarization (speaker_0, speaker_1)
                                                   - English Translation
                                                              │
                                                              ▼
                                                   Speaker Role Mapping (speaker_mapper.py)
                                                   - Bedrock LLM primary (greeting analysis)
                                                   - Gemini LLM fallback
                                                   - Heuristic fallback (earliest speaker)
                                                              │
                                                              ▼
+-------------------------------------------------------------┼-------------------------------------------+
|                                    ELASTICSEARCH INTELLIGENCE LAYER                                     |
+-------------------------------------------------------------┼-------------------------------------------+
                                                              │
                                                              ▼
                                                   Index into ES 'calls'
                                                   - Nested transcript segments
                                                   - Original & English full text
                                                   - Jina v5 semantic text embedding
                                                              │
                       ┌──────────────────────────────────────┴──────────────────────────────────────┐
                       ▼                                                                             ▼
            Deterministic Rules Engine                                                    Suitability Checker
            - Rule 1: Guaranteed Returns                                                  - Pull Customer Profile (MySQL)
            - Rule 2: Exaggerated Claims                                                  - Pull Product Risk Class (MySQL)
            - Keyword Disclosures Checker                                                 - Mismatch Matrix Evaluation
                       │                                                                             │
                       └──────────────────────────────────────┬──────────────────────────────────────┘
                                                              ▼
                                                   Candidate Builder (candidate_builder.py)
                                                   - Assembles preliminary violation triggers
                                                              │
                                                              ▼
                                                   Regulatory Hybrid Retrieval (regulation_retriever.py)
                                                   - BM25 keyword matching on chunk_text
                                                   - Dense semantic vector search on chunk_text_semantic
                                                   - Reciprocal Rank Fusion against ES 'regulations'
                                                              │
                                                              ▼
+-------------------------------------------------------------┼-------------------------------------------+
|                                      FORENSIC AI REASONING ENGINE                                       |
+-------------------------------------------------------------┼-------------------------------------------+
                                                              │
                                                              ▼
                                                   Investigator Agent (investigator_agent.py)
                                                   - Primary: AWS Bedrock (Claude Sonnet 4)
                                                   - Fallback: Google Gemini (Gemini 3.6 Flash)
                                                   - Citation Grounding Enforcement (must match candidate)
                                                   - High Severity Completeness Validation
                                                   - Dismissal State Machine
                                                              │
                                                              ▼
                                                   ComplianceFinding (Pydantic Schema)
                                                              │
+-------------------------------------------------------------┼-------------------------------------------+
|                                      TRANSACTIONAL WORKFLOW & AUDIT                                     |
+-------------------------------------------------------------┼-------------------------------------------+
                                                              │
                                                              ▼
                                                   Atomic Dual-Write State Machine (case_service.py)
                                                   1. MySQL Transaction:
                                                      - INSERT compliance_case
                                                      - INSERT case_activity_log
                                                   2. Elasticsearch Update:
                                                      - INDEX compliance_findings
                                                      - UPDATE calls (has_violation=True, finding_ids)
                                                   3. Drift Detection (logs DRIFT_RISK on ES failure)
                                                              │
                       ┌──────────────────────────────────────┴──────────────────────────────────────┐
                       ▼                                                                             ▼
            FastAPI Application Services                                                  Elastic Observability
            - REST Endpoints (/api/*)                                                     - elastic-apm Python agent
            - Interactive Agent Builder Chat                                              - Custom Native Spans
            - RM Performance & Email Reports                                              - Structured ECS JSON Logging
                       │                                                                             │
                       └──────────────────────────────────────┬──────────────────────────────────────┘
                                                              ▼
+---------------------------------------------------------------------------------------------------------+
|                                       PRESENTATION & CASE WORKFLOW                                      |
+---------------------------------------------------------------------------------------------------------+
                                                              │
                                                              ▼
                                                   React 18 + TypeScript SPA
                                                   - Executive Compliance Dashboard
                                                   - WaveSurfer.js Audio Player & Timestamp Seek
                                                   - Interactive Evidence Chain Visualization
                                                   - Natural Language Investigation Chat
                                                   - RM Analytics & Kibana APM Dashboard
```

---

## 2. Component Responsibilities

### 2.1 Audio Ingestion & Preprocessing (`backend/ingestion/`)
- **`watch_folder.py` / `file_watcher.py`:** Utilizes Python `watchdog` to monitor the `CallAudio/` directory for incoming audio files.
- **`stability_check.py`:** Verifies that incoming files are completely written by sampling file sizes over consecutive intervals before releasing them to processing.
- **`audio_validator.py`:** Inspects audio metadata (format, duration, channels, sample rate) using `wave` and `mutagen` to reject corrupt recordings.
- **`filename_parser.py`:** Extracts institutional metadata from standardized filenames (e.g., `CALL_RM001_CUST001_20260310_1030.wav` -> RM ID: `RM001`, Customer ID: `CUST001`, Timestamp: `2026-03-10 10:30`).
- **`speaker_mapper.py`:** Maps anonymized diarization tags (`speaker_0`, `speaker_1`) to institutional roles (`RM`, `CUSTOMER`). Employs a multi-tiered hierarchy:
  1. Primary: AWS Bedrock LLM contextual prompt analyzing greeting dialogue.
  2. Fallback 1: Google Gemini LLM.
  3. Fallback 2: Earliest-speaker timing heuristic (sales protocol dictates RM initiates the call).

### 2.2 Speech-to-Text & Translation (`backend/sarvam/`)
- Integrates with Sarvam AI's `saaras:v3` production API.
- Converts conversational audio into time-stamped speaker turns.
- Generates both verbatim vernacular transcripts and standardized English translations necessary for regulatory compliance analysis.

### 2.3 Regulatory Corpus Indexing (`backend/indexing/`)
- Extracts raw text from 5 primary statutory PDFs across SEBI and AMFI using PyMuPDF (`fitz`).
- Applies regular expressions to detect and strip recurring headers and footers across non-adjacent pages.
- Deconstructs regulatory documents into discrete structural chunks (chapters, sections, clauses).
- Enforces a 7-point pre-indexing validation gate before document indexing.
- Pushes chunks to the `regulations` Elasticsearch index, generating dense vector embeddings via the `.jina-embeddings-v5-text-small` inference pipeline.

### 2.4 Hybrid Detection Engine (`backend/compliance/`)
- **`deterministic_rules.py`:** Evaluates RM utterances against regex-based rule sets:
  - *Rule 1 (Guaranteed Returns):* Unambiguous assurances of capital safety or fixed returns (violating AMFI Distributor Code §II.4.g).
  - *Rule 2 (Exaggerated Claims):* Unsubstantiated performance projections (violating AMFI Code of Ethics §6).
- **`product_identifier.py`:** Scans transcript turns to detect fund names or scheme IDs referenced in conversation, cross-referencing MySQL product catalogs.
- **`suitability_checker.py`:** Evaluates investor vulnerability by cross-referencing MySQL `customer.risk_profile` and `customer.investment_experience` against `product.risk_class` and `product.suitable_risk_profiles`. Flags high-risk asset allocation recommended to conservative/low-experience investors.
- **`disclosure_checker.py`:** Verifies the presence of mandatory statutory disclosures (e.g., "Mutual fund investments are subject to market risks...").
- **`regulation_retriever.py`:** Queries the `regulations` index using Elasticsearch hybrid retrieval, fusing BM25 keyword matching with dense semantic kNN vector search via Reciprocal Rank Fusion (RRF).
- **`candidate_builder.py`:** Consolidates triggers into unified `ViolationCandidate` packages containing transcript turns, customer/product context, and candidate statutory citations.

### 2.5 Forensic Investigator Agent (`backend/agents/investigator_agent.py`)
- Evaluates preliminary candidates using full contextual prompts.
- Employs **AWS Bedrock (Claude Sonnet 4)** as primary reasoning engine, failing over to **Google Gemini (Gemini 3.6 Flash)** on API throttling or network failure.
- Strictly validates model output against Pydantic schema `ComplianceFinding`.
- Enforces automated forensic guardrails:
  - *Citation-Match Enforcement:* If the LLM cites a clause not present in the candidate's retrieved citation set, the finding is dismissed as a hallucination.
  - *High-Severity Completeness:* Rejects any `HIGH` severity classification lacking exact timestamps or statutory citations.

### 2.6 Workflow Engine & Dual-Write Layer (`backend/workflows/case_service.py`)
- Manages institutional case progression (`OPEN` -> `RESOLVED`), reviewer assignments, escalation to compliance committees, and case notes.
- Enforces pessimistic concurrency control (`SELECT ... FOR UPDATE`) in MySQL.
- Coordinates dual-write persistence: commits transactional state to MySQL before issuing updates to Elasticsearch `compliance_findings`.
- Emits structured `DRIFT_RISK` logs when Elasticsearch synchronization fails, preventing data inconsistencies from passing undetected.

### 2.7 Application & Reporting Services (`backend/api/`, `backend/reports/`)
- Exposes RESTful endpoints for dashboard aggregation, case triage, transcript playback, and system diagnostics.
- Houses the interactive AI Chat Agent (`backend/agents/chat_agent.py`) using Elastic Agent Builder tool conventions.
- Generates institutional compliance summary reports for Relationship Managers, with secure automated delivery via **Elastic Connectors** (Kibana Email Connectors in `backend/reports/email_service.py`).

---

## 3. Elasticsearch Indices Architecture

Vigil provisions three purpose-built Elasticsearch indices, each optimized for specific query patterns:

| Index Name | Primary Purpose | Key Fields | Search Strategy |
|---|---|---|---|
| **`regulations`** | Grounding knowledge base of statutory circulars and ethical codes. | `chunk_id`, `document_id`, `regulator`, `clause`, `citation_label`, `chunk_text`, `chunk_text_semantic` | Hybrid: BM25 on `chunk_text` + dense semantic vector search on `chunk_text_semantic` via `.jina-embeddings-v5-text-small`. |
| **`calls`** | Comprehensive repository of ingested audio calls, transcripts, and metadata. | `call_id`, `rm_id`, `customer_id`, `date_time`, `transcript_english_text`, `transcript_semantic`, `transcript_segments` (nested) | Filtered full-text, nested queries for speaker-isolated evidence, and semantic text matching. |
| **`compliance_findings`** | Fast analytical and read-optimized store for confirmed violations. | `finding_id`, `call_id`, `rm_id`, `category`, `severity`, `confidence`, `status`, `timestamp_start/end`, `regulation_citation_label` | ES|QL aggregations, real-time dashboard facet counts, and RM historical violation profiling. |

### Why `transcript_segments` is a Nested Field
In Elasticsearch, standard object arrays are flattened, destroying the correlation between inner object fields. If `transcript_segments` were a flat object array:
- Query: `speaker == 'RM'` AND `text == 'guaranteed return'`
- In a flattened structure, if the Customer mentioned "guaranteed return" and the RM said "hello", the document would erroneously match, creating a false positive.
By declaring `transcript_segments` as `type: nested`, Elasticsearch indexes each turn as an independent hidden document, ensuring that speaker identity and utterance text evaluate within the exact same conversational boundary.

---

## 4. MySQL Relational Schema & Storage Architecture

Vigil uses MySQL 8.0 for master data and transactional state management. Relational storage is deliberately segregated from Elasticsearch:

```
                  +-------------------+       +-------------------+
                  |      rm           |       |    customer       |
                  +-------------------+       +-------------------+
                  | rm_id (PK)        |       | customer_id (PK)  |
                  | full_name         |       | full_name         |
                  | branch            |       | risk_profile      |
                  | joined_date       |       | invest_experience |
                  +--------+----------+       +---------+---------+
                           |                            |
                           |    +------------------+    |
                           +--->|  transaction     |<---+
                                +------------------+
                                | transaction_id(PK|
                                | customer_id (FK) |
                                | rm_id (FK)       |
                                | product_id (FK)  |
                                | amount, type     |
                                +--------+---------+
                                         |
                                         v
                                +------------------+
                                |    product       |
                                +------------------+
                                | product_id (PK)  |
                                | product_name     |
                                | risk_class       |
                                | suitable_profiles|
                                +------------------+

                  +-------------------+       +-------------------+
                  |   compliance_case |       |    reviewer       |
                  +-------------------+       +-------------------+
                  | case_id (PK)      |       | reviewer_id (PK)  |
                  | finding_id        |       | full_name         |
                  | call_id           |       | role              |
                  | rm_id (FK)        |       +---------+---------+
                  | customer_id (FK)  |                 |
                  | status            |                 |
                  | escalated         |                 |
                  | assigned_to (FK)  |<----------------+
                  | resolution_type   |
                  +--------+----------+
                           |
                           v
                  +-------------------+
                  | case_activity_log |
                  +-------------------+
                  | log_id (PK, Auto) |
                  | case_id (FK)      |
                  | action            |
                  | actor (FK)        |
                  | details           |
                  | timestamp         |
                  +-------------------+
```

### Institutional Schema Inventory
1. **`rm`**: Master roster of Relationship Managers, branch affiliations, and employment status.
2. **`customer`**: Investor master records containing `risk_profile` (Conservative, Moderate, Aggressive) and `investment_experience` (Low, Medium, High).
3. **`product`**: Mutual fund product catalog defining `risk_class` (Low, Medium, High) and `suitable_risk_profiles`.
4. **`transaction`**: Historical investment records linking Customer, RM, and Scheme.
5. **`reviewer`**: Authorized compliance officers permitted to triage, assign, and resolve compliance cases.
6. **`compliance_case`**: The authoritative state machine record for compliance findings. Case status is strictly binary (`OPEN` or `RESOLVED`). Escalations are tracked via a dedicated boolean flag (`escalated`), preserving state-machine invariants.
7. **`case_activity_log`**: Immutable audit log capturing all state changes, reassignments, and notes with timestamps and actor IDs.
8. **`app_settings`**: Key-value configuration store persisting runtime thresholds (e.g., confidence cutoffs) across system restarts.
9. **`users`**: Institutional identity and access control store supporting role-based authentication.
10. **`report_audit_log`**: Audit log tracking compliance report generation and email dispatch.

---

## 5. Architectural Decisions & Rationale (ADRs)

### ADR-1: MySQL as Single Source of Truth for Case Status vs. Elasticsearch Denormalization
- **Context:** Compliance officers update case status (`OPEN` -> `RESOLVED`), escalate matters to supervisory committees, and assign cases to peers.
- **Decision:** MySQL is the sole authoritative system of record for all case lifecycle mutations. Elasticsearch stores a denormalized copy of `status` strictly for low-latency search and ES|QL aggregation.
- **Rationale:** Financial compliance demands strict ACID properties, pessimistic locking (`SELECT ... FOR UPDATE`), and foreign key referential integrity. Elasticsearch is an eventually-consistent document store that lacks multi-document transaction primitives. Permitting direct status mutations in Elasticsearch risks split-brain scenarios and phantom updates during concurrent reviewer audits.

### ADR-2: Distinct `chunk_text` and `chunk_text_semantic` Representations
- **Context:** Chunks indexed into the `regulations` index must serve both verbatim keyword citation and dense semantic retrieval.
- **Decision:** Each chunk produces two distinct textual representations:
  - `chunk_text`: Contains the verbatim heading and clause text. Used exclusively for BM25 exact phrase queries and evidence presentation.
  - `chunk_text_semantic`: Prepends the document name, hierarchical breadcrumbs (`Chapter`, `Section`, `Regulation`, `Clause`), and broader context to the clause text. Used exclusively for dense semantic embeddings.
- **Rationale:** Isolated regulatory clauses frequently lack local semantic cues (e.g., a clause stating "No intermediary shall promise 15% per annum" lacks the context that it belongs to the AMFI Distributor Code regarding Assured Returns). Embedding structural hierarchy alongside the clause ensures the embedding model accurately captures the regulatory intent and domain context.

### ADR-3: Speaker-Role Disambiguation Hierarchy
- **Context:** Audio diarization models tag speakers generically (`speaker_0`, `speaker_1`). Downstream compliance rules must know definitively which party is the RM.
- **Decision:** Employ a three-stage hierarchy:
  1. AWS Bedrock LLM contextual greeting prompt.
  2. Google Gemini fallback.
  3. Deterministic earliest-speaker timing heuristic.
- **Rationale:** Financial sales calls follow strict conversational norms: Relationship Managers introduce themselves and state their institutional affiliation within the first 30 seconds. An LLM reliably identifies role introductions across varied colloquial patterns. If cloud LLM services fail, falling back to the earliest speaker ensures the ingestion pipeline does not stall.

### ADR-4: Bedrock Primary with Gemini Zero-Downtime Fallback
- **Context:** Core forensic evaluations depend on cloud LLM APIs, which are susceptible to regional throttling, service outages, or quota exhaustion.
- **Decision:** Wrap LLM execution in an automated failover service (`execute_forensic_evaluation`). Bedrock Claude Sonnet 4 is invoked first; on any `BotoCoreError`, `ClientError`, or JSON parsing failure, the engine automatically routes the prompt to Google Gemini (Gemini 3.6 Flash).
- **Rationale:** Compliance ingestion pipelines cannot stall due to single-vendor cloud outages. By enforcing an identical Pydantic schema (`ComplianceFinding`) across both providers, downstream consumers remain completely agnostic to provider failover.

### ADR-5: Elastic Agent Builder Read-Only Tool Partitioning
- **Context:** The AI Investigation chat interface exposes backend tools to an LLM agent.
- **Decision:** Partition tools into:
  - Read-Only Index Search (`search_calls`, `search_regulations`)
  - Read-Only Analytics (`get_rm_history`)
  - Read-Only Database Lookups (`get_customer_profile`, `get_product_details`, `get_transactions`)
  Mutating workflow actions (such as `mark_reviewed` or `escalate`) are strictly excluded from the conversational agent.
- **Rationale:** Conversational LLM agents are susceptible to prompt injection. Prohibiting mutating actions within the chat interface guarantees that users cannot trigger unauthorized case status changes or dismiss violations via adversarial prompts.

---

## 6. Known Limitations & Stated Risks

### 6.1 Dual-Write Drift Risk
- **Risk:** If a case status is updated in MySQL, but the secondary Elasticsearch update fails (e.g., network partition), the dashboard may temporarily display stale status.
- **Mitigation:** The workflow engine encapsulates dual-writes with structured exception handling. If Elasticsearch fails, the transaction commits in MySQL, logs a structured `DRIFT_RISK` event with the affected `case_id` and `finding_id`, and returns `sync_status: "partial"`. A background reconciliation worker can re-sync drifted indices.

### 6.2 Keyword-Only Mandatory Disclosure Verification
- **Risk:** `disclosure_checker.py` evaluates statutory risk disclosures using exact regex keywords.
- **Mitigation:** RMs who paraphrase disclosures or translate standard risk warnings into colloquial idioms might be flagged for missing disclosures. This deliberate design decision errs on the side of regulatory caution, routing ambiguous disclosures to human review.

### 6.3 Text-Based PDF Pipeline (No OCR Engine)
- **Risk:** `backend/indexing/extract.py` relies on PyMuPDF text extraction.
- **Mitigation:** The current pipeline assumes all statutory circulars are clean, digitally generated PDFs. Scanned image PDFs will fail text extraction. Physical scans require an upstream OCR engine (e.g., Tesseract or AWS Textract) before ingestion.

### 6.4 Single-Node Audio Watcher Scalability
- **Risk:** `watch_folder.py` executes on a single host monitoring local filesystem directories.
- **Mitigation:** Suitable for branch-level deployments and proof-of-concept surveillance. Production horizontal scaling requires replacing local folder watchers with object storage event notifications (e.g., AWS S3 Event Notifications -> AWS SQS -> Celery/Temporal workers).

---
*Vigil Architecture Reference — Phase 13 Observability & Surveillance Specification*
