import React, { useState } from "react";
import { ComplianceFinding } from "../../types";
import { SeverityBadge } from "./SeverityBadge";
import { cn } from "../../lib/utils";
import {
  ShieldAlert,
  FileText,
  UserCheck,
  Briefcase,
  Sparkles,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";

interface EvidenceChainPanelProps {
  finding: ComplianceFinding;
  className?: string;
}

export const EvidenceChainPanel: React.FC<EvidenceChainPanelProps> = ({
  finding,
  className,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const confidencePercent = Math.round(
    finding.confidence <= 1 ? finding.confidence * 100 : finding.confidence
  );

  const rawClause = finding.regulation_clause_text?.trim() || "";
  const isLong = rawClause.length > 350;
  const displayClause = isLong && !isExpanded ? `${rawClause.slice(0, 350)}...` : rawClause;

  return (
    <div
      className={cn(
        "bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm space-y-5",
        className
      )}
    >
      <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-red-600 dark:text-red-400" />
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            Compliance Evidence Chain
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Model Confidence:</span>
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800">
            {confidencePercent}%
          </span>
        </div>
      </div>

      {/* Chain Step 1: Violation & Severity */}
      <div className="relative pl-6 before:absolute before:left-2 before:top-2 before:bottom-0 before:w-0.5 before:bg-slate-200 dark:before:bg-slate-800">
        <div className="absolute left-0 top-1 w-4 h-4 rounded-full bg-red-600 border-2 border-white dark:border-slate-900 flex items-center justify-center text-[9px] text-white font-bold">
          1
        </div>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Primary Finding
            </span>
            <SeverityBadge severity={finding.severity} size="sm" />
          </div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
            {finding.category}
          </h3>
          <div className="inline-flex items-center gap-2 font-mono text-xs text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded">
            <span>Timestamp Window:</span>
            <strong className="text-slate-900 dark:text-slate-200">
              {finding.timestamp_start} — {finding.timestamp_end}
            </strong>
          </div>
        </div>
      </div>

      {/* Chain Step 2: Risk Profile Mismatch */}
      <div className="relative pl-6 before:absolute before:left-2 before:top-2 before:bottom-0 before:w-0.5 before:bg-slate-200 dark:before:bg-slate-800">
        <div className="absolute left-0 top-1 w-4 h-4 rounded-full bg-amber-500 border-2 border-white dark:border-slate-900 flex items-center justify-center text-[9px] text-white font-bold">
          2
        </div>
        <div className="space-y-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Client Suitability Context
          </span>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
            <div className="p-2.5 rounded border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40">
              <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400 font-medium mb-1">
                <UserCheck className="w-3.5 h-3.5 text-blue-500" />
                Customer Risk Profile
              </div>
              <p className="font-semibold text-slate-900 dark:text-slate-200">
                {finding.customer_risk_profile}
              </p>
            </div>
            <div className="p-2.5 rounded border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40">
              <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400 font-medium mb-1">
                <Briefcase className="w-3.5 h-3.5 text-amber-500" />
                Product Risk Class
              </div>
              <p className="font-semibold text-slate-900 dark:text-slate-200">
                {finding.product_risk_class}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Chain Step 3: Statutory Regulation Citation */}
      <div className="relative pl-6 before:absolute before:left-2 before:top-2 before:bottom-0 before:w-0.5 before:bg-slate-200 dark:before:bg-slate-800">
        <div className="absolute left-0 top-1 w-4 h-4 rounded-full bg-blue-600 border-2 border-white dark:border-slate-900 flex items-center justify-center text-[9px] text-white font-bold">
          3
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Regulatory Corpus Match
            </span>
            <div className="flex items-center gap-1.5 font-mono text-xs text-blue-600 dark:text-blue-400">
              <FileText className="w-3 h-3" />
              <span>{finding.regulation_citation_label || finding.regulation_id || "Statutory Clause"}</span>
              {finding.regulation_source_url && (
                <a
                  href={finding.regulation_source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors ml-0.5"
                  title="Open source regulatory PDF"
                >
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          </div>
          <div className="p-3 bg-blue-50/50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900/60 rounded text-xs leading-relaxed text-slate-800 dark:text-slate-300 font-serif italic whitespace-pre-line max-h-96 overflow-y-auto">
            {displayClause ? (
              <>
                &ldquo;{displayClause}&rdquo;
                {isLong && (
                  <button
                    type="button"
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="mt-2.5 inline-flex items-center not-italic font-sans text-[11px] font-semibold text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 transition-colors cursor-pointer"
                  >
                    {isExpanded ? "Collapse statutory clause" : "Read full statutory clause"}
                  </button>
                )}
              </>
            ) : (
              <span className="text-slate-500 dark:text-slate-400 not-italic font-sans">
                Statutory requirement indexed under {finding.regulation_citation_label || finding.regulation_id || "regulatory framework"}.
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Chain Step 4: AI Reasoning */}
      <div className="relative pl-6 before:absolute before:left-2 before:top-2 before:bottom-0 before:w-0.5 before:bg-slate-200 dark:before:bg-slate-800">
        <div className="absolute left-0 top-1 w-4 h-4 rounded-full bg-purple-600 border-2 border-white dark:border-slate-900 flex items-center justify-center text-[9px] text-white font-bold">
          4
        </div>
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
            <Sparkles className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400" />
            AI Auditor Reasoning
          </div>
          <p className="text-xs leading-relaxed text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-950/40 p-3 rounded border border-slate-200 dark:border-slate-800">
            {finding.reasoning}
          </p>
        </div>
      </div>

      {/* Chain Step 5: Recommended Action */}
      <div className="relative pl-6">
        <div className="absolute left-0 top-1 w-4 h-4 rounded-full bg-emerald-600 border-2 border-white dark:border-slate-900 flex items-center justify-center text-[9px] text-white font-bold">
          5
        </div>
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            Recommended Audit Action
          </div>
          <div className="text-xs leading-relaxed text-slate-800 dark:text-slate-200 bg-emerald-50/70 dark:bg-emerald-950/30 p-3 rounded border border-emerald-200 dark:border-emerald-800 font-medium">
            {finding.recommended_action}
          </div>
        </div>
      </div>
    </div>
  );
};
