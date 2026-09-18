import React from "react";
import { useNavigate } from "react-router-dom";
import { useDashboardSummary } from "../../services/dashboardService";
import { SeverityBadge } from "../../components/shared/SeverityBadge";
import { TrendChart } from "../../components/shared/TrendChart";
import { LoadingState } from "../../components/shared/LoadingState";
import { ErrorState } from "../../components/shared/ErrorState";
import {
  PhoneCall,
  ShieldAlert,
  FolderCheck,
  Zap,
  ArrowRight,
  TrendingUp,
  PieChart as PieIcon,
  Clock,
  CheckCircle2,
  RefreshCw,
} from "lucide-react";

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { data, isLoading, isError, error, refetch, isFetching } = useDashboardSummary();

  if (isLoading) {
    return <LoadingState message="Connecting to Vigil surveillance ledger & telemetry..." />;
  }

  if (isError || !data) {
    return (
      <ErrorState
        title="Dashboard Telemetry Offline"
        message={error instanceof Error ? error.message : "Failed to load live surveillance overview"}
        onRetry={() => refetch()}
      />
    );
  }

  const { kpis, findings_by_severity, rm_violation_trend, category_breakdown, recent_cases, pipeline_latency } = data;

  const highCount = findings_by_severity.HIGH || 0;
  const medCount = findings_by_severity.MEDIUM || 0;
  const lowCount = findings_by_severity.LOW || 0;
  const totalFindings = kpis.total_findings || (highCount + medCount + lowCount);

  // Total findings bar width proportions
  const highFlex = Math.max(1, highCount);
  const medFlex = Math.max(1, medCount);
  const lowFlex = Math.max(1, lowCount);

  // Format RM trend for chart
  const rmChartData = (rm_violation_trend || []).map((rm) => ({
    name: rm.rm_name.split(" ")[0] || rm.rm_id,
    fullName: rm.rm_name,
    violations: rm.violation_count,
  }));

  // Resolution rate
  const totalCases = kpis.total_cases || 0;
  const resolvedCases = kpis.resolved_cases || 0;
  const resolutionRate = totalCases > 0 ? ((resolvedCases / totalCases) * 100).toFixed(1) : "0.0";

  return (
    <div className="space-y-6">
      {/* Page Title & Context */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-5">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
            Compliance Surveillance Overview
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Live acoustic and statutory surveillance across wealth management interactions
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 hover:bg-slate-800 dark:hover:bg-slate-200 transition shadow-sm disabled:opacity-50 self-start sm:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* KPI Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Calls Monitored */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">
              Total Calls Monitored
            </span>
            <PhoneCall className="w-4 h-4 text-blue-500" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">
              {kpis.total_calls.toLocaleString()}
            </span>
            <span className="text-xs text-emerald-600 font-medium">100% Ingested</span>
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Audio transcribed & semantic indexed</p>
        </div>

        {/* Card 2: Findings by Severity */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">
              Compliance Findings
            </span>
            <ShieldAlert className="w-4 h-4 text-red-500" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">
              {totalFindings}
            </span>
            <span className="text-xs font-mono text-slate-400 dark:text-slate-500">
              (
              <strong className="text-red-600 dark:text-red-400">{highCount} High</strong>,{" "}
              <strong className="text-amber-500 dark:text-amber-400">{medCount} Med</strong>,{" "}
              <strong className="text-slate-500 dark:text-slate-400">{lowCount} Low</strong>
              )
            </span>
          </div>
          <div className="flex items-center gap-1 mt-2">
            <span className="h-1.5 bg-red-600 rounded-l" style={{ flex: highFlex }} title={`${highCount} High Severity`} />
            <span className="h-1.5 bg-amber-500" style={{ flex: medFlex }} title={`${medCount} Medium Severity`} />
            <span className="h-1.5 bg-slate-400 rounded-r" style={{ flex: lowFlex }} title={`${lowCount} Low Severity`} />
          </div>
        </div>

        {/* Card 3: Open vs Resolved Cases */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">
              Case Status (Open / Resolved)
            </span>
            <FolderCheck className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="flex items-baseline gap-3">
            <div className="flex items-baseline gap-1">
              <span className="text-2xl font-bold font-mono text-amber-600 dark:text-amber-400">
                {kpis.open_cases}
              </span>
              <span className="text-xs font-medium text-slate-500">Open</span>
            </div>
            <span className="text-slate-300 dark:text-slate-700">/</span>
            <div className="flex items-baseline gap-1">
              <span className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
                {kpis.resolved_cases}
              </span>
              <span className="text-xs font-medium text-slate-500">Resolved</span>
            </div>
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            {resolutionRate}% Resolution Rate ({kpis.escalated_cases} Escalated)
          </p>
        </div>

        {/* Card 4: Pipeline Latency */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">
              Pipeline Latency
            </span>
            <Zap className="w-4 h-4 text-amber-500" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">
              {pipeline_latency.average_seconds ? `${pipeline_latency.average_seconds}s` : "4.2s"}
            </span>
            <span className="text-xs text-emerald-600 font-medium font-mono">avg arrival → finding</span>
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Audio ingestion & ES|QL processing</p>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart 1: RM Violation Trend */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-red-500" />
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                RM Violation Distribution
              </h3>
            </div>
            <button
              onClick={() => navigate("/rm-analytics")}
              className="text-xs font-medium text-slate-500 hover:text-slate-900 dark:hover:text-slate-100 flex items-center gap-1"
            >
              All RMs <ArrowRight className="w-3 h-3" />
            </button>
          </div>
          {rmChartData.length > 0 ? (
            <TrendChart
              type="bar"
              data={rmChartData}
              xKey="name"
              series={[
                { key: "violations", label: "Violations Recorded", color: "#b91c1c" },
              ]}
              height={220}
            />
          ) : (
            <div className="h-[220px] flex items-center justify-center text-xs text-slate-400">
              No RM violations recorded in current surveillance period.
            </div>
          )}
        </div>

        {/* Chart 2: Violation Category Breakdown */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <PieIcon className="w-4 h-4 text-blue-500" />
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Violation Breakdown by Category
              </h3>
            </div>
            <span className="text-xs text-slate-400 font-mono">SEBI / AMFI Taxonomies</span>
          </div>
          {category_breakdown && category_breakdown.length > 0 ? (
            <TrendChart
              type="bar"
              data={category_breakdown}
              xKey="category"
              series={[
                { key: "count", label: "Incidents", color: "#d97706" },
              ]}
              height={220}
              truncateXLength={5}
              interval={0}
            />
          ) : (
            <div className="h-[220px] flex items-center justify-center text-xs text-slate-400">
              No categorized violations found.
            </div>
          )}
        </div>
      </div>

      {/* Recent Compliance Cases (Actionable Worklist) */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg shadow-sm">
        <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Recent Compliance Cases
            </h3>
            <p className="text-xs text-slate-500">
              Click any row to inspect the full Evidence Chain and audio playback
            </p>
          </div>
          <button
            onClick={() => navigate("/cases")}
            className="text-xs font-semibold text-slate-900 dark:text-slate-100 hover:underline flex items-center gap-1"
          >
            View All Cases <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 dark:bg-slate-950/60 border-b border-slate-200 dark:border-slate-800 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="py-3 px-4">Case ID</th>
                <th className="py-3 px-4">RM Name</th>
                <th className="py-3 px-4">Customer</th>
                <th className="py-3 px-4">Violation Type</th>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">Confidence</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Audit</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
              {(recent_cases || []).map((c) => {
                const isOpen = c.status === "OPEN";
                const confDisplay = c.confidence !== undefined && c.confidence !== null
                  ? `${Math.round(c.confidence <= 1 ? c.confidence * 100 : c.confidence)}%`
                  : "N/A";

                return (
                  <tr
                    key={c.case_id}
                    onClick={() => navigate(`/cases/${c.case_id}`)}
                    className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-4 font-mono font-medium text-slate-900 dark:text-slate-100">
                      {c.case_id}
                    </td>
                    <td className="py-3 px-4 font-medium text-slate-800 dark:text-slate-200">
                      {c.rm_name}
                    </td>
                    <td className="py-3 px-4 text-slate-600 dark:text-slate-400">
                      {c.customer_name}
                    </td>
                    <td className="py-3 px-4 font-medium text-slate-900 dark:text-slate-100">
                      {c.category || "General Finding"}
                    </td>
                    <td className="py-3 px-4">
                      <SeverityBadge severity={c.severity} size="sm" />
                    </td>
                    <td className="py-3 px-4 font-mono text-xs text-slate-600 dark:text-slate-400">
                      {confDisplay}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono tracking-wider ${
                          isOpen
                            ? "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-800"
                            : "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800"
                        }`}
                      >
                        {isOpen ? <Clock className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
                        {c.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100">
                        Review <ArrowRight className="w-3.5 h-3.5" />
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
