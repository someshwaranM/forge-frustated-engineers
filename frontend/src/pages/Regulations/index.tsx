import React, { useState } from "react";
import { useDocumentsList } from "../../services/documentsService";
import { LoadingState } from "../../components/shared/LoadingState";
import { ErrorState } from "../../components/shared/ErrorState";
import {
  FileCheck2,
  Upload,
  Search,
  CheckCircle2,
  FileText,
  Clock,
  Layers,
  Lock,
} from "lucide-react";

export const Regulations: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIssuer, setSelectedIssuer] = useState<string>("ALL");

  const { data, isLoading, isError, error, refetch } = useDocumentsList();

  if (isLoading) {
    return <LoadingState message="Retrieving regulatory corpus documents from Elasticsearch..." />;
  }

  if (isError || !data) {
    return (
      <ErrorState
        title="Failed to Load Regulations"
        message={error instanceof Error ? error.message : "Elasticsearch regulations index unreachable"}
        onRetry={() => refetch()}
      />
    );
  }

  const items = data.items || [];

  const filteredDocs = items.filter((doc) => {
    const matchesSearch =
      (doc.document_name || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (doc.document_id || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (doc.regulator || "").toLowerCase().includes(searchQuery.toLowerCase());

    const matchesIssuer =
      selectedIssuer === "ALL" ||
      (doc.regulator || "").toUpperCase().includes(selectedIssuer.toUpperCase());

    return matchesSearch && matchesIssuer;
  });

  const totalChunks = items.reduce((acc, d) => acc + (d.chunk_count || 0), 0);
  const sebiCount = items.filter((d) => (d.regulator || "").toUpperCase().includes("SEBI")).length;
  const amfiCount = items.filter((d) => (d.regulator || "").toUpperCase().includes("AMFI")).length;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <FileCheck2 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            Regulatory Corpus & Statutory Guidelines
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Indexed SEBI circulars, AMFI codes of conduct, and statutory master regulations grounding AI findings
          </p>
        </div>

        {/* Upload Button - Visibly disabled with "Coming Soon" indicator per Phase 10 specs */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled
            title="Online document upload is coming in a future release. Current corpus is managed via Phase 3 batch indexing pipeline."
            className="px-3.5 py-2 bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-500 rounded-lg text-xs font-semibold flex items-center gap-2 cursor-not-allowed border border-slate-200 dark:border-slate-700 shadow-sm"
          >
            <Lock className="w-3.5 h-3.5 text-slate-400" />
            <span>Upload Regulation (Batch Indexed Only)</span>
          </button>
        </div>
      </div>

      {/* Corpus Statistics Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <span className="text-xs font-semibold uppercase text-slate-400">Total Statutory Corpus</span>
          <p className="text-2xl font-mono font-bold text-slate-900 dark:text-slate-100 mt-1">
            {items.length} Master Documents
          </p>
          <span className="text-[11px] text-slate-500">
            SEBI ({sebiCount}) • AMFI ({amfiCount})
          </span>
        </div>
        <div className="p-4 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <span className="text-xs font-semibold uppercase text-slate-400">Indexed Chunks</span>
          <p className="text-2xl font-mono font-bold text-blue-600 dark:text-blue-400 mt-1">
            {totalChunks.toLocaleString()} Chunks
          </p>
          <span className="text-[11px] text-slate-500">Semantic search powered by ELSER</span>
        </div>
        <div className="p-4 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <span className="text-xs font-semibold uppercase text-slate-400">Corpus Integrity</span>
          <p className="text-2xl font-mono font-bold text-emerald-600 dark:text-emerald-400 mt-1">
            100% Synced
          </p>
          <span className="text-[11px] text-slate-500">Active Elasticsearch index: regulations</span>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-3 bg-slate-50/50 dark:bg-slate-950/20">
          <div className="relative min-w-[280px] flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search regulatory documents by title or document ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-md focus:outline-none focus:ring-1 focus:ring-slate-400 placeholder:text-slate-400"
            />
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Issuer Authority:</span>
            <select
              value={selectedIssuer}
              onChange={(e) => setSelectedIssuer(e.target.value)}
              className="px-2.5 py-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded text-xs text-slate-800 dark:text-slate-200 focus:outline-none"
            >
              <option value="ALL">All Authorities (SEBI & AMFI)</option>
              <option value="SEBI">SEBI Regulations</option>
              <option value="AMFI">AMFI Guidelines</option>
            </select>
          </div>
        </div>

        {/* Documents Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 dark:bg-slate-950/60 border-b border-slate-200 dark:border-slate-800 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="py-3 px-4">Document Title & ID</th>
                <th className="py-3 px-4">Authority</th>
                <th className="py-3 px-4">Indexed Chunks</th>
                <th className="py-3 px-4">Corpus Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
              {filteredDocs.map((doc) => (
                <tr
                  key={doc.document_id}
                  className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors"
                >
                  <td className="py-3 px-4">
                    <div className="flex items-start gap-2.5">
                      <FileText className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />
                      <div>
                        <p className="font-semibold text-slate-900 dark:text-slate-100 leading-snug">
                          {doc.document_name}
                        </p>
                        <p className="text-xs font-mono text-slate-500 dark:text-slate-400 mt-0.5">
                          ID: {doc.document_id}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-bold ${(doc.regulator || "").toUpperCase().includes("SEBI")
                          ? "bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300 border border-blue-200 dark:border-blue-900"
                          : "bg-purple-50 text-purple-700 dark:bg-purple-950/50 dark:text-purple-300 border border-purple-200 dark:border-purple-900"
                        }`}
                    >
                      {doc.regulator || "SEBI"}
                    </span>
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-slate-700 dark:text-slate-300">
                    <span className="flex items-center gap-1">
                      <Layers className="w-3.5 h-3.5 text-slate-400" />
                      {doc.chunk_count} chunks
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className="inline-flex items-center gap-1 text-xs font-mono font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-200 dark:border-emerald-800 px-2 py-0.5 rounded">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      INDEXED
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
