// frontend/src/services/chatService.ts
import { useMutation } from "@tanstack/react-query";
import { api } from "./api";

export interface GroundedResultItem {
  type: string;
  id: string;
}

export interface ChatResponse {
  session_id: string;
  response_text: string;
  grounded_results: GroundedResultItem[];
  tool_calls_made: string[];
  provider_used: string;
}

export interface SendMessagePayload {
  session_id: string;
  message: string;
}

export const chatService = {
  sendMessage: (payload: SendMessagePayload) =>
    api.post<ChatResponse>("/api/chat", payload),

  resetSession: (sessionId: string) =>
    api.delete<any>(`/api/chat/sessions/${sessionId}`),
};

export function useSendChatMessage() {
  return useMutation({
    mutationFn: (payload: SendMessagePayload) =>
      chatService.sendMessage(payload),
  });
}
