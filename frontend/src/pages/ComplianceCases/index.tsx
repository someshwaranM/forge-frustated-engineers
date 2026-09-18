import React, { useState } from "react";
import { useCasesList, useUpdateCaseStatus } from "../../services/casesService";
import { CaseCallTable } from "../../components/shared/CaseCallTable";
import { LoadingState } from "../../components/shared/LoadingState";
import { ErrorState } from "../../components/shared/ErrorState";
import { ComplianceCase, CaseStatus } from "../../types";
import { ShieldAlert, CheckCircle2, Clock, AlertTriangle } from "lucide-react";

export const ComplianceCases: React.FC = () => {
  const { data, isLoading, isError, error, refetch } = useCasesList({ limit: 100 });
  const updateStatusMutation = useUpdateCaseStatus();
  const [feedbackNotice, setFeedbackNotice] = useState<{ message: string; type: "success" | "conflict" } | null>(null);

  const handleStatusChange = (caseId: string, targetStatus: CaseStatus) => {
    // If targetStatus is RESOLVED, perform mark_reviewed
    const action = targetStatus === "RESOLVED" ? "mark_reviewed" : "mark_reviewed";

    updateStatusMutation.mutate(
      {
        caseId,
        payload: {
          reviewer_id: "REV001",
          action: "mark_reviewed",
          notes: "Toggled from Compliance Case Management table",
        },
      },
      {
        onSuccess: () => {
          setFeedbackNotice({
            message: `Case ${caseId} successfully marked as reviewed and resolved.`,
            type: "success",
          });
          setTimeout(() => setFeedbackNotice(null), 4000);
        },
        onError: (err: any) => {
          const isConflict = err?.status === 409 || err?.isConflict;
          const msg = isConflict
            ? `Idempotency Guardrail: Case ${caseId} has already been resolved or closed.`
            : `Failed to update status: ${err?.message || "Server error"}`;
          setFeedbackNotice({
            message: msg,
            type: "conflict",
          });
          setTimeout(() => setFeedbackNotice(null), 5000);
        },
      }
    );
  };

  if (isLoading) {
    return <LoadingState message="Fetching compliance audit worklist from MySQL & Elasticsearch..." />;
  }

  if (isError || !data) {
    return (
      <ErrorState
        title="Failed to Load Cases"
        message={error instanceof Error ? error.message : "Compliance case database unreachable"}
        onRetry={() => refetch()}
      />
    );
  }

  const cases: ComplianceCase[] = (data.items || []).map((c: any) => ({
    case_id: c.case_id,
    finding_id: c.finding_id,
    call_id: c.call_id,
    rm_id: c.rm_id,
    rm_name: c.rm_name || `RM ${c.rm_id}`,
    customer_id: c.customer_id,
    customer_name: c.customer_name || `Customer ${c.customer_id}`,
    status: c.status as CaseStatus,
    priority: (c.severity === "HIGH" ? "HIGH" : c.severity === "MEDIUM" ? "MEDIUM" : "LOW") as any,
    opened_at: c.created_at || "",
    closed_at: c.status === "RESOLVED" ? (c.updated_at || "Resolved") : undefined,
    finding: {
      finding_id: c.finding_id,
      call_id: c.call_id,
      category: c.category,
      severity: c.severity,
      timestamp_start: "01:24",
      timestamp_end: "01:42",
      transcript_evidence: "",
      customer_risk_profile: "",
      product_risk_class: "",
      regulation_id: c.regulation_citation_label || "",
      reasoning: "",
      confidence: c.confidence ?? 0.85,
      recommended_action: "",
    },
  }));

  const openCount = cases.filter((c) => c.status === "OPEN").length;
  const resolvedCount = cases.filter((c) => c.status === "RESOLVED").length;

  return (
    <div className="space-y-5">
      {/* Feedback Banner */}
      {feedbackNotice && (
        <div
          className={`p-3 rounded-md text-xs font-mono flex items-center gap-2 border shadow-sm transition-all ${
            feedbackNotice.type === "conflict"
              ? "bg-amber-50 text-amber-900 border-amber-300 dark:bg-amber-950/50 dark:text-amber-200 dark:border-amber-800"
              : "bg-emerald-50 text-emerald-900 border-emerald-300 dark:bg-emerald-950/50 dark:text-emerald-200 dark:border-emerald-800"
          }`}
        >
          {feedbackNotice.type === "conflict" ? (
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          )}
          <span>{feedbackNotice.message}</span>
        </div>
      )}

      {/* Page Title & Status Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-red-600 dark:text-red-400" />
            Compliance Case Management
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Active audit worklist of flagged calls requiring compliance officer triage and resolution
          </p>
        </div>

        {/* Counter Summary (Strictly Open and Resolved) */}
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-900/60 font-semibold shadow-sm">
            <Clock className="w-3.5 h-3.5 text-amber-600" />
            {openCount} Open Cases
          </span>
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900/60 font-semibold shadow-sm">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            {resolvedCount} Resolved
          </span>
        </div>
      </div>

      {/* Shared Table Component configured for Cases */}
      <CaseCallTable
        type="cases"
        casesData={cases}
        onStatusChange={handleStatusChange}
      />
    </div>
  );
};
