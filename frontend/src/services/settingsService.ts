// frontend/src/services/settingsService.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export interface SettingsResponse {
  confidence_threshold?: number;
  active_ai_provider?: string;
  [key: string]: any;
}

export interface SettingsUpdatePayload {
  confidence_threshold?: number;
  active_ai_provider?: string;
}

export interface ProviderStatusResponse {
  total_findings_analyzed: number;
  primary_provider: {
    name: string;
    key: string;
    findings_count: number;
    status: string;
    description: string;
  };
  secondary_provider: {
    name: string;
    key: string;
    findings_count: number;
    status: string;
    description: string;
  };
  fallback_triggered: boolean;
  providers_breakdown: Array<{
    provider: string;
    key: string;
    count: number;
    active: boolean;
  }>;
}

export const settingsService = {
  getSettings: () => api.get<SettingsResponse>("/api/settings"),

  updateSettings: (payload: SettingsUpdatePayload) =>
    api.patch<SettingsResponse>("/api/settings", payload),

  getProviderStatus: () =>
    api.get<ProviderStatusResponse>("/api/settings/provider-status"),
};

export const SETTINGS_QUERY_KEYS = {
  all: ["settings"] as const,
  main: () => [...SETTINGS_QUERY_KEYS.all, "config"] as const,
  providerStatus: () => [...SETTINGS_QUERY_KEYS.all, "provider-status"] as const,
};

export function useSettings() {
  return useQuery({
    queryKey: SETTINGS_QUERY_KEYS.main(),
    queryFn: settingsService.getSettings,
  });
}

export function useProviderStatus() {
  return useQuery({
    queryKey: SETTINGS_QUERY_KEYS.providerStatus(),
    queryFn: settingsService.getProviderStatus,
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: SettingsUpdatePayload) =>
      settingsService.updateSettings(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: SETTINGS_QUERY_KEYS.all });
      queryClient.invalidateQueries({ queryKey: ["cases"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
