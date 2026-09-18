# Vigil — Phase 8 Dev Prompt: Backend API & Case Workflow
`docs/dev_prompts/08_backend_api_case_workflow.md`

*(Scope: FastAPI routes exposing everything built in Phases 3-7 to the
frontend, plus the case workflow actions — Mark Reviewed, Dismiss, Escalate,
Assign, Add Note. AI Chat/search_regulations tooling is Phase 9, not this
phase.)*

---

## Schema patch needed first

```sql
ALTER TABLE compliance_case ADD COLUMN resolution_type VARCHAR(30) NULL;
-- values: CONFIRMED_ACTION_TAKEN | DISMISSED_FALSE_POSITIVE | ESCALATED_RESOLVED
-- NULL while status = OPEN; populated only when status transitions to RESOLVED
```

Apply this to `data/mysql_ddl.sql` and the live database before building the
routes below — several of them depend on it existing.

---

## Route map

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/dashboard/summary` | Dashboard KPIs, trends, category breakdown, recent cases |
| GET | `/api/calls` | Filterable call list (rm_id, customer_id, severity, status, date range) |
| GET | `/api/calls/{call_id}` | Full call detail incl. transcript_segments |
| GET | `/api/cases` | Filterable case list (status, severity, rm_id, category) |
| GET | `/api/cases/{case_id}` | Full Evidence Chain: case + finding + call + activity log, assembled in one response |
| PATCH | `/api/cases/{case_id}/status` | Mark Reviewed / Dismiss (see below) |
| POST | `/api/cases/{case_id}/escalate` | Escalate to Committee |
| POST | `/api/cases/{case_id}/assign` | Assign to a reviewer |
| POST | `/api/cases/{case_id}/notes` | Add a note |
| GET | `/api/rm/{rm_id}/analytics` | Per-RM stats, trend, repeat-violation flag |
| GET | `/api/documents` | Regulation list w/ indexed status, from the regulations ES index |
| GET | `/api/settings` | Read app_settings |
| PATCH | `/api/settings` | Update app_settings (e.g. confidence_threshold) |

Every mutating endpoint requires `reviewer_id` in the request body — there
is no auth/session system in this build (a deliberate scope decision, not an
oversight), so the caller must say explicitly who is acting.

---

## The prompt (paste this verbatim to Codex / Claude Code / Antigravity)

````
You are running Phase 8 of the Vigil build: FastAPI routes and case
workflow, inside backend/api/routes/ and backend/workflows/ (per Phase 1
scaffolding). Do NOT implement AI Chat, search_regulations tooling, or any
Agent Builder tools — that's Phase 9.

STEP 1 — Apply the schema patch: add compliance_case.resolution_type
VARCHAR(30) NULL to data/mysql_ddl.sql and the live database.

STEP 2 — Case workflow service (backend/workflows/case_service.py). MySQL
and Elasticsearch cannot be one ACID transaction — don't claim atomicity
across them. Every function here must instead follow this exact sequence:
  a) BEGIN a MySQL transaction. Update the compliance_case row AND insert
     the case_activity_log row (case_id, action, actor = the reviewer_id
     from the request, details, timestamp) together, then COMMIT. These two
     writes ARE atomic with each other (same database, real transaction).
  b) AFTER the MySQL transaction commits, update the denormalized status
     field on the matching document in the compliance_findings ES index
     (fetch by finding_id from the case row) — this is the dual-write
     flagged back in Phase 3.1.
  c) If step (b) fails, do NOT silently ignore it and do NOT roll back the
     already-committed MySQL transaction (that would just move the
     inconsistency elsewhere). Instead: log a structured DRIFT_RISK event
     (case_id, finding_id, attempted status, error) and return a response
     that tells the caller synchronization is incomplete — e.g. HTTP 207 or
     a 200 with a `"sync_status": "partial"` field — rather than a plain 200
     that implies everything succeeded. The MySQL write is the source of
     truth if the two ever disagree; the ES field is a denormalized copy for
     read performance, not the other way around.

  Before mutating anything, each function must also validate the case's
  CURRENT state and reject invalid transitions rather than blindly applying
  the action twice:
  - mark_reviewed / dismiss: only valid when status = "OPEN". If the case is
    already "RESOLVED", return 409 Conflict with
    {"error": "CASE_ALREADY_RESOLVED", "message": "..."} — do not silently
    re-apply or overwrite the existing resolution.
  - escalate: only valid when escalated = false. If already escalated,
    return 409 with {"error": "CASE_ALREADY_ESCALATED", ...} — do not create
    a second escalation activity-log entry for an already-escalated case.
  - assign: allowed regardless of current assignment (reassignment is a
    normal action), but if assignee_reviewer_id is already the current
    assigned_to, still succeed without erroring — just don't write a
    redundant activity-log entry for a no-op reassignment to the same person.
  - add_note: allowed regardless of case status — notes should be addable
    on OPEN or RESOLVED cases.

  Implement these specific functions:
  - mark_reviewed(case_id, reviewer_id, notes) → status="RESOLVED",
    resolution_type="CONFIRMED_ACTION_TAKEN", activity action="STATUS_CHANGE"
  - dismiss(case_id, reviewer_id, notes) → status="RESOLVED",
    resolution_type="DISMISSED_FALSE_POSITIVE", activity action="STATUS_CHANGE"
  - escalate(case_id, reviewer_id, notes) → escalated=true, status UNCHANGED
    (still OPEN — escalation doesn't close a case), activity action="ESCALATED"
  - assign(case_id, reviewer_id_performing_action, assignee_reviewer_id) →
    assigned_to=assignee_reviewer_id, activity action="ASSIGNED"
  - add_note(case_id, reviewer_id, note_text) → activity action="NOTE_ADDED"
    only — does not change status/resolution_type/assigned_to

STEP 3 — Build the routes from the table above.
  - PATCH /api/cases/{case_id}/status: body {reviewer_id, action:
    "mark_reviewed"|"dismiss", notes} — routes to the matching case_service
    function. Reject any other action value with a 400, don't silently
    default to one. Propagate case_service's 409 responses
    (CASE_ALREADY_RESOLVED) as-is — this is what makes a duplicate/retried
    request from the frontend safe rather than silently double-applying.
  - GET /api/cases/{case_id}: assemble the FULL Evidence Chain in one
    response — the compliance_case row (MySQL), its finding (fetched from
    compliance_findings ES by finding_id), the call (fetched from calls ES
    by call_id, including transcript_segments), and the full
    case_activity_log history (MySQL, ordered by timestamp) with actor names
    joined from the reviewer table. The frontend's Case Detail page should
    need exactly this one call, not several.
  - GET /api/rm/{rm_id}/analytics: compute the repeat-violation flag LIVE
    (COUNT(*) FROM compliance_case WHERE rm_id=? AND category=? GROUP BY
    category HAVING COUNT(*) > 1) — do not cache this in a stored field, per
    the earlier decision that a live query is simpler and can't go stale at
    this data volume.
  - GET /api/documents: aggregate the regulations ES index by document_id —
    return document_name, regulator, status (current/historical),
    chunk count, and a synthetic "indexed_status: INDEXED" (there's no
    partial-indexing state possible in this build, so this is always
    INDEXED once Phase 3 has run — don't build logic for a PROCESSING/FAILED
    state that can't actually occur here).
  - GET /api/dashboard/summary: total calls (count on calls index), findings
    by severity (count on compliance_findings, grouped), open/resolved
    counts (MySQL), RM-wise violation trend and category breakdown (MySQL
    GROUP BY), recent cases (last 5-10 by created_at). For pipeline latency:
    if no per-stage timestamp instrumentation exists yet from Phases 5-7,
    return a clearly-labeled placeholder/omit the field rather than
    fabricating a number — real latency tracking is Phase 12's job
    (observability panel), not this phase's.
  - GET/PATCH /api/settings: read/write the app_settings key-value table.
    PATCH should validate confidence_threshold is a float between 0 and 1
    before writing.

STEP 4 — Wire the confidence_threshold setting into something that actually
uses it (it's pointless as a stored value nothing reads): on GET
/api/cases and GET /api/dashboard/summary, add a computed
needs_review: true flag on any finding/case whose confidence is below the
currently stored confidence_threshold. Do NOT change Phase 7's
finding-creation logic to use this threshold — keep this a read-time
computed flag, decoupled from detection, so adjusting the slider in Settings
has an immediate, visible effect on what's flagged without needing to
re-run detection.

STEP 5 — CORS: enable for the frontend's dev origin. Error handling: return
structured JSON errors (not raw stack traces) for 404s (unknown case_id/
call_id/rm_id) and 400s (invalid action values, out-of-range settings).

STEP 6 — Verification, with real output:
- Fetch GET /api/cases/{case_id} for one of your confirmed findings from
  Phase 7 and confirm the full Evidence Chain assembles correctly in one
  response.
- Call mark_reviewed on one case, dismiss on another, escalate on a third —
  confirm all three: (a) the MySQL transaction committed the case update +
  activity log row together, (b) the corresponding compliance_findings ES
  document's status field updated to match after the commit.
- Deliberately call mark_reviewed AGAIN on the same case you just marked
  reviewed. Confirm it returns 409 CASE_ALREADY_RESOLVED and does NOT create
  a second case_activity_log entry — this is the idempotency/duplicate-
  request test, and it matters more for a real system than the happy path
  does.
- Deliberately call escalate twice on the same case. Confirm the second call
  returns 409 CASE_ALREADY_ESCALATED and does not create a duplicate
  escalation activity-log entry.
- Confirm GET /api/rm/{rm_id}/analytics for RM001 or RM002 (your repeat-
  pattern RMs) shows a real repeat-violation flag if applicable.
- Set confidence_threshold to a value that should flag at least one existing
  finding, and confirm needs_review appears correctly on GET /api/cases.

Report back the actual JSON responses from the Step 6 tests, including the
409 responses from the duplicate-action tests — not hypothetical ones.
````

---

## What "good" looks like

- MySQL's compliance_case + case_activity_log update together as a real transaction; the ES status update happens after, and a failure there produces a loud, structured DRIFT_RISK signal and a non-plain-200 response — never a silent inconsistency between the two stores.
- `resolution_type` actually distinguishes a confirmed case from a dismissed one in the data — this is the column that turns "case was closed" into "case was closed because X," which is what RM Analytics and any future false-positive-rate reporting needs.
- A duplicate/retried mark_reviewed or escalate call is safe — it returns a clear 409 instead of silently double-applying, which is what keeps a flaky frontend network retry or a double-click from corrupting the activity log.
- `GET /api/cases/{case_id}` is a single round trip for the entire Case Detail page — no N+1 of separate calls to assemble one Evidence Chain.
- The confidence_threshold slider in Settings has a real, immediately visible effect on API responses the moment it's changed — not a stored value nothing reads.
- Escalating a case does NOT close it — `status` stays OPEN, only `escalated` flips — preserving the earlier decision that escalation is a flag and an activity-log entry, not a third status value.
