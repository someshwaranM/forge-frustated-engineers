import React from "react";
import { useNavigate } from "react-router-dom";
import { ChatMessage } from "../../types";
import { SeverityBadge } from "./SeverityBadge";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { cn } from "../../lib/utils";
import {
  Bot,
  User,
  Wrench,
  ExternalLink,
  ShieldAlert,
  CheckCircle2,
} from "lucide-react";

interface ChatMessageCardProps {
  message: ChatMessage;
  className?: string;
}

export const ChatMessageCard: React.FC<ChatMessageCardProps> = ({
  message,
  className,
}) => {
  const navigate = useNavigate();
  const isAssistant = message.role === "assistant";

  return (
    <div
      className={cn(
        "flex gap-3 text-sm",
        isAssistant ? "justify-start" : "justify-end",
        className
      )}
    >
      {isAssistant && (
        <div className="w-8 h-8 rounded-full bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
          <Bot className="w-4 h-4" />
        </div>
      )}

      <div
        className={cn(
          "rounded-lg p-4 space-y-3",
          isAssistant
            ? "max-w-3xl w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm"
            : "max-w-2xl bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
        )}
      >
        {/* Tool Invocations Badge Row */}
        {isAssistant && message.tools_called && message.tools_called.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pb-2 border-b border-slate-100 dark:border-slate-800/80">
            <span className="text-[11px] font-mono text-slate-400 flex items-center gap-1">
              <Wrench className="w-3 h-3" /> Grounded via tools:
            </span>
            {message.tools_called.map((tool) => (
              <span
                key={tool}
                className="px-1.5 py-0.5 text-[10px] font-mono font-medium rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
              >
                {tool}()
              </span>
            ))}
          </div>
        )}

        {/* Message Content */}
        {isAssistant ? (
          <MarkdownRenderer
            content={message.content}
            className="min-w-0 text-slate-800 dark:text-slate-200"
          />
        ) : (
          <div
            className="leading-relaxed text-sm text-slate-100 dark:text-slate-900 font-normal"
          >
            {message.content}
          </div>
        )}

        {/* Grounded Result Card (doorway into Case Detail) */}
        {isAssistant && message.grounded_case && (
          <div
            onClick={() => navigate(`/cases/${message.grounded_case?.case_id}`)}
            className="group mt-2 p-3 bg-red-50/50 hover:bg-red-50 dark:bg-red-950/20 dark:hover:bg-red-950/40 border border-red-200 dark:border-red-900/60 rounded-md cursor-pointer transition-all shadow-sm"
          >
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-red-600 dark:text-red-400" />
                <span className="font-mono text-xs font-bold text-slate-900 dark:text-slate-100">
                  {message.grounded_case.case_id}
                </span>
                <SeverityBadge severity={message.grounded_case.severity} size="sm" />
              </div>
              <span className="inline-flex items-center gap-1 text-xs font-medium text-red-700 dark:text-red-400 group-hover:underline">
                View Evidence Chain <ExternalLink className="w-3 h-3" />
              </span>
            </div>

            <p className="text-xs font-medium text-slate-900 dark:text-slate-100 mb-1">
              {message.grounded_case.finding_category}
            </p>
            <p className="text-xs text-slate-600 dark:text-slate-400 line-clamp-2">
              {message.grounded_case.summary}
            </p>

            <div className="mt-2 pt-2 border-t border-red-100 dark:border-red-900/40 flex items-center justify-between text-[11px] text-slate-500 font-mono">
              <span>RM: {message.grounded_case.rm_name}</span>
              <span>Confidence: {Math.round(message.grounded_case.confidence * 100)}%</span>
            </div>
          </div>
        )}

        {/* Live Grounded Result Items */}
        {isAssistant && message.grounded_results && message.grounded_results.length > 0 && !message.grounded_case && (
          <div className="mt-2 pt-2 border-t border-slate-100 dark:border-slate-800 space-y-1.5">
            <span className="text-[11px] font-mono text-slate-400 flex items-center gap-1">
              <ExternalLink className="w-3 h-3" /> Grounded Evidence Links:
            </span>
            <div className="flex flex-wrap gap-1.5">
              {message.grounded_results.map((item, idx) => {
                const targetUrl =
                  item.type === "call"
                    ? `/calls/${item.id}`
                    : item.type === "case"
                    ? `/cases/${item.id}`
                    : item.type === "regulation"
                    ? `/regulations`
                    : `/cases`;

                return (
                  <button
                    key={`${item.id}-${idx}`}
                    type="button"
                    onClick={() => navigate(targetUrl)}
                    className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 text-xs font-mono text-slate-800 dark:text-slate-200 transition-colors cursor-pointer"
                  >
                    <span className="uppercase text-[10px] text-slate-500 font-bold">{item.type}:</span>
                    <span>{item.id}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div
          className={cn(
            "text-[10px] font-mono",
            isAssistant ? "text-slate-400" : "text-slate-300 dark:text-slate-500 text-right"
          )}
        >
          {message.timestamp}
        </div>
      </div>

      {!isAssistant && (
        <div className="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 flex items-center justify-center shrink-0 mt-0.5">
          <User className="w-4 h-4" />
        </div>
      )}
    </div>
  );
};
