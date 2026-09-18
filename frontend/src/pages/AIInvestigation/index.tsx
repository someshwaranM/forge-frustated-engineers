import React, { useState, useEffect, useRef } from "react";
import { useSendChatMessage } from "../../services/chatService";
import { ChatMessage } from "../../types";
import { ChatMessageCard } from "../../components/shared/ChatMessageCard";
import {
  Send,
  Bot,
  HelpCircle,
  RotateCcw,
} from "lucide-react";

const STORAGE_KEY_SESSION = "vigil_chat_session_id";
const STORAGE_KEY_MESSAGES = "vigil_chat_messages";

const INITIAL_MESSAGE: ChatMessage = {
  id: "init-1",
  role: "assistant",
  content:
    "Welcome to the Vigil AI Compliance Investigator. I am grounded directly in your MySQL case tables, Elasticsearch call audio transcripts, and indexed SEBI/AMFI regulatory corpus. Ask any question to inspect advisory interactions.",
  timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
};

function getOrCreateSessionId(): string {
  const existing = sessionStorage.getItem(STORAGE_KEY_SESSION);
  if (existing) return existing;
  const newId =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `sess-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
  sessionStorage.setItem(STORAGE_KEY_SESSION, newId);
  return newId;
}

function loadMessages(): ChatMessage[] {
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY_MESSAGES);
    if (stored) {
      const parsed = JSON.parse(stored) as ChatMessage[];
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch {
    // ignore malformed storage
  }
  return [INITIAL_MESSAGE];
}

export const AIInvestigation: React.FC = () => {
  const [sessionId, setSessionId] = useState<string>(getOrCreateSessionId);
  const [messages, setMessages] = useState<ChatMessage[]>(loadMessages);
  const [inputValue, setInputValue] = useState("");
  const isFirstRender = useRef(true);

  // Persist messages to sessionStorage whenever they change
  useEffect(() => {
    // Skip the very first render to avoid overwriting storage with the
    // possibly-stale initializer value before loadMessages() has been resolved.
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    sessionStorage.setItem(STORAGE_KEY_MESSAGES, JSON.stringify(messages));
  }, [messages]);

  const sendChatMessageMutation = useSendChatMessage();

  const sampleQueries = [
    "Which RM has the most repeat violations?",
    "Show high-severity findings this month",
    "Find calls where guaranteed returns were mentioned",
    "What SEBI circular applies to suitability mismatch?",
  ];

  const handleSend = (textToSend?: string) => {
    const text = textToSend || inputValue.trim();
    if (!text || sendChatMessageMutation.isPending) return;

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputValue("");

    sendChatMessageMutation.mutate(
      {
        session_id: sessionId,
        message: text,
      },
      {
        onSuccess: (res) => {
          // Identify any grounded case
          const caseGrounded = res.grounded_results?.find(
            (g: any) => g.type === "case" || g.id.startsWith("CASE-")
          );

          const assistantMsg: ChatMessage = {
            id: `msg-${Date.now() + 1}`,
            role: "assistant",
            content: res.response_text,
            timestamp: new Date().toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
            tools_called: res.tool_calls_made || [],
            grounded_results: res.grounded_results || [],
            grounded_case: caseGrounded
              ? {
                case_id: caseGrounded.id,
                severity: "HIGH",
                finding_category: "Grounded Compliance Case",
                summary: `Investigator agent grounded finding via tools: ${(res.tool_calls_made || []).join(", ") || "search"}.`,
                confidence: 0.94,
                rm_name: "Investigated Subject",
              }
              : undefined,
          };

          setMessages((prev) => [...prev, assistantMsg]);
        },
        onError: (err: any) => {
          const errMsg: ChatMessage = {
            id: `err-${Date.now()}`,
            role: "assistant",
            content: `Investigation query failed: ${err?.message || "Server error communicating with agent builder"}.`,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          };
          setMessages((prev) => [...prev, errMsg]);
        },
      }
    );
  };

  const handleReset = () => {
    const newId =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `sess-${Date.now()}`;
    sessionStorage.setItem(STORAGE_KEY_SESSION, newId);
    sessionStorage.removeItem(STORAGE_KEY_MESSAGES);
    setSessionId(newId);
    setMessages([
      {
        id: `init-${Date.now()}`,
        role: "assistant",
        content: "Investigation session reset. Conversation context cleared.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)] bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-6 py-3.5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/60 dark:bg-slate-950/40">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 flex items-center justify-center">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
              Grounded AI Investigator
            </h2>
            <p className="text-[11px] text-slate-500">
              Natural-language inquiry grounded against call transcripts & SEBI/AMFI regulatory corpus
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs text-slate-400">
          <span className="font-mono text-[11px] hidden sm:inline">
            Session: {sessionId.substring(0, 8)}...
          </span>
          <button
            type="button"
            onClick={handleReset}
            className="p-1.5 rounded hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100 transition-colors flex items-center gap-1 text-xs font-medium cursor-pointer"
            title="Reset conversation session"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span className="hidden md:inline">Reset Context</span>
          </button>
        </div>
      </div>

      {/* Suggested Quick Inquiries */}
      <div className="px-6 py-2 bg-slate-50 dark:bg-slate-950/20 border-b border-slate-100 dark:border-slate-800 flex flex-wrap items-center gap-2">
        <span className="text-[11px] text-slate-400 flex items-center gap-1">
          <HelpCircle className="w-3 h-3" /> Quick queries:
        </span>
        {sampleQueries.map((query) => (
          <button
            key={query}
            type="button"
            onClick={() => handleSend(query)}
            disabled={sendChatMessageMutation.isPending}
            className="text-[11px] px-2.5 py-1 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer disabled:opacity-50"
          >
            &ldquo;{query}&rdquo;
          </button>
        ))}
      </div>

      {/* Message List */}
      <div className="flex-1 p-6 overflow-y-auto space-y-4">
        {messages.map((msg) => (
          <ChatMessageCard key={msg.id} message={msg} />
        ))}

        {sendChatMessageMutation.isPending && (
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400 p-2">
            <Bot className="w-4 h-4 animate-spin text-blue-500" />
            <span>Agent executing tool queries against Elasticsearch & MySQL...</span>
          </div>
        )}
      </div>

      {/* Input Box */}
      <div className="p-4 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center gap-2"
        >
          <div className="relative flex-1">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              disabled={sendChatMessageMutation.isPending}
              placeholder="Ask anything about calls, RMs, risk mismatches, or SEBI circular clauses..."
              className="w-full pl-4 pr-10 py-2.5 text-sm bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg focus:outline-none focus:ring-1 focus:ring-slate-400 dark:focus:ring-slate-600 placeholder:text-slate-400 disabled:opacity-50"
            />
          </div>
          <button
            type="submit"
            disabled={!inputValue.trim() || sendChatMessageMutation.isPending}
            className="px-4 py-2.5 bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 hover:bg-slate-800 dark:hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-semibold flex items-center gap-1.5 transition-colors shadow-sm cursor-pointer"
          >
            <span>Ask</span>
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>
    </div>
  );
};
