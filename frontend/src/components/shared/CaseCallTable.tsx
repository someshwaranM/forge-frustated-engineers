import React, { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ComplianceCase, CallRecord, SeverityLevel, CaseStatus } from "../../types";
import { SeverityBadge } from "./SeverityBadge";
import { cn } from "../../lib/utils";
import {
  Search,
  Filter,
  ArrowRight,
  Phone,
  ShieldAlert,
  Calendar,
  CheckCircle2,
  Clock,
} from "lucide-react";

interface CaseCallTableProps {
  type: "cases" | "calls";
  casesData?: ComplianceCase[];
  callsData?: CallRecord[];
  onStatusChange?: (caseId: string, newStatus: CaseStatus) => void;
  className?: string;
}

export const CaseCallTable: React.FC<CaseCallTableProps> = ({
  type,
  casesData = [],
  callsData = [],
  onStatusChange,
  className,
}) => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState(searchParams.get("search") || "");
  const [selectedSeverity, setSelectedSeverity] = useState<string>("ALL");
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");

  useEffect(() => {
    const q = searchParams.get("search");
    if (q !== null && q !== undefined) {
      setSearchQuery(q);
    }
  }, [searchParams]);

  // Filtering for Cases
  const filteredCases = casesData.filter((item) => {
    const matchesSearch =
      item.case_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.rm_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.customer_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (item.finding?.category || "").toLowerCase().includes(searchQuery.toLowerCase());

    const matchesSeverity =
      selectedSeverity === "ALL" ||
      item.finding?.severity === selectedSeverity;

    const matchesStatus =
      selectedStatus === "ALL" || item.status === selectedStatus;

    return matchesSearch && matchesSeverity && matchesStatus;
  });

  // Filtering for Calls
  const filteredCalls = callsData.filter((item) => {
    const matchesSearch =
      item.call_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.rm_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.customer_name.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesSeverity =
      selectedSeverity === "ALL" ||
      (selectedSeverity === "CLEAN" && !item.has_violation) ||
      item.severity === selectedSeverity;

    const matchesStatus =
      selectedStatus === "ALL" || item.processing_status === selectedStatus;

    return matchesSearch && matchesSeverity && matchesStatus;
  });

  return (
    <div
      className={cn(
        "bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg shadow-sm overflow-hidden",
        className
      )}
    >
      {/* Table Toolbar & Filters */}
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-3 bg-slate-50/50 dark:bg-slate-950/20">
        <div className="relative min-w-[280px] flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder={
              type === "cases"
                ? "Search case ID, RM, customer, or violation..."
                : "Search call ID, RM, or customer..."
            }
            value={searchQuery}
            onChange={(e) => {
              const val = e.target.value;
              setSearchQuery(val);
              if (val) {
                setSearchParams({ search: val }, { replace: true });
              } else {
                setSearchParams({}, { replace: true });
              }
            }}
            className="w-full pl-9 pr-4 py-2 text-sm bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-md focus:outline-none focus:ring-1 focus:ring-slate-400 dark:focus:ring-slate-600 placeholder:text-slate-400"
          />
        </div>

        <div className="flex items-center gap-2.5">
          {/* Severity Filter */}
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Filter className="w-3.5 h-3.5" />
            <span>Severity:</span>
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="px-2 py-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded text-xs text-slate-800 dark:text-slate-200 focus:outline-none"
            >
              <option value="ALL">All Severities</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
              {type === "calls" && <option value="CLEAN">Clean (No Flag)</option>}
            </select>
          </div>

          {/* Status Filter (strictly OPEN | RESOLVED for cases) */}
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <span>Status:</span>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="px-2 py-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded text-xs text-slate-800 dark:text-slate-200 focus:outline-none"
            >
              {type === "cases" ? (
                <>
                  <option value="ALL">All (Open & Resolved)</option>
                  <option value="OPEN">Open Only</option>
                  <option value="RESOLVED">Resolved Only</option>
                </>
              ) : (
                <>
                  <option value="ALL">All Pipelines</option>
                  <option value="DETECTED">Detected</option>
                  <option value="INDEXED">Indexed</option>
                  <option value="TRANSCRIBED">Transcribed</option>
                  <option value="INGESTED">Ingested</option>
                </>
              )}
            </select>
          </div>
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 dark:bg-slate-950/60 border-b border-slate-200 dark:border-slate-800 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            {type === "cases" ? (
              <tr>
                <th className="py-3 px-4">Case ID</th>
                <th className="py-3 px-4">RM</th>
                <th className="py-3 px-4">Customer</th>
                <th className="py-3 px-4">Violation Category</th>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">Confidence</th>
                <th className="py-3 px-4">Date Opened</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            ) : (
              <tr>
                <th className="py-3 px-4">Call ID</th>
                <th className="py-3 px-4">RM</th>
                <th className="py-3 px-4">Customer</th>
                <th className="py-3 px-4">Duration</th>
                <th className="py-3 px-4">Date / Time</th>
                <th className="py-3 px-4">Pipeline Status</th>
                <th className="py-3 px-4">Findings</th>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            )}
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
            {type === "cases" ? (
              filteredCases.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-center py-8 text-slate-500 text-sm">
                    No compliance cases match the current filter criteria.
                  </td>
                </tr>
              ) : (
                filteredCases.map((c) => {
                  const isOpen = c.status === "OPEN";
                  const confidence = c.finding
                    ? Math.round(
                        c.finding.confidence <= 1
                          ? c.finding.confidence * 100
                          : c.finding.confidence
                      )
                    : 0;

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
                        {c.finding?.category || "General Finding"}
                      </td>
                      <td className="py-3 px-4">
                        <SeverityBadge severity={c.finding?.severity} size="sm" />
                      </td>
                      <td className="py-3 px-4 font-mono text-xs text-slate-600 dark:text-slate-400">
                        {confidence}%
                      </td>
                      <td className="py-3 px-4 font-mono text-xs text-slate-500">
                        {c.opened_at}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono tracking-wider",
                            isOpen
                              ? "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-800"
                              : "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800"
                          )}
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
                })
              )
            ) : filteredCalls.length === 0 ? (
              <tr>
                <td colSpan={9} className="text-center py-8 text-slate-500 text-sm">
                  No call records match the current filter criteria.
                </td>
              </tr>
            ) : (
              filteredCalls.map((call) => (
                <tr
                  key={call.call_id}
                  onClick={() => navigate(`/calls/${call.call_id}`)}
                  className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 cursor-pointer transition-colors"
                >
                  <td className="py-3 px-4 font-mono font-medium text-slate-900 dark:text-slate-100">
                    <div className="flex items-center gap-2">
                      <Phone className="w-3.5 h-3.5 text-slate-400" />
                      <span>{call.call_id}</span>
                    </div>
                  </td>
                  <td className="py-3 px-4 font-medium text-slate-800 dark:text-slate-200">
                    {call.rm_name}
                  </td>
                  <td className="py-3 px-4 text-slate-600 dark:text-slate-400">
                    {call.customer_name}
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-slate-600 dark:text-slate-400">
                    {call.duration}
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-slate-500">
                    {call.date_time}
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={cn(
                        "inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-medium",
                        call.processing_status === "DETECTED" &&
                          "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800",
                        call.processing_status === "INDEXED" &&
                          "bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400 border border-blue-200 dark:border-blue-800",
                        call.processing_status === "TRANSCRIBED" &&
                          "bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-400 border border-purple-200 dark:border-purple-800",
                        call.processing_status === "INGESTED" &&
                          "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400 border border-slate-200 dark:border-slate-700"
                      )}
                    >
                      {call.processing_status}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    {call.finding_count > 0 ? (
                      <span className="inline-flex items-center gap-1 font-mono text-xs font-semibold text-red-700 dark:text-red-400">
                        <ShieldAlert className="w-3.5 h-3.5" />
                        {call.finding_count} Flagged
                      </span>
                    ) : (
                      <span className="font-mono text-xs text-slate-500">0 Clean</span>
                    )}
                  </td>
                  <td className="py-3 px-4">
                    <SeverityBadge severity={call.severity} size="sm" />
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100">
                      Transcript <ArrowRight className="w-3.5 h-3.5" />
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
