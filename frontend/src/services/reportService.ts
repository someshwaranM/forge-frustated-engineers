// frontend/src/services/reportService.ts
// Service for generating and sending compliance report emails

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export interface SendReportRequest {
  recipients: string[];
  request_id?: string;
}

export interface SendReportResponse {
  success: boolean;
  rm_id: string;
  recipients: string[];
  sent_at: string;
  report_id: string;
  idempotent_replay?: boolean;
}

export const reportService = {
  /**
   * Dispatch RM compliance report email via backend / Elastic Kibana connector
   */
  sendRmReport: (rmId: string, payload: SendReportRequest): Promise<SendReportResponse> =>
    api.post<SendReportResponse>(`/api/rm/${rmId}/report/email`, payload),
};

export const REPORT_QUERY_KEYS = {
  all: ["reports"] as const,
  rm: (rmId: string) => [...REPORT_QUERY_KEYS.all, "rm", rmId] as const,
};

export function useSendRmReport() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ rmId, payload }: { rmId: string; payload: SendReportRequest }) =>
      reportService.sendRmReport(rmId, payload),
    onSuccess: (_, variables) => {
      // Invalidate relevant queries so UI stays fresh
      queryClient.invalidateQueries({ queryKey: ["rm", "analytics", variables.rmId] });
      queryClient.invalidateQueries({ queryKey: ["cases"] });
    },
  });
}
