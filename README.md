# Vigil: Autonomous, Explainable Compliance Intelligence for BFSI

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![Elasticsearch](https://img.shields.io/badge/Elasticsearch-Cloud-yellow.svg)](https://www.elastic.co/elasticsearch/)
[![React 18](https://img.shields.io/badge/React-18.3-cyan.svg)](https://reactjs.org/)
[![License: Proprietary](https://img.shields.io/badge/license-Proprietary-red.svg)](#)

> **Vigil** is an autonomous, explainable compliance intelligence platform designed for Banking, Financial Services, and Insurance (BFSI) institutions, specifically mutual fund distributors and asset management companies (AMCs) governed by SEBI and AMFI regulations. Vigil continuously audits Relationship Manager (RM) sales interactions, automatically flags statutory violations, and constructs a court-ready, auditable **Evidence Chain** for every finding.

---

## Demo Video & PPT

Watch the Vigil platform walkthrough: https://drive.google.com/drive/folders/1naqyI7tghWqBbJsY8tr_PlczIk0OFNHo?usp=sharing

---

## 1. Executive Summary & Problem Statement

In mutual fund distribution, regulatory oversight is high-stakes. The **Securities and Exchange Board of India (SEBI)** and the **Association of Mutual Funds in India (AMFI)** enforce stringent codes of conduct regarding risk disclosure, product suitability, and performance claims. 

Traditional compliance surveillance suffers from three critical bottlenecks:
1. **Sample Audits (<30–35% Coverage):** Due to the immense volume of telephony interactions, human compliance officers manually review only a small fraction of calls. Violations go undetected until investor complaints or regulatory penalties occur.
2. **"Black-Box" AI Scores:** Generic LLM-based speech solutions produce subjective, unstructured summaries or arbitrary risk scores (e.g., "Risk: High, 87/100") without citing specific clauses, precise audio timestamps, or investor risk profiles. Compliance officers cannot defend arbitrary scores to SEBI auditors.
3. **Audit Trail Fractures:** Compliance workflow actions (reviewing, escalating, dismissing, and archiving) are often siloed in spreadsheets or generic ticketing systems disconnected from call recordings and statutory documents.

### What Vigil Does End-to-End

Vigil resolves these gaps through an autonomous, multi-stage compliance pipeline:
- **Continuous Ingestion:** Monitors audio drop folders, validates WAV/MP3 files, and verifies audio stability.
- **Multilingual Speech Intelligence:** Transcribes and diarizes multilingual Hindi-English audio via Sarvam AI, translating Indian vernacular dialogue into English.
- **Speaker Role Disambiguation:** Differentiates RM from Customer using Bedrock LLM contextual analysis with heuristic fallback.
- **Hybrid Compliance Detection:** Runs deterministic phrase matchers, risk suitability checks against investor profiles, and mandatory disclosure verifiers.
- **Forensic Investigation:** Dispatches candidate violations to an **Investigator Agent** (AWS Bedrock Claude Sonnet 4 primary with Google Gemini 3.6 Flash zero-downtime fallback) that verifies evidence against indexed SEBI/AMFI regulatory chunks.
- **Auditable Evidence Chain:** Emits structured `ComplianceFinding` records containing the exact audio timestamp, verbatim transcript snippet, customer risk profile, product risk class, retrieved SEBI/AMFI clause text, forensic reasoning, and recommended action.
- **Case Management & Dual-Write:** Persists cases in MySQL for transactional integrity while updating Elasticsearch for sub-second dashboard search and aggregations.
- **Elastic Connector Email Delivery:** Generates and dispatches executive compliance dossiers and audit reports to branch supervisors using native Elastic Connectors.
- **Interactive Surveillance UI:** React-based executive dashboard featuring real-time audio playback via WaveSurfer.js, one-click seek-to-violation timestamps, natural language AI chat, and comprehensive Elastic Observability APM telemetry.

---

## 2. Key Differentiators

### 1. The Auditable Evidence Chain
Vigil does not output black-box risk numbers. Every confirmed finding produces a tamper-resistant, 9-point Evidence Chain:
```
[1. Severity & Confidence] ──> [2. Verbatim Dialogue Snippet] ──> [3. Exact Audio Timestamp]
                                                                          │
[6. Matched SEBI/AMFI Clause] <── [5. Product Risk Class] <── [4. Customer Risk Profile]
        │
        └──> [7. Forensic AI Reasoning] ──> [8. Recommended Action] ──> [9. Reviewer Audit Trail]
```
If any link in this chain cannot be grounded—such as a missing timestamp or a hallucinated regulation citation—the finding is **automatically rejected** by automated guardrails.

### 2. Dual-Write Auditability (MySQL + Elasticsearch)
- **MySQL 8.0** serves as the **Single Source of Truth** for transactional case states (`OPEN`, `RESOLVED`), reviewer assignments, resolution types, and row-level locked activity logs (`case_activity_log`).
- **Elasticsearch** serves as the **High-Speed Query Engine**, storing denormalized call records, hybrid-searchable regulatory text, and finding documents for ES|QL analytical aggregation.
- Dual-write mutations are strictly orchestrated: atomic MySQL commits precede Elasticsearch denormalized updates, and any synchronization discrepancy is logged as structured `DRIFT_RISK` telemetry.

### 3. Dual-Engine LLM Fallback Architecture
Forensic reasoning requires zero downtime. Vigil orchestrates **AWS Bedrock (Claude Sonnet 4)** as its primary reasoning engine and **Google Gemini (Gemini 3.6 Flash)** as an automated fallback. Both engines adhere to an identical Pydantic contract (`ComplianceFinding`), ensuring seamless failover without downstream schema breakage.

---

## 3. Platform Architecture Overview

```
                         [ Audio Streams (WAV / MP3) ]
                                       │
                                       ▼
                   ┌───────────────────────────────────────┐
                   │        Audio Ingestion Pipeline       │
                   │  (Watchdog, Stability Check, PyMuPDF) │
                   └───────────────────┬───────────────────┘
                                       │
                                       ▼
                   ┌───────────────────────────────────────┐
                   │         Sarvam AI Speech API          │
                   │ (Saaras v3 STT, Diarization, Translate│
                   └───────────────────┬───────────────────┘
                                       │
                                       ▼
                   ┌───────────────────────────────────────┐
                   │      Elasticsearch "calls" Index      │
                   │   (Nested Transcript Segments Isolation│
                   └───────────────────┬───────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
  ┌───────────────────────────┐                 ┌───────────────────────────┐
  │   Deterministic Engine    │                 │    Suitability Checker    │
  │ (Guaranteed Returns Rule) │                 │ (Customer vs Product Risk)│
  └─────────────┬─────────────┘                 └─────────────┬─────────────┘
                └──────────────────────┬──────────────────────┘
                                       │
                                       ▼
                   ┌───────────────────────────────────────┐
                   │      Regulatory Hybrid Retriever      │
                   │  (BM25 + Dense Semantic Vector Search)│
                   └───────────────────┬───────────────────┘
                                       │
                                       ▼
                   ┌───────────────────────────────────────┐
                   │       Forensic Investigator Agent     │
                   │ (AWS Bedrock Claude Sonnet 4 / Gemini 3.6 Flash Backup)│
                   └───────────────────┬───────────────────┘
                                       │
                                       ▼
                   ┌───────────────────────────────────────┐
                   │   Atomic Dual-Write State Machine     │
                   │   MySQL (Authoritative) + ES (Search) │
                   └───────────────────┬───────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
  ┌───────────────────────────┐                 ┌───────────────────────────┐
  │   FastAPI REST Services   │                 │    Elastic Observability  │
  │  (Endpoints & Chat Agent) │                 │ (Native APM & ECS Logging)│
  └─────────────┬─────────────┘                 └─────────────┬─────────────┘
                └──────────────────────┬──────────────────────┘
                                       │
                                       ▼
                   ┌───────────────────────────────────────┐
                   │     React + TypeScript Dashboard      │
                   │ (WaveSurfer.js Player, Cases, Analytics)
                   └───────────────────────────────────────┘
```

For full architectural diagrams, component responsibilities, and system design rationales, refer to [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 4. Repository Structure

```
d:/vigil
├── ARCHITECTURE.md              # Detailed system architecture and design decisions
├── README.md                    # Project overview, setup, and navigation (this document)
├── SUBMISSION.md                # Hackathon & executive project submission summary
├── CallAudio/                   # Active drop folder monitored by Watchdog for new calls
├── CallAudio-Archive/           # Processed audio files moved here post-ingestion
├── CallAudio-Failed/            # Errored audio files isolated for inspection
├── RegulatoryDocs/              # Master PDF corpus from SEBI and AMFI
│   ├── AMFI/                    # AMFI Code of Ethics, Code of Conduct for Distributors
│   └── SEBI/                    # SEBI MF Regulations (1996, 2026), Master Circular
├── backend/                     # Python 3.11+ backend services
│   ├── api/                     # FastAPI route definitions
│   │   └── routes/              # calls, cases, findings, rm, chat, dashboard, etc.
│   ├── agents/                  # Forensic Investigator and AI Chat Agent implementations
│   │   └── prompts/             # System prompts and grounding templates
│   ├── compliance/              # Detection rules, suitability checks, candidate builder
│   ├── db/                      # MySQL session management and connection pooling
│   ├── elastic/                 # Elasticsearch client and query helpers
│   ├── indexing/                # Regulatory document extraction, chunking, and validation
│   ├── ingestion/               # Audio file watcher, Sarvam STT pipeline, speaker mapping
│   ├── observability/           # Elastic APM integration, ECS logging, pipeline spans
│   ├── reports/                 # RM email compliance report generator and dispatchers
│   ├── benchmark/               # 10-call benchmark harness against ground-truth labels
│   ├── main.py                  # Backend application entrypoint & middleware configuration
│   └── requirements.txt         # Backend Python dependencies
├── data/                        # Catalogs, DDL scripts, schemas, and synthetic data
│   ├── mysql_ddl.sql            # MySQL schema DDL (all 9 institutional tables)
│   ├── seed_data.sql            # Master synthetic customer, RM, and product datasets
│   └── schemas/                 # Pydantic schemas and Elasticsearch JSON mappings
├── docs/                        # Complete technical documentation suite
│   ├── api_documentation.md     # Comprehensive REST API catalog
│   ├── backend_documentation.md # Backend internals, modules, schemas, guardrails
│   ├── frontend_documentation.md# React application hierarchy, state, WaveSurfer
│   ├── phase_plan.md            # Sequential build narrative across all 15 phases
│   ├── regulatory_corpus.md     # Regulatory grounding, chunking, and validation gate
│   └── techstack.md             # Technology decisions, libraries, and design choices
├── frontend/                    # React 18 + TypeScript SPA
│   ├── src/                     # Source application code
│   │   ├── components/          # Shared atomic components (AudioPlayer, Badges, etc.)
│   │   ├── pages/               # Top-level route pages (Dashboard, Cases, RM, etc.)
│   │   ├── services/            # Axios API client integrations
│   │   └── router.tsx           # React Router route registry
│   ├── package.json             # Frontend package definitions
│   └── vite.config.ts           # Vite bundler configuration
└── scripts/                     # Operational automation scripts
    ├── create_es_indices.py     # Elasticsearch schema deployment script
    ├── seed_mysql.py            # MySQL database initialization script
    └── run_benchmark.py         # Automated pipeline evaluation runner
```

---

## 5. Prerequisites

Before running Vigil locally, verify the following dependencies:
- **Operating System:** Windows 10/11, macOS, or Linux
- **Python:** 3.11 or higher
- **Node.js:** v18.0.0 or higher (with `npm` v9+)
- **MySQL:** 8.0 or higher (running locally or accessible via network)
- **Elasticsearch:** (Elastic Cloud Serverless or self-managed cluster with semantic search enabled)
- **API Credentials:**
  - **AWS Bedrock:** IAM credentials with access to `anthropic.claude-sonnet-4-20250514-v1:0`
  - **Google Gemini:** API Key with access to `gemini-3.6-flash`
  - **Sarvam AI:** API Key for multilingual speech-to-text (`saaras:v3`)

---

## 6. Quickstart & Local Setup

### Step 1: Clone and Configure Environment

Navigate to the backend directory and configure the environment variables:
```bash
cd backend
cp .env.example .env
```

Open `.env` and supply the required connection strings and API keys:
```ini
# AWS Bedrock Primary Engine
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
AWS_BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514-v1:0

# Google Gemini Fallback Engine
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL_ID=gemini-3.6-flash

# Sarvam Multilingual Speech Intelligence
SARVAM_API_KEY=your_sarvam_api_key

# Elasticsearch Cloud
ELASTICSEARCH_URL=https://your-deployment.es.io:443
ELASTICSEARCH_API_KEY=your_elastic_api_key

# Relational Storage (MySQL 8.0)
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=vigil
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password

# Elastic Observability & APM
ELASTIC_APM_SERVER_URL=https://your-apm-server:443
ELASTIC_APM_SECRET_TOKEN=your_apm_token
ELASTIC_APM_SERVICE_NAME=vigil-backend
ELASTIC_APM_ENVIRONMENT=production
ELASTIC_APM_ENABLED=true
```

### Step 2: Initialize Database and Elasticsearch Indices

1. **Initialize MySQL Schema & Seed Master Catalogs:**
```bash
# In project root:
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS vigil;"
mysql -u root -p vigil < data/mysql_ddl.sql
mysql -u root -p vigil < data/seed_data.sql
```

2. **Deploy Elasticsearch Indices (`calls`, `regulations`, `compliance_findings`):**
```bash
python scripts/create_es_indices.py
```

### Step 3: Run the Regulatory Indexing Pipeline

Index the 5 foundational SEBI and AMFI regulatory PDFs:
```bash
python backend/indexing/run_pipeline.py
```
This script executes PDF text extraction, strips recurring headers/footers, applies semantic chunking, executes the 7-point validation gate, and pushes dense semantic vectors to Elasticsearch.

### Step 4: Launch Backend API

Install Python dependencies and start the FastAPI service:
```bash
cd backend
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
The API server starts on `http://localhost:8000`. Access Swagger interactive documentation at `http://localhost:8000/docs`.

### Step 5: Launch Frontend Application

Install Node packages and run the Vite development server:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser. Default login credentials initialized at startup:
- **Username:** `admin`
- **Password:** `admin12345`

---

## 7. Running the Pipeline & Verification

To process audio recordings through the entire automated compliance pipeline:

### Process Audio Files Automatically
Drop any `.wav` or `.mp3` call file into `d:\vigil\CallAudio\`. The automated file watcher picks up the file, checks stability, transcribes and diarizes via Sarvam, performs speaker role identification, evaluates compliance rules, triggers the Investigator Agent, and updates MySQL and Elasticsearch.

Alternatively, process all pending files synchronously via script:
```bash
python backend/ingestion/process_now.py
```

### Execute the System Benchmark
Run the automated benchmark harness comparing pipeline outputs against 10 ground-truth audio calls:
```bash
python scripts/run_benchmark.py
```
This produces an auditable evaluation report at `backend/benchmark/benchmark_report.md` measuring Precision, Recall, Severity Alignment, and Fallback Latency.

---

## 8. Complete Documentation Index

For detailed, deep-dive technical documentation, refer to the following dedicated manuals:

| Document | Primary Focus |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | High-level system architecture, component boundaries, dual-write design, and architectural rationale. |
| [SUBMISSION.md](SUBMISSION.md) | Hackathon submission overview, problem/solution fit, demo flows, and feature roadmap. |
| [docs/frontend_documentation.md](docs/frontend_documentation.md) | React component hierarchy, WaveSurfer.js audio integration, state management, and page workflows. |
| [docs/backend_documentation.md](docs/backend_documentation.md) | FastAPI services, Pydantic schemas, detection engine, investigator guardrails, and MySQL schema. |
| [docs/api_documentation.md](docs/api_documentation.md) | Exhaustive REST API endpoint catalog, query parameters, schemas, and 409 conflict error codes. |
| [docs/regulatory_corpus.md](docs/regulatory_corpus.md) | The 5 SEBI/AMFI source documents, semantic chunking strategy, header stripping, and validation gates. |
| [docs/techstack.md](docs/techstack.md) | Technology choices, architectural roles, and package dependencies across all tiers. |
| [docs/phase_plan.md](docs/phase_plan.md) | Comprehensive engineering narrative documenting the implementation across all 15 development phases. |

---
*Vigil Platform — Engineering Documentation — Confidential & Proprietary*
