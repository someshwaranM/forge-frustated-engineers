import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Search,
  Sun,
  Moon,
  Sparkles,
  Activity,
  Database,
  LogOut,
  ShieldCheck,
  Building2,
  Mail,
  User,
  ChevronDown,
  PanelLeftClose,
  PanelLeftOpen,
  LayoutDashboard,
  Bot,
  PhoneCall,
  ShieldAlert,
  Users,
  FileCheck2,
  Settings,
  ArrowRight,
  X,
} from "lucide-react";
import { useTheme } from "../../context/ThemeContext";
import { useAuth } from "../../context/AuthContext";
import { useSidebar } from "../../context/SidebarContext";
import { useSystemHealth } from "../../services/systemService";
import { useNavigate } from "react-router-dom";

// ---------------------------------------------------------------------------
// All navigable destinations
// ---------------------------------------------------------------------------
const ALL_PAGES = [
  { label: "Dashboard", path: "/", icon: LayoutDashboard, keywords: ["dashboard", "overview", "home", "kpi"] },
  { label: "AI Investigation", path: "/ai-investigation", icon: Bot, keywords: ["ai", "chat", "investigator", "gemini", "agent"] },
  { label: "Calls", path: "/calls", icon: PhoneCall, keywords: ["calls", "audio", "transcripts", "recordings"] },
  { label: "Compliance Cases", path: "/cases", icon: ShieldAlert, keywords: ["cases", "compliance", "violations", "findings", "open"] },
  { label: "RM Analytics", path: "/rm-analytics", icon: Users, keywords: ["rm", "relationship manager", "analytics", "violations"] },
  { label: "Regulations", path: "/regulations", icon: FileCheck2, keywords: ["regulations", "sebi", "amfi", "documents", "corpus"] },
  { label: "Observability", path: "/observability", icon: Activity, keywords: ["observability", "errors", "pipeline", "latency", "apm", "elastic"] },
  { label: "Settings", path: "/settings", icon: Settings, keywords: ["settings", "config", "preferences"] },
];

interface SearchResult {
  type: "page" | "case" | "call";
  label: string;
  sublabel?: string;
  path: string;
  icon: React.ElementType;
}

function buildResults(query: string): SearchResult[] {
  const q = query.trim().toLowerCase();
  if (!q) return ALL_PAGES.map((p) => ({ type: "page" as const, label: p.label, path: p.path, icon: p.icon }));

  const results: SearchResult[] = [];

  // Page matches
  for (const page of ALL_PAGES) {
    const haystack = [page.label, ...page.keywords].join(" ").toLowerCase();
    if (haystack.includes(q)) {
      results.push({ type: "page", label: page.label, path: page.path, icon: page.icon });
    }
  }

  // Case ID pattern: starts with C- or is numeric-looking (e.g. C-001, CASE-123)
  if (/^(c-?|case-?)\w*/i.test(query) || /^\d{2,}/.test(query)) {
    results.push({
      type: "case",
      label: `Go to Case: ${query.toUpperCase()}`,
      sublabel: "Jump directly to compliance case",
      path: `/cases/${query.toUpperCase()}`,
      icon: ShieldAlert,
    });
  }

  // Call ID pattern: UUID-like or CALL- prefix
  if (/^[0-9a-f]{8}-/i.test(query) || /^(call-?|audio-?)\w*/i.test(query)) {
    results.push({
      type: "call",
      label: `Go to Call: ${query}`,
      sublabel: "Jump directly to call record",
      path: `/calls/${query}`,
      icon: PhoneCall,
    });
  }

  return results;
}

// ---------------------------------------------------------------------------
// Global Search Component
// ---------------------------------------------------------------------------
const GlobalSearch: React.FC = () => {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const results = buildResults(query);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setActiveIdx(0);
  }, []);

  const go = useCallback(
    (path: string) => {
      navigate(path);
      close();
      inputRef.current?.blur();
    },
    [navigate, close]
  );

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        close();
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [close]);

  // Global ⌘K / Ctrl+K to focus
  useEffect(() => {
    function handleGlobal(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    }
    document.addEventListener("keydown", handleGlobal);
    return () => document.removeEventListener("keydown", handleGlobal);
  }, []);

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Escape") { close(); return; }
    if (e.key === "ArrowDown") { e.preventDefault(); setActiveIdx((i) => Math.min(i + 1, results.length - 1)); return; }
    if (e.key === "ArrowUp") { e.preventDefault(); setActiveIdx((i) => Math.max(i - 1, 0)); return; }
    if (e.key === "Enter" && results[activeIdx]) { go(results[activeIdx].path); return; }
  }

  return (
    <div ref={containerRef} className="relative w-72">
      {/* Input */}
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); setActiveIdx(0); }}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        placeholder="Search pages, cases, calls… ⌘K"
        className="w-full pl-8 pr-8 py-1.5 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-md focus:outline-none focus:ring-1 focus:ring-slate-400 dark:focus:ring-slate-600 placeholder:text-slate-400"
      />
      {query && (
        <button
          onClick={close}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
        >
          <X className="w-3 h-3" />
        </button>
      )}

      {/* Dropdown */}
      {open && results.length > 0 && (
        <div className="absolute top-full left-0 mt-1.5 w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg shadow-xl z-50 overflow-hidden">
          {!query && (
            <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-100 dark:border-slate-800">
              Navigate to
            </div>
          )}
          <ul className="py-1 max-h-72 overflow-y-auto">
            {results.map((r, idx) => {
              const Icon = r.icon;
              const isActive = idx === activeIdx;
              return (
                <li key={r.path + idx}>
                  <button
                    type="button"
                    onMouseEnter={() => setActiveIdx(idx)}
                    onClick={() => go(r.path)}
                    className={`w-full flex items-center gap-3 px-3 py-2 text-left transition-colors ${
                      isActive
                        ? "bg-slate-100 dark:bg-slate-800"
                        : "hover:bg-slate-50 dark:hover:bg-slate-800/60"
                    }`}
                  >
                    <Icon className={`w-3.5 h-3.5 shrink-0 ${
                      r.type === "case" ? "text-red-500" :
                      r.type === "call" ? "text-blue-500" :
                      "text-slate-400"
                    }`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-slate-900 dark:text-slate-100 truncate">{r.label}</p>
                      {r.sublabel && (
                        <p className="text-[10px] text-slate-500 truncate">{r.sublabel}</p>
                      )}
                    </div>
                    {isActive && <ArrowRight className="w-3 h-3 text-slate-400 shrink-0" />}
                  </button>
                </li>
              );
            })}
          </ul>
          <div className="px-3 py-1.5 border-t border-slate-100 dark:border-slate-800 flex items-center gap-3 text-[10px] text-slate-400">
            <span><kbd className="font-mono bg-slate-100 dark:bg-slate-800 px-1 rounded">↑↓</kbd> navigate</span>
            <span><kbd className="font-mono bg-slate-100 dark:bg-slate-800 px-1 rounded">↵</kbd> go</span>
            <span><kbd className="font-mono bg-slate-100 dark:bg-slate-800 px-1 rounded">esc</kbd> close</span>
          </div>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Topbar
// ---------------------------------------------------------------------------
export const Topbar: React.FC = () => {
  const { isDark, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const { isCollapsed, toggleSidebar } = useSidebar();
  const { data: health } = useSystemHealth();
  const navigate = useNavigate();

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const esStatus = health?.services?.elasticsearch?.status;
  const isEsConnected = esStatus ? esStatus === "CONNECTED" : true;

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = async () => {
    setDropdownOpen(false);
    await logout();
    navigate("/login");
  };

  // Derive initials
  const initials = user?.full_name
    ? user.full_name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "AO";

  return (
    <header className="h-16 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-4 flex items-center justify-between sticky top-0 z-20">
      {/* Left: Sidebar Toggle + Search */}
      <div className="flex items-center gap-3">
        {/* Sidebar Toggle */}
        <button
          type="button"
          onClick={toggleSidebar}
          title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          className="p-2 rounded-md text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
        >
          {isCollapsed
            ? <PanelLeftOpen className="w-4 h-4" />
            : <PanelLeftClose className="w-4 h-4" />}
        </button>

        {/* Global Search */}
        <GlobalSearch />
      </div>


      {/* Topbar Right Actions & Status Indicators */}
      <div className="flex items-center gap-4">
        {/* Elastic Status Badge */}
        <div
          className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-mono border border-slate-200 dark:border-slate-700"
          title={health?.services?.elasticsearch?.message || "Elasticsearch Serverless live"}
        >
          <Database className="w-3.5 h-3.5 text-teal-500" />
          <span>Elastic:</span>
          <strong className="text-slate-900 dark:text-slate-100 flex items-center gap-1">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isEsConnected ? "bg-emerald-500 animate-pulse" : "bg-red-500"
              }`}
            />
            {isEsConnected ? "Connected" : "Offline"}
          </strong>
        </div>

        {/* Active AI Provider Status Badge */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-mono border border-slate-200 dark:border-slate-700">
          <Sparkles className="w-3.5 h-3.5 text-blue-500" />
          <span>Active Provider:</span>
          <strong className="text-slate-900 dark:text-slate-100">Bedrock</strong>
        </div>

        {/* Pipeline Latency Indicator */}
        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-mono border border-slate-200 dark:border-slate-700">
          <Activity className="w-3.5 h-3.5 text-emerald-500" />
          <span>Latency:</span>
          <strong className="text-slate-900 dark:text-slate-100">3.2s</strong>
        </div>

        {/* Theme Toggle Button */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-md text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
          title={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
          type="button"
        >
          {isDark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4" />}
        </button>

        {/* User Profile Badge & Dropdown */}
        <div className="relative pl-2 border-l border-slate-200 dark:border-slate-800" ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen((prev) => !prev)}
            type="button"
            className="flex items-center gap-2.5 p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800/80 transition-colors text-left cursor-pointer"
          >
            <div className="w-8 h-8 rounded-full bg-red-500/10 dark:bg-red-500/20 border border-red-500/30 flex items-center justify-center font-mono text-xs font-bold text-red-600 dark:text-red-400">
              {initials}
            </div>
            <div className="hidden lg:block text-left">
              <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 leading-tight">
                {user?.role || "Audit Officer"}
              </p>
              <p className="text-[10px] text-slate-500 dark:text-slate-400 font-medium">
                {user?.team || "Compliance"}
              </p>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 hidden sm:block" />
          </button>

          {/* Interactive User Dropdown */}
          {dropdownOpen && (
            <div className="absolute right-0 mt-2 w-72 bg-white dark:bg-slate-900 rounded-xl shadow-xl border border-slate-200 dark:border-slate-800 py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
              {/* Profile Header */}
              <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-red-500/10 dark:bg-red-500/20 border border-red-500/30 flex items-center justify-center font-mono text-sm font-bold text-red-600 dark:text-red-400">
                    {initials}
                  </div>
                  <div className="overflow-hidden">
                    <p className="text-sm font-bold text-slate-900 dark:text-slate-100 truncate">
                      {user?.full_name || "Audit Officer"}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 truncate flex items-center gap-1 font-mono">
                      <Mail className="w-3 h-3 shrink-0" />
                      {user?.email || "audit.officer@vigil.com"}
                    </p>
                  </div>
                </div>

                <div className="mt-2.5 flex items-center gap-1.5">
                  <span className="px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider rounded bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20">
                    {user?.role || "Audit Officer"}
                  </span>
                  <span className="px-2 py-0.5 text-[10px] font-medium rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                    {user?.team || "Compliance"}
                  </span>
                </div>
              </div>

              {/* Permissions & Details */}
              <div className="px-4 py-2.5 space-y-1.5 text-xs text-slate-600 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-[11px]">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                    Access Authorization
                  </span>
                  <span className="font-mono text-[11px] font-bold text-emerald-600 dark:text-emerald-400">
                    {user?.access || "All"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-[11px]">
                    <User className="w-3.5 h-3.5 text-slate-400" />
                    Account ID
                  </span>
                  <span className="font-mono text-[11px] text-slate-500">
                    {user?.user_id || "USR-001"}
                  </span>
                </div>
              </div>

              {/* Sign Out Action */}
              <div className="p-1">
                <button
                  onClick={handleLogout}
                  type="button"
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 rounded-lg transition-colors cursor-pointer"
                >
                  <LogOut className="w-4 h-4 shrink-0" />
                  <span>Sign Out of Surveillance Console</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
