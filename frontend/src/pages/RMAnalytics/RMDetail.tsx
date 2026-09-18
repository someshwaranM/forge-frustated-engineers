import React from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useRMAnalytics } from "../../services/rmService";
import { TrendChart } from "../../components/shared/TrendChart";
import { SeverityBadge } from "../../components/shared/SeverityBadge";
import { LoadingState } from "../../components/shared/LoadingState";
import { ErrorState } from "../../components/shared/ErrorState";
import {
  ArrowLeft,
  Users,
  AlertTriangle,
  Building,
  MapPin,
  TrendingDown,
  ShieldAlert,
  ArrowRight,
  ExternalLink,
  Mail,
} from "lucide-react";
import { SendReportModal } from "../../components/reports/SendReportModal";

export const RMDetail: React.FC = () => {
  const { rmId } = useParams<{ rmId: string }>();
  const navigate = useNavigate();
  const [isReportModalOpen, setIsReportModalOpen] = React.useState(false);

  const { data: analytics, isLoading, isError, error, refetch } = useRMAnalytics(rmId || "");

  if (isLoading) {
    return <LoadingState message={`Analyzing behavioral telemetry for ${rmId}...`} />;
  }

  if (isError || !analytics || !analytics.rm) {
    return (
      <ErrorState
        title="Relationship Manager Dossier Not Found"
        message={error instanceof Error ? error.message : `Unable to retrieve records for ${rmId}`}
        onRetry={() => refetch()}
      />
    );
  }

  const { rm, total_calls, total_cases, open_cases, resolved_cases, escalated_cases, has_repeat_violations, repeat_categories, category_breakdown, severity_breakdown, recent_cases } = analytics;

  const highCount = severity_breakdown.find((s: any) => s.severity === "HIGH")?.count || 0;
  const medCount = severity_breakdown.find((s: any) => s.severity === "MEDIUM")?.count || 0;
  const lowCount = severity_breakdown.find((s: any) => s.severity === "LOW")?.count || 0;

  const riskScore = Math.min(100, (highCount * 30) + (medCount * 15) + (lowCount * 5) + (has_repeat_violations ? 25 : 0));
  const primaryRepeatCat = repeat_categories?.[0]?.category || (has_repeat_violations ? "Multiple Category Infractions" : null);

  // Derive region from branch
  const branch = rm.branch || "Mumbai Branch";
  const region = branch.includes("Mumbai") || branch.includes("Pune") ? "West Region" : branch.includes("Bengaluru") ? "South Region" : "North Region";

  return (
    <div className="space-y-6">
      {/* Top Bar: Back link and Action Button */}
      <div className="flex items-center justify-between gap-4">
        <button
          onClick={() => navigate("/rm-analytics")}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to RM Analytics Roster
        </button>

        <button
          type="button"
          onClick={() => setIsReportModalOpen(true)}
          className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-sm transition-colors cursor-pointer"
        >
          <Mail className="w-4 h-4" />
          Send Report on Mail
        </button>
      </div>

      {/* Header Profile Card */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 flex items-center justify-center font-bold text-lg">
              {rm.full_name.split(" ").map((n: string) => n[0]).join("")}
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                  {rm.full_name}
                </h1>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                  {rm.rm_id}
                </span>
                {has_repeat_violations && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-700 dark:bg-red-950/60 dark:text-red-400 border border-red-200 dark:border-red-900">
                    <AlertTriangle className="w-3 h-3" />
                    Repeat Violation Flag
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4 text-xs text-slate-500 mt-1">
                <span className="flex items-center gap-1">
                  <Building className="w-3.5 h-3.5" />
                  {branch}
                </span>
                <span className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5" />
                  {region}
                </span>
                <span>Reporting Manager: Suresh Patel (Branch Head)</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="text-right">
              <span className="text-[11px] uppercase font-semibold text-slate-400">
                Composite Risk Score
              </span>
              <p className="text-2xl font-mono font-bold text-red-600 dark:text-red-400">
                {riskScore} / 100
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Repeat Violation Signal Warning */}
      {has_repeat_violations && (
        <div className="p-4 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900/60 rounded-lg">
          <div className="flex items-center gap-2 text-red-900 dark:text-red-300 font-bold text-sm mb-1">
            <AlertTriangle className="w-4 h-4 text-red-600" />
            Repeat Statutory Violation Signal: {primaryRepeatCat}
          </div>
          <p className="text-xs text-red-800 dark:text-red-400">
            Acoustic transcripts demonstrate systemic pattern of repeat statutory non-compliance. Flagged for priority supervisory review and branch surveillance audit.
          </p>
        </div>
      )}

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <span className="text-xs font-semibold uppercase text-slate-400">Total Monitored Calls</span>
          <p className="text-2xl font-mono font-bold text-slate-900 dark:text-slate-100 mt-1">
            {total_calls}
          </p>
        </div>
        <div className="p-4 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <span className="text-xs font-semibold uppercase text-slate-400">Total Violations</span>
          <p className="text-2xl font-mono font-bold text-red-600 dark:text-red-400 mt-1">
            {total_cases}
          </p>
        </div>
        <div className="p-4 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <span className="text-xs font-semibold uppercase text-slate-400">High Severity</span>
          <p className="text-2xl font-mono font-bold text-red-700 dark:text-red-500 mt-1">
            {highCount}
          </p>
        </div>
        <div className="p-4 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <span className="text-xs font-semibold uppercase text-slate-400">Open Cases</span>
          <p className="text-2xl font-mono font-bold text-amber-600 dark:text-amber-400 mt-1">
            {open_cases}
          </p>
        </div>
      </div>

      {/* Category Breakdown */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-1">
          Violations by Regulatory Category
        </h3>
        <p className="text-xs text-slate-500 mb-4">
          Statutory infractions detected across monitored advisory conversations
        </p>
        {category_breakdown && category_breakdown.length > 0 ? (
          <TrendChart
            type="bar"
            data={category_breakdown}
            xKey="category"
            series={[{ key: "count", label: "Infractions", color: "#b91c1c" }]}
            height={220}
          />
        ) : (
          <div className="h-32 flex items-center justify-center text-xs text-slate-400">
            No violation categories recorded for this Relationship Manager.
          </div>
        )}
      </div>

      {/* Associated Cases Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200 dark:border-slate-800">
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
            Associated Incident History ({recent_cases.length} cases)
          </h3>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 dark:bg-slate-950/60 border-b border-slate-200 dark:border-slate-800 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="py-3 px-4">Case ID</th>
                <th className="py-3 px-4">Customer ID</th>
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
              {recent_cases.map((c: any) => (
                <tr
                  key={c.case_id}
                  onClick={() => navigate(`/cases/${c.case_id}`)}
                  className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 cursor-pointer transition-colors"
                >
                  <td className="py-3 px-4 font-mono font-medium text-slate-900 dark:text-slate-100">
                    {c.case_id}
                  </td>
                  <td className="py-3 px-4 text-xs font-mono text-slate-600 dark:text-slate-400">
                    {c.customer_id}
                  </td>
                  <td className="py-3 px-4 text-xs font-medium text-slate-800 dark:text-slate-200">
                    {c.category}
                  </td>
                  <td className="py-3 px-4">
                    <SeverityBadge severity={c.severity} size="sm" />
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                      {c.status}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100">
                      Inspect <ArrowRight className="w-3.5 h-3.5" />
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* RM Compliance Report Email Modal */}
      <SendReportModal
        isOpen={isReportModalOpen}
        onClose={() => setIsReportModalOpen(false)}
        rmId={rm.rm_id}
        rmName={rm.full_name}
        rmEmail={rm.email}
      />
    </div>
  );
};

