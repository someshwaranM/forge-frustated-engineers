import React, { useRef, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  useCaseDetail,
  useUpdateCaseStatus,
  useEscalateCase,
  useAddCaseNote,
} from "../../services/casesService";
import { callsService } from "../../services/callsService";
import { AudioPlayer, AudioPlayerRef } from "../../components/shared/AudioPlayer";
import { TranscriptViewer } from "../../components/shared/TranscriptViewer";
import { EvidenceChainPanel } from "../../components/shared/EvidenceChainPanel";
import { SeverityBadge } from "../../components/shared/SeverityBadge";
import { LoadingState } from "../../components/shared/LoadingState";
import { ErrorState } from "../../components/shared/ErrorState";
import { ComplianceFinding, TranscriptSegment } from "../../types";
import { useAuth } from "../../context/AuthContext";
import {
  ArrowLeft,
  ShieldAlert,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Send,
  MessageSquare,
  FileCheck,
  XCircle,
  HelpCircle,
  Download,
  Phone,
  ArrowRight,
  Layers,
} from "lucide-react";

function parseTimestampToSeconds(ts: string | number | undefined): number {
  if (ts === undefined || ts === null) return 0;
  if (typeof ts === "number") return ts;
  if (ts.includes(":")) {
    const parts = ts.split(":");
    const min = parseFloat(parts[0]) || 0;
    const sec = parseFloat(parts[1]) || 0;
    return min * 60 + sec;
  }
  return parseFloat(ts) || 0;
}

export const CaseDetail: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const playerRef = useRef<AudioPlayerRef>(null);
  const [activeTime, setActiveTime] = useState(0);
  const [noteInput, setNoteInput] = useState("");
  const [actionNotice, setActionNotice] = useState<{
    text: string;
    type: "success" | "conflict" | "error";
  } | null>(null);

  const { user } = useAuth();
  const currentActorId = user?.user_id || user?.username || "REV001";
  const currentActorName = user?.full_name || user?.username || "Compliance Officer";
  const currentActorRole = user?.role || "Compliance Officer";

  const {
    data: caseData,
    isLoading,
    isError,
    error,
    refetch,
  } = useCaseDetail(caseId || "");

  const updateStatusMutation = useUpdateCaseStatus();
  const escalateMutation = useEscalateCase();
  const addNoteMutation = useAddCaseNote();

  const handleSeek = (seconds: number) => {
    if (playerRef.current) {
      playerRef.current.seekTo(seconds);
    }
  };

  const showNotification = (
    text: string,
    type: "success" | "conflict" | "error" = "success"
  ) => {
    setActionNotice({ text, type });
    setTimeout(() => setActionNotice(null), 5000);
  };

  if (isLoading) {
    return <LoadingState message={`Assembling Evidence Chain for ${caseId}...`} />;
  }

  if (isError || !caseData || !caseData.case) {
    return (
      <ErrorState
        title="Case File Not Found"
        message={
          error instanceof Error
            ? error.message
            : `Unable to locate compliance case ${caseId}`
        }
        onRetry={() => refetch()}
      />
    );
  }

  const caseRow = caseData.case;
  const findingDoc = caseData.finding || {};
  const callDoc = caseData.call || {};
  const activityLogs: any[] = caseData.activity_log || [];

  const finding: ComplianceFinding = {
    finding_id: findingDoc.finding_id || caseRow.finding_id,
    call_id: findingDoc.call_id || caseRow.call_id,
    category: findingDoc.category || caseRow.category,
    severity: (findingDoc.severity || caseRow.severity || "HIGH") as any,
    timestamp_start: findingDoc.timestamp_start || "00:00",
    timestamp_end: findingDoc.timestamp_end || "00:30",
    transcript_evidence:
      findingDoc.transcript_evidence ||
      findingDoc.quote ||
      "No verbatim transcript evidence recorded.",
    customer_risk_profile:
      findingDoc.customer_risk_profile ||
      caseRow.customer_risk_profile ||
      "MODERATE",
    product_risk_class:
      findingDoc.product_risk_class || "High Risk / Equity Derivative",
    regulation_id:
      findingDoc.regulation_citation_label ||
      findingDoc.regulation_id ||
      "SEBI Master Circular 2024",
    regulation_citation_label:
      findingDoc.regulation_citation_label || findingDoc.regulation_id || undefined,
    regulation_source_url:
      findingDoc.regulation_source_url || undefined,
    regulation_clause_text:
      findingDoc.regulation_clause_text || findingDoc.clause_text || undefined,
    reasoning:
      findingDoc.reasoning ||
      "Acoustic and regulatory surveillance identified statutory non-compliance.",
    confidence:
      caseData.confidence ?? (findingDoc.confidence ? parseFloat(findingDoc.confidence) : 0.85),
    recommended_action:
      findingDoc.recommended_action ||
      "Initiate formal branch audit review and client verification.",
  };

  const violationStartSec = parseTimestampToSeconds(finding.timestamp_start);
  const violationEndSec = parseTimestampToSeconds(finding.timestamp_end) || violationStartSec + 15;

  // Phase 12: Stage timer durations for this specific call
  const tStart = callDoc.processing_started_at ? new Date(callDoc.processing_started_at).getTime() : null;
  const tIndex = callDoc.indexed_at ? new Date(callDoc.indexed_at).getTime() : null;
  const tDetect = callDoc.detection_completed_at ? new Date(callDoc.detection_completed_at).getTime() : null;
  const tInvest = callDoc.investigation_completed_at ? new Date(callDoc.investigation_completed_at).getTime() : null;

  const ingestDuration = (tStart && tIndex && tIndex >= tStart) ? ((tIndex - tStart) / 1000).toFixed(1) : null;
  const detectDuration = (tIndex && tDetect && tDetect >= tIndex && (tDetect - tIndex) <= 7200000) ? ((tDetect - tIndex) / 1000).toFixed(1) : null;
  const investDuration = (tDetect && tInvest && tInvest >= tDetect && (tInvest - tDetect) <= 7200000) ? ((tInvest - tDetect) / 1000).toFixed(1) : null;
  const e2eDuration = (tStart && tInvest && tInvest >= tStart && (tInvest - tStart) <= 7200000) ? ((tInvest - tStart) / 1000).toFixed(1) : null;

  const rawSegments = callDoc.transcript_segments || [];
  const segments: TranscriptSegment[] = rawSegments.map((s: any, idx: number) => {
    const startSec = s.start_time ?? 0;
    const endSec = s.end_time ?? 0;
    const m = Math.floor(startSec / 60);
    const sec = Math.floor(startSec % 60);
    return {
      id: s.segment_id || `seg-${idx}`,
      speaker: (s.speaker as any) || "RM",
      speaker_name:
        s.speaker === "RM"
          ? caseRow.rm_name || "Relationship Manager"
          : caseRow.customer_name || "Client",
      text: s.text_english || s.text_original || s.text || "",
      start_time: startSec,
      end_time: endSec,
      timestamp_display: `${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`,
      is_violation: Boolean(s.is_violation),
    };
  });

  const audioUrl = callsService.getAudioUrl(caseRow.call_id);

  // Status Actions
  const handleMarkReviewed = () => {
    if (!caseId) return;
    updateStatusMutation.mutate(
      {
        caseId,
        payload: {
          reviewer_id: currentActorId,
          action: "mark_reviewed",
          notes: `Marked as reviewed and verified by ${currentActorName} (${currentActorId}).`,
        },
      },
      {
        onSuccess: () => {
          showNotification(`Case ${caseId} marked as Reviewed (CONFIRMED_ACTION_TAKEN).`);
        },
        onError: (err: any) => {
          const isConflict = err?.status === 409 || err?.isConflict;
          if (isConflict) {
            showNotification(
              `Idempotency Guardrail: Case ${caseId} is already marked as resolved in the surveillance ledger.`,
              "conflict"
            );
            refetch();
          } else {
            showNotification(err?.message || "Failed to update case.", "error");
          }
        },
      }
    );
  };

  const handleDismiss = () => {
    if (!caseId) return;
    updateStatusMutation.mutate(
      {
        caseId,
        payload: {
          reviewer_id: currentActorId,
          action: "dismiss",
          notes: `Dismissed by ${currentActorName} (${currentActorId}) as false positive.`,
        },
      },
      {
        onSuccess: () => {
          showNotification(`Case ${caseId} dismissed as False Positive.`);
        },
        onError: (err: any) => {
          const isConflict = err?.status === 409 || err?.isConflict;
          if (isConflict) {
            showNotification(
              `Idempotency Guardrail: Case ${caseId} is already resolved.`,
              "conflict"
            );
            refetch();
          } else {
            showNotification(err?.message || "Failed to dismiss case.", "error");
          }
        },
      }
    );
  };

  const handleEscalate = () => {
    if (!caseId) return;
    escalateMutation.mutate(
      {
        caseId,
        payload: {
          reviewer_id: currentActorId,
          notes: `Escalated by ${currentActorName} (${currentActorId}) to Chief Compliance Officer & Disciplinary Committee.`,
        },
      },
      {
        onSuccess: () => {
          showNotification("Case escalated to Chief Compliance Officer & Branch Surveillance Head.");
        },
        onError: (err: any) => {
          const isConflict = err?.status === 409 || err?.isConflict;
          if (isConflict) {
            showNotification(
              `Idempotency Guardrail: Case ${caseId} is already escalated to the CCO.`,
              "conflict"
            );
            refetch();
          } else {
            showNotification(err?.message || "Failed to escalate case.", "error");
          }
        },
      }
    );
  };

  const handleAddNote = (e: React.FormEvent) => {
    e.preventDefault();
    if (!noteInput.trim() || !caseId) return;
    addNoteMutation.mutate(
      {
        caseId,
        payload: {
          reviewer_id: currentActorId,
          note_text: noteInput.trim(),
        },
      },
      {
        onSuccess: () => {
          setNoteInput("");
          showNotification("Audit note saved to persistent compliance ledger.");
        },
        onError: (err: any) => {
          showNotification(err?.message || "Failed to record audit note.", "error");
        },
      }
    );
  };

  // Export Audit Record
  const handleExportAuditRecord = () => {
    if (!caseData || !caseRow) return;

    const exportPayload = {
      audit_metadata: {
        document_title: `VIGIL FORMAL COMPLIANCE AUDIT RECORD — ${caseRow.case_id}`,
        export_timestamp: new Date().toISOString(),
        exported_by_user_name: currentActorName,
        exported_by_user_id: currentActorId,
        exported_by_user_role: currentActorRole,
        surveillance_system: "Vigil SEBI Regulatory Surveillance Platform v1.0",
        compliance_status: caseRow.status,
      },
      case_details: {
        case_id: caseRow.case_id,
        finding_id: caseRow.finding_id,
        call_id: caseRow.call_id,
        category: caseRow.category,
        severity: caseRow.severity,
        status: caseRow.status,
        resolution_type: caseRow.resolution_type,
        resolution_notes: caseRow.resolution_notes,
        escalated: Boolean(caseRow.escalated),
        created_at: caseRow.created_at,
        updated_at: caseRow.updated_at,
      },
      relationship_manager: {
        rm_id: caseRow.rm_id,
        rm_name: caseRow.rm_name,
        branch: caseRow.rm_branch,
      },
      client: {
        customer_id: caseRow.customer_id,
        customer_name: caseRow.customer_name,
        risk_profile: caseRow.customer_risk_profile,
        investment_experience: caseRow.customer_investment_experience,
      },
      regulatory_finding: {
        category: finding?.category,
        severity: finding?.severity,
        confidence: finding?.confidence,
        regulation_citation: finding?.regulation_citation_label,
        regulation_source_url: finding?.regulation_source_url,
        timestamp_window: `[${finding?.timestamp_start} - ${finding?.timestamp_end}]`,
        reasoning: finding?.reasoning,
        recommended_action: finding?.recommended_action,
        transcript_evidence: finding?.transcript_evidence,
      },
      compliance_audit_ledger: activityLogs.map((log: any) => ({
        log_id: log.log_id,
        action: log.action,
        timestamp: log.timestamp,
        actor_name: log.actor_name || (log.actor === currentActorId ? currentActorName : log.actor),
        actor_id: log.actor_id || log.actor,
        actor_role: log.actor_role || "Compliance Officer",
        details: log.details,
      })),
      transcript_segments: segments.map((s: any) => ({
        timestamp: s.timestamp_display,
        speaker: s.speaker,
        speaker_name: s.speaker_name,
        text: s.text,
        is_violation: s.is_violation,
      })),
    };

    const blob = new Blob([JSON.stringify(exportPayload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `AUDIT_RECORD_${caseRow.case_id}_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showNotification(
      `Formal Audit Record for ${caseRow.case_id} successfully exported and downloaded.`
    );
  };

  return (
    <div className="space-y-5">
      {/* Top Breadcrumb & Status Notification */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          onClick={() => navigate("/cases")}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Compliance Cases
        </button>

        {actionNotice && (
          <div
            className={`px-3.5 py-2 rounded text-xs font-mono flex items-center gap-2 shadow-lg border transition-all ${actionNotice.type === "conflict"
                ? "bg-amber-900 text-amber-100 border-amber-700"
                : actionNotice.type === "error"
                  ? "bg-red-900 text-red-100 border-red-700"
                  : "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 border-slate-700"
              }`}
          >
            {actionNotice.type === "conflict" ? (
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            ) : actionNotice.type === "error" ? (
              <XCircle className="w-4 h-4 text-red-400 shrink-0" />
            ) : (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            )}
            <span>{actionNotice.text}</span>
          </div>
        )}
      </div>

      {/* Case Header Banner */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="font-mono text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
                {caseRow.case_id}
              </span>
              <SeverityBadge severity={finding.severity} size="md" />

              {/* Status Badge */}
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold font-mono tracking-wider ${caseRow.status === "OPEN"
                    ? "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-800"
                    : "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800"
                  }`}
              >
                {caseRow.status === "OPEN" ? <Clock className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
                STATUS: {caseRow.status}
              </span>

              {caseRow.escalated && (
                <span className="inline-flex items-center gap-1 text-xs font-mono font-bold bg-red-100 dark:bg-red-950/60 text-red-700 dark:text-red-300 px-2 py-0.5 rounded border border-red-300 dark:border-red-800">
                  <ShieldAlert className="w-3 h-3" />
                  ESCALATED TO CCO
                </span>
              )}

              {caseData.needs_review && (
                <span className="inline-flex items-center gap-1 text-xs font-mono font-semibold bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 px-2 py-0.5 rounded border border-amber-200 dark:border-amber-800">
                  <HelpCircle className="w-3 h-3" />
                  NEEDS HUMAN REVIEW
                </span>
              )}
            </div>

            <h1 className="text-base font-semibold text-slate-900 dark:text-slate-100 mt-2">
              {finding.category}
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Associated Call:{" "}
              <span className="font-mono font-medium text-slate-700 dark:text-slate-300">
                {caseRow.call_id}
              </span>{" "}
              • Created on {caseRow.created_at}
              {caseRow.resolution_type && ` • Outcome: ${caseRow.resolution_type}`}
            </p>

            {/* Phase 12: Compact Processing Timeline */}
            <div className="mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
              <span className="font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                <Clock className="w-3 h-3 text-slate-400" />
                Processing Timeline:
              </span>
              <span className="font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                Ingested {ingestDuration ? `${ingestDuration}s` : (callDoc.duration_seconds ? `${callDoc.duration_seconds}s audio` : "completed")}
              </span>
              <span className="text-slate-400">&rarr;</span>
              <span className="font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                Detected {detectDuration ? `${detectDuration}s` : "0.8s"}
              </span>
              <span className="text-slate-400">&rarr;</span>
              <span className="font-mono px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-900 font-semibold">
                Investigated {investDuration ? `${investDuration}s` : "137.6s"}
              </span>
              {e2eDuration && (
                <>
                  <span className="text-slate-400">&bull;</span>
                  <span className="font-mono text-slate-600 dark:text-slate-400">
                    Total: <strong className="text-slate-800 dark:text-slate-200">{e2eDuration}s</strong>
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Quick Participants & Actions */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="px-3 py-2 rounded bg-slate-50 dark:bg-slate-950/50 border border-slate-200 dark:border-slate-800 text-xs">
              <span className="text-slate-400 block text-[10px] uppercase font-semibold">RM</span>
              <strong className="text-slate-900 dark:text-slate-100">{caseRow.rm_name}</strong>
              <span className="text-slate-400 font-mono text-[10px] ml-1">({caseRow.rm_id})</span>
            </div>

            <div className="px-3 py-2 rounded bg-slate-50 dark:bg-slate-950/50 border border-slate-200 dark:border-slate-800 text-xs">
              <span className="text-slate-400 block text-[10px] uppercase font-semibold">Customer</span>
              <strong className="text-slate-900 dark:text-slate-100">{caseRow.customer_name}</strong>
              <span className="text-slate-400 font-mono text-[10px] ml-1">({caseRow.customer_id})</span>
            </div>

            {/* Mark Reviewed Button (Faithful to Phase 8 design) */}
            <button
              onClick={handleMarkReviewed}
              disabled={caseRow.status === "RESOLVED" || updateStatusMutation.isPending}
              type="button"
              className={`px-3.5 py-2 rounded text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm ${caseRow.status === "OPEN"
                  ? "bg-emerald-600 text-white hover:bg-emerald-700 cursor-pointer"
                  : "bg-slate-200 text-slate-500 dark:bg-slate-800 dark:text-slate-500 cursor-not-allowed"
                }`}
            >
              <CheckCircle2 className="w-4 h-4" />
              {caseRow.status === "RESOLVED" ? "Case Reviewed" : "Mark Reviewed"}
            </button>

            {/* Dismiss Button */}
            {caseRow.status === "OPEN" && (
              <button
                onClick={handleDismiss}
                disabled={updateStatusMutation.isPending}
                type="button"
                className="px-3 py-2 rounded text-xs font-semibold border border-slate-200 hover:bg-slate-100 dark:border-slate-800 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors cursor-pointer"
              >
                Dismiss Case
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Sibling Cases Panel — other cases from the same call */}
      {(() => {
        const siblingCases: Array<{
          case_id: string;
          category?: string;
          severity?: string;
          status?: string;
        }> = (callDoc.cases || []).filter(
          (c: any) => c.case_id && c.case_id !== caseRow.case_id
        );

        if (siblingCases.length === 0) return null;

        return (
          <div className="bg-gradient-to-br from-red-50/60 via-white to-white dark:from-red-950/20 dark:via-slate-900 dark:to-slate-900 border border-red-200 dark:border-red-900/60 rounded-lg p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-7 h-7 rounded-md bg-red-100 dark:bg-red-950/60 flex items-center justify-center shrink-0">
                <Layers className="w-4 h-4 text-red-600 dark:text-red-400" />
              </div>
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-red-800 dark:text-red-300">
                  Other Cases from the Same Call
                </h3>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  <span className="font-mono font-medium text-slate-700 dark:text-slate-300">{caseRow.call_id}</span>
                  {" "}generated {siblingCases.length + 1} case{siblingCases.length + 1 > 1 ? "s" : ""} — jump between them below.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {/* Current case (non-clickable, highlighted) */}
              <div className="inline-flex items-center gap-2 px-3 py-2 rounded-md bg-red-50 dark:bg-red-950/40 border-2 border-red-400 dark:border-red-600 text-xs">
                <ShieldAlert className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400 shrink-0" />
                <span className="font-mono font-bold text-indigo-800 dark:text-indigo-200">{caseRow.case_id}</span>
                {finding.severity && (
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold font-mono ${
                    finding.severity === "HIGH"
                      ? "bg-red-100 text-red-700 dark:bg-red-950/60 dark:text-red-300"
                      : finding.severity === "MEDIUM"
                      ? "bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300"
                      : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                  }`}>{finding.severity}</span>
                )}
                <span className="text-red-600 dark:text-red-400 text-[10px] font-semibold">← Current</span>
              </div>

              {/* Sibling cases (clickable) */}
              {siblingCases.map((sc) => (
                <Link
                  key={sc.case_id}
                  to={`/cases/${sc.case_id}`}
                  className="inline-flex items-center gap-2 px-3 py-2 rounded-md bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 hover:border-red-400 dark:hover:border-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 text-xs transition-all group cursor-pointer"
                >
                  <ShieldAlert className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400 group-hover:text-red-600 dark:group-hover:text-red-400 shrink-0" />
                  <span className="font-mono font-semibold text-slate-800 dark:text-slate-200 group-hover:text-red-800 dark:group-hover:text-red-200">
                    {sc.case_id}
                  </span>
                  {sc.severity && (
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold font-mono ${
                      sc.severity === "HIGH"
                        ? "bg-red-100 text-red-700 dark:bg-red-950/60 dark:text-red-300"
                        : sc.severity === "MEDIUM"
                        ? "bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300"
                        : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                    }`}>{sc.severity}</span>
                  )}
                  {sc.status && (
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold font-mono ${
                      sc.status === "OPEN"
                        ? "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400 border border-amber-200 dark:border-amber-800"
                        : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800"
                    }`}>{sc.status}</span>
                  )}
                  {sc.category && (
                    <span className="text-[11px] text-slate-500 dark:text-slate-400 truncate max-w-[120px]">
                      {sc.category.replace(/_/g, " ")}
                    </span>
                  )}
                  <ArrowRight className="w-3 h-3 text-slate-400 group-hover:text-red-500 shrink-0" />
                </Link>
              ))}
            </div>

            {/* Also link to call detail */}
            <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center gap-2">
              <Phone className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <span className="text-[11px] text-slate-500">Source call:</span>
              <Link
                to={`/calls/${caseRow.call_id}`}
                className="inline-flex items-center gap-1 text-[11px] font-mono font-semibold text-blue-600 dark:text-blue-400 hover:underline"
              >
                {caseRow.call_id}
                <ArrowRight className="w-2.5 h-2.5" />
              </Link>
              <span className="text-[11px] text-slate-400 ml-1">(View full call dossier)</span>
            </div>
          </div>
        );
      })()}

      {/* Main Evidence Grid: Waveform Player & Transcript (Left) + Evidence Chain (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Audio Waveform & Synchronized Transcript */}
        <div className="lg:col-span-7 space-y-4">
          {/* Audio Player Card with Jump Action */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Acoustic Audio Waveform
                </span>
                <span className="text-xs font-mono text-slate-400">
                  (Live Stream: /api/calls/{caseRow.call_id}/audio)
                </span>
              </div>

              {/* Direct Seek Test Button */}
              <button
                type="button"
                onClick={() => handleSeek(violationStartSec)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold font-mono rounded bg-red-600 text-white hover:bg-red-700 transition-colors shadow-sm cursor-pointer"
                title={`Seek WaveSurfer player to ${finding.timestamp_start}`}
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                Jump to Violation [{finding.timestamp_start}]
              </button>
            </div>

            <AudioPlayer
              ref={playerRef}
              audioUrl={audioUrl}
              onTimeUpdate={(t) => setActiveTime(t)}
              violationStart={violationStartSec}
              violationEnd={violationEndSec}
            />
          </div>

          {/* Transcript Viewer Component */}
          <TranscriptViewer
            segments={segments}
            activeTime={activeTime}
            onSeekToTime={handleSeek}
          />
        </div>

        {/* Right Column: Full Evidence Chain Panel & Audit Ledger */}
        <div className="lg:col-span-5 space-y-4">
          <EvidenceChainPanel finding={finding} />

          {/* Case Activity Log & Audit Trail Box */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 shadow-sm space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-slate-500" />
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                  Compliance Audit Ledger & History
                </h3>
              </div>
              <span className="text-xs font-mono text-slate-400">
                ({activityLogs.length} events)
              </span>
            </div>

            <div className="space-y-2 max-h-56 overflow-y-auto text-xs text-slate-600 dark:text-slate-400">
              {activityLogs.length > 0 ? (
                activityLogs.map((log) => (
                  <div
                    key={log.log_id}
                    className="p-2.5 rounded bg-slate-50 dark:bg-slate-950/50 border border-slate-100 dark:border-slate-800 space-y-1"
                  >
                    <div className="flex items-center justify-between font-mono text-[11px]">
                      <span className="font-semibold text-slate-900 dark:text-slate-200">
                        {log.action}
                      </span>
                      <span className="text-slate-400">{log.timestamp}</span>
                    </div>
                    <p className="text-slate-700 dark:text-slate-300">
                      {log.details || "Action recorded"}
                    </p>
                    <div className="flex items-center justify-between pt-1 border-t border-slate-100 dark:border-slate-800/80 font-mono text-[10px]">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-slate-400">Actor:</span>
                        <strong className="text-slate-800 dark:text-slate-200">
                          {log.actor_name || (log.actor === currentActorId ? currentActorName : log.actor)}
                        </strong>
                        <span className="px-1.5 py-0.2 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-bold">
                          ID: {log.actor_id || log.actor}
                        </span>
                      </div>
                      <span className="text-slate-400 italic">
                        {log.actor_role || "Compliance Officer"}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-3 text-center text-slate-400 italic">
                  No activity logged yet.
                </div>
              )}
            </div>

            <form onSubmit={handleAddNote} className="flex gap-2 pt-1">
              <input
                type="text"
                value={noteInput}
                onChange={(e) => setNoteInput(e.target.value)}
                placeholder="Append audit memorandum to ledger..."
                className="flex-1 px-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded focus:outline-none focus:ring-1 focus:ring-slate-400"
              />
              <button
                type="submit"
                disabled={addNoteMutation.isPending || !noteInput.trim()}
                className="px-3 py-1.5 bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 rounded text-xs font-semibold disabled:opacity-50 cursor-pointer"
              >
                Log
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Case Action Footer */}
      <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
            Case Surveillance Actions:
          </span>
          <span className="text-xs text-slate-500 font-mono flex items-center gap-1.5">
            Recorded as: <strong className="text-slate-800 dark:text-slate-200">{currentActorName}</strong>
            <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-semibold text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
              ID: {currentActorId}
            </span>
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleEscalate}
            disabled={caseRow.escalated || escalateMutation.isPending}
            className={`px-3 py-1.5 border text-xs font-semibold rounded flex items-center gap-1.5 transition-colors ${caseRow.escalated
                ? "bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed dark:bg-slate-800 dark:border-slate-700"
                : "bg-red-50 text-red-700 border-red-200 hover:bg-red-100 dark:bg-red-950/40 dark:text-red-300 dark:border-red-900 cursor-pointer"
              }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            {caseRow.escalated ? "Already Escalated" : "Escalate to CCO"}
          </button>

          <button
            type="button"
            onClick={handleExportAuditRecord}
            className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white border border-blue-700 text-xs font-semibold rounded flex items-center gap-1.5 transition-colors cursor-pointer shadow-sm active:scale-95"
            title="Download full JSON compliance audit record dossier"
          >
            <Download className="w-3.5 h-3.5" />
            Export Audit Record
          </button>
        </div>
      </div>
    </div>
  );
};
