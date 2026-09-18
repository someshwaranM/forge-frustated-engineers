# Vigil — Frontend Architecture & UI Documentation

## 1. Executive Overview

Vigil's frontend is a single-page application (SPA) built with **React 18**, **TypeScript**, and **Vite**. The interface is designed specifically for financial compliance officers, audit leads, and surveillance supervisors. 

### Core Design Philosophy
In compliance surveillance, arbitrary scores and unexplained flags are unacceptable. A score of "87% Risk" means nothing to a regulator or internal audit team. Consequently, Vigil's frontend is built around a single unifying principle: **Every finding must be verifiable in seconds.**
- No bare risk scores or unlinked severity badges.
- Every violation links directly to verbatim transcript dialogue, customer risk context, and the exact statutory clause.
- **The Flagship Interaction:** On the Case Detail view, clicking a violation's timestamp marker immediately seeks the audio player to that exact second and highlights the corresponding transcript turn.

---

## 2. Technology Stack & Libraries

| Technology / Library | Version | Role & Architectural Purpose |
|---|---|---|
| **React** | `^18.3.1` | Core UI component model with functional components and hooks. |
| **TypeScript** | `^5.7.3` | Enforces compile-time type safety across API contracts and `ComplianceFinding` schemas. |
| **Vite** | `^6.2.0` | Fast development server and production bundler. |
| **Tailwind CSS** | `^3.4.17` | Utility-first styling with native dark mode support (`dark:` selector). |
| **TanStack React Query** | `^5.67.1` | Asynchronous server-state management, automated cache invalidation, and optimistic UI mutations. |
| **React Router** | `^6.30.0` | Client-side routing with nested layout hierarchies and protected route guards. |
| **WaveSurfer.js** | `^7.9.1` | Web Audio waveform rendering, seek-to-time audio playback, and visual progress tracking. |
| **Recharts** | `^2.15.1` | Declarative SVG charting for severity breakdowns and time-series violation distributions. |
| **Lucide React** | `^1.16.0` | Consistent institutional iconography. |
| **Axios** | `^1.7.0` | Promise-based HTTP client configured with base URL, bearer tokens, and standardized error interception. |

---

## 3. Navigation & Route Hierarchy

The application navigation is consolidated into a collapsible sidebar layout (`AppShell`), supporting full keyboard and responsive navigation.

```
/login                                     ──> Login page (Authentication)
/                                          ──> AppShell (Protected Layout)
│
├── /                                      ──> 🏠 Dashboard (Executive Compliance Overview)
├── /ai-investigation                      ──> 🤖 AI Investigation (Elastic Agent Builder Chat)
├── /calls                                 ──> 📞 Calls (Audited Call Population)
│    └── /calls/:callId                    ──> 🔎 Call Detail (Transcript & Audio Review)
├── /cases                                 ──> 🚨 Compliance Cases (Case Workflow Triage)
│    └── /cases/:caseId                    ──> 🔎 Compliance Case Detail (Evidence Chain & Audio Player)
├── /rm-analytics                          ──> 👥 RM Analytics (Relationship Manager Fleet Profiling)
│    └── /rm-analytics/:rmId               ──> 👤 RM Detail (Individual RM Dossier & Report Dispatch)
├── /regulations                           ──> 📄 Regulations (Statutory Corpus Explorer)
├── /observability                         ──> ⚡ Observability (APM Telemetry & Pipeline Latencies)
└── /settings                              ──> ⚙️ Settings (Runtime Thresholds & Engine Diagnostics)
```

### Route Guarding & Authentication
All routes under `/` are wrapped with `<ProtectedRoute>`. If an active JWT token is absent from `localStorage`, the router redirects unauthenticated users to `/login`.

---

## 4. Page-by-Page Architectural Breakdown

### 4.1 🏠 Dashboard (`src/pages/Dashboard/`)
- **Purpose:** Executive command center providing high-level surveillance visibility across all monitored calls and active cases.
- **Key Metrics & Widgets:**
  - *Metric Cards:* Total Calls Monitored, Processing Latency, Open Cases, Confirmed Violations.
  - *Severity Distribution Chart:* Recharts pie/donut chart breaking down findings into `HIGH`, `MEDIUM`, and `LOW`.
  - *Category Breakdown:* Bar chart showing prevalence of `GUARANTEED_RETURN`, `SUITABILITY_MISMATCH`, and `MISSING_DISCLOSURE`.
  - *Recent High-Risk Cases:* Clickable list routing directly to the corresponding Case Detail.
  - *Top Flagged RMs:* Summarized list of RMs with repeat compliance infractions.
- **Data Hook:** `useDashboardSummary()` hitting `GET /api/dashboard/summary`.

### 4.2 🤖 AI Investigation (`src/pages/AIInvestigation/`)
- **Purpose:** Natural language conversational assistant powered by Elasticsearch Agent Builder tools. Allows compliance officers to query call transcripts, regulatory clauses, and RM histories in plain English.
- **Key Components:**
  - *Chat Message Thread:* Renders markdown responses with grounded citation cards.
  - *Evidence Cards:* Clickable inline cards displaying Case ID, Severity, and summary that link directly into `/cases/:caseId`.
  - *Tool Invocation Indicator:* Displays collapsed pills indicating which backend tools were executed (e.g. `search_calls`, `search_regulations`).
  - *Suggested Query Chips:* One-click prompts (e.g., "Show high-severity guaranteed return findings", "Which RM has repeat violations?").
- **Data Hook:** `useChatMutation()` submitting to `POST /api/chat`.

### 4.3 📞 Calls (`src/pages/Calls/`)
- **Purpose:** Complete tabular audit log of every call processed by the ingestion pipeline—both flagged and clean.
- **Columns:** Call ID, RM Name, Customer Name, Date/Time, Duration, Language, Processing Status, Finding Count.
- **Filters:** Text search (Call ID, RM, Customer), Processing Status filter, Violation filter (`ALL`, `WITH_VIOLATIONS`, `CLEAN`).
- **Child Route (`CallDetail.tsx`):** Displays call metadata, full dialogue transcript with speaker labels (`RM` vs `CUSTOMER`), and linked findings.
- **Data Hooks:** `useCallsList()` hitting `GET /api/calls`, `useCallDetail(callId)` hitting `GET /api/calls/{callId}`.

### 4.4 🚨 Compliance Cases (`src/pages/ComplianceCases/`)
- **Purpose:** Primary case triage worklist where compliance officers review and act on detected violations.
- **Columns:** Case ID, RM ID, Customer ID, Category, Severity Badge, Confidence Score, Status (`OPEN` / `RESOLVED`), Date.
- **Filters:** Status (`ALL`, `OPEN`, `RESOLVED`), Severity (`HIGH`, `MEDIUM`, `LOW`), Category dropdown.
- **Triage Actions:** Quick navigation into the full Evidence Chain.
- **Data Hook:** `useCasesList()` hitting `GET /api/cases`.

### 4.5 🔎 Compliance Case Detail (`src/pages/ComplianceCases/CaseDetail.tsx`)
- **Purpose:** **The core investigative screen of the entire application.** Assembles the complete 9-point Evidence Chain on a single unified canvas.
- **Layout Architecture:**
  1. *Header Bar:* Case ID, RM ID, Customer ID, Severity Badge, Binary Status Badge (`OPEN`/`RESOLVED`), and Escalation Indicator.
  2. *Center Canvas — Audio & Dialogue:*
     - **WaveSurfer.js Audio Player:** Interactive waveform showing audio duration, play/pause controls, seek controls, and visual timestamp marker.
     - **Verbatim Transcript Viewer:** Time-stamped speaker turns. The turn containing the regulatory infraction is highlighted with an amber/red border.
  3. *Right Rail — Grounding & Context:*
     - **Customer Risk Profile:** KYC status, risk tolerance (`Conservative`/`Moderate`/`Aggressive`), investment experience (`Low`/`Medium`/`High`).
     - **Product Risk Class:** Scheme name, category, risk class, and approved investor risk profiles.
     - **Regulatory Citation:** Retrieved SEBI circular or AMFI code clause text, citation label, and source link.
     - **Forensic AI Reasoning:** Claude Sonnet 4 / Gemini 3.6 Flash forensic analysis explaining why dialogue constitutes a breach.
  4. *Case Action Bar & Audit Trail:*
     - **Reviewer Actions:** Mark Reviewed (`CONFIRMED_ACTION_TAKEN`), Dismiss (`DISMISSED_FALSE_POSITIVE`), Escalate (`ESCALATED_RESOLVED`), Reassign Reviewer.
     - **Add Case Note:** Form persisting notes to MySQL `case_activity_log`.
     - **Activity History:** Chronological feed of all human and automated actions on this case.
- **Data Hooks:** `useCaseDetail(caseId)`, `useUpdateCaseStatus()`, `useEscalateCase()`, `useAddCaseNote()`.

### 4.6 👥 RM Analytics (`src/pages/RMAnalytics/`)
- **Purpose:** Fleet-level surveillance monitoring repeated compliance infractions across Relationship Managers.
- **Features:**
  - *RM Master Table:* RM ID, Name, Branch, Total Calls, Violation Count, High-Severity Infractions, and Risk Score.
  - *Repeat Offender Banner:* Prominently highlights RMs with multiple violations in the same category (e.g. repeated guaranteed-return claims).
- **Child Route (`RMDetail.tsx`):**
  - Comprehensive RM dossier with category breakdown and violation timeline.
  - **Email Report Generator:** Modal allowing officers to dispatch an institutional HTML/text compliance report to branch supervisors via **Elastic Connectors** (Kibana email connectors).
- **Data Hooks:** `useRMList()` hitting `GET /api/rm`, `useRMAnalytics(rmId)` hitting `GET /api/rm/{rmId}/analytics`, `useSendReportEmail()`.

### 4.7 📄 Regulations (`src/pages/Regulations/`)
- **Purpose:** Document management repository displaying the 5 indexed SEBI/AMFI regulatory master circulars.
- **Corpus Statistics:** Total master documents (5), Total indexed chunks (~1,500+), Elasticsearch index status (`100% Synced`).
- **Document List:** Expandable document cards detailing authority (SEBI vs AMFI), publication date, effective status, chunk count, and direct link to regulatory PDF.
- **Data Hook:** `useDocumentsList()` hitting `GET /api/documents`.

### 4.8 ⚡ Observability (`src/pages/Observability/`)
- **Purpose:** Real-time surveillance dashboard exposing Elastic APM telemetry, pipeline execution latencies, and service health without exposing Elastic Cloud credentials to the client.
- **Tabs:**
  1. *Overview:* Health status, APM service indicators, active transaction rates, and Kibana deep links.
  2. *Pipeline Latencies:* Latency breakdown across each processing stage (Audio Validation, Sarvam STT, Hybrid Retrieval, Forensic Agent Evaluation).
  3. *Error Stream:* Live in-memory error ring buffer capturing backend `logger.error()` exceptions with stack traces.
- **Data Hook:** `useObservabilityMetrics()`, `useObservabilityErrors()`, `useObservabilityTraces()`.

### 4.9 ⚙️ Settings (`src/pages/Settings/`)
- **Purpose:** Minimal administrative configuration and diagnostic screen.
- **Controls:**
  - *Theme Toggle:* Switch between Light Mode and Dark Mode (persisted in `localStorage`).
  - *Confidence Threshold:* Slider adjusting the confidence threshold for automated triage (persisted to MySQL `app_settings` via API).
  - *AI Provider Status:* Live status badge showing active LLM provider (AWS Bedrock Claude Sonnet 4 vs Google Gemini 3.6 Flash fallback).
- **Data Hook:** `useSettings()`, `useUpdateSettings()`.

---

## 5. Audio Playback Integration & WaveSurfer.js Mechanics

The synchronized audio playback in `AudioPlayer.tsx` and `TranscriptViewer.tsx` is engineered using `wavesurfer.js`:

```
User clicks [00:45] timestamp on violation badge
                       │
                       ▼
            handleSeek(45.0) in CaseDetail.tsx
                       │
                       ▼
            AudioPlayerRef.seekTo(45.0)
                       │
                       ▼
         WaveSurfer.setTime(45.0) + WaveSurfer.play()
                       │
                       ▼
        onTimeUpdate(45.0) fires continuous time ticks
                       │
                       ▼
       TranscriptViewer auto-scrolls to Segment 3
            and applies CSS active highlight
```

### Implementation Safeguards
- **Zero Page Reloads:** All seeking occurs client-side against the already-buffered audio stream.
- **Audio Stream Fallback:** If the call's dedicated audio endpoint (`/api/calls/{call_id}/audio`) is unavailable, the player falls back to a bundled static sample audio file (`/audio/sample_call.wav`), preventing UI crashes during demonstration environments.
- **Visual Marker:** A vertical visual indicator is drawn on the waveform between `violationStart` and `violationEnd`.

---

## 6. Known Non-Functional UI Elements & Intentional Stubs

To ensure complete transparency, the following UI elements are deliberately non-functional or stubbed in the current release:

1. **Upload Regulation Button (`src/pages/Regulations/index.tsx`):**
   - *Status:* **Visibly Disabled (`disabled`)** with a lock icon.
   - *Reason:* Regulatory documents undergo rigorous offline chunking, header/footer stripping, and a 7-point validation gate via `backend/indexing/run_pipeline.py`. Online ad-hoc PDF uploading is deferred to the future roadmap.
2. **Kibana Direct Trace Deep Links:**
   - *Status:* Read-only external link buttons in `src/pages/Observability/index.tsx`.
   - *Reason:* Requires a live configured Kibana deployment URL in `.env`. When not configured, clicking the link notifies the user that Kibana APM URL is unconfigured.
3. **Delete Regulation Button:**
   - *Status:* Not rendered in UI.
   - *Reason:* Statutory master regulations are immutable baseline documents in production surveillance; ad-hoc deletion is disallowed via UI.

---

## 7. Component Hierarchy & Shared Directory

```
frontend/src/
├── components/
│   ├── auth/
│   │   └── ProtectedRoute.tsx     # Session validation wrapper
│   ├── layout/
│   │   ├── AppShell.tsx           # Base layout with Sidebar, Topbar, and Outlet
│   │   ├── Sidebar.tsx            # Collapsible navigation drawer
│   │   └── Topbar.tsx             # Breadcrumbs, quick search, user avatar
│   └── shared/
│       ├── AudioPlayer.tsx        # WaveSurfer.js audio waveform player
│       ├── TranscriptViewer.tsx   # Speaker turn viewer with sync scrolling
│       ├── EvidenceChainPanel.tsx # Structured 9-point grounding visualizer
│       ├── SeverityBadge.tsx      # Semantic badge (HIGH: red, MEDIUM: amber, LOW: blue)
│       ├── LoadingState.tsx       # Standardized skeleton and spinner loader
│       └── ErrorState.tsx         # User-friendly error message with retry button
```

---
*Vigil Frontend Architecture Reference — React 18 / TypeScript / WaveSurfer.js Specification*