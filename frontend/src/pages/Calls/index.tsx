import React from "react";
import { useCallsList } from "../../services/callsService";
import { CaseCallTable } from "../../components/shared/CaseCallTable";
import { LoadingState } from "../../components/shared/LoadingState";
import { ErrorState } from "../../components/shared/ErrorState";
import { CallRecord } from "../../types";
import { PhoneCall } from "lucide-react";

export const Calls: React.FC = () => {
  const { data, isLoading, isError, error, refetch } = useCallsList({ limit: 100 });

  if (isLoading) {
    return <LoadingState message="Querying acoustic call records from Elasticsearch..." />;
  }

  if (isError || !data) {
    return (
      <ErrorState
        title="Failed to Load Call Records"
        message={error instanceof Error ? error.message : "Elasticsearch calls index unreachable."}
        onRetry={() => refetch()}
      />
    );
  }

  const callsData: CallRecord[] = (data.items || []).map((c: any) => ({
    call_id: c.call_id,
    rm_id: c.rm_id || "RM001",
    rm_name: c.rm_name || `RM ${c.rm_id}`,
    customer_id: c.customer_id || "CUST001",
    customer_name: c.customer_name || `Customer ${c.customer_id}`,
    duration: c.duration || (c.duration_seconds ? `${Math.floor(c.duration_seconds / 60)}:${String(Math.floor(c.duration_seconds % 60)).padStart(2, "0")}` : "02:15"),
    duration_seconds: c.duration_seconds || 135,
    date_time: c.date_time || "",
    processing_status: (c.processing_status as any) || "INGESTED",
    has_violation: Boolean(c.has_violation),
    finding_count: c.finding_count || (c.findings ? c.findings.length : (c.has_violation ? 1 : 0)),
    severity: c.findings?.[0]?.severity || (c.has_violation ? "HIGH" : undefined),
    case_id: c.case_id || (c.findings?.[0]?.finding_id ? `CASE-${c.findings[0].finding_id}` : undefined),
  }));

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <PhoneCall className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            Processed Call Records
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Complete surveillance archive across both clean and flagged customer interactions
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-slate-600 dark:text-slate-400 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-3 py-1.5 rounded shadow-sm">
            Total Calls Ingested: <strong className="text-slate-900 dark:text-slate-100">{data.total}</strong>
          </span>
        </div>
      </div>

      {/* Shared Table Component configured for Calls */}
      <CaseCallTable type="calls" callsData={callsData} />
    </div>
  );
};
