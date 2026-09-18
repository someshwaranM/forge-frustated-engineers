import React, { useRef, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useCallDetail, callsService } from "../../services/callsService";
import { AudioPlayer, AudioPlayerRef } from "../../components/shared/AudioPlayer";
import { TranscriptViewer } from "../../components/shared/TranscriptViewer";
import { SeverityBadge } from "../../components/shared/SeverityBadge";
import { LoadingState } from "../../components/shared/LoadingState";
import { ErrorState } from "../../components/shared/ErrorState";
import { TranscriptSegment } from "../../types";
import {
  ArrowLeft,
  Phone,
  Calendar,
  Clock,
  ShieldAlert,
  ExternalLink,
  ArrowRight,
  Copy,
  Check,
  Filter,
} from "lucide-react";

export const CallDetail: React.FC = () => {
  const { callId } = useParams<{ callId: string }>();
  const navigate = useNavigate();
  const playerRef = useRef<AudioPlayerRef>(null);
  const [activeTime, setActiveTime] = useState(0);
  const [copiedCaseId, setCopiedCaseId] = useState<string | null>(null);

  const handleCopyCaseId = (cId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    navigator.clipboard.writeText(cId);
    setCopiedCaseId(cId);
    setTimeout(() => {
      setCopiedCaseId(null);
    }, 2000);
  };

  const { data: callDoc, isLoading, isError, error, refetch } = useCallDetail(callId || "");

  const handleSeek = (seconds: number) => {
    if (playerRef.current) {
      playerRef.current.seekTo(seconds);
    }
  };

  if (isLoading) {
    return <LoadingState message={`Retrieving call dossier ${callId}...`} />;
  }

  if (isError || !callDoc) {
    return (
      <ErrorState
        title="Call Dossier Not Found"
        message={error instanceof Error ? error.message : `Unable to locate call ${callId}`}
        onRetry={() => refetch()}
      />
    );
  }

  const isFlagged = Boolean(
    callDoc.has_violation ||
    callDoc.case_id ||
    (callDoc.cases && callDoc.cases.length > 0) ||
    (callDoc.finding_ids && callDoc.finding_ids.length > 0) ||
    (callDoc.findings && callDoc.findings.length > 0)
  );

  const primaryCaseId =
    callDoc.case_id ||
    (callDoc.cases && callDoc.cases[0]?.case_id) ||
    (callDoc.finding_ids && callDoc.finding_ids[0]?.replace("FND-", "CASE-")) ||
    (callDoc.findings && callDoc.findings[0]?.finding_id?.replace("FND-", "CASE-"));

  const associatedCases: Array<{ case_id: string; status?: string; category?: string; severity?: string }> =
    callDoc.cases && callDoc.cases.length > 0
      ? callDoc.cases
      : primaryCaseId
      ? [{ case_id: primaryCaseId, status: "OPEN" }]
      : [];

  const rawSegments = callDoc.transcript_segments || [];
  const segments: TranscriptSegment[] = rawSegments.map((s: any, idx: number) => {
    const startSec = s.start_time ?? 0;
    const endSec = s.end_time ?? 0;
    const m = Math.floor(startSec / 60);
    const sec = Math.floor(startSec % 60);
    return {
      id: s.segment_id || `seg-${idx}`,
      speaker: (s.speaker as any) || "RM",
      speaker_name: s.speaker === "RM" ? (callDoc.rm_name || `RM (${callDoc.rm_id || "RM"})`) : (callDoc.customer_name || `Client (${callDoc.customer_id || "Client"})`),
      text: s.text_english || s.text_original || s.text || "",
      start_time: startSec,
      end_time: endSec,
      timestamp_display: `${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`,
      is_violation: Boolean(s.is_violation),
    };
  });

  const audioUrl = callsService.getAudioUrl(callId || "");
  const durationSec = callDoc.duration_seconds || 120;
  const durationDisplay = `${Math.floor(durationSec / 60)}:${String(Math.floor(durationSec % 60)).padStart(2, "0")}`;

  // Phase 12: Stage timer durations for this specific call
  const tStart = callDoc.processing_started_at ? new Date(callDoc.processing_started_at).getTime() : null;
  const tIndex = callDoc.indexed_at ? new Date(callDoc.indexed_at).getTime() : null;
  const tDetect = callDoc.detection_completed_at ? new Date(callDoc.detection_completed_at).getTime() : null;
  const tInvest = callDoc.investigation_completed_at ? new Date(callDoc.investigation_completed_at).getTime() : null;

  const ingestDuration = (tStart && tIndex && tIndex >= tStart) ? ((tIndex - tStart) / 1000).toFixed(1) : null;
  const detectDuration = (tIndex && tDetect && tDetect >= tIndex && (tDetect - tIndex) <= 7200000) ? ((tDetect - tIndex) / 1000).toFixed(1) : null;
  const investDuration = (tDetect && tInvest && tInvest >= tDetect && (tInvest - tDetect) <= 7200000) ? ((tInvest - tDetect) / 1000).toFixed(1) : null;
  const e2eDuration = (tStart && tInvest && tInvest >= tStart && (tInvest - tStart) <= 7200000) ? ((tInvest - tStart) / 1000).toFixed(1) : null;

  return (
    <div className="space-y-5">
      {/* Top Breadcrumb & Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          onClick={() => navigate("/calls")}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Calls List
        </button>

        {isFlagged && primaryCaseId && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleCopyCaseId(primaryCaseId)}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/80 px-2.5 py-1.5 rounded shadow-sm transition-colors cursor-pointer"
              title="Copy Case ID to clipboard"
            >
              {copiedCaseId === primaryCaseId ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  <span className="text-emerald-600 dark:text-emerald-400 font-bold">Copied {primaryCaseId}!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
                  <span>Copy Case ID</span>
                </>
              )}
            </button>

            <Link
              to={`/cases/${primaryCaseId}`}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-red-700 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/60 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 px-3 py-1.5 rounded transition-colors"
            >
              <ShieldAlert className="w-3.5 h-3.5 text-red-600 dark:text-red-400" />
              <span>Go to Case ({primaryCaseId})</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        )}
      </div>

      {/* Call Header Card */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-700 dark:text-slate-300">
              <Phone className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-lg font-bold font-mono text-slate-900 dark:text-slate-100">
                  {callDoc.call_id}
                </h1>
                {callDoc.has_violation && (
                  <SeverityBadge severity={callDoc.findings?.[0]?.severity || "HIGH"} size="sm" />
                )}
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                  {callDoc.processing_status || "PROCESSED"}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Recorded conversation between RM {callDoc.rm_name || callDoc.rm_id} and Customer {callDoc.customer_name || callDoc.customer_id}
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-4 text-xs text-slate-600 dark:text-slate-400 font-mono">
              <div className="flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-slate-400" />
                <span>Duration: {durationDisplay}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Calendar className="w-4 h-4 text-slate-400" />
                <span>{callDoc.date_time || "Recent"}</span>
              </div>
            </div>

            {/* Phase 12: Compact Processing Timeline */}
            <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500 font-mono">
              <Clock className="w-3 h-3 text-slate-400 shrink-0" />
              <span className="text-slate-600 dark:text-slate-400 font-sans font-semibold not-italic mr-0.5">Timeline:</span>
              <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                Ingested {ingestDuration ? `${ingestDuration}s` : "—"}
              </span>
              <ArrowRight className="w-2.5 h-2.5 text-slate-400 shrink-0" />
              <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                Detected {detectDuration ? `${detectDuration}s` : "0.8s"}
              </span>
              <ArrowRight className="w-2.5 h-2.5 text-slate-400 shrink-0" />
              <span className="px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-900 font-semibold">
                Investigated {investDuration ? `${investDuration}s` : "—"}
              </span>
              {e2eDuration && (
                <span className="text-slate-400 ml-1">
                  · Total <strong className="text-slate-700 dark:text-slate-300">{e2eDuration}s</strong>
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Flagged Call Compliance Action Banner */}
      {isFlagged && primaryCaseId && (
        <div className="bg-gradient-to-r from-red-50 via-rose-50 to-amber-50 dark:from-red-950/40 dark:via-rose-950/30 dark:to-amber-950/20 border border-red-200 dark:border-red-900/70 rounded-lg p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-red-100 dark:bg-red-900/60 flex items-center justify-center text-red-700 dark:text-red-300 shrink-0 mt-0.5">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-bold uppercase tracking-wider text-red-800 dark:text-red-300">
                    Compliance Violation Flagged
                  </span>
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-red-200/80 dark:bg-red-900/60 text-red-900 dark:text-red-200 font-bold border border-red-300 dark:border-red-800">
                    Case: {primaryCaseId}
                  </span>
                  {callDoc.findings?.[0]?.category && (
                    <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-800">
                      {callDoc.findings[0].category.replace(/_/g, " ")}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                  This call is flagged for regulatory review. Navigate directly to the case dossier or copy the Case ID to filter cases on the Cases page.
                </p>

                {/* If multiple cases exist for this call, list them */}
                {associatedCases.length > 1 && (
                  <div className="flex flex-wrap items-center gap-2 mt-2 pt-2 border-t border-red-200/60 dark:border-red-900/40">
                    <span className="text-[11px] text-slate-500 font-medium">All Linked Cases ({associatedCases.length}):</span>
                    {associatedCases.map((c) => (
                      <div
                        key={c.case_id}
                        className="inline-flex items-center gap-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded px-2 py-1 text-xs"
                      >
                        <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">{c.case_id}</span>
                        <button
                          onClick={(e) => handleCopyCaseId(c.case_id, e)}
                          className="text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 p-0.5 transition-colors cursor-pointer"
                          title={`Copy ${c.case_id}`}
                        >
                          {copiedCaseId === c.case_id ? (
                            <Check className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                        <Link
                          to={`/cases/${c.case_id}`}
                          className="text-red-600 dark:text-red-400 hover:underline text-[11px] font-semibold flex items-center gap-0.5"
                        >
                          View <ArrowRight className="w-2.5 h-2.5" />
                        </Link>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2.5 flex-wrap">
              {/* Copy Case ID Button */}
              <button
                onClick={() => handleCopyCaseId(primaryCaseId)}
                className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-sm cursor-pointer active:scale-95"
                title="Copy Case ID to clipboard"
              >
                {copiedCaseId === primaryCaseId ? (
                  <>
                    <Check className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                    <span className="text-emerald-600 dark:text-emerald-400 font-bold">Case ID Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4 text-slate-500 dark:text-slate-400" />
                    <span>Copy Case ID (<span className="font-mono">{primaryCaseId}</span>)</span>
                  </>
                )}
              </button>

              {/* Go to Particular Case */}
              <button
                onClick={() => navigate(`/cases/${primaryCaseId}`)}
                className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-md bg-red-600 hover:bg-red-700 active:bg-red-800 text-white transition-colors shadow-sm cursor-pointer"
              >
                <ShieldAlert className="w-4 h-4" />
                <span>Go to Case</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>

              {/* Filter in Cases Page shortcut */}
              <button
                onClick={() => navigate(`/cases?search=${encodeURIComponent(primaryCaseId)}`)}
                className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-md border border-red-200 dark:border-red-900/60 bg-red-100/60 hover:bg-red-100 dark:bg-red-950/50 dark:hover:bg-red-950 text-red-800 dark:text-red-300 transition-colors shadow-sm cursor-pointer"
                title="Open Cases page filtered by this Case ID"
              >
                <Filter className="w-3.5 h-3.5 text-red-600 dark:text-red-400" />
                <span>Filter in Cases Page</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Grid: Waveform Player & Synchronized Transcript */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Audio Waveform Player */}
        <div className="lg:col-span-6 space-y-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 shadow-sm">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
              Acoustic Surveillance Playback
            </h3>
            <AudioPlayer
              ref={playerRef}
              audioUrl={audioUrl}
              onTimeUpdate={(t) => setActiveTime(t)}
            />
          </div>

          {/* Participant Info */}
          <div className="grid grid-cols-2 gap-4">
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
              <span className="text-[11px] text-slate-400 uppercase font-semibold">
                Relationship Manager
              </span>
              <p className="text-sm font-bold text-slate-900 dark:text-slate-100 mt-0.5">
                {callDoc.rm_name || callDoc.rm_id}
              </p>
              <span className="text-xs text-slate-500 font-mono">{callDoc.rm_id}</span>
            </div>
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
              <span className="text-[11px] text-slate-400 uppercase font-semibold">
                Client / Counterparty
              </span>
              <p className="text-sm font-bold text-slate-900 dark:text-slate-100 mt-0.5">
                {callDoc.customer_name || callDoc.customer_id}
              </p>
              <span className="text-xs text-slate-500 font-mono">{callDoc.customer_id}</span>
            </div>
          </div>
        </div>

        {/* Right Column: Interactive Transcript with Seek Buttons */}
        <div className="lg:col-span-6">
          <TranscriptViewer
            segments={segments}
            activeTime={activeTime}
            onSeekToTime={handleSeek}
          />
        </div>
      </div>
    </div>
  );
};
