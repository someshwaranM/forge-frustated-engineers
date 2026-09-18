import React, { useState, useEffect } from "react";
import {
  Settings as SettingsIcon,
  Sun,
  Moon,
  Sliders,
  CheckCircle2,
  Save,
} from "lucide-react";
import { useTheme } from "../../context/ThemeContext";
import {
  useSettings,
  useUpdateSettings,
} from "../../services/settingsService";
import { LoadingState } from "../../components/shared/LoadingState";

export const Settings: React.FC = () => {
  const { isDark, setTheme } = useTheme();

  const { data: settingsData, isLoading: settingsLoading } = useSettings();
  const updateSettingsMutation = useUpdateSettings();

  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(75);
  const [autoEscalateThreshold, setAutoEscalateThreshold] = useState<number>(90);
  const [savedNotice, setSavedNotice] = useState(false);

  useEffect(() => {
    if (settingsData?.confidence_threshold !== undefined) {
      const val = Math.round(settingsData.confidence_threshold * 100);
      setConfidenceThreshold(val);
    }
  }, [settingsData]);

  const handleToggleTheme = (mode: "light" | "dark") => {
    setTheme(mode);
  };

  const handleSaveSettings = () => {
    updateSettingsMutation.mutate(
      {
        confidence_threshold: confidenceThreshold / 100,
      },
      {
        onSuccess: () => {
          setSavedNotice(true);
          setTimeout(() => setSavedNotice(false), 3500);
        },
      }
    );
  };

  if (settingsLoading) {
    return <LoadingState message="Loading configuration..." />;
  }

  return (
    <div className="max-w-4xl space-y-6">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <SettingsIcon className="w-5 h-5 text-slate-700 dark:text-slate-300" />
            System & Surveillance Settings
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Operational configurations, AI inference parameters, and audit surveillance thresholds
          </p>
        </div>

        {savedNotice && (
          <div className="px-3 py-1.5 rounded bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 text-xs font-mono flex items-center gap-1.5 shadow-sm">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span>Parameters saved to database</span>
          </div>
        )}
      </div>

      {/* Section 1: Appearance Theme (Working Light/Dark Toggle) */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Interface Appearance & Contrast
          </h3>
          <p className="text-xs text-slate-500">
            Select high-legibility theme mode for regulatory audit review
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <button
            type="button"
            onClick={() => handleToggleTheme("light")}
            className={`p-4 rounded-lg border text-left transition-all flex items-start gap-3 cursor-pointer ${
              !isDark
                ? "border-slate-900 bg-slate-50 dark:border-slate-100 ring-2 ring-slate-900/10"
                : "border-slate-200 dark:border-slate-800 hover:border-slate-400"
            }`}
          >
            <Sun className={`w-5 h-5 mt-0.5 ${!isDark ? "text-amber-500" : "text-slate-400"}`} />
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Light Audit Mode (Default)
              </p>
              <span className="text-xs text-slate-500">
                Restrained off-white slate background with high-contrast typography
              </span>
            </div>
          </button>

          <button
            type="button"
            onClick={() => handleToggleTheme("dark")}
            className={`p-4 rounded-lg border text-left transition-all flex items-start gap-3 cursor-pointer ${
              isDark
                ? "border-slate-100 bg-slate-950 dark:border-slate-700 ring-2 ring-slate-700"
                : "border-slate-200 dark:border-slate-800 hover:border-slate-400"
            }`}
          >
            <Moon className={`w-5 h-5 mt-0.5 ${isDark ? "text-blue-400" : "text-slate-400"}`} />
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Dark Mode
              </p>
              <span className="text-xs text-slate-500">
                Low-fatigue dark slate base for extended investigation sessions
              </span>
            </div>
          </button>
        </div>
      </div>

      {/* Section 2: Surveillance Sensitivity & Confidence Thresholds */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm space-y-5">
        <div>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Sliders className="w-4 h-4 text-blue-600" />
            Surveillance Sensitivity & Confidence Thresholds
          </h3>
          <p className="text-xs text-slate-500">
            Calibrate detection thresholds below which findings dynamically route to manual human review
          </p>
        </div>

        {/* Slider 1 */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              Minimum Case Flagging Confidence Floor:
            </span>
            <span className="font-mono font-bold text-sm text-blue-600 dark:text-blue-400">
              {confidenceThreshold}%
            </span>
          </div>
          <input
            type="range"
            min={50}
            max={98}
            value={confidenceThreshold}
            onChange={(e) => setConfidenceThreshold(Number(e.target.value))}
            className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-600"
          />
          <span className="text-[11px] text-slate-400 block">
            Acoustic extractions scoring below {confidenceThreshold}% are tagged with NEEDS HUMAN REVIEW.
          </span>
        </div>

        {/* Slider 2 */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              Automated CCO Escalation Threshold (HIGH Severity):
            </span>
            <span className="font-mono font-bold text-sm text-red-600 dark:text-red-400">
              {autoEscalateThreshold}%
            </span>
          </div>
          <input
            type="range"
            min={75}
            max={99}
            value={autoEscalateThreshold}
            onChange={(e) => setAutoEscalateThreshold(Number(e.target.value))}
            className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-red-600"
          />
          <span className="text-[11px] text-slate-400 block">
            Findings with severity HIGH and confidence &ge; {autoEscalateThreshold}% trigger priority surveillance dispatch.
          </span>
        </div>

        <div className="pt-2 flex justify-end">
          <button
            type="button"
            onClick={handleSaveSettings}
            disabled={updateSettingsMutation.isPending}
            className="px-4 py-2 bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 rounded-lg text-xs font-semibold flex items-center gap-1.5 hover:bg-slate-800 dark:hover:bg-slate-200 transition-colors shadow-sm cursor-pointer disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5" />
            {updateSettingsMutation.isPending ? "Saving..." : "Save Configuration"}
          </button>
        </div>
      </div>
    </div>
  );
};
