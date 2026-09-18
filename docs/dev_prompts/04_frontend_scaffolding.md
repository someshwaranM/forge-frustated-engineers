# Vigil — Phase 4 Dev Prompt: Frontend Scaffolding
`docs/dev_prompts/04_frontend_scaffolding.md`

*(Being run ahead of Phase 3 — frontend scaffolding has no dependency on
MySQL or Elasticsearch, so this reordering is safe. Regulation indexing still
needs to happen before Phase 9 (AI Chat) and Phase 10 (frontend integration
with real data), just not before this phase.)*

---

## Before running this: give the agent the detailed frontend doc too

Copy `Vigil_Frontend_Documentation.md` into the repo at `docs/frontend_documentation.md` (it isn't in the repo yet — it was written separately from the phase-plan docs). It has page-by-page detail, the shared-component table, and the UI/UX direction in more depth than this prompt restates. Paste it into the agent's context alongside this prompt, or point the agent at the file path directly, with an instruction like:

> "Also read docs/frontend_documentation.md before starting — it has the full page-by-page breakdown, the shared-component reuse table, and the detailed UI/UX direction. Where it and this prompt overlap, they should agree; where it has more detail (e.g. exact page contents, component reuse across pages), follow it."

---

## What this phase is — and isn't

This builds the app shell and every page's empty skeleton, wired into routing and navigation, styled to the final visual direction — but with **zero real data**. Every page renders placeholder/mock content. No API calls happen yet (that's Phase 10). The goal is that by the end of this phase, clicking through the whole nav feels like a real, finished product — just an empty one — so that Phase 10 becomes "swap mock data for real API calls," not "build the UI while also wiring it."

---

## The prompt (paste this verbatim to Codex / Claude Code / Antigravity)

````
You are running Phase 4 of the Vigil build: frontend scaffolding.

Before starting, read docs/frontend_documentation.md in full — it contains
the detailed page-by-page breakdown, the shared-component reuse table
(Section 6), and the UI/UX direction (Section 7) that this prompt summarizes
but does not fully restate. Treat it as the primary reference for anything
this prompt is ambiguous or under-specified about — the page contents,
which components are shared across which pages, and the visual tone. If
this prompt and that document ever conflict, follow the document.

Build the app shell, routing, navigation, and an empty (mock-data) version of
every page inside the frontend/ folder already scaffolded in Phase 1. Do NOT
wire any real API calls — no fetch/axios/TanStack Query calls to a backend.
Every page must render using local mock data defined inline or in a small
mockData.ts file, so the app is fully clickable and visually complete without
the backend running at all.

STEP 1 — Project setup:
- Initialize the Vite + React + TypeScript project inside frontend/ if not
  already initialized.
- Install and configure: Tailwind CSS, shadcn/ui, React Router, Recharts,
  WaveSurfer.js, TanStack Query (installed now, not used for real calls yet),
  Lucide (icons).
- Set up Tailwind theme tokens matching this visual direction: a restrained
  neutral base (off-white/light-grey background, near-black text), with a
  small, deliberate severity palette — muted red for HIGH, amber for MEDIUM,
  cool blue-grey for LOW/clean. This is a compliance/audit tool for financial
  institutions — the visual tone should read as trustworthy and legible, not
  flashy. No decorative gradients; color always carries information
  (severity/status), never just decoration.

STEP 2 — App shell (frontend/src/components/layout/):
- AppShell: the overall layout wrapper (sidebar + topbar + content area).
- Sidebar: the 7-item nav — Dashboard, AI Investigation, Calls, Compliance
  Cases, RM Analytics, Regulations, Settings — with active-route highlighting.
- Topbar: minimal — app name/logo, maybe a global search placeholder, no
  real functionality needed yet.

STEP 3 — Routing (frontend/src/router.tsx):
Set up React Router with these routes, each pointing at a page component
under frontend/src/pages/ (folders already scaffolded in Phase 1):
- /                     → Dashboard
- /ai-investigation     → AIInvestigation
- /calls                → Calls
- /calls/:callId        → Calls detail view (shares the transcript/audio
                          component with Case Detail, per the frontend doc)
- /cases                → ComplianceCases
- /cases/:caseId        → ComplianceCases/CaseDetail
- /rm-analytics         → RMAnalytics
- /rm-analytics/:rmId   → RMAnalytics detail view
- /regulations          → Regulations
- /settings             → Settings

STEP 4 — Build each page with realistic MOCK data (hardcoded arrays/objects,
not from any API):

- Dashboard: stat cards (total calls, findings by severity, open/resolved
  cases), a mock RM violation trend chart, a mock violation category
  breakdown chart, a mock "recent cases" list (5 rows), a mock latency stat.
- AI Investigation: a chat UI shell — message list + input box. Seed it with
  1-2 example exchanges as static mock messages, including one that renders
  a clickable "grounded result" card (case ID, severity, one-line summary)
  inline, to prove that layout works before real chat logic exists.
- Calls: a filterable table shell (RM, customer, date, violation, severity,
  status columns) with ~10 mock rows. Filters can be non-functional UI for
  now (dropdowns render, don't need to actually filter yet).
- Compliance Cases: same table pattern, ~8 mock case rows with Case ID, RM,
  customer, violation type, severity, confidence, date, status.
- Case Detail: THE MOST IMPORTANT PAGE. Build the full Evidence Chain layout
  with mock data: header (case ID/severity/confidence/status), audio player
  using WaveSurfer.js pointed at any placeholder/silent audio file for now,
  a mock transcript with one highlighted "violating" line, a clickable mock
  timestamp marker that seeks the WaveSurfer player (this interaction must
  actually work end-to-end even with placeholder audio — that's the point of
  building it now, not faking it), a right rail with mock customer risk
  profile / product context / regulation clause / AI reasoning, and a
  recommended-action + case-action buttons footer.
- RM Analytics: mock per-RM stat cards + a mock trend chart + a mock
  violation-category breakdown, plus a mock "repeat violations" flag.
- Regulations: a mock document list (use the actual 5 real document names
  from the regulatory corpus — SEBI MF Regulations 2026, SEBI Master
  Circular, AMFI Code of Ethics, etc. — as realistic mock rows) with mock
  "indexed" status badges, and a non-functional upload button.
- Settings: theme toggle (should actually work — wire it to a real light/dark
  mode since it's cheap and testable now), a mock confidence-threshold
  slider, a mock "active AI provider: Bedrock" status indicator.

STEP 5 — Shared components (frontend/src/components/shared/): build
SeverityBadge, CaseCallTable, AudioPlayer (WaveSurfer wrapper),
TranscriptViewer, EvidenceChainPanel, TrendChart, ChatMessageCard as real,
reusable components — even though they're fed mock data right now, they
should be built to the exact prop shapes that will later come from
data/schemas/compliance_finding_schema.py, so Phase 10 only has to change
the data source, not the components.

Do NOT build backend/, do NOT touch MySQL or Elasticsearch, do NOT implement
any real API service files beyond empty stubs with TODO comments pointing at
Phase 10. Stop once every route renders a complete, styled, mock-data page
and the timestamp-click → audio-seek interaction works on Case Detail with
placeholder audio.
````

---

## What "good" looks like

- Every one of the 10 routes renders a complete, styled page with no console errors, using only mock data.
- The Case Detail timestamp-click → audio-seek interaction genuinely works, even against placeholder audio — this is the interaction the whole product's credibility rests on, and proving it works mechanically now (before real data exists) means Phase 10 is just a data swap, not a first attempt under time pressure.
- Shared components are typed against the real `ComplianceFinding` shape from `data/schemas/compliance_finding_schema.py`, even while fed mock data — so Phase 10 changes a data source, not a component's props.
- Settings' theme toggle actually works — it's the one piece of "real" functionality in this phase, and free proof the app isn't just static mockups.
