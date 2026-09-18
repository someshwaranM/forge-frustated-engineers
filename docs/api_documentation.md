# Vigil — REST API Reference Manual

## 1. Overview & API Conventions

All API endpoints are served under the base path `/api`. The Vigil backend enforces strict JSON input/output schemas using **Pydantic v2**. 

### Authentication & Headers
Protected endpoints require an institutional JWT Bearer token supplied in the standard HTTP header:
```http
Authorization: Bearer <jwt_token>
```
Endpoints mutating case status or recording audit notes also accept an optional `x-actor-id` or extract the authenticated `user_id` to populate MySQL `case_activity_log.actor`.

### Standard Error Response Format
All error responses adhere to a consistent JSON structure:
```json
{
  "error": "CASE_ALREADY_RESOLVED",
  "message": "Case 'CASE_001' is already in RESOLVED status.",
  "status_code": 409
}
```

### Common HTTP Status Codes
- `200 OK`: Request succeeded.
- `201 Created`: Resource successfully created.
- `400 Bad Request`: Malformed parameters or invalid payload.
- `401 Unauthorized`: Missing or expired Bearer token.
- `403 Forbidden`: Insufficient institutional role permissions.
- `404 Not Found`: Target entity does not exist in MySQL or Elasticsearch.
- `409 Conflict`: Business logic or concurrency conflict (e.g. attempting to resolve an already-resolved case).
- `422 Unprocessable Entity`: Request body failed Pydantic schema validation.
- `500 Internal Server Error`: Unhandled server exception (automatically reported to Elastic APM).

---

## 2. Authentication Endpoints (`/api/auth`)

### `POST /api/auth/login`
- **Purpose:** Authenticates a compliance officer and returns a JWT Bearer token with institutional claims.
- **Access:** Public.
- **Request Body (`LoginRequest`):**
  ```json
  {
    "username": "audit_officer",
    "password": "Vigil@Audit2026"
  }
  ```
- **Response (`200 OK` - `LoginResponse`):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user": {
      "user_id": "usr_audit_01",
      "username": "audit_officer",
      "full_name": "Audit Officer",
      "role": "Audit Officer",
      "team": "Compliance",
      "access_level": "All"
    }
  }
  ```

### `GET /api/auth/me`
- **Purpose:** Validates the active Bearer token and returns the current user profile.
- **Access:** Authenticated (`Bearer` required).
- **Response (`200 OK`):** User profile object.

---

## 3. Executive Dashboard (`/api/dashboard`)

### `GET /api/dashboard/summary`
- **Purpose:** High-density aggregation endpoint feeding the main surveillance dashboard.
- **Access:** Authenticated. Read-only.
- **Query Parameters:** None.
- **Response (`200 OK` - `DashboardSummaryResponse`):**
  ```json
  {
    "total_calls": 10,
    "total_findings": 7,
    "severity_counts": {
      "HIGH": 3,
      "MEDIUM": 2,
      "LOW": 2
    },
    "category_counts": {
      "GUARANTEED_RETURN": 3,
      "SUITABILITY_MISMATCH": 2,
      "MISSING_DISCLOSURE": 2
    },
    "case_status_counts": {
      "OPEN": 5,
      "RESOLVED": 2
    },
    "top_violating_rms": [
      {
        "rm_id": "RM001",
        "rm_name": "Vikram Malhotra",
        "violations_count": 2
      }
    ],
    "recent_cases": [
      {
        "case_id": "CASE_CALL_RM001_CUST001_20260310_1030",
        "call_id": "CALL_RM001_CUST001_20260310_1030",
        "rm_id": "RM001",
        "category": "SUITABILITY_MISMATCH",
        "severity": "HIGH",
        "status": "OPEN",
        "created_at": "2026-03-10T10:35:00Z"
      }
    ],
    "avg_processing_time_ms": 3420.5
  }
  ```

---

## 4. Calls Resource (`/api/calls`)

### `GET /api/calls`
- **Purpose:** Retrieves a paginated list of calls from the Elasticsearch `calls` index.
- **Access:** Authenticated. Read-only.
- **Query Parameters:**
  - `limit` (int, default: 50): Number of records.
  - `offset` (int, default: 0): Pagination offset.
  - `status` (string, optional): Processing status filter (`COMPLETED`, `FAILED`).
  - `has_violation` (boolean, optional): Filter by violation presence.
  - `rm_id` (string, optional): Filter by Relationship Manager ID.
- **Response (`200 OK`):**
  ```json
  {
    "total": 10,
    "calls": [
      {
        "call_id": "CALL_RM001_CUST001_20260310_1030",
        "rm_id": "RM001",
        "customer_id": "CUST001",
        "date_time": "2026-03-10T10:30:00Z",
        "duration_seconds": 185,
        "processing_status": "COMPLETED",
        "language": "hi-IN",
        "has_violation": true,
        "finding_ids": ["FND-2026-001"]
      }
    ]
  }
  ```

### `GET /api/calls/{call_id}`
- **Purpose:** Retrieves complete call document, including metadata and linked finding IDs.
- **Access:** Authenticated. Read-only.
- **Response (`200 OK`):** Complete call object.
- **Errors:** `404 Not Found` if `call_id` does not exist in Elasticsearch.

### `GET /api/calls/{call_id}/transcript`
- **Purpose:** Retrieves synchronized, speaker-diarized transcript turns.
- **Access:** Authenticated. Read-only.
- **Response (`200 OK`):**
  ```json
  {
    "call_id": "CALL_RM001_CUST001_20260310_1030",
    "segments": [
      {
        "segment_id": "seg_0",
        "speaker": "RM",
        "start_time": 0.0,
        "end_time": 5.2,
        "text_original": "नमस्ते सर, मैं विक्रम बोल रहा हूँ...",
        "text_english": "Hello sir, I am Vikram speaking from...",
        "is_violation": false
      },
      {
        "segment_id": "seg_1",
        "speaker": "RM",
        "start_time": 45.0,
        "end_time": 52.8,
        "text_original": "आप चिंता मत कीजिये, इस फण्ड में १५% गारंटेड रिटर्न मिलेगा।",
        "text_english": "Do not worry at all, this fund offers a 15% guaranteed return.",
        "is_violation": true
      }
    ]
  }
  ```

### `GET /api/calls/{call_id}/audio`
- **Purpose:** Streams the original audio file (`audio/wav` or `audio/mpeg`) for WaveSurfer.js playback.
- **Access:** Authenticated. Read-only.
- **Errors:** `404 Not Found` if the audio file is missing from disk.

---

## 5. Compliance Cases Resource (`/api/cases`)

### `GET /api/cases`
- **Purpose:** Retrieves compliance cases joined from MySQL `compliance_case` and customer master data.
- **Access:** Authenticated. Read-only.
- **Query Parameters:**
  - `status` (string, optional): Filter by `OPEN` or `RESOLVED`.
  - `severity` (string, optional): Filter by `HIGH`, `MEDIUM`, or `LOW`.
  - `rm_id` (string, optional): Filter by RM ID.
  - `escalated` (boolean, optional): Filter by escalation state.
- **Response (`200 OK`):** List of case summaries.

### `GET /api/cases/{case_id}`
- **Purpose:** Assembles the full **Evidence Chain** for a case by joining MySQL case records, activity audit logs, and Elasticsearch findings/calls documents.
- **Access:** Authenticated. Read-only.
- **Response (`200 OK`):**
  ```json
  {
    "case": {
      "case_id": "CASE_CALL_RM001_CUST001_20260310_1030",
      "finding_id": "FND-2026-001",
      "call_id": "CALL_RM001_CUST001_20260310_1030",
      "rm_id": "RM001",
      "customer_id": "CUST001",
      "category": "GUARANTEED_RETURN",
      "severity": "HIGH",
      "status": "OPEN",
      "escalated": false,
      "assigned_to": "REV001",
      "created_at": "2026-03-10T10:35:00Z"
    },
    "finding": {
      "finding_id": "FND-2026-001",
      "timestamp_start": 45.0,
      "timestamp_end": 52.8,
      "transcript_evidence": "Do not worry at all, this fund offers a 15% guaranteed return.",
      "customer_risk_profile": "Conservative",
      "product_risk_class": "High",
      "regulation_chunk_id": "COC_2022_II_4_g",
      "regulation_citation_label": "AMFI Distributor Code §II.4.g, p.4",
      "reasoning": "RM explicitly assured a 15% fixed return on an equity scheme, directly violating AMFI prohibition on indicative returns.",
      "recommended_action": "Issue formal compliance warning and require re-training on distributor code.",
      "confidence": 0.98
    },
    "activity_log": [
      {
        "action": "STATUS_CHANGE",
        "actor": "REV001",
        "details": "Case created automatically by Vigil Investigator Agent",
        "timestamp": "2026-03-10T10:35:00Z"
      }
    ]
  }
  ```

### `PATCH /api/cases/{case_id}/status`
- **Purpose:** Updates case workflow state (`OPEN` -> `RESOLVED`). Executes atomic dual-write.
- **Access:** Authenticated. Mutating.
- **Request Body (`UpdateCaseStatusRequest`):**
  ```json
  {
    "status": "RESOLVED",
    "resolution_type": "CONFIRMED_ACTION_TAKEN",
    "resolution_notes": "Reviewed with RM branch supervisor. Written caution issued."
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "success": true,
    "case_id": "CASE_CALL_RM001_CUST001_20260310_1030",
    "status": "RESOLVED",
    "sync_status": "full"
  }
  ```
- **Errors:**
  - `404 Not Found`: Case does not exist (`CASE_NOT_FOUND`).
  - `409 Conflict`: Case is already resolved (`CASE_ALREADY_RESOLVED`).

### `POST /api/cases/{case_id}/escalate`
- **Purpose:** Flags case as escalated to the supervisory compliance committee (`escalated=True`).
- **Access:** Authenticated. Mutating.
- **Request Body:**
  ```json
  {
    "reason": "Repeated guaranteed return claim across multiple client interactions."
  }
  ```
- **Errors:**
  - `409 Conflict`: Case has already been escalated (`CASE_ALREADY_ESCALATED`).

### `PATCH /api/cases/{case_id}/assign`
- **Purpose:** Reassigns case to another compliance reviewer.
- **Access:** Authenticated. Mutating.
- **Request Body:**
  ```json
  {
    "reviewer_id": "REV002"
  }
  ```
- **Errors:**
  - `404 Not Found`: Reviewer ID does not exist in `reviewer` table (`REVIEWER_NOT_FOUND`).

### `POST /api/cases/{case_id}/notes`
- **Purpose:** Appends an internal audit note to the case activity log.
- **Access:** Authenticated. Mutating.
- **Request Body:**
  ```json
  {
    "note": "Awaiting branch manager written response."
  }
  ```

---

## 6. Relationship Managers Resource (`/api/rm`)

### `GET /api/rm`
- **Purpose:** Lists all Relationship Managers with aggregated performance and compliance risk metrics.
- **Access:** Authenticated. Read-only.
- **Response (`200 OK`):**
  ```json
  [
    {
      "rm_id": "RM001",
      "full_name": "Vikram Malhotra",
      "branch": "Mumbai Main",
      "total_calls": 2,
      "total_violations": 2,
      "high_severity_count": 1,
      "repeat_offender": true
    }
  ]
  ```

### `GET /api/rm/{rm_id}/analytics`
- **Purpose:** Retrieves telemetry, category breakdown, violation timeline, and live repeat-offender calculation for an individual RM.
- **Access:** Authenticated. Read-only.
- **Response (`200 OK`):**
  ```json
  {
    "rm_id": "RM001",
    "full_name": "Vikram Malhotra",
    "branch": "Mumbai Main",
    "repeat_offender": true,
    "repeat_categories": ["GUARANTEED_RETURN"],
    "category_breakdown": {
      "GUARANTEED_RETURN": 2
    },
    "violation_timeline": [
      {
        "case_id": "CASE_CALL_RM001_CUST001_20260310_1030",
        "date": "2026-03-10",
        "category": "GUARANTEED_RETURN",
        "severity": "HIGH"
      }
    ]
  }
  ```

### `POST /api/rm/{rm_id}/report/email`
- **Purpose:** Generates a formatted compliance dossier for the RM and dispatches it to supervisors via the **Elastic Email Connector** (Kibana Actions API).
- **Access:** Authenticated (`Audit Officer`, `Compliance Head`, `Reviewer`, or `admin`). Mutating.
- **Request Body (`SendReportRequest`):**
  ```json
  {
    "recipients": ["compliance.head@vigil.com", "branch.manager@vigil.com"],
    "request_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "success": true,
    "rm_id": "RM001",
    "recipients": ["compliance.head@vigil.com"],
    "sent_at": "2026-09-18T12:00:00Z",
    "report_id": "RPT-2026-001",
    "idempotent_replay": false
  }
  ```

---

## 7. AI Investigation Chat (`/api/chat`)

### `POST /api/chat`
- **Purpose:** Natural language query endpoint powered by the conversational agent using Elastic Agent Builder tools.
- **Access:** Authenticated. Read-only tools.
- **Request Body:**
  ```json
  {
    "query": "Show all high-severity guaranteed return claims by RM001",
    "history": []
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "response": "Found 1 high-severity violation for RM001 regarding guaranteed return claims.",
    "tools_called": ["search_calls", "get_rm_history"],
    "sources": [
      {
        "case_id": "CASE_CALL_RM001_CUST001_20260310_1030",
        "title": "Guaranteed Return Violation",
        "severity": "HIGH",
        "summary": "15% assured return claim."
      }
    ]
  }
  ```

---

## 8. Regulatory Documents (`/api/documents`)

### `GET /api/documents`
- **Purpose:** Aggregates document metadata and chunk counts from the Elasticsearch `regulations` index.
- **Access:** Authenticated. Read-only.
- **Response (`200 OK`):**
  ```json
  {
    "total": 5,
    "items": [
      {
        "document_id": "AMFI_COC_2022",
        "document_name": "AMFI Code of Conduct for Mutual Fund Distributors",
        "regulator": "AMFI",
        "status": "current",
        "chunk_count": 48,
        "indexed_status": "INDEXED"
      }
    ]
  }
  ```

---

## 9. Observability & Health Telemetry (`/api/observability`, `/api/health`)

### `GET /api/health`
- **Purpose:** Container liveness probe.
- **Access:** Public.
- **Response (`200 OK`):**
  ```json
  {
    "status": "ok",
    "service": "vigil-api",
    "version": "1.0.0",
    "apm_enabled": true
  }
  ```

### `GET /api/observability/metrics`
- **Purpose:** Returns pipeline latency breakdowns, throughput, and Elasticsearch/MySQL operational metrics.
- **Access:** Authenticated.
- **Response (`200 OK`):** Includes stage-by-stage latencies (audio validation, STT, retrieval, LLM).

### `GET /api/observability/errors`
- **Purpose:** Retrieves the in-memory error ring buffer capturing recent server exceptions with stack traces.
- **Access:** Authenticated.

---

## 10. Application Settings (`/api/settings`)

### `GET /api/settings`
- **Purpose:** Retrieves persisted runtime settings from MySQL `app_settings`.
- **Access:** Authenticated. Read-only.

### `PATCH /api/settings`
- **Purpose:** Updates runtime configuration (e.g. `confidence_threshold`).
- **Access:** Authenticated (`admin` or `Compliance Head`). Mutating.

---
*Vigil REST API Specification — OpenAPI 3.0 Conforming Reference*
