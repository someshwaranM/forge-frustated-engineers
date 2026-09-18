// frontend/src/services/observabilityService.ts
// Vigil — Phase 13: Elastic Observability Frontend Service
// Connects to backend /api/observability/* endpoints for telemetry, pipeline stats, and service health

import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export interface ObservabilitySummary {
  status: "ok" | "partial" | "error";
  collected_at: string;
  apm_enabled: boolean;
  calls_processed: number;
  failed_calls: number;
  findings_generated: number;
  cases_created: number;
  processing_success_rate: number | null;
  avg_processing_time_seconds: number | null;
  avg_processing_time_human?: string | null;
  data_sources: string[];
  data_freshness?: string;
  es_error?: string;
  db_error?: string;
}

export interface StageMetric {
  mean_seconds: number | null;
  median_seconds: number | null;
  min_seconds: number | null;
  max_seconds: number | null;
  count: number;
  mean_human?: string | null;
}

export interface ObservabilityPipeline {
  status: string;
  apm_enabled: boolean;
  total_calls_monitored: number;
  complete_pipeline_runs: number;
  legacy_or_partial_runs: number;
  stages: {
    ingestion: StageMetric;
    detection: StageMetric;
    investigation: StageMetric;
    end_to_end: StageMetric;
  };
  headline: {
    mean_end_to_end_seconds: number | null;
    median_end_to_end_seconds: number | null;
    fastest_run_seconds: number | null;
    slowest_run_seconds: number | null;
  };
  per_call?: Array<{
    call_id: string;
    is_complete_run: boolean;
    timestamps: {
      processing_started_at: string | null;
      indexed_at: string | null;
      detection_completed_at: string | null;
      investigation_completed_at: string | null;
    };
    durations: {
      ingestion_seconds: number | null;
      detection_seconds: number | null;
      investigation_seconds: number | null;
      end_to_end_seconds: number | null;
    };
  }>;
}

export interface PipelineErrorEntry {
  timestamp: string;
  stage: string;
  error_type: string;
  message: string;
  call_id?: string;
  logger?: string;    // logger name, e.g. "backend.agents.chat_agent"
  source?: string;    // "log" | "elasticsearch" | "pipeline" | "system"
  [key: string]: any;
}

export interface ObservabilityErrorsResponse {
  status: string;
  source: string;
  total_recent_errors: number;
  errors: PipelineErrorEntry[];
}

export interface ObservabilityServiceItem {
  status: "connected" | "degraded" | "unavailable" | "unknown";
  type: "live" | "last_known";
  latency_ms?: number | null;
  message: string;
  cluster_name?: string | null;
  database?: string | null;
  build_flavor?: string | null;
  findings_count?: number;
  fallback_fired_count?: number;
  calls_transcribed?: number;
  last_successful_call_at?: string | null;
  last_call_id?: string | null;
}

export interface ObservabilityServicesResponse {
  status: "HEALTHY" | "DEGRADED" | "DOWN";
  checked_at: string;
  apm_enabled: boolean;
  services: {
    mysql: ObservabilityServiceItem;
    elasticsearch: ObservabilityServiceItem;
    bedrock: ObservabilityServiceItem;
    gemini: ObservabilityServiceItem;
    sarvam: ObservabilityServiceItem;
  };
}

export const observabilityService = {
  getSummary: () => api.get<ObservabilitySummary>("/api/observability/summary"),
  getPipeline: () => api.get<ObservabilityPipeline>("/api/observability/pipeline"),
  getErrors: () => api.get<ObservabilityErrorsResponse>("/api/observability/errors"),
  getServices: () => api.get<ObservabilityServicesResponse>("/api/observability/services"),
};

export function useObservabilitySummary(refetchInterval = 30000) {
  return useQuery({
    queryKey: ["observability", "summary"],
    queryFn: observabilityService.getSummary,
    refetchInterval,
  });
}

export function useObservabilityPipeline(refetchInterval = 30000) {
  return useQuery({
    queryKey: ["observability", "pipeline"],
    queryFn: observabilityService.getPipeline,
    refetchInterval,
  });
}

export function useObservabilityErrors(refetchInterval = 30000) {
  return useQuery({
    queryKey: ["observability", "errors"],
    queryFn: observabilityService.getErrors,
    refetchInterval,
  });
}

export function useObservabilityServices(refetchInterval = 30000) {
  return useQuery({
    queryKey: ["observability", "services"],
    queryFn: observabilityService.getServices,
    refetchInterval,
  });
}
