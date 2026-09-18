// frontend/src/services/casesService.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "./api";
import { DASHBOARD_QUERY_KEY } from "./dashboardService";

export interface CasesListParams {
  status?: string;
  severity?: string;
  rm_id?: string;
  category?: string;
  limit?: number;
  offset?: number;
}

export interface CaseStatusUpdatePayload {
  reviewer_id: string;
  action: "mark_reviewed" | "dismiss";
  notes?: string;
}

export interface CaseEscalatePayload {
  reviewer_id: string;
  notes?: string;
}

export interface CaseAssignPayload {
  reviewer_id: string;
  assignee_reviewer_id: string;
}

export interface CaseNotePayload {
  reviewer_id: string;
  note_text: string;
}

export interface CaseDetailResponse {
  case: {
    case_id: string;
    finding_id: string;
    call_id: string;
    rm_id: string;
    rm_name: string;
    rm_branch?: string;
    customer_id: string;
    customer_name: string;
    customer_risk_profile?: string;
    customer_investment_experience?: string;
    category: string;
    severity: "HIGH" | "MEDIUM" | "LOW";
    status: "OPEN" | "RESOLVED";
    resolution_type?: string;
    escalated: boolean;
    assigned_to?: string;
    assignee_name?: string;
    assignee_role?: string;
    resolution_notes?: string;
    created_at: string;
    updated_at?: string;
  };
  finding: any;
  call: any;
  activity_log: Array<{
    log_id: number;
    case_id: string;
    action: string;
    actor: string;
    actor_name?: string;
    actor_role?: string;
    details?: string;
    timestamp: string;
  }>;
  confidence?: number;
  confidence_threshold: number;
  needs_review: boolean;
}

export interface CasesListResponse {
  total: number;
  confidence_threshold: number;
  items: any[];
}

export const casesService = {
  listCases: (params?: CasesListParams) =>
    api.get<CasesListResponse>("/api/cases", params),

  getCase: (caseId: string) =>
    api.get<CaseDetailResponse>(`/api/cases/${caseId}`),

  updateStatus: (caseId: string, payload: CaseStatusUpdatePayload) =>
    api.patch<any>(`/api/cases/${caseId}/status`, payload),

  escalate: (caseId: string, payload: CaseEscalatePayload) =>
    api.post<any>(`/api/cases/${caseId}/escalate`, payload),

  assign: (caseId: string, payload: CaseAssignPayload) =>
    api.post<any>(`/api/cases/${caseId}/assign`, payload),

  addNote: (caseId: string, payload: CaseNotePayload) =>
    api.post<any>(`/api/cases/${caseId}/notes`, payload),
};

export const CASES_QUERY_KEYS = {
  all: ["cases"] as const,
  lists: () => [...CASES_QUERY_KEYS.all, "list"] as const,
  list: (params?: CasesListParams) => [...CASES_QUERY_KEYS.lists(), params || {}] as const,
  details: () => [...CASES_QUERY_KEYS.all, "detail"] as const,
  detail: (caseId: string) => [...CASES_QUERY_KEYS.details(), caseId] as const,
};

export function useCasesList(params?: CasesListParams) {
  return useQuery({
    queryKey: CASES_QUERY_KEYS.list(params),
    queryFn: () => casesService.listCases(params),
  });
}

export function useCaseDetail(caseId: string) {
  return useQuery({
    queryKey: CASES_QUERY_KEYS.detail(caseId),
    queryFn: () => casesService.getCase(caseId),
    enabled: Boolean(caseId),
  });
}

export function useUpdateCaseStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      caseId,
      payload,
    }: {
      caseId: string;
      payload: CaseStatusUpdatePayload;
    }) => casesService.updateStatus(caseId, payload),
    onSuccess: (_, variables) => {
      // Invalidate both broad and granular keys
      queryClient.invalidateQueries({ queryKey: CASES_QUERY_KEYS.all });
      queryClient.invalidateQueries({ queryKey: CASES_QUERY_KEYS.detail(variables.caseId) });
      queryClient.invalidateQueries({ queryKey: DASHBOARD_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: ["rm"] });
    },
  });
}

export function useEscalateCase() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      caseId,
      payload,
    }: {
      caseId: string;
      payload: CaseEscalatePayload;
    }) => casesService.escalate(caseId, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: CASES_QUERY_KEYS.all });
      queryClient.invalidateQueries({ queryKey: CASES_QUERY_KEYS.detail(variables.caseId) });
      queryClient.invalidateQueries({ queryKey: DASHBOARD_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: ["rm"] });
    },
  });
}

export function useAssignCase() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      caseId,
      payload,
    }: {
      caseId: string;
      payload: CaseAssignPayload;
    }) => casesService.assign(caseId, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: CASES_QUERY_KEYS.all });
      queryClient.invalidateQueries({ queryKey: CASES_QUERY_KEYS.detail(variables.caseId) });
    },
  });
}

export function useAddCaseNote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      caseId,
      payload,
    }: {
      caseId: string;
      payload: CaseNotePayload;
    }) => casesService.addNote(caseId, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: CASES_QUERY_KEYS.detail(variables.caseId) });
    },
  });
}
