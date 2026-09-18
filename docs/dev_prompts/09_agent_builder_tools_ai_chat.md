# Vigil — Phase 9 Dev Prompt: AI Chat & Agent Builder Tools
`docs/dev_prompts/09_agent_builder_tools_ai_chat.md`

*(Scope: the AI Investigation page's backend. Read/investigate only — no
case creation, no notifications. Reuses the Bedrock-primary/Gemini-fallback
pattern already built for the Investigator Agent in Phase 7, extended to a
multi-turn tool-use loop instead of single-shot.)*

---

## Tool inventory — split by where the data actually lives

| Tool | Data source | Implementation |
|---|---|---|
| `search_calls` | `calls` ES index | Elastic Agent Builder index-search or ES\|QL tool |
| `search_regulations` | `regulations` ES index | Elastic Agent Builder tool — reuses Phase 6's hybrid BM25+semantic query pattern |
| `get_rm_history` | `compliance_findings` ES index | Elastic Agent Builder ES\|QL tool — reuses Phase 7's aggregation query |
| `get_customer_profile` | MySQL `customer` | Plain Python function in the chat tool-use loop |
| `get_product_details` | MySQL `product` | Plain Python function in the chat tool-use loop |
| `get_transactions` | MySQL `transaction` | Plain Python function in the chat tool-use loop |

**Not built in this phase:** `create_compliance_case`, `notify_compliance_team`
— see the design note above. If you want these reinstated with guardrails
instead of cut, that's a call to make explicitly, not by default.

---

## The prompt (paste this verbatim to Codex / Claude Code / Antigravity)

````
You are running Phase 9 of the Vigil build: AI Chat, backed by a mix of
Elastic Agent Builder tools and application-level MySQL lookups in a single
tool-use loop. Do NOT implement case creation or notification tools — the
chat agent is investigative/read-only. Do NOT build a second, separate
Bedrock/Gemini calling pattern — reuse the exact primary/fallback structure
from backend/agents/investigator_agent.py and gemini_fallback.py, adapted
for multi-turn conversation with tool-calling instead of single-shot.

STEP 0 — Verify Agent Builder's actual API surface on this specific
cluster before building anything: can a single named tool be executed
directly via API (for the FastAPI backend to call), independent of Agent
Builder's own full chat/conversation orchestration? Check the Kibana/
Elasticsearch API docs for this ES 9.6.0 Serverless instance. If direct
single-tool execution is straightforward, use it. If it turns out to require
more integration work than fits this phase, the acceptable fallback is:
implement the same hybrid BM25+semantic queries directly against the ES
client in application code (reusing Phase 6's regulation_retriever.py
pattern for search_regulations, and a new equivalent for search_calls) —
but still define the tools in Agent Builder's UI for the "grounds every
answer in real indexed data" story to remain literally true, even if the
FastAPI backend ends up calling the underlying ES query directly rather
than through Agent Builder's execution API. State clearly in your report-
back which path was actually used and why.

STEP 1 — Define in Elastic Agent Builder (Kibana UI or API):
- search_calls: an index-search or ES|QL tool over the "calls" index,
  supporting filters (rm_id, customer_id, severity, date range) AND
  free-text/semantic search over transcript_english_text +
  transcript_semantic (e.g. "find calls where guaranteed returns were
  mentioned" needs real hybrid search here, not just structured filters —
  this is new capability, not something Phase 8's GET /api/calls already
  does).
- search_regulations: reuses Phase 6's hybrid query pattern (BM25 on
  chunk_text + semantic on chunk_text_semantic) against the "regulations"
  index.
- get_rm_history: reuses Phase 7's aggregation query against the
  "compliance_findings" index (count + categories of prior findings for
  a given rm_id).

STEP 2 — Implement the MySQL-backed tools as plain Python functions in
backend/agents/chat_tools.py:
- get_customer_profile(customer_id) → customer table row.
- get_product_details(product_id) → product table row.
- get_transactions(customer_id=None, rm_id=None) → transaction rows,
  filtered by whichever ID is given.

STEP 2A — Tool safety and result limits, non-negotiable for every tool in
this phase:
- All 6 tools are strictly read-only. The MySQL tools (Step 2) must execute
  SELECT statements only — do NOT implement or expose a generic
  execute_sql(query)-style tool that takes arbitrary SQL from the model.
  Each tool's query is fixed/parameterized code, never a string the model
  constructs freely.
- No tool may call backend/workflows/case_service.py or any other mutating
  function — this is what makes "read-only" true at the implementation
  level, not just a description in this doc.
- Every search-style tool (search_calls, search_regulations,
  get_transactions) must have: a default result limit of 10, a maximum of
  25, deterministic sorting (e.g. by date_time or relevance score, not
  arbitrary), and a total_count field when available — so the model can say
  "I found 2 matching calls" instead of receiving (and potentially dumping
  into context or into a response) a large unbounded result set.

STEP 2B — get_rm_history needs two distinct, separately callable modes, not
one ambiguous aggregation:
  - get_rm_history(rm_id, before_date=None): if before_date is given, return
    only confirmed findings with date_time strictly before it (this is the
    Phase 7 semantics — "prior findings relative to a specific call").
  - get_rm_history(rm_id, before_date=None) with before_date omitted: return
    ALL confirmed findings for that RM, unfiltered by date. This is the mode
    a general chat question like "What is RM001's violation history?" needs
    — there is no "current call" in a chat context, so don't default to
    reusing Phase 7's before-a-specific-call filtering here unless the user
    question genuinely references a specific call's timing.

STEP 3 — Build backend/agents/chat_agent.py: a multi-turn conversation loop
that:
- Maintains conversation history in-memory per session, with an explicit
  lifecycle: session_id → history → user message → tool calls → assistant
  response, appended each turn. Previous assistant messages may provide
  conversational context (e.g. what was discussed earlier) but must NEVER
  be treated as authoritative evidence for regulations, findings, calls, or
  customer data — if a follow-up question needs a regulation, call
  search_regulations again even if a similar answer was given earlier in
  the conversation. This matters specifically because a follow-up like
  "what regulation applies?" after an earlier answer should re-verify, not
  trust its own prior answer as settled fact.
- Gives the model (Bedrock primary, Gemini fallback — identical fallback
  logic to Phase 7) access to all 6 tools from the table above via
  function-calling/tool-use.
- `grounded_results` is built from TOOL OUTPUTS, not from parsing the
  model's final text. Collect every call_id/case_id/finding_id that
  actually came back from a successful tool call during the current turn,
  deduplicated by type+id, and construct grounded_results from that list
  directly — before the model even produces its final response text. Do
  NOT scan the model's free-text answer for IDs as the source of truth; the
  model might reference something conversationally ("RM001's March call")
  without stating an ID, or could in principle generate an ID that looks
  valid but wasn't actually returned by any tool. Scanning the final text
  can still run as a secondary/supplementary check, but grounded_results
  must never depend on it being right.
- Never let the model answer from its own general knowledge about SEBI/
  AMFI rules without calling search_regulations first if the question is
  regulation-related — the grounding requirement applies here exactly as
  much as it does in the Investigator Agent.

STEP 3B — Loop limits: maximum 8 tool calls per user turn, maximum 5 model/
tool iterations per turn. If either is exceeded, stop and return a
controlled response — "Investigation exceeded the maximum tool-call limit."
— rather than looping indefinitely. Unlikely to hit this with a 10-call demo
dataset, but it's a real guardrail against a genuinely open-ended multi-turn
loop, not a hypothetical concern.

STEP 4 — Build POST /api/chat (backend/api/routes/chat.py): accepts
{session_id, message}, returns {response_text, grounded_results,
tool_calls_made} (include which tools fired for this turn — the Frontend
Documentation calls for a small "sources" indicator showing which tools
were used, don't skip this).

STEP 5 — Verification, with real output, using the actual example queries
from the Frontend Documentation (one query adjusted from the original list
— see note):
- "Show high-severity calls this month" (adjusted from "findings" to
  "calls" — the 6-tool design has search_calls, not a separate
  search_findings; calls carry severity via their linked finding, so this
  phrasing maps cleanly onto the tool that actually exists. Don't add a
  search_findings tool for this alone — the current design is cleaner for
  this build's scope, and nothing in the UI requires querying findings
  independently of their calls yet).
- "Which RM has the most violations?" → should call get_rm_history (or an
  aggregate across RMs) and cite real numbers.
- "Find calls where guaranteed returns were mentioned" → should exercise
  search_calls' semantic/hybrid text search specifically — confirm it
  returns your actual guaranteed-return demo calls (#2, #3), not an empty
  or hallucinated result.
- "What regulation applies to this finding?" → should call
  search_regulations and/or reference a real finding's regulation_id, not
  invent a clause.
- "Show me all cases for RM001" → should call search_calls/get_rm_history
  scoped to RM001 and return your actual RM001 calls (#1, #2) — confirm the
  response respects the 10-result default limit and reports total_count
  rather than assuming there are only 2 results because that's what this
  demo dataset happens to have.

Also specifically test:
- Ask a follow-up regulation question in the same session as an earlier
  regulation question, and confirm search_regulations is called AGAIN
  rather than the model reusing its earlier answer from conversation
  history as if it were still-verified fact.
- Deliberately ask something that would require more than 8 tool calls to
  answer thoroughly (or mock this in a unit test) and confirm the
  controlled limit-exceeded response fires instead of an unbounded loop.

Report back the actual response (including grounded_results and
tool_calls_made) for all test queries above.
````

---

## What "good" looks like

- `grounded_results` is built from what tools actually returned this turn, not from parsing the model's free-text answer — the model's phrasing can never be the thing that decides what counts as grounded.
- Every MySQL tool executes a fixed, parameterized SELECT — there is no generic SQL-executor tool a model could misuse, and no tool anywhere in this phase can call into `case_service.py` or any other mutating path.
- A follow-up regulation question re-verifies via `search_regulations` rather than trusting an earlier answer in the same conversation — conversation history is context, never evidence.
- Every search-style tool returns a bounded, sorted result set with a total count — the model reports "found 2 of 2" or "found 10 of 47," never silently receives (or dumps) an unbounded result set.
- The tool-call/iteration limits exist and actually fire under a forced test — not just present in the prompt text but verified to trigger the controlled error response.
- `grounded_results` gives the frontend real IDs to render as clickable cards, not text the frontend has to parse for mentions of "Case 001."
- The semantic/hybrid search test ("find calls where guaranteed returns were mentioned") actually returns your real demo calls — this is the test that proves `search_calls` does genuine retrieval, not just structured filtering.
- The chat agent cannot create or modify a single compliance_case — the investigative surface and the case-action surface (Phase 8) stay cleanly separated, so a stray or misinterpreted chat message can never quietly alter the audit trail.
