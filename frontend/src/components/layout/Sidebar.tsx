import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Bot,
  PhoneCall,
  ShieldAlert,
  Users,
  FileCheck2,
  Settings,
  Shield,
  Activity,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { useSidebar } from "../../context/SidebarContext";

const NAV_ITEMS = [
  { label: "Dashboard", path: "/", icon: LayoutDashboard },
  { label: "AI Investigation", path: "/ai-investigation", icon: Bot },
  { label: "Calls", path: "/calls", icon: PhoneCall },
  { label: "Compliance Cases", path: "/cases", icon: ShieldAlert },
  { label: "RM Analytics", path: "/rm-analytics", icon: Users },
  { label: "Regulations", path: "/regulations", icon: FileCheck2 },
  { label: "Observability", path: "/observability", icon: Activity },
  { label: "Settings", path: "/settings", icon: Settings },
];

export const Sidebar: React.FC = () => {
  const { isCollapsed, toggleSidebar } = useSidebar();

  return (
    <aside
      className={cn(
        "bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col shrink-0 h-screen sticky top-0 transition-all duration-300 ease-in-out",
        isCollapsed ? "w-[68px]" : "w-64"
      )}
    >
      {/* Brand Header */}
      <div
        className={cn(
          "h-16 flex items-center border-b border-slate-200 dark:border-slate-800 transition-all duration-300",
          isCollapsed ? "justify-center px-3" : "gap-2.5 px-6"
        )}
      >
        <div className="w-8 h-8 rounded bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 flex items-center justify-center font-bold shadow-sm shrink-0">
          <Shield className="w-4 h-4 text-red-500" />
        </div>

        {/* Brand Text — only visible when expanded */}
        <div
          className={cn(
            "overflow-hidden transition-all duration-300",
            isCollapsed ? "w-0 opacity-0" : "w-auto opacity-100"
          )}
        >
          <h1 className="font-bold text-sm tracking-wider text-slate-900 dark:text-slate-100 flex items-center gap-1.5 whitespace-nowrap">
            VIGIL{" "}
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
              AUDIT
            </span>
          </h1>
          <p className="text-[10px] text-slate-400 tracking-tight whitespace-nowrap">
            Compliance Surveillance AI
          </p>
        </div>
      </div>

      {/* Navigation list */}
      <nav className="flex-1 px-2 py-4 space-y-0.5 overflow-y-auto overflow-x-hidden">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/"}
              title={isCollapsed ? item.label : undefined}
              className={({ isActive }) =>
                cn(
                  "flex items-center rounded-md text-xs font-medium transition-all duration-200 group relative",
                  isCollapsed ? "px-0 py-2.5 justify-center" : "gap-3 px-3.5 py-2.5",
                  isActive
                    ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 font-semibold shadow-sm"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800/60"
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    className={cn(
                      "w-4 h-4 shrink-0 transition-colors",
                      isActive
                        ? "text-red-400 dark:text-red-600"
                        : "text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300"
                    )}
                  />

                  {/* Nav label — only visible when expanded */}
                  <span
                    className={cn(
                      "overflow-hidden whitespace-nowrap transition-all duration-300",
                      isCollapsed ? "w-0 opacity-0" : "w-auto opacity-100"
                    )}
                  >
                    {item.label}
                  </span>

                  {/* Tooltip on collapsed state */}
                  {isCollapsed && (
                    <div className="absolute left-full ml-3 px-2 py-1 bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 text-xs rounded-md opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-150 whitespace-nowrap z-50 shadow-lg">
                      {item.label}
                    </div>
                  )}
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Bottom Section — Status Box + Collapse Toggle */}
      <div className="border-t border-slate-200 dark:border-slate-800">
        {/* Status badge — hidden when collapsed */}
        {!isCollapsed && (
          <div className="p-4">
            <div className="p-2.5 rounded bg-slate-50 dark:bg-slate-950/50 border border-slate-100 dark:border-slate-800/80 text-[11px] space-y-1">
              <div className="flex items-center justify-between text-slate-500">
                <span>Surveillance Mode</span>
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              </div>
              <p className="font-mono text-xs font-semibold text-slate-800 dark:text-slate-200">
                SEBI / AMFI Real-Time
              </p>
            </div>
          </div>
        )}

        {/* Collapsed mini status dot */}
        {isCollapsed && (
          <div className="py-3 flex justify-center">
            <span
              className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"
              title="Surveillance Mode Active"
            />
          </div>
        )}

        {/* Collapse / Expand Toggle Button */}
        <div className={cn("pb-4", isCollapsed ? "flex justify-center" : "px-4")}>
          <button
            type="button"
            onClick={toggleSidebar}
            title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
            className={cn(
              "flex items-center gap-2 rounded-md text-xs font-medium text-slate-500 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800/60 transition-all cursor-pointer",
              isCollapsed ? "p-2 justify-center" : "w-full px-3.5 py-2"
            )}
          >
            {isCollapsed ? (
              <ChevronRight className="w-4 h-4 shrink-0" />
            ) : (
              <>
                <ChevronLeft className="w-4 h-4 shrink-0" />
                <span>Collapse</span>
              </>
            )}
          </button>
        </div>
      </div>
    </aside>
  );
};
