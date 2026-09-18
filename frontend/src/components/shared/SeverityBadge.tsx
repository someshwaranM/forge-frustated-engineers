import React from "react";
import { SeverityLevel } from "../../types";
import { cn } from "../../lib/utils";
import { AlertTriangle, AlertCircle, Info } from "lucide-react";

interface SeverityBadgeProps {
  severity?: SeverityLevel;
  className?: string;
  size?: "sm" | "md" | "lg";
  showIcon?: boolean;
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({
  severity,
  className,
  size = "md",
  showIcon = true,
}) => {
  if (!severity) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 font-medium rounded-full bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 border border-slate-200 dark:border-slate-700",
          size === "sm" && "px-2 py-0.5 text-xs",
          size === "md" && "px-2.5 py-0.5 text-xs tracking-wider",
          size === "lg" && "px-3 py-1 text-sm font-semibold",
          className
        )}
      >
        CLEAN
      </span>
    );
  }

  const styles = {
    HIGH: {
      badge: "bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-400 dark:border-red-900/60",
      dot: "bg-red-600 dark:bg-red-400",
      icon: AlertCircle,
    },
    MEDIUM: {
      badge: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-900/60",
      dot: "bg-amber-500 dark:bg-amber-400",
      icon: AlertTriangle,
    },
    LOW: {
      badge: "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
      dot: "bg-slate-400 dark:bg-slate-500",
      icon: Info,
    },
  }[severity];

  const IconComponent = styles.icon;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-medium font-mono uppercase rounded border transition-colors",
        styles.badge,
        size === "sm" && "px-2 py-0.5 text-[11px]",
        size === "md" && "px-2.5 py-1 text-xs tracking-wider",
        size === "lg" && "px-3.5 py-1.5 text-sm font-semibold",
        className
      )}
    >
      {showIcon && <IconComponent className={cn("shrink-0", size === "sm" ? "w-3 h-3" : "w-3.5 h-3.5")} />}
      <span>{severity}</span>
    </span>
  );
};
