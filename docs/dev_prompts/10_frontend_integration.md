# Vigil — Phase 10 Dev Prompt: Frontend Integration
`docs/dev_prompts/10_frontend_integration.md`

*(Scope: swap every page's Phase 4 mock data for real calls to the Phase 8/9
backend. No new pages, no new visual design — this phase makes the existing
UI real.)*

---

## Gaps to close first — these weren't built in earlier phases and integration will fail without them

1. **`GET /api/calls/{call_id}/audio`** (new, add to `backend/api/routes/calls.py`) — streams the WAV file from its archived path (`audio_file_path` on the call document) back to the browser. Without this, Case Detail's audio player has no real source.
2. **`GET /api/rm`** (new, add to `backend/api/routes/rm_analytics.py` or wherever Phase 8 put the RM routes) — lists all RMs with basic summary stats (total calls, total violations) for the RM Analytics landing page. Phase 8 only built the single-RM detail endpoint.
3. **`frontend/.env`** (new) — `VITE_API_BASE_URL=http://localhost:8000` (or whatever the backend actually runs on). This is the first and only frontend env file in this build, per the earlier env-consolidation decision — don't add anything else to it beyond what's actually needed.
4. **AI Provider Status on Settings** — compute this from real data: query `compliance_findings` for the `provider_used` breakdown (e.g. count grouped by provider) rather than reading the static seeded `app_settings.active_ai_provider` value, which never changes after seeding and would silently misrepresent whether the Gemini fallback ever actually fired.

---

## The prompt (paste this verbatim to Codex / Claude Code / Antigravity)

````
You are running Phase 10 of the Vigil build: wiring the Phase 4 frontend to
the real Phase 8/9 backend. Do not change page layouts, add new pages, or
redesign components — every shared component from Phase 4 was already typed
against the real ComplianceFinding/ComplianceCase/CallRecord shapes, so this
phase is a data-source swap, not a rebuild.

STEP 1 — Close the three gaps above: add the audio-streaming endpoint, the
RM-list endpoint, and frontend/.env. Confirm the backend and frontend can
reach each other (a basic fetch from the frontend dev server to
/api/dashboard/summary succeeding) before touching individual pages.

STEP 2 — Build the typed service files in frontend/src/services/ (per the
Frontend Documentation's plan) as thin TanStack Query wrappers around each
FastAPI route group: dashboardService.ts, callsService.ts, casesService.ts,
rmService.ts, documentsService.ts, settingsService.ts, chatService.ts. Every
read uses useQuery; every case action (mark_reviewed, dismiss, escalate,
assign, add_note) uses useMutation with onSuccess invalidating the relevant
case/dashboard queries so the UI reflects the change immediately, not after
a manual refresh.

STEP 3 — Page by page, replace mock data with real queries:
- Dashboard → dashboardService (summary stats, trends, recent cases).
- Calls / Compliance Cases lists → callsService/casesService, with real
  filters wired to the query params Phase 8 actually supports.
- Case Detail → casesService.getCase(caseId), which now returns the full
  assembled Evidence Chain from Phase 8's single-round-trip endpoint. Point
  the AudioPlayer at GET /api/calls/{call_id}/audio (Step 1) instead of the
  Phase 4 placeholder file. The timestamp-click → seek interaction should
  need NO changes — it was already built against the real
  ComplianceFinding.timestamp_start shape, only the data source changes.
- RM Analytics → rmService (list view uses the new GET /api/rm; detail view
  uses the existing GET /api/rm/{rm_id}/analytics).
- Regulations → documentsService (GET /api/documents). The "Upload
  Regulation" button STAYS non-functional — no upload/reindex-on-demand
  endpoint exists (Phase 3's indexing is a batch script, not an API-
  triggered flow), and building one is out of scope for this phase. Don't
  silently leave it looking broken either — keep it visibly disabled or
  labeled "coming soon" rather than a dead click.
- Settings → settingsService (GET/PATCH /api/settings for confidence
  threshold), plus the real AI-provider-usage query from the gap note above
  instead of the static seeded value.
- AI Investigation → chatService (POST /api/chat). Generate a session_id
  client-side (a UUID, persisted for the browser tab/session) and send it
  with every message. Render grounded_results as the clickable inline case
  cards the ChatMessageCard component already supports, and show
  tool_calls_made as the small "sources" indicator per the Frontend
  Documentation.

STEP 4 — Case-action error handling: when a mutation gets a 409
(CASE_ALREADY_RESOLVED, CASE_ALREADY_ESCALATED), show a clear inline message
(not a raw error dump) and refetch the case so the UI reflects its actual
current state — this is the direct frontend consequence of Phase 8's
idempotency guardrails, and silently swallowing or mishandling a 409 would
undo the value of having built it.

STEP 5 — Loading and error states: every page needs a loading state (the
Phase 4 mock data was always instantly available; real API calls aren't)
and an error state (network failure, 404, 500) — reuse one shared
loading/error UI pattern across pages rather than each page inventing its
own.

STEP 6 — Verification, with real output:
- Load the Dashboard and confirm real numbers appear (not the Phase 4 mock
  stats) — cross-check at least one number (e.g. total findings by
  severity) against what you know is actually in compliance_findings.
- Open Case Detail for one of your confirmed HIGH findings, confirm the
  audio actually plays, and confirm clicking the violation timestamp
  genuinely seeks the real audio to the right moment.
- Perform mark_reviewed on a case from the UI, confirm the case list
  updates without a manual page refresh, then try the same action again and
  confirm the 409 is handled gracefully in the UI.
- Ask the AI Investigation chat one of Phase 9's test queries and confirm a
  real grounded result card renders and is clickable through to the actual
  case/call.
- Load RM Analytics, confirm the list view shows all 5 RMs, and drill into
  RM001 to confirm real repeat-violation data appears.

Report back screenshots or the actual rendered state description for each
of the Step 6 checks, not a description of what should happen.
````

---

## What "good" looks like

- Every page shows real data that traces back to something you can independently verify in MySQL/Elasticsearch — no more Phase 4 placeholder numbers surviving into the working build.
- The Case Detail audio player actually plays a real recording and the timestamp-click interaction works against real timestamps — this was always the single interaction the whole pitch rests on, and Phase 10 is where it stops being a mechanically-proven demo (Phase 4) and becomes a real one.
- A 409 from a duplicate case action produces a clear, handled UI state, not a console error or a silently stale case list.
- The AI Provider Status on Settings reflects actual Bedrock/Gemini usage from real findings — if the Gemini fallback has never fired, it should visibly say so, not display a stale seeded assumption.
- The Upload Regulation button is honestly non-functional (disabled/labeled), not a dead click that looks like a bug.
