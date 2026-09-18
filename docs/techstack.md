# Vigil — Technology Stack & Architectural Inventory

## 1. System-Wide Technology Overview

Vigil is built upon an enterprise stack selected specifically for low-latency speech processing, high-precision legal retrieval, transactional case integrity, and verifiable AI reasoning.

```
+-----------------------------------------------------------------------------------------------+
|                                      FRONTEND INTERFACE                                       |
| React 18  •  TypeScript 5.7  •  Vite 6  •  Tailwind CSS  •  TanStack Query v5  •  WaveSurfer  |
+-----------------------------------------------------------------------------------------------+
                                               │ (HTTP / JSON REST)
                                               ▼
+-----------------------------------------------------------------------------------------------+
|                                      BACKEND CORE & API                                       |
| Python 3.11  •  FastAPI  •  Starlette  •  Pydantic v2  •  Uvicorn  •  Watchdog  •  PyMuPDF   |
+-----------------------------------------------------------------------------------------------+
         │                                     │                                    │
         ▼                                     ▼                                    ▼
+-----------------------+            +-----------------------+            +---------------------+
| SPEECH INTELLIGENCE   |            | SEARCH & VECTORS      |            | RELATIONAL DATABASE |
| Sarvam AI (saaras:v3) |            | Elasticsearch         |            | MySQL 8.0 (PyMySQL) |
| Multilingual STT      |            | Serverless / Cloud    |            | Master Roster, Risk |
| Diarization           |            | Jina v5 Semantic Text |            | Profiles, ACID Case |
| Vernacular Translate  |            | Hybrid BM25 + Vector  |            | Workflows & Audits  |
+-----------------------+            +-----------------------+            +---------------------+
         │                                     │                                    │
         └─────────────────────────────────────┼────────────────────────────────────┘
                                               │
                                               ▼
+-----------------------------------------------------------------------------------------------+
|                                    REASONING & OBSERVABILITY                                  |
| AWS Bedrock (Claude Sonnet 4)  •  Google Gemini (Gemini 3.6 Flash Fallback)  •  Elastic APM  |
+-----------------------------------------------------------------------------------------------+
```

---

## 2. Component-by-Component Technology Inventory

### 2.1 Search, Vector Storage & Knowledge Layer
- **Elasticsearch (Serverless / Cloud):**
  - *Role:* Central intelligence store housing `calls`, `regulations`, and `compliance_findings` indices.
  - *Why Chosen:* Provides native hybrid retrieval combining high-precision BM25 keyword matching with dense kNN vector search, evaluated via Reciprocal Rank Fusion (RRF). Eliminates the need for a separate vector database (like Pinecone or Milvus), keeping operational complexity low.
- **Embedding Model (`.jina-embeddings-v5-text-small`):**
  - *Role:* Drives dense semantic representations across `chunk_text_semantic` and `transcript_semantic` fields.
  - *Why Chosen:* Elastic Cloud's native inference pipeline eliminates external embedding API latency and handles high-context legal text with superior semantic fidelity.

### 2.2 Relational Storage & Workflow Integrity
- **MySQL 8.0 (PyMySQL Driver):**
  - *Role:* Single Source of Truth for customer risk profiles, product risk rules, RM rosters, user credentials, and case workflow state.
  - *Why Chosen:* Institutional compliance requires ACID guarantees and pessimistic row-level locking (`SELECT ... FOR UPDATE`). Elasticsearch is eventually consistent and lacks multi-document transactional locking. Separating relational workflow state from search indices guarantees zero state drift during concurrent reviewer audits.

### 2.3 Speech Processing & Multilingual Diarization
- **Sarvam AI (`saaras:v3`):**
  - *Role:* Out-of-the-box multilingual Speech-to-Text, speaker diarization, and English translation.
  - *Why Chosen:* Indian BFSI sales calls are heavily multilingual, blending Hindi, Indian English, and regional dialects ("Hinglish"). Generic Western STT engines (like Whisper or AWS Transcribe) degrade significantly on Indian accents and code-switching. Sarvam provides best-in-class vernacular transcription and time-aligned speaker diarization.

### 2.4 AI Reasoning & Forensic Evaluation
- **AWS Bedrock (`anthropic.claude-sonnet-4-20250514-v1:0`):**
  - *Role:* Primary reasoning engine powering the Investigator Agent and speaker role mapping.
  - *Why Chosen:* Claude Sonnet 4 offers superior complex reasoning, strict adherence to structured JSON schemas, and nuanced legal interpretation without hallucination.
- **Google Gemini (`gemini-3.6-flash`):**
  - *Role:* Automated zero-downtime fallback engine.
  - *Why Chosen:* Sub-second response times and high availability. When AWS Bedrock encounters quota limits or transient connectivity errors, Gemini executes the exact same prompt and Pydantic schema seamlessly.

### 2.5 Backend Services & Ingestion
- **Python 3.11:**
  - *Role:* Modern runtime with improved async performance, exception groups, and type hinting.
- **FastAPI (`0.115+`) & Starlette:**
  - *Role:* High-throughput asynchronous REST API framework.
  - *Why Chosen:* Native async support, automatic OpenAPI documentation generation, and high execution speed.
- **Pydantic v2 (`2.7+`):**
  - *Role:* Strict data validation across API boundaries and LLM forensic outputs (`ComplianceFinding`).
  - *Why Chosen:* Enforces non-negotiable typing; model outputs that do not conform to schema are caught and dismissed immediately.
- **PyMuPDF (`fitz` `1.24+`):**
  - *Role:* High-speed PDF text extraction and layout inspection for statutory regulatory circulars.
- **Watchdog (`4.0+`):**
  - *Role:* Asynchronous filesystem event listener monitoring `CallAudio/` drop directories.

### 2.6 Observability & Telemetry
- **Elastic APM (`elastic-apm` Python Agent `6.22+`):**
  - *Role:* Native, in-process performance monitoring and distributed tracing.
  - *Why Chosen:* Avoids the heavy memory and operational overhead of OpenTelemetry collector sidecars. Auto-instruments FastAPI/Starlette routes and traces custom native spans across audio validation, Sarvam batch API, Elasticsearch indexing, and LLM execution.
- **Elastic Common Schema (ECS):**
  - *Role:* Standardized JSON logging structure embedding `@timestamp`, `log.level`, `trace.id`, and `transaction.id`.

### 2.7 Automated Reporting via Elastic Connectors
- **Elastic Connectors (Kibana Actions API):**
  - *Role:* Enterprise notification and compliance audit dispatch mechanism.
  - *Why Chosen:* Utilizes the native Elastic Email Connector (`vigil-mail`) triggered via Kibana's Actions Execution API (`/api/actions/connector/{id}/_execute`). Dispatches supervisory compliance digests directly to branch managers without maintaining raw SMTP server configurations or credentials within the application, keeping credentials centrally managed and securing audit trail logging.

### 2.8 Frontend Application
- **React 18 (`^18.3.1`) & TypeScript (`^5.7.3`):**
  - *Role:* Type-safe single-page user interface.
- **Vite 6 (`^6.2.0`):**
  - *Role:* Next-generation frontend tooling providing lightning-fast HMR and optimized production bundles.
- **Tailwind CSS (`^3.4.17`):**
  - *Role:* Utility-first styling framework supporting dark/light surveillance themes.
- **TanStack React Query (`^5.67.1`):**
  - *Role:* Server-state management handling caching, background polling, and optimistic updates.
- **WaveSurfer.js (`^7.9.1`):**
  - *Role:* Web Audio waveform rendering, visual playback markers, and seek-to-timestamp audio navigation.
- **Recharts (`^2.15.1`):**
  - *Role:* Declarative charting library for rendering compliance trends and severity distributions.
- **Lucide React (`^1.16.0`):**
  - *Role:* Crisp, consistent institutional iconography.

---
*Vigil Technology Stack Specification — Complete Architectural Manifest*
