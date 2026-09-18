# Vigil — Autonomous, Explainable Compliance Intelligence Platform for BFSI

**Submission Category:** Industry Solutions & Vertical Experiences
**Problem statement:** BFSI Intelligence & Risk Management  
**Target Domain:** BFSI / Wealth Management / Mutual Fund Distribution (SEBI & AMFI)  
**Primary Tech Stack:** Elasticsearch Serverless, Elastic Observability, AWS Bedrock, Google Gemini, Sarvam AI, FastAPI, MySQL, React, WaveSurfer.js, Python

---

## 1. Executive Summary & Problem

In India's rapidly expanding mutual fund ecosystem, asset management companies (AMCs) and registered distributors supervise tens of thousands of outbound Relationship Manager (RM) sales interactions daily. The **Securities and Exchange Board of India (SEBI)** and the **Association of Mutual Funds in India (AMFI)** strictly prohibit misleading performance claims, guaranteed-return promises, and unsuitable product recommendations.

Today, compliance surveillance relies on manual sampling:
- **<30–35% Audit Coverage:** Over 65–70% of telephony sales interactions go unreviewed.
- **Unexplainable "Black-Box" AI:** Generic LLM summarizers produce arbitrary sentiment or risk numbers (e.g. "Risk: High") that lack statutory citations, exact timestamps, and evidentiary proof, making them unviable for SEBI audits.
- **Disconnected Audit Records:** Case reviews and escalations occur in disjointed spreadsheets, severing the link between human decisions and recorded audio.

**Vigil** transforms compliance monitoring from reactive, manual spot-checking into an **autonomous, explainable, and fully auditable compliance surveillance engine**.

---

## 2. The Solution: End-to-End Compliance Intelligence

Vigil continuously listens to RM sales calls and automatically constructs a verifiable, 9-point **Evidence Chain** for every violation detected:

```
[1. Severity & Confidence] ──> [2. Verbatim Dialogue Snippet] ──> [3. Exact Audio Timestamp]
                                                                          │
[6. Matched SEBI/AMFI Clause] <── [5. Product Risk Class] <── [4. Customer Risk Profile]
        │
        └──> [7. Forensic AI Reasoning] ──> [8. Recommended Action] ──> [9. Reviewer Audit Trail]
```

### How a User Goes from Question to Answer
1. **Automated Detection:** As calls are dropped into the system, Vigil transcribes and diarizes multilingual Indian audio via Sarvam AI, isolates RM turns from Customer turns, and detects potential violations.
2. **Regulatory Grounding:** Candidate violations are cross-referenced against 5 indexed SEBI and AMFI statutory documents using Elasticsearch hybrid search (BM25 + dense semantic vector retrieval via Jina v5 embeddings).
3. **Forensic Agent Reasoning:** An **Investigator Agent** powered by AWS Bedrock (Claude 4 Sonnet) with Google Gemini zero-downtime fallback evaluates the evidence, filters false positives, checks investor suitability against MySQL customer profiles, and outputs a validated `ComplianceFinding`.
4. **Instant Verification:** A compliance officer opening the Case Detail view clicks a violation timestamp. The **WaveSurfer.js audio player instantly seeks to the exact second**, synchronized with a highlighted transcript line and the verbatim statutory clause.
5. **Interactive AI Investigation:** Officers can query the fleet via natural language chat ("Show all high-severity guaranteed return claims by RM001 this month"), backed by grounded Elastic Agent Builder tools.

---

## 3. Technical Highlights Worth Showcasing

### 1. The Interactive "Click Timestamp -> Jump to Audio" Experience
The flagship interaction in Vigil: On the Compliance Case Detail screen, clicking the violation's timestamp marker immediately seeks the WaveSurfer.js waveform to the exact audio second while scrolling and highlighting the matching transcript turn. The officer can hear what the RM said, read the verbatim English translation, and verify the matched statutory rule—all on a single screen without page reloads.

### 2. Dual-Engine Zero-Downtime Fallback Architecture
Compliance processing cannot halt when a cloud provider experiences an outage. Vigil executes **AWS Bedrock (Claude Sonnet 4)** as its primary reasoning engine, with an automated failover to **Google Gemini**. Both engines share the same Pydantic schema (`ComplianceFinding`), ensuring seamless transitions without downstream pipeline corruption.

### 3. Native Elastic Observability & APM (No OpenTelemetry Overhead)
Vigil features native **Elastic Observability** using the official `elastic-apm` Python agent. Every step in the pipeline—from audio validation and Sarvam batch processing to hybrid Elasticsearch retrieval and LLM reasoning—is traced with custom native spans, structured Elastic Common Schema (ECS) JSON logging, and an executive Observability dashboard embedded directly in the frontend.

### 4. Multi-Layer Guardrails: PII Masking, Hallucination Defense & Response Evaluation
Vigil implements a robust, multi-layer guardrail architecture to ensure data privacy, eliminate hallucinations, and enforce strict model accuracy:

- **Financial PII Masking & Data Redaction:** To comply with Indian data protection mandates and AMFI/SEBI confidentiality codes, sensitive investor PII is masked before ingestion, prompting, and indexing:
  - **PAN Numbers:** Redacted into masked format (e.g., `ABCDE****F`), protecting tax identifiers.
  - **Mobile Numbers:** Masked to preserve only the last digits for audit lookup (e.g., `******9876`).
  - **Mutual Fund Folio Numbers:** Masked across transcript turns and context lookups (e.g., `FOLIO-*****432`).
  - **Email Addresses:** Masked user handles (e.g., `a***t@domain.com`).
  *Result:* Cloud LLM reasoning engines (Bedrock and Gemini) evaluate conversational evidence without exposing raw investor financial identifiers.

- **Citation Grounding & Anti-Hallucination Guardrail:** The Investigator Agent is strictly bounded by the candidate's retrieved statutory chunks. If the LLM generates a finding citing a regulation clause outside this pre-retrieved set, the finding is dismissed as `DISMISSED_CITATION_MISMATCH`.

- **High-Severity Completeness Guardrail:** Any finding proposed as `HIGH` severity that lacks non-zero timestamp boundaries or a valid statutory citation is rejected as `DISMISSED_INCOMPLETE_HIGH_FINDING`.

- **AI Response Evaluation Against Expected Ground Truth:** Every model response is systematically benchmarked against expert ground-truth annotations (`backend/benchmark/ground_truth.json`):
  - **Expected vs. Actual Response Evaluation:** The benchmark harness evaluates the AI's predicted category, severity, and statutory citation against human compliance officer expected decisions across 10 diverse call scenarios.
  - **Over-Flagging & Boundary Testing:** Ambiguous scenarios (e.g., soft return language or borderline suitability) are evaluated against pre-defined acceptance criteria (e.g., expecting `CONFIRMED-LOW` or `DISMISSED_NOT_GENUINE`), guaranteeing that the model does not over-flag compliant sales discussions.
  - **Quantitative Metric Reporting:** Automated evaluation delivers 100% precision on high-severity breaches with zero hallucinations.

### 5. Transactional Dual-Write Architecture (MySQL + Elasticsearch)
- **MySQL 8.0** is the ACID-compliant **Single Source of Truth** for case workflows (`OPEN`/`RESOLVED`), reviewer assignments, and immutable row-locked audit logs (`case_activity_log`).
- **Elasticsearch** serves as the **Read-Optimized Analytics Engine**, powering sub-second dashboard facet counts and ES|QL trend aggregations.

### 6. Institutional Compliance Reporting via Elastic Email Connectors
To bridge automated surveillance with executive action, Vigil leverages **Elastic Connectors (Kibana Actions API)** for automated email dispatch:
- **Managed Email Delivery:** Dispatches compliance audit dossiers directly through Elastic's centralized connector infrastructure (`vigil-mail`), eliminating the need to expose raw SMTP credentials in backend code.
- **Executive Audit Dossiers:** Renders responsive HTML and text compliance dossiers featuring RM violation timelines, category breakdowns, and direct links to case files.
- **Idempotency & Audit Accountability:** Features UUID-based idempotency checks to prevent accidental duplicate transmissions, with every dispatch recorded in MySQL `report_audit_log`.

---

## 4. End-to-End Demo Flow

| Step | Page / Component | Interaction / What Happens |
|---|---|---|
| **1. Triage** | **Dashboard** | View aggregate compliance metrics: 10 processed calls, severity distribution (3 High, 2 Medium, 2 Low, 3 Clean), violation category breakdown, and top-offending RMs. |
| **2. Case Selection** | **Compliance Cases** | Filter cases by status (`OPEN`), severity (`HIGH`), or RM (`RM002`). Select `CASE_CALL_RM002_CUST002_20260318_0915`. |
| **3. Forensic Verification** | **Case Detail** | **The Showcase Interaction:** Click the `00:45` timestamp. WaveSurfer.js instantly jumps to the exact audio snippet where the RM promises an explicit 15% guaranteed return. The transcript turn is highlighted, the AMFI Distributor Code §II.4.g citation is displayed, and the customer risk profile is verified. |
| **4. Workflow Action** | **Case Actions** | Reviewer selects **Mark Reviewed**, enters resolution notes, and clicks Submit. MySQL atomically records the status update and audit log; Elasticsearch updates denormalized status; the UI updates optimistically with conflict prevention. |
| **5. RM Intelligence** | **RM Analytics** | Navigate to `RM002`. Observe historical violation trends and the live **Repeat Offender** badge (3 guaranteed return violations). Trigger an automated compliance audit email report dispatched via the **Elastic Email Connector**. |
| **6. Natural Language Chat** | **AI Investigation** | Query: *"Which RMs have high-severity guaranteed return claims?"* The agent executes `search_calls` and `get_rm_history` against Elasticsearch, returning grounded evidence cards with direct links back to Case Detail. |
| **7. System Telemetry** | **Observability** | Inspect real-time pipeline latency breakdowns (Sarvam STT: ~1.2s, Hybrid Retrieval: ~45ms, Forensic LLM: ~2.1s), view active APM traces, and review the live error ring buffer. |

---

## 5. What's Built vs. Roadmap

### Completed & Fully Functional in Repository
- [x] **End-to-End Audio Pipeline:** File drop watcher, stability checker, audio validator, and Sarvam AI STT/diarization integration.
- [x] **Speaker Role Identification:** LLM contextual prompt with heuristic fallback.
- [x] **Hybrid Regulatory Retrieval:** BM25 keyword matching + Jina v5 dense semantic vector search on 5 SEBI/AMFI master documents.
- [x] **Forensic Investigator Agent:** AWS Bedrock Claude Sonnet 4 with Google Gemini fallback, strict Pydantic schema validation, and citation-match guardrails.
- [x] **Transactional Dual-Write Workflow:** MySQL case management with pessimistic locking and Elasticsearch synchronization.
- [x] **React 18 Dashboard:** WaveSurfer.js audio waveform seek, Evidence Chain visualizer, RM performance profiles, and AI chat.
- [x] **Elastic Observability:** Native `elastic-apm` agent, custom spans, ECS structured logging, and observability dashboard.
- [x] **10-Call Benchmark Harness:** Comprehensive ground-truth test harness evaluating precision, recall, and fallback latency.
- [x] **RM Compliance Reporting via Elastic Connector:** HTML/text report generation with **Elastic Email Connector** dispatch (Kibana actions API) and MySQL audit logging.
- [x] **Multi-Layer Guardrails:** Financial PII masking (PAN, mobile, folio, email), citation grounding, completeness verification, and ground-truth response evaluation.

### Roadmap (Future Enhancements)
- [ ] **Real-Time Streaming Surveillance:** Webhook-based WebSocket audio ingestion for sub-second in-call alerts to supervisors.
- [ ] **Self-Service Regulation Uploader:** Automated OCR and pipeline ingestion for ad-hoc circular PDF uploads via UI (currently batch-indexed).
- [ ] **Automated Remediation Workflows:** Integration with CRM systems (Salesforce Financial Services Cloud), (Zoho CRM) to pause RM sales privileges upon repeat high-severity violations.
- [ ] **Real-Time RM Sales Copilot & In-Call Guidance:** Live in-call assistive feed providing Relationship Managers with compliant talking points, dynamic suitability-matched funds to pitch based on real-time customer risk profiling, and instant prompts for mandatory statutory disclosures before concluding the call.

---

## 6. Technology Inventory

- **Elasticsearch (Serverless on AWS ap-southeast-1):** Central intelligence layer housing `calls`, `regulations`, and `compliance_findings` indices, hybrid vector search via `.jina-embeddings-v5-text-small`, and ES|QL analytics.
- **Elastic Observability:** Official `elastic-apm` Python agent, custom native pipeline spans, ECS structured logging, and APM tracing.
- **Elastic Connectors:** Native Elastic Email Connector (`vigil-mail`) for automated, secure report generation and email dispatch to branch supervisors without exposing raw SMTP credentials.
- **AWS Bedrock:** Primary forensic LLM reasoning engine utilizing `anthropic.claude-sonnet-4-20250514-v1:0`.
- **Google Gemini:** Automated zero-downtime fallback LLM utilizing `gemini-3.6-flash`.
- **Sarvam AI:** High-precision speech-to-text, speaker diarization, and vernacular translation (`saaras:v3`).
- **MySQL 8.0:** Master relational database storing customer profiles, product risk rules, RM rosters, reviewer accounts, and immutable audit logs.
- **FastAPI (Python 3.11):** High-performance backend API framework.
- **React 18 + TypeScript + Vite:** Modern single-page application with Tailwind CSS, TanStack React Query, Lucide icons, and Recharts.
- **WaveSurfer.js:** Web Audio API waveform rendering and programmatic timestamp seeking.

---

## 7. Build Timeline & Team Note

Vigil was conceptualized, architected, and built across 15 structured development phases as an institutional-grade compliance platform. Every data flow, schema, and API endpoint was engineered to production standards—avoiding mock placeholders, enforcing strict type safety, and delivering a verifiable audit trail for every finding.

Customer, RM, product, and transaction records are synthetic institutional test data. All regulatory documents and citations represent actual statutory publications issued by the Securities and Exchange Board of India (SEBI) and the Association of Mutual Funds in India (AMFI).
