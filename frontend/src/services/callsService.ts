// frontend/src/services/callsService.ts
import { useQuery } from "@tanstack/react-query";
import { api, API_BASE_URL } from "./api";
import { CallRecord } from "../types";

export interface CallsListParams {
  rm_id?: string;
  customer_id?: string;
  severity?: string;
  status?: string;
  has_violation?: boolean;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

export interface CallsListResponse {
  total: number;
  items: any[];
}

export const callsService = {
  listCalls: (params?: CallsListParams) =>
    api.get<CallsListResponse>("/api/calls", params),

  getCall: (callId: string) =>
    api.get<any>(`/api/calls/${callId}`),

  getAudioUrl: (callId: string) =>
    `${API_BASE_URL}/api/calls/${callId}/audio`,
};

export const CALLS_QUERY_KEYS = {
  all: ["calls"] as const,
  lists: () => [...CALLS_QUERY_KEYS.all, "list"] as const,
  list: (params?: CallsListParams) => [...CALLS_QUERY_KEYS.lists(), params || {}] as const,
  details: () => [...CALLS_QUERY_KEYS.all, "detail"] as const,
  detail: (callId: string) => [...CALLS_QUERY_KEYS.details(), callId] as const,
};

export function useCallsList(params?: CallsListParams) {
  return useQuery({
    queryKey: CALLS_QUERY_KEYS.list(params),
    queryFn: () => callsService.listCalls(params),
  });
}

export function useCallDetail(callId: string) {
  return useQuery({
    queryKey: CALLS_QUERY_KEYS.detail(callId),
    queryFn: () => callsService.getCall(callId),
    enabled: Boolean(callId),
  });
}
