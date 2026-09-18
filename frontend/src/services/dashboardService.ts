// frontend/src/services/dashboardService.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export interface DashboardSummaryResponse {
  kpis: {
    total_calls: number;
    total_findings: number;
    total_cases: number;
    open_cases: number;
    resolved_cases: number;
    escalated_cases: number;
    confidence_threshold: number;
  };
  findings_by_severity: {
    HIGH: number;
    MEDIUM: number;
    LOW: number;
    [key: string]: number;
  };
  rm_violation_trend: Array<{
    rm_id: string;
    rm_name: string;
    branch: string;
    violation_count: number;
  }>;
  category_breakdown: Array<{
    category: string;
    count: number;
  }>;
  recent_cases: Array<{
    case_id: string;
    finding_id: string;
    call_id: string;
    rm_id: string;
    rm_name: string;
    customer_id: string;
    customer_name: string;
    category: string;
    severity: "HIGH" | "MEDIUM" | "LOW";
    status: "OPEN" | "RESOLVED";
    resolution_type?: string;
    escalated: boolean;
    confidence?: number;
    needs_review: boolean;
    created_at: string;
  }>;
  pipeline_latency: {
    average_seconds: number | null;
    message: string;
    status: string;
  };
}

export const dashboardService = {
  getSummary: () => api.get<DashboardSummaryResponse>("/api/dashboard/summary"),
};

export const DASHBOARD_QUERY_KEY = ["dashboard", "summary"] as const;

export function useDashboardSummary() {
  return useQuery({
    queryKey: DASHBOARD_QUERY_KEY,
    queryFn: dashboardService.getSummary,
  });
}
