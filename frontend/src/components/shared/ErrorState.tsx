import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { cn } from "../../lib/utils";

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
  isConflict?: boolean;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = "Telemetry Synchronization Error",
  message = "Failed to communicate with surveillance backend.",
  onRetry,
  className,
  isConflict = false,
}) => {
  return (
    <div
      className={cn(
        "rounded-lg border p-6 flex flex-col items-center text-center max-w-md mx-auto my-8 space-y-4",
        isConflict
          ? "bg-amber-50 dark:bg-amber-950/30 border-amber-300 dark:border-amber-800"
          : "bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-900/60",
        className
      )}
    >
      <div
        className={cn(
          "w-10 h-10 rounded-full flex items-center justify-center shrink-0",
          isConflict
            ? "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300"
            : "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300"
        )}
      >
        <AlertTriangle className="w-5 h-5" />
      </div>

      <div className="space-y-1">
        <h3
          className={cn(
            "text-sm font-bold tracking-tight",
            isConflict
              ? "text-amber-950 dark:text-amber-200"
              : "text-red-950 dark:text-red-200"
          )}
        >
          {title}
        </h3>
        <p
          className={cn(
            "text-xs leading-relaxed",
            isConflict
              ? "text-amber-800 dark:text-amber-300"
              : "text-red-700 dark:text-red-400"
          )}
        >
          {message}
        </p>
      </div>

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className={cn(
            "px-3.5 py-1.5 rounded text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm cursor-pointer",
            isConflict
              ? "bg-amber-700 text-white hover:bg-amber-800 dark:bg-amber-600"
              : "bg-red-600 text-white hover:bg-red-700"
          )}
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry Operation</span>
        </button>
      )}
    </div>
  );
};
