// frontend/src/services/systemService.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export interface ServiceHealth {
  status: string;
  type: "live" | "last_known";
  latency_ms?: number | null;
  database?: string | null;
  build_flavor?: string | null;
  cluster_name?: string | null;
  findings_count?: number;
  fallback_fired_count?: number;
  calls_transcribed?: number;
  last_successful_call_at?: string | null;
  last_call_id?: string | null;
  message: string;
}

export interface SystemHealthResponse {
  status: "HEALTHY" | "DEGRADED";
  checked_at: string;
  services: {
    mysql: ServiceHealth;
    elasticsearch: ServiceHealth;
    bedrock: ServiceHealth;
    gemini: ServiceHealth;
    sarvam: ServiceHealth;
  };
}

export interface StageLatencyStats {
  mean_seconds: number | null;
  median_seconds: number | null;
  min_seconds: number | null;
  max_seconds: number | null;
  count: number;
}

export interface PipelineDiagnosticsResponse {
  status: string;
  total_calls_monitored: number;
  complete_pipeline_runs: number;
  legacy_or_partial_runs: number;
  stages: {
    ingestion: StageLatencyStats;
    detection: StageLatencyStats;
    investigation: StageLatencyStats;
    end_to_end: StageLatencyStats;
  };
  per_call: Array<{
    call_id: string;
    is_complete_run: boolean;
    timestamps: {
      processing_started_at: string | null;
      indexed_at: string | null;
      detection_completed_at: string | null;
      investigation_completed_at: string | null;
    };
    durations: {
      ingestion_duration_seconds: number | null;
      detection_duration_seconds: number | null;
      investigation_duration_seconds: number | null;
      end_to_end_duration_seconds: number | null;
    };
    notes: string[];
  }>;
}

export const systemService = {
  getHealth: () => api.get<SystemHealthResponse>("/api/system/health"),
  getDiagnostics: () => api.get<PipelineDiagnosticsResponse>("/api/system/diagnostics"),
};

export const SYSTEM_QUERY_KEYS = {
  all: ["system"] as const,
  health: () => [...SYSTEM_QUERY_KEYS.all, "health"] as const,
  diagnostics: () => [...SYSTEM_QUERY_KEYS.all, "diagnostics"] as const,
};

export function useSystemHealth() {
  return useQuery({
    queryKey: SYSTEM_QUERY_KEYS.health(),
    queryFn: systemService.getHealth,
    refetchInterval: 30000, // Background refresh every 30s
  });
}

export function useSystemDiagnostics() {
  return useQuery({
    queryKey: SYSTEM_QUERY_KEYS.diagnostics(),
    queryFn: systemService.getDiagnostics,
  });
}
