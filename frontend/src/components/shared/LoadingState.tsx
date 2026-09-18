import React from "react";
import { Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";

interface LoadingStateProps {
  message?: string;
  className?: string;
  size?: "sm" | "md" | "lg";
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = "Loading surveillance telemetry...",
  className,
  size = "md",
}) => {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 px-4 space-y-3",
        className
      )}
    >
      <div className="relative">
        <div className="w-10 h-10 rounded-full border-2 border-slate-200 dark:border-slate-800 animate-pulse" />
        <Loader2
          className={cn(
            "text-slate-700 dark:text-slate-300 animate-spin absolute inset-0 m-auto",
            size === "sm" && "w-4 h-4",
            size === "md" && "w-6 h-6",
            size === "lg" && "w-8 h-8"
          )}
        />
      </div>
      <p className="text-xs font-mono text-slate-500 dark:text-slate-400 tracking-wide">
        {message}
      </p>
    </div>
  );
};
