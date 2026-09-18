// frontend/src/components/reports/SendReportModal.tsx
// Modal for selecting recipients and dispatching RM compliance reports

import React, { useState, useEffect, useId } from "react";
import { useQuery } from "@tanstack/react-query";
import { authService, User } from "../../services/authService";
import { useSendRmReport, SendReportResponse } from "../../services/reportService";
import {
  X,
  Mail,
  Send,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  ShieldCheck,
  UserCheck,
  FileText,
} from "lucide-react";

interface SendReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  rmId: string;
  rmName: string;
  rmEmail?: string | null;
}

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const INTERNAL_DOMAINS = ["vigil.com"];

export const SendReportModal: React.FC<SendReportModalProps> = ({
  isOpen,
  onClose,
  rmId,
  rmName,
  rmEmail,
}) => {
  const [recipientType, setRecipientType] = useState<"vigil_user" | "rm_email" | "custom">("vigil_user");
  const [selectedUserEmail, setSelectedUserEmail] = useState<string>("");
  const [customEmail, setCustomEmail] = useState<string>("");
  const [customEmailError, setCustomEmailError] = useState<string>("");
  const [isExternalDomain, setIsExternalDomain] = useState<boolean>(false);
  const [requestId, setRequestId] = useState<string>("");
  const [successData, setSuccessData] = useState<SendReportResponse | null>(null);

  // Generate unique request ID per modal open for idempotency
  useEffect(() => {
    if (isOpen) {
      const newId = `req_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
      setRequestId(newId);
      setSuccessData(null);
      setCustomEmailError("");
      setIsExternalDomain(false);
    }
  }, [isOpen]);

  // Dynamically load active Vigil users
  const { data: users, isLoading: isLoadingUsers } = useQuery<User[]>({
    queryKey: ["users", "list"],
    queryFn: authService.getUsers,
    enabled: isOpen,
  });

  // Auto-select first active user email
  useEffect(() => {
    if (users && users.length > 0 && !selectedUserEmail) {
      const activeUser = users.find((u) => u.is_active) || users[0];
      setSelectedUserEmail(activeUser.email);
    }
  }, [users, selectedUserEmail]);

  // Handle custom email input validation & domain check
  const handleCustomEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setCustomEmail(val);

    if (!val.trim()) {
      setCustomEmailError("");
      setIsExternalDomain(false);
      return;
    }

    if (!EMAIL_REGEX.test(val.trim())) {
      setCustomEmailError("Please enter a valid email address.");
      setIsExternalDomain(false);
    } else {
      setCustomEmailError("");
      const domain = val.trim().split("@")[1]?.toLowerCase();
      const isExt = !INTERNAL_DOMAINS.some((d) => domain === d || domain?.endsWith(`.${d}`));
      setIsExternalDomain(isExt);
    }
  };

  const sendMutation = useSendRmReport();

  if (!isOpen) return null;

  const determineRecipient = (): string | null => {
    if (recipientType === "vigil_user") {
      return selectedUserEmail || null;
    }
    if (recipientType === "rm_email") {
      return rmEmail || null;
    }
    if (recipientType === "custom") {
      const clean = customEmail.trim();
      return EMAIL_REGEX.test(clean) ? clean : null;
    }
    return null;
  };

  const activeRecipient = determineRecipient();
  const isSendDisabled = !activeRecipient || sendMutation.isPending;

  const handleSend = () => {
    if (!activeRecipient) return;

    sendMutation.mutate(
      {
        rmId,
        payload: {
          recipients: [activeRecipient],
          request_id: requestId,
        },
      },
      {
        onSuccess: (data) => {
          setSuccessData(data);
        },
      }
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div
        className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xl w-full max-w-lg overflow-hidden transition-all"
        role="dialog"
        aria-modal="true"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/40">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400">
              <Mail className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                Send RM Compliance Report
              </h3>
              <p className="text-xs text-slate-500">
                Formal supervisory telemetry & evidence dossier dispatch
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={sendMutation.isPending}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5">
          {successData ? (
            /* Success State */
            <div className="text-center py-4 space-y-4">
              <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 mx-auto flex items-center justify-center">
                <CheckCircle2 className="w-7 h-7" />
              </div>
              <div>
                <h4 className="text-base font-bold text-slate-900 dark:text-slate-100">
                  Report Dispatched Successfully
                </h4>
                <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 max-w-sm mx-auto">
                  Statutory RM compliance report for <strong>{rmName}</strong> ({rmId}) was dispatched to:
                </p>
                <div className="mt-2.5 inline-block px-3 py-1.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 font-mono text-xs font-semibold">
                  {successData.recipients.join(", ")}
                </div>
              </div>

              <div className="p-3 bg-slate-50 dark:bg-slate-950/50 border border-slate-200 dark:border-slate-800 rounded-lg text-left text-xs text-slate-500 space-y-1">
                <div><strong>Report ID:</strong> <span className="font-mono">{successData.report_id}</span></div>
                <div><strong>Dispatch Timestamp:</strong> {new Date(successData.sent_at).toLocaleString()}</div>
                <div><strong>Audit Event:</strong> <span className="text-emerald-600 font-semibold">RECORDED (SENT)</span></div>
              </div>

              <div className="pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="w-full py-2.5 px-4 bg-slate-900 hover:bg-slate-800 dark:bg-slate-100 dark:hover:bg-white text-white dark:text-slate-900 rounded-lg text-sm font-semibold transition-colors shadow-sm"
                >
                  Done
                </button>
              </div>
            </div>
          ) : (
            /* Form State */
            <>
              {/* Target RM Context Card */}
              <div className="flex items-center justify-between p-3.5 bg-slate-50 dark:bg-slate-950/40 border border-slate-200 dark:border-slate-800 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 flex items-center justify-center font-bold text-xs">
                    {rmName.split(" ").map((n) => n[0]).join("")}
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-400 uppercase">Target Relationship Manager</div>
                    <div className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                      {rmName}
                      <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                        {rmId}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Recipient Selection Section */}
              <div className="space-y-3">
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500">
                  Select Recipient
                </label>

                {/* Option A: Vigil System User */}
                <label
                  className={`flex items-start gap-3 p-3.5 rounded-lg border cursor-pointer transition-colors ${
                    recipientType === "vigil_user"
                      ? "border-indigo-600 bg-indigo-50/40 dark:bg-indigo-950/20 dark:border-indigo-500"
                      : "border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40"
                  }`}
                >
                  <input
                    type="radio"
                    name="recipient_option"
                    checked={recipientType === "vigil_user"}
                    onChange={() => setRecipientType("vigil_user")}
                    className="mt-1 text-indigo-600 focus:ring-indigo-500"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-slate-900 dark:text-slate-100">
                      <UserCheck className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                      Vigil Compliance Officer / Reviewer
                    </div>
                    {isLoadingUsers ? (
                      <div className="flex items-center gap-2 text-xs text-slate-400 mt-2">
                        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading system users...
                      </div>
                    ) : (
                      <select
                        value={selectedUserEmail}
                        onChange={(e) => setSelectedUserEmail(e.target.value)}
                        disabled={recipientType !== "vigil_user"}
                        className="mt-2 w-full text-xs font-medium rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 py-1.5 px-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60"
                      >
                        {users?.map((u) => (
                          <option key={u.user_id} value={u.email}>
                            {u.full_name} ({u.role}) — {u.email}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                </label>

                {/* Option B: RM Direct Email */}
                {rmEmail ? (
                  <label
                    className={`flex items-start gap-3 p-3.5 rounded-lg border cursor-pointer transition-colors ${
                      recipientType === "rm_email"
                        ? "border-indigo-600 bg-indigo-50/40 dark:bg-indigo-950/20 dark:border-indigo-500"
                        : "border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40"
                    }`}
                  >
                    <input
                      type="radio"
                      name="recipient_option"
                      checked={recipientType === "rm_email"}
                      onChange={() => setRecipientType("rm_email")}
                      className="mt-1 text-indigo-600 focus:ring-indigo-500"
                    />
                    <div className="flex-1">
                      <div className="text-xs font-bold text-slate-900 dark:text-slate-100">
                        Send Directly to RM
                      </div>
                      <div className="text-xs font-mono text-slate-500 mt-0.5">{rmEmail}</div>
                    </div>
                  </label>
                ) : null}

                {/* Option C: Custom Email */}
                <label
                  className={`flex items-start gap-3 p-3.5 rounded-lg border cursor-pointer transition-colors ${
                    recipientType === "custom"
                      ? "border-indigo-600 bg-indigo-50/40 dark:bg-indigo-950/20 dark:border-indigo-500"
                      : "border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40"
                  }`}
                >
                  <input
                    type="radio"
                    name="recipient_option"
                    checked={recipientType === "custom"}
                    onChange={() => setRecipientType("custom")}
                    className="mt-1 text-indigo-600 focus:ring-indigo-500"
                  />
                  <div className="flex-1 space-y-2">
                    <div className="text-xs font-bold text-slate-900 dark:text-slate-100">
                      Custom Email Recipient
                    </div>
                    <input
                      type="email"
                      placeholder="e.g. audit.officer@vigil.com"
                      value={customEmail}
                      onChange={handleCustomEmailChange}
                      disabled={recipientType !== "custom"}
                      className="w-full text-xs font-medium rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 py-1.5 px-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60"
                    />
                    {customEmailError && (
                      <p className="text-[11px] text-red-600 dark:text-red-400 font-medium">
                        {customEmailError}
                      </p>
                    )}

                    {/* Section 52.1 External Domain Warning */}
                    {isExternalDomain && !customEmailError && (
                      <div className="p-2.5 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/60 rounded text-[11px] text-amber-800 dark:text-amber-300 flex items-start gap-2">
                        <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                        <div>
                          <strong>External Domain Advisory:</strong> This recipient is outside the organization. The generated report contains sensitive customer KYC and compliance audit telemetry.
                        </div>
                      </div>
                    )}
                  </div>
                </label>
              </div>

              {/* Report Contents Checklist */}
              <div className="p-3.5 bg-slate-50 dark:bg-slate-950/40 border border-slate-200 dark:border-slate-800 rounded-lg text-xs space-y-2">
                <div className="font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                  Report Payload Includes
                </div>
                <div className="grid grid-cols-2 gap-1.5 text-slate-600 dark:text-slate-400">
                  <div className="flex items-center gap-1">✓ RM identity & branch profile</div>
                  <div className="flex items-center gap-1">✓ Monitored call analytics</div>
                  <div className="flex items-center gap-1">✓ Confirmed statutory findings</div>
                  <div className="flex items-center gap-1">✓ Case details & reviewer state</div>
                  <div className="flex items-center gap-1">✓ Acoustic evidence excerpts</div>
                  <div className="flex items-center gap-1">✓ SEBI/AMFI regulatory references</div>
                </div>
              </div>

              {/* Error Banner */}
              {sendMutation.isError && (
                <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-lg text-xs text-red-800 dark:text-red-300 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                  <div>
                    <strong>Dispatch Failed:</strong>{" "}
                    {sendMutation.error instanceof Error
                      ? sendMutation.error.message
                      : "Unable to send the report. Please verify recipient address or email service configuration."}
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={sendMutation.isPending}
                  className="px-4 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSend}
                  disabled={isSendDisabled}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  {sendMutation.isPending ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Sending Report...
                    </>
                  ) : (
                    <>
                      <Send className="w-3.5 h-3.5" />
                      Send Report on Mail
                    </>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
