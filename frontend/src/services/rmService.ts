// frontend/src/services/rmService.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { RMStats } from "../types";

export const rmService = {
  listRMs: () => api.get<any[]>("/api/rm"),

  getRMAnalytics: (rmId: string) =>
    api.get<any>(`/api/rm/${rmId}/analytics`),
};

export const RM_QUERY_KEYS = {
  all: ["rm"] as const,
  list: () => [...RM_QUERY_KEYS.all, "list"] as const,
  analytics: (rmId: string) => [...RM_QUERY_KEYS.all, "analytics", rmId] as const,
};

export function useRMList() {
  return useQuery({
    queryKey: RM_QUERY_KEYS.list(),
    queryFn: rmService.listRMs,
  });
}

export function useRMAnalytics(rmId: string) {
  return useQuery({
    queryKey: RM_QUERY_KEYS.analytics(rmId),
    queryFn: () => rmService.getRMAnalytics(rmId),
    enabled: Boolean(rmId),
  });
}
