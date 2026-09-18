// frontend/src/types/index.ts
// Strict TypeScript types matching compliance_finding_schema.py and MySQL DDL

export type SeverityLevel = "LOW" | "MEDIUM" | "HIGH";
export type CaseStatus = "OPEN" | "RESOLVED";
export type ProcessingStatus = "INGESTED" | "TRANSCRIBED" | "INDEXED" | "DETECTED";

export interface ComplianceFinding {
  finding_id: string;
  call_id: string;
  category: string;
  severity: SeverityLevel;
  timestamp_start: string | number; // e.g. "01:24" or seconds
  timestamp_end: string | number;   // e.g. "01:42" or seconds
  transcript_evidence: string;
  customer_risk_profile: string;
  product_risk_class: string;
  regulation_id?: string;
  regulation_chunk_id?: string;
  regulation_citation_label?: string;
  regulation_source_url?: string;
  regulation_clause_text?: string;
  reasoning: string;
  confidence: number; // 0.0 to 1.0 (or percentage 0-100)
  recommended_action: string;
  rm_id?: string;
  customer_id?: string;
  status?: string;
  provider_used?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ComplianceCase {
  case_id: string;
  finding_id: string;
  call_id: string;
  rm_id: string;
  rm_name: string;
  customer_id: string;
  customer_name: string;
  status: CaseStatus;
  priority: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  opened_at: string;
  closed_at?: string;
  finding?: ComplianceFinding;
}

export interface TranscriptSegment {
  id: string;
  speaker: "RM" | "CUSTOMER";
  speaker_name: string;
  text: string;
  start_time: number; // in seconds
  end_time: number;   // in seconds
  timestamp_display: string; // e.g. "01:24"
  is_violation?: boolean;
}

export interface CallRecord {
  call_id: string;
  rm_id: string;
  rm_name: string;
  customer_id: string;
  customer_name: string;
  duration: string;
  duration_seconds: number;
  date_time: string;
  processing_status: ProcessingStatus;
  has_violation: boolean;
  finding_count: number;
  severity?: SeverityLevel;
  case_id?: string;
  audio_url?: string;
  transcript?: TranscriptSegment[];
  finding?: ComplianceFinding;
}

export interface RegulationDoc {
  document_id: string;
  filename: string;
  relative_path: string;
  title: string;
  issuer: "SEBI" | "AMFI";
  category: string;
  indexed_status: "INDEXED" | "PROCESSING" | "FAILED";
  chunks_count: number;
  size_formatted: string;
  last_updated: string;
}

export interface RMStats {
  rm_id: string;
  name: string;
  branch: string;
  region: string;
  manager_name: string;
  total_calls: number;
  total_violations: number;
  high_severity_count: number;
  medium_severity_count: number;
  low_severity_count: number;
  repeat_violation_flag: boolean;
  repeat_violation_category?: string;
  risk_score: number; // 0 - 100
  trend: {
    month: string;
    violations: number;
    calls: number;
  }[];
  category_breakdown: {
    category: string;
    count: number;
  }[];
}

export interface GroundedResultCardData {
  case_id: string;
  severity: SeverityLevel;
  finding_category: string;
  summary: string;
  confidence: number;
  rm_name: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  tools_called?: string[];
  grounded_case?: GroundedResultCardData;
  grounded_results?: Array<{ type: string; id: string }>;
}
