import React from "react";
import { useNavigate } from "react-router-dom";
import { useRMList } from "../../services/rmService";
import { TrendChart } from "../../components/shared/TrendChart";
import { LoadingState } from "../../components/shared/LoadingState";
import { ErrorState } from "../../components/shared/ErrorState";
import {
  Users,
  AlertTriangle,
  ArrowRight,
  TrendingDown,
  PhoneCall,
  CheckCircle2,
} from "lucide-react";
import { cn } from "../../lib/utils";

export const RMAnalytics: React.FC = () => {
  const navigate = useNavigate();
  const { data: rmList, isLoading, isError, error, refetch } = useRMList();

  if (isLoading) {
    return <LoadingState message="Aggregating Relationship Manager behavioral telemetry..." />;
  }

  if (isError || !rmList) {
    return (
      <ErrorState
        title="Failed to Load RM Roster"
        message={error instanceof Error ? error.message : "Unable to reach RM surveillance service"}
        onRetry={() => refetch()}
      />
    );
  }

  // Find candidate for repeat violation or highest risk
  const flaggedRM =
    rmList.find((r) => r.repeat_violation_flag) ||
    rmList.find((r) => r.high_severity_count > 0) ||
    rmList[0];

  // Aggregate violations for trend display
  const totalCallsMonitored = rmList.reduce((acc, r) => acc + (r.total_calls || 0), 0);
  const totalViolationsDetected = rmList.reduce((acc, r) => acc + (r.total_violations || 0), 0);

  // Distribution chart data across the 5 RMs
  const distributionChartData = rmList.map((r) => ({
    name: r.name.split(" ")[0] || r.rm_id,
    violations: r.total_violations || 0,
    calls: r.total_calls || 0,
  }));

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Users className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            Relationship Manager Analytics
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Identify recurring behavioral patterns, repeat statutory violations, and distribution risks across RMs
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-slate-500 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-3 py-1.5 rounded shadow-sm">
            Active RMs Tracked: <strong className="text-slate-900 dark:text-slate-100">{rmList.length}</strong>
          </span>
          <span className="text-xs font-mono text-slate-500 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-3 py-1.5 rounded shadow-sm">
            Monitored Calls: <strong className="text-blue-600 dark:text-blue-400">{totalCallsMonitored}</strong>
          </span>
        </div>
      </div>

      {/* High-Risk Repeat Violations Alert Card */}
      {flaggedRM && (
        <div className="p-4 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900/60 rounded-lg flex flex-wrap items-center justify-between gap-3 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-red-600 text-white flex items-center justify-center shrink-0">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-red-950 dark:text-red-200">
                {flaggedRM.repeat_violation_flag
                  ? "Repeat Statutory Violation Signal Detected"
                  : "High Priority Surveillance Attention Flagged"}
              </h3>
              <p className="text-xs text-red-700 dark:text-red-400 mt-0.5">
                <strong>{flaggedRM.name} ({flaggedRM.rm_id})</strong> has registered{" "}
                {flaggedRM.total_violations} compliance cases ({flaggedRM.high_severity_count} HIGH severity) in {flaggedRM.branch}.
                {flaggedRM.repeat_violation_category && ` Recurring pattern: ${flaggedRM.repeat_violation_category}.`}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => navigate(`/rm-analytics/${flaggedRM.rm_id}`)}
            className="px-3 py-1.5 bg-red-600 text-white hover:bg-red-700 rounded text-xs font-semibold flex items-center gap-1 transition-colors cursor-pointer"
          >
            Inspect RM Dossier <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Aggregate Distribution Chart */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Cross-RM Incident & Call Telemetry
            </h3>
            <p className="text-xs text-slate-500">
              Recorded calls and flagged non-compliance incidents across advisory roster
            </p>
          </div>
          <span className="text-xs font-mono text-slate-500 font-semibold flex items-center gap-1">
            Total Violations: <strong className="text-red-600 dark:text-red-400">{totalViolationsDetected}</strong>
          </span>
        </div>
        <TrendChart
          type="bar"
          data={distributionChartData}
          xKey="name"
          series={[
            { key: "violations", label: "Violations Recorded", color: "#b91c1c" },
            { key: "calls", label: "Calls Monitored", color: "#3b82f6" },
          ]}
          height={200}
        />
      </div>

      {/* Per-RM Roster & Risk Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200 dark:border-slate-800">
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
            Relationship Manager Performance & Surveillance Roster
          </h3>
          <p className="text-xs text-slate-500">
            Click any RM to open detailed behavioral telemetry, repeat violation patterns, and incident history
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 dark:bg-slate-950/60 border-b border-slate-200 dark:border-slate-800 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="py-3 px-4">RM Profile</th>
                <th className="py-3 px-4">Branch / Region</th>
                <th className="py-3 px-4">Monitored Calls</th>
                <th className="py-3 px-4">Total Violations</th>
                <th className="py-3 px-4">High Severity</th>
                <th className="py-3 px-4">Repeat Pattern</th>
                <th className="py-3 px-4">Risk Index</th>
                <th className="py-3 px-4 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
              {rmList.map((rm) => (
                <tr
                  key={rm.rm_id}
                  onClick={() => navigate(`/rm-analytics/${rm.rm_id}`)}
                  className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 cursor-pointer transition-colors"
                >
                  <td className="py-3 px-4">
                    <p className="font-semibold text-slate-900 dark:text-slate-100">
                      {rm.name}
                    </p>
                    <span className="font-mono text-xs text-slate-400">
                      {rm.rm_id} • Mgr: {rm.manager_name}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-xs text-slate-600 dark:text-slate-400">
                    <p className="font-medium text-slate-800 dark:text-slate-200">
                      {rm.branch}
                    </p>
                    <span className="text-slate-500">{rm.region}</span>
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-slate-700 dark:text-slate-300">
                    {rm.total_calls}
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={cn(
                        "font-mono font-bold text-xs px-2 py-0.5 rounded",
                        rm.total_violations > 0
                          ? "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-400 border border-red-200 dark:border-red-900"
                          : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                      )}
                    >
                      {rm.total_violations}
                    </span>
                  </td>
                  <td className="py-3 px-4 font-mono text-xs font-semibold text-red-600 dark:text-red-400">
                    {rm.high_severity_count}
                  </td>
                  <td className="py-3 px-4">
                    {rm.repeat_violation_flag ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-red-700 dark:text-red-400 bg-red-100 dark:bg-red-950/50 border border-red-200 dark:border-red-900 px-2 py-0.5 rounded">
                        <AlertTriangle className="w-3 h-3" />
                        REPEAT PATTERN
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400">None detected</span>
                    )}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <div className="w-12 bg-slate-200 dark:bg-slate-700 h-2 rounded-full overflow-hidden">
                        <div
                          className={cn(
                            "h-full rounded-full",
                            rm.risk_score > 60
                              ? "bg-red-600"
                              : rm.risk_score > 30
                              ? "bg-amber-500"
                              : "bg-emerald-500"
                          )}
                          style={{ width: `${Math.min(100, Math.max(10, rm.risk_score))}%` }}
                        />
                      </div>
                      <span className="font-mono text-xs font-semibold text-slate-800 dark:text-slate-200">
                        {rm.risk_score}
                      </span>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100">
                      View Dossier <ArrowRight className="w-3.5 h-3.5" />
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
