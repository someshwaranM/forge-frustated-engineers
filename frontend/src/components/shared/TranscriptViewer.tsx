import React from "react";
import { TranscriptSegment } from "../../types";
import { cn } from "../../lib/utils";
import { User, Headphones, Clock, AlertTriangle } from "lucide-react";

interface TranscriptViewerProps {
  segments: TranscriptSegment[];
  activeTime?: number;
  onSeekToTime?: (seconds: number) => void;
  className?: string;
  highlightViolationId?: string;
}

export const TranscriptViewer: React.FC<TranscriptViewerProps> = ({
  segments,
  activeTime = 0,
  onSeekToTime,
  className,
}) => {
  return (
    <div
      className={cn(
        "bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 shadow-sm flex flex-col h-[520px]",
        className
      )}
    >
      <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800 mb-3">
        <div className="flex items-center gap-2">
          <Headphones className="w-4 h-4 text-slate-500" />
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Call Audio Transcript
          </h3>
          <span className="text-xs text-slate-500 font-mono">
            ({segments.length} segments)
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {segments.map((segment) => {
          const isRM = segment.speaker === "RM";
          const isViolating = Boolean(segment.is_violation);
          const isCurrentlyPlaying =
            activeTime >= segment.start_time && activeTime <= segment.end_time;

          return (
            <div
              key={segment.id}
              className={cn(
                "p-3 rounded-lg border transition-all text-sm leading-relaxed",
                isViolating
                  ? "bg-red-50/70 border-red-300 dark:bg-red-950/30 dark:border-red-800 shadow-sm"
                  : isCurrentlyPlaying
                    ? "bg-slate-50 border-slate-300 dark:bg-slate-800/60 dark:border-slate-700"
                    : "bg-slate-50/40 border-slate-100 dark:bg-slate-950/40 dark:border-slate-800/70"
              )}
            >
              {/* Header row: Speaker & Clickable Timestamp */}
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <div
                    className={cn(
                      "w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold",
                      isRM
                        ? "bg-blue-100 text-blue-700 dark:bg-blue-900/60 dark:text-blue-300"
                        : "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/60 dark:text-emerald-300"
                    )}
                  >
                    {isRM ? "RM" : <User className="w-3 h-3" />}
                  </div>
                  <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                    {segment.speaker_name}
                  </span>

                  {isViolating && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold font-mono bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300 px-2 py-0.5 rounded">
                      <AlertTriangle className="w-3 h-3" />
                      FLAGGED EVIDENCE
                    </span>
                  )}
                </div>

                {/* Clickable timestamp marker that jumps audio */}
                <button
                  type="button"
                  onClick={() => onSeekToTime && onSeekToTime(segment.start_time)}
                  className={cn(
                    "inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono text-xs font-medium transition-colors cursor-pointer group",
                    isViolating
                      ? "bg-red-200/80 text-red-900 dark:bg-red-900/70 dark:text-red-200 hover:bg-red-300"
                      : "bg-slate-200/70 text-slate-700 dark:bg-slate-800 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-700"
                  )}
                  title={`Jump audio to ${segment.timestamp_display}`}
                >
                  <Clock className="w-3 h-3 text-slate-500 group-hover:text-slate-900 dark:group-hover:text-slate-100" />
                  <span>[{segment.timestamp_display}]</span>
                </button>
              </div>

              {/* Spoken Text */}
              <p
                className={cn(
                  "text-slate-700 dark:text-slate-300",
                  isViolating && "font-medium text-red-950 dark:text-red-200"
                )}
              >
                {segment.text}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
};
