// frontend/src/services/documentsService.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export interface DocumentItem {
  document_id: string;
  document_name: string;
  regulator: string;
  status: string;
  chunk_count: number;
  indexed_status: string;
}

export interface DocumentsResponse {
  total: number;
  items: DocumentItem[];
}

export const documentsService = {
  listDocuments: () => api.get<DocumentsResponse>("/api/documents"),
};

export const DOCUMENTS_QUERY_KEY = ["documents", "list"] as const;

export function useDocumentsList() {
  return useQuery({
    queryKey: DOCUMENTS_QUERY_KEY,
    queryFn: documentsService.listDocuments,
  });
}
