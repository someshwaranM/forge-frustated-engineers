# VIGIL — Phase 13: Elastic Observability Implementation

**File:** `docs/dev_prompts/13_elastic_observability_implementation.md`

**Scope:** Implement real **Elastic Observability** across the complete Vigil application. This phase must replace the existing custom `StageTimer`-based observability with genuine Elastic Observability capabilities.

> **IMPORTANT:** This phase must use **Elastic Observability directly**.  
> **Do NOT use OpenTelemetry, OpenTelemetry SDKs, OTel exporters, or OTel instrumentation.**

At the end of this phase, both **backend and frontend changes must be complete**, and the entire Vigil pipeline must be observable through Elastic.

---

# 1. Phase Objective

Vigil currently has a lightweight custom timing mechanism based on `StageTimer`.

That is not sufficient for the final implementation.

This phase upgrades Vigil to real Elastic Observability so that the system itself can be monitored.

The final implementation must provide visibility into:

- Backend/API health
- Application performance
- Request latency
- Application errors
- Logs
- Metrics
- Distributed/request traces where supported by Elastic's native APM implementation
- Sarvam processing latency
- Elasticsearch performance
- Compliance detection latency
- Regulation retrieval latency
- Investigator/AI latency
- Agent/tool execution latency where supported
- Database performance where practical
- End-to-end call processing latency
- Processing throughput
- Failures and exceptions
- Operational alerts
- Observability dashboards

---

# 2. NON-NEGOTIABLE TECHNOLOGY RULE

## Use Elastic Observability directly

The implementation must use the **Elastic Observability stack and its native capabilities**.

Use the appropriate Elastic-native components available in the configured environment, such as:

- Elastic APM
- Elastic Agent
- Elasticsearch
- Kibana / Elastic Observability
- APM Server / Elastic APM Server where required by the deployment
- Elastic Logs
- Elastic Metrics
- Elastic Traces
- Elastic dashboards
- Elastic alerting

The exact Elastic components should be selected based on the actual Elastic environment already configured for Vigil.

## Absolutely do NOT use

```text
OpenTelemetry
OpenTelemetry SDK
OTel API
OTel exporters
OTel Collector
OTel instrumentation
OTEL_* environment variables
```

Do not introduce OpenTelemetry as an intermediate layer.

---

# 3. Existing State

The current Vigil implementation contains a custom stage-timing mechanism.

Conceptually:

```text
Audio
  ↓
Ingestion
  ↓
Sarvam STT
  ↓
Elasticsearch
  ↓
Detection
  ↓
Regulation Retrieval
  ↓
Investigator
  ↓
Finding
  ↓
Case
```

The current implementation measures stages using application-side timers.

This phase must replace that approach with genuine Elastic Observability.

The existing `StageTimer` should no longer be treated as the primary observability system.

If some business-level duration is still useful inside application data, it may remain, but it must not be presented as Elastic APM/Observability telemetry.

---

# 4. Definition of Success

At the end of Phase 13, the team must be able to run a real Vigil call and observe the processing activity in Elastic.

Example:

```text
CALL-1042
    │
    ├── API Request
    │
    ├── Audio Ingestion
    │
    ├── Sarvam STT
    │
    ├── Elasticsearch Indexing
    │
    ├── Compliance Detection
    │
    ├── Regulation Retrieval
    │
    ├── Investigator
    │
    ├── Finding Creation
    │
    └── Case Creation
```

Elastic Observability must provide enough information to determine:

```text
What happened?
When did it happen?
How long did it take?
Which service/stage was slow?
Did it fail?
What caused the failure?
```

---

# 5. First Task — Inspect Existing Repository

Before making changes, inspect the complete existing project.

Understand:

```text
backend/
frontend/
elastic/
ingestion/
sarvam/
agents/
compliance/
db/
workflows/
api/
```

Also inspect:

```text
.env
.env.example
requirements.txt
pyproject.toml
package.json
Docker files
existing Elastic configuration
existing logging
existing StageTimer
existing health endpoints
existing dashboard APIs
```

Do not blindly create duplicate implementations.

Reuse existing project architecture wherever possible.

---

# 6. Elastic Environment Discovery

Before implementation, determine how the project is currently connected to Elastic.

Identify:

```text
Elasticsearch URL
Kibana URL
Elastic Cloud or self-managed deployment
Authentication method
Existing API keys
Existing indices
Existing Kibana space
Existing APM configuration
Existing Elastic Agent configuration
```

Do not print secrets.

Do not commit credentials.

If Elastic APM is already available, use it.

If APM is not configured, implement the required Elastic-native APM setup appropriate to the existing environment.

Do not replace the existing Elasticsearch cluster.

---

# 7. Elastic APM

Implement **Elastic APM** for the Vigil backend.

The backend should be visible as an actual service in Elastic Observability.

Expected conceptual service:

```text
vigil-backend
```

Elastic APM should capture:

- requests
- transactions
- spans
- latency
- errors
- exceptions
- service health
- dependency performance

Use the official/native Elastic APM agent for the backend language.

Do not implement equivalent functionality manually if Elastic APM already provides it.

---

# 8. FastAPI Instrumentation

Instrument the existing FastAPI application using the Elastic-native APM mechanism.

Important endpoints include:

```text
GET  /api/calls
GET  /api/calls/{call_id}

POST /api/calls/process

POST /api/investigate
POST /api/chat

POST /api/cases

GET  /api/dashboard/summary
GET  /api/findings

GET  /api/rm/{rm_id}/analytics
```

Use the actual routes present in the repository.

Elastic APM must be able to show:

```text
HTTP method
endpoint
status
response time
transaction
errors
```

Do not expose request bodies containing sensitive information.

---

# 9. Backend Service Identification

Configure proper Elastic APM service metadata.

At minimum identify:

```text
service name
service version
environment
```

Example:

```text
vigil-backend
```

Use environment variables/configuration rather than hardcoded secrets.

The exact configuration should follow the Elastic APM agent being used.

---

# 10. End-to-End Vigil Pipeline Monitoring

Instrument the actual Vigil processing pipeline.

The target is:

```text
Audio
 ↓
Ingestion
 ↓
Sarvam
 ↓
Transcript Processing
 ↓
Elasticsearch
 ↓
Detection
 ↓
Regulation Retrieval
 ↓
Investigator
 ↓
Finding
 ↓
Case
```

Each major operation must be observable through Elastic APM.

Use Elastic APM's native transaction/span mechanisms where custom instrumentation is required.

Do not recreate an OpenTelemetry-like abstraction layer.

---

# 11. Custom Elastic APM Spans

Where automatic instrumentation is insufficient, add Elastic APM native spans around important operations.

At minimum cover:

```text
audio.ingestion
sarvam.transcription
transcript.normalization
elasticsearch.index
compliance.detection
regulation.retrieval
investigator
finding.creation
case.creation
```

Use the actual Elastic APM API for the installed agent.

Example conceptual structure:

```text
Vigil API Transaction
│
├── audio.ingestion
├── sarvam.transcription
├── elasticsearch.index
├── compliance.detection
├── regulation.retrieval
├── investigator
├── finding.creation
└── case.creation
```

Do not create spans for imaginary operations.

---

# 12. Call Correlation

Every pipeline execution must be correlatable using a safe business identifier.

Use:

```text
call_id
finding_id
case_id
rm_id
```

where appropriate.

For example:

```text
CALL-1042
```

must allow the team to identify the corresponding processing activity.

Do not use customer PII as trace/span identifiers.

---

# 13. Sarvam Observability

Monitor the real Sarvam STT integration.

Capture:

```text
request execution
latency
success/failure
retry
exception
```

Where Elastic APM custom spans are required, create a Sarvam span.

Example:

```text
sarvam.transcription

duration: 4.82 sec
status: success
call_id: CALL-1042
```

Never record:

```text
raw audio
full transcript
API key
authentication token
customer PII
```

---

# 14. Elasticsearch Observability

Vigil already relies heavily on Elasticsearch.

Elastic Observability must provide visibility into Elasticsearch-dependent operations.

Monitor where supported:

```text
indexing latency
search latency
request volume
errors
connection failures
slow operations
```

Important Vigil indices include:

```text
calls
regulations
findings
```

The implementation must preserve existing Elasticsearch functionality.

Do not introduce a second Elasticsearch connection architecture solely for observability.

---

# 15. Detection Engine Observability

Instrument the compliance detection engine.

Monitor:

```text
detection execution time
candidate detection time
semantic search time
successful detections
failed detections
exceptions
```

Safe metadata may include:

```text
call_id
candidate_count
duration
status
```

Do not send complete transcripts to APM metadata.

---

# 16. Regulation Retrieval Observability

Regulation retrieval is a critical part of Vigil.

Make the retrieval operation observable.

Track:

```text
retrieval latency
search success/failure
query errors
```

Where appropriate, record safe identifiers such as:

```text
regulation_id
```

Do not record sensitive user/customer information.

---

# 17. Investigator / AI Observability

Instrument the Investigator Agent.

Track:

```text
investigation count
investigation latency
success/failure
errors
tool execution
```

Where Elastic APM custom spans are appropriate:

```text
investigator
│
├── search_calls
├── search_regulations
├── get_customer_profile
├── get_product_details
├── get_transactions
└── get_rm_history
```

Only instrument tools that actually execute.

Do not create fake tool spans.

---

# 18. AI Model Information

Where the actual AI provider exposes safe metadata, capture useful information such as:

```text
provider
model
latency
success/failure
```

If token usage or cost information is actually available through the provider integration, expose it.

Do not invent token or cost metrics.

Do not log full prompts or model responses containing sensitive information.

---

# 19. MySQL Observability

Where practical, use Elastic-native application/database instrumentation to monitor MySQL operations.

Focus on:

```text
query latency
connection failures
database errors
case creation latency
```

Do not log:

```text
passwords
connection strings
PII-containing query parameters
sensitive query values
```

Do not over-engineer database monitoring if it is not supported cleanly by the available Elastic environment.

---

# 20. Application Logs

Implement structured application logging that integrates with Elastic Observability.

Important events should be searchable in Elastic.

Examples:

```text
audio.ingestion.started
audio.ingestion.completed
transcription.started
transcription.completed
detection.completed
investigation.completed
finding.created
case.created
pipeline.failed
```

Logs should contain safe fields such as:

```text
timestamp
level
service
event
call_id
finding_id
case_id
stage
status
duration_ms
```

---

# 21. Log Correlation

Logs and APM data should be correlated wherever Elastic supports the capability.

A developer should be able to go conceptually from:

```text
Error
 ↓
Service
 ↓
Transaction
 ↓
Span
 ↓
Exception
```

Use Elastic's native correlation mechanisms.

Do not create an independent custom trace-ID framework if Elastic APM already provides the required correlation.

---

# 22. Error Tracking

Elastic Observability must show application errors.

Capture:

```text
FastAPI exceptions
Sarvam failures
Elasticsearch failures
Detection failures
Investigator failures
Database failures
Pipeline failures
```

Errors should include enough information to diagnose the problem.

Never include:

```text
passwords
API keys
customer PII
raw audio
full transcripts
authentication tokens
```

---

# 23. Metrics

Use Elastic-native application metrics where supported.

Useful Vigil metrics include:

```text
HTTP request count
HTTP error count
request latency

calls processed
calls failed

findings generated
cases created

pipeline processing duration

STT duration
detection duration
regulation retrieval duration
investigation duration
```

Avoid high-cardinality metric labels.

Do not use:

```text
call_id
customer_id
transcript
```

as metric dimensions.

---

# 24. Throughput Monitoring

Elastic Observability must provide visibility into processing throughput.

Example:

```text
Calls processed / minute
Findings generated / minute
Cases created / minute
Failed calls / minute
```

Use real application activity.

Do not create synthetic numbers for the dashboard.

---

# 25. End-to-End Latency

Measure the actual pipeline:

```text
Audio received
       ↓
Finding generated
```

The final observability view should make it possible to understand:

```text
Total processing time
```

and the contribution of:

```text
STT
Elasticsearch
Detection
Regulation Retrieval
Investigator
Case Creation
```

Use Elastic APM transactions/spans rather than the old `StageTimer` as the authoritative technical timing source.

---

# 26. Elastic Observability Dashboard

Create a dedicated Kibana / Elastic Observability dashboard:

```text
Vigil — Application & Pipeline Observability
```

The dashboard should contain real Elastic data.

---

## 26.1 System Health

Show:

```text
Vigil Backend
Elasticsearch
Database
AI Pipeline
```

Use real telemetry/health information.

---

## 26.2 API Performance

Show:

```text
Request rate
Average latency
P95 latency where available
Error rate
HTTP status distribution
Top slow endpoints
```

---

## 26.3 Pipeline Performance

Show:

```text
Calls processed
Average processing duration
P95 processing duration
STT latency
Detection latency
Regulation retrieval latency
Investigator latency
Case creation latency
```

---

## 26.4 Elasticsearch Performance

Show:

```text
Search performance
Indexing performance
Errors
Request volume
```

Focus on the Elasticsearch operations actually used by Vigil.

---

## 26.5 AI / Investigator Performance

Show:

```text
Investigation count
Investigation latency
Investigation failures
Tool execution latency
```

Only show token/cost information if real data is available.

---

## 26.6 Errors

Show:

```text
Errors over time
Top exceptions
Failed transactions
Failed services
```

Allow the team to drill into the relevant APM error/transaction where Kibana supports it.

---

# 27. Elastic APM Service View

Verify that Vigil appears as a service in Elastic APM.

The team should be able to open:

```text
Vigil Backend
```

and inspect:

```text
Transactions
Dependencies
Errors
Latency
Throughput
Spans
```

This must be populated by real Vigil traffic.

---

# 28. Trace / Transaction Drill-Down

The implementation must support investigation of a real call processing operation.

Example:

```text
CALL-1042

Total: 11.15 sec

Audio ingestion       180 ms
Sarvam STT           4820 ms
ES indexing           240 ms
Detection            1320 ms
Regulation search     680 ms
Investigator          3720 ms
Case creation         190 ms
```

These values must be generated from real execution telemetry.

Do not hardcode them.

---

# 29. Alerts

Create meaningful Elastic alerts.

At minimum:

### Alert 1 — API Error Spike

Detect an abnormal increase in backend API errors.

### Alert 2 — High Pipeline Latency

Detect when call processing latency exceeds a reasonable configured threshold.

### Alert 3 — STT Failure Spike

Detect an abnormal increase in Sarvam failures.

### Alert 4 — Elasticsearch Failure / Latency

Detect Elasticsearch failures or abnormal latency.

### Alert 5 — Investigator Failure Spike

Detect abnormal Investigator failures.

Use configurable thresholds.

Document the selected thresholds.

Do not pretend hackathon thresholds are production SLOs.

---

# 30. Frontend Implementation

The backend instrumentation alone is not enough.

The coding agent must also complete the frontend changes.

Do not redesign the existing Vigil UI.

Add an operational observability surface while preserving the current compliance-focused design.

---

# 31. Add Observability Navigation

Add:

```text
Observability
```

to the existing navigation.

Target:

```text
VIGIL
│
├── Dashboard
├── AI Investigation
├── Calls
├── Compliance Cases
├── RM Analytics
├── Regulations
├── Observability
└── Settings
```

Preserve the existing navigation structure and styling.

---

# 32. Vigil Observability Page

Create:

```text
Observability
```

as an operational monitoring page.

The page should include:

```text
System Health
API Performance
Pipeline Performance
Errors
Throughput
```

---

# 33. System Health UI

Display the real status of important Vigil dependencies.

Example:

```text
SYSTEM HEALTH

Vigil API            ● Healthy
Elasticsearch        ● Healthy
Database             ● Healthy
Sarvam               ● Healthy
Investigator         ● Healthy
```

Do not hardcode:

```text
Healthy
```

The status must be based on actual backend/Elastic telemetry or reliable health checks.

---

# 34. Pipeline UI

Show real pipeline performance:

```text
PIPELINE PERFORMANCE

Audio Ingestion
Sarvam STT
Elasticsearch
Detection
Regulation Retrieval
Investigator
Case Creation
```

For each:

```text
Average
P95 where available
Error count
```

---

# 35. Operational Summary

Show:

```text
Calls Processed
Findings Generated
Cases Created
Processing Success Rate
Average Processing Time
```

All values must come from real application/Elastic data.

No mock values.

---

# 36. Error Panel

Show recent operational errors.

Example:

```text
RECENT ERRORS

Elasticsearch timeout
2 minutes ago

Sarvam request failed
8 minutes ago

Investigator timeout
12 minutes ago
```

Clicking an error should provide useful drill-down where supported.

---

# 37. Frontend → Backend Observability APIs

Do not expose Elastic credentials to the browser.

If the frontend requires aggregated observability information, create secure backend endpoints such as:

```text
GET /api/observability/summary
GET /api/observability/pipeline
GET /api/observability/errors
GET /api/observability/services
```

Use the actual project API conventions.

These endpoints must query real Elastic/backend telemetry.

Do not create fake responses.

---

# 38. Frontend Loading / Error States

The Observability page must gracefully handle:

```text
Elastic unavailable
No telemetry yet
API failure
Empty metrics
Partial telemetry
```

Example:

```text
Observability data temporarily unavailable
```

is preferable to fake:

```text
0 errors
100% healthy
```

---

# 39. Existing Dashboard Update

The existing main Dashboard contains pipeline processing latency.

Keep it because the Dashboard is still the compliance overview.

However, where appropriate, replace the previous `StageTimer` source with real Elastic-backed telemetry.

Do not turn the main Dashboard into an APM dashboard.

The dedicated:

```text
Observability
```

page is the detailed operational monitoring surface.

---

# 40. Privacy Requirements

This is mandatory.

Elastic Observability must never become a PII dump.

Do NOT send:

```text
Customer name
Phone number
Email
PAN
Bank account number
Transaction account number
Raw audio
Full transcript
Passwords
API keys
Access tokens
Secrets
```

to logs, APM metadata, metrics, or error messages.

Safe identifiers include:

```text
call_id
finding_id
case_id
rm_id
regulation_id
```

when appropriate.

---

# 41. Performance Requirements

Observability instrumentation must not materially slow down Vigil.

Telemetry must be:

```text
non-blocking where possible
failure-tolerant
low overhead
```

If Elastic telemetry is temporarily unavailable, the core compliance pipeline must continue functioning.

Observability failure must not cause:

```text
STT failure
Detection failure
Finding failure
Case creation failure
```

---

# 42. Configuration

Update:

```text
.env.example
```

with the required Elastic Observability configuration.

Use the configuration appropriate to the actual Elastic APM/Observability deployment.

Examples of configuration categories may include:

```text
APM server URL
APM secret/token
service name
environment
server verification configuration
```

Do not add OpenTelemetry variables.

Specifically, the final project must NOT contain:

```text
OTEL_*
```

configuration.

---

# 43. Dependency Requirements

Add only the required official/native Elastic dependencies.

Before adding a dependency:

1. Inspect existing dependencies.
2. Check whether Elastic instrumentation already exists.
3. Avoid duplicate libraries.
4. Use the official Elastic-supported mechanism for the backend stack.
5. Do not install OpenTelemetry packages.

Final dependency tree must contain **no OpenTelemetry dependency introduced for this phase**.

---

# 44. Remove / Deprecate Old Observability Implementation

Inspect the existing `StageTimer`.

If it is currently used as the main observability mechanism:

- remove it from the observability architecture
- remove unnecessary timing JSON generation
- remove frontend dependency on those timing files
- replace it with Elastic-backed telemetry

If some timing information is still needed for business workflow data, retain only what is genuinely required.

Do not present custom timers as Elastic APM.

---

# 45. Documentation Updates

Update:

```text
README.md
ARCHITECTURE.md
docs/techstack.md
docs/phase_plan.md
```

Document:

```text
Elastic Observability
Elastic APM
Elastic logs
Elastic metrics
Elastic traces
Elastic dashboards
Elastic alerts
```

Document the actual implementation.

Remove outdated wording that says:

```text
observability = StageTimer
```

or:

```text
observability = simple self-logged timing
```

Do not document features that were not actually implemented.

---

# 46. Architecture Documentation

Update the architecture to show:

```text
                    VIGIL
                      │
              ┌───────▼───────┐
              │   React UI    │
              └───────┬───────┘
                      │
              ┌───────▼───────┐
              │ FastAPI       │
              │ Backend       │
              └───────┬───────┘
                      │
       ┌──────────────┼────────────────┐
       │              │                │
       ▼              ▼                ▼
    Sarvam      Elasticsearch        MySQL
       │              │                │
       └──────────────┼────────────────┘
                      │
                Investigator
                      │
                 Finding/Case
                      │
                      ▼
             Elastic Observability
              ┌───────┼────────┐
              │       │        │
             APM     Logs     Metrics
              │
            Traces
              │
         Dashboards
              │
            Alerts
```

Do not show OpenTelemetry anywhere in the Phase 13 architecture.

---

# 47. Testing

The coding agent MUST perform real tests.

## Test 1 — Backend API

Execute a real Vigil API request.

Verify it appears in Elastic APM.

---

## Test 2 — Audio Processing

Process one real sample audio file.

Verify Elastic captures the real processing activity.

---

## Test 3 — Pipeline

Verify the actual processing path:

```text
Audio
→ Sarvam
→ Elasticsearch
→ Detection
→ Regulation Retrieval
→ Investigator
→ Finding
→ Case
```

is observable to the degree supported by the implementation.

---

## Test 4 — Error

Trigger one safe test failure.

Verify:

```text
Elastic error
+
application log
+
APM transaction/span
```

can be correlated.

Restore the system afterward.

---

## Test 5 — Elasticsearch

Execute a real Elasticsearch operation used by Vigil.

Verify its performance/error information is visible.

---

## Test 6 — Investigator

Execute one actual investigation.

Verify the Investigator activity is observable.

---

## Test 7 — Frontend

Open:

```text
/observability
```

or the project's equivalent route.

Verify:

- real data loads
- health status works
- latency works
- errors work
- throughput works
- empty state works
- Elastic failure state works
- no hardcoded values exist

---

# 48. Final End-to-End Demo Test

Run the following:

```text
1. Start Elastic
2. Start Vigil backend
3. Start Vigil frontend
4. Ensure Elastic Observability is enabled
5. Process one real audio call
6. Wait for the complete pipeline
7. Open Elastic Observability
8. Open Vigil APM service
9. Inspect transaction
10. Inspect spans
11. Inspect errors/logs
12. Inspect metrics
13. Open Vigil Observability page
14. Verify corresponding operational metrics
```

The demo must use real data generated during execution.

---

# 49. Required Demo Trace

Prepare at least one successful call that can be demonstrated.

Example:

```text
CALL-1042
```

The team should be able to explain:

```text
Audio received
      ↓
Sarvam STT
      ↓
Elasticsearch
      ↓
Detection
      ↓
Regulation Retrieval
      ↓
Investigator
      ↓
Finding
      ↓
Case
```

Then show the corresponding Elastic Observability view.

---

# 50. Judge-Level Demonstration

The preferred demonstration sequence is:

### Step 1

Show Vigil processing a call.

### Step 2

Show the compliance finding.

### Step 3

Open Elastic Observability.

### Step 4

Show the Vigil backend service.

### Step 5

Open the relevant transaction.

### Step 6

Show the pipeline latency.

### Step 7

Drill into the slowest stage.

### Step 8

Show the corresponding logs/error information.

### Step 9

Show the Observability dashboard.

The narrative:

> **"Vigil doesn't only detect compliance risk. We also monitor the health of the intelligence pipeline itself using Elastic Observability."**

---

# 51. Final Architecture Story

The final Vigil architecture should clearly distinguish the roles of Elastic products.

```text
Elasticsearch
        ↓
Compliance data + search + semantic retrieval
        ↓
Agent Builder
        ↓
AI investigation
        ↓
Elastic Observability
        ↓
Health + performance + logs + metrics + APM + traces + alerts
```

The final story is:

> **Elasticsearch understands the compliance evidence.**

> **Agent Builder investigates that evidence.**

> **Elastic Observability monitors the intelligence system itself.**

---

# 52. Definition of Done

Phase 13 is complete only when ALL applicable requirements below are satisfied.

## Elastic Observability

- [ ] Elastic Observability configured
- [ ] Elastic APM configured
- [ ] Vigil backend visible as an APM service
- [ ] Real transactions visible
- [ ] Real spans visible where custom instrumentation is required
- [ ] Real errors visible
- [ ] Real logs visible
- [ ] Real metrics visible
- [ ] Pipeline performance visible
- [ ] Elasticsearch performance visible
- [ ] Investigator performance visible
- [ ] Dashboard created
- [ ] Alerts created

## Backend

- [ ] FastAPI instrumentation implemented
- [ ] Audio ingestion observable
- [ ] Sarvam observable
- [ ] Elasticsearch operations observable
- [ ] Detection observable
- [ ] Regulation retrieval observable
- [ ] Investigator observable
- [ ] Finding creation observable
- [ ] Case creation observable
- [ ] Database observable where practical
- [ ] Structured logging implemented
- [ ] Error tracking implemented
- [ ] Safe call correlation implemented

## Frontend

- [ ] Observability page created
- [ ] Navigation updated
- [ ] System health displayed
- [ ] Pipeline performance displayed
- [ ] API performance displayed
- [ ] Error information displayed
- [ ] Throughput displayed
- [ ] Real backend/Elastic data used
- [ ] No hardcoded telemetry
- [ ] Proper loading/error/empty states
- [ ] Existing dashboard remains compliance-focused

## Privacy

- [ ] No raw audio in telemetry
- [ ] No full transcript in telemetry
- [ ] No customer PII in telemetry
- [ ] No credentials in telemetry
- [ ] No secrets in repository
- [ ] No Elastic credentials exposed to browser

## Technology

- [ ] No OpenTelemetry
- [ ] No OpenTelemetry SDK
- [ ] No OTel Collector
- [ ] No OTel exporters
- [ ] No `OTEL_*` configuration
- [ ] Elastic-native observability only

## Validation

- [ ] Real API transaction verified
- [ ] Real call pipeline verified
- [ ] Real Elasticsearch operation verified
- [ ] Real Investigator operation verified
- [ ] Real error verified
- [ ] Frontend observability page verified
- [ ] Elastic dashboard verified
- [ ] Alerts verified
- [ ] End-to-end demo completed

---

# 53. Final Phase Outcome

After Phase 13, Vigil must move from:

```text
Custom StageTimer
        ↓
Simple latency panel
```

to:

```text
                    VIGIL
                      │
                      ▼
              Real Application
                      │
                      ▼
              Elastic APM
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
       Traces       Logs       Metrics
          │           │           │
          └───────────┼───────────┘
                      ▼
             Elastic Observability
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
       Dashboard    Alerts      Errors
```

The final implementation must be **real, functional, demonstrable, and backed by actual Elastic telemetry**.

No fake telemetry.

No mock observability.

No OpenTelemetry.

No `StageTimer` as the primary observability layer.

**Phase 13 = complete Elastic Observability implementation across Vigil backend + frontend.**