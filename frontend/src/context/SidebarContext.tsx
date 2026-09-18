// frontend/src/context/SidebarContext.tsx
import React, { createContext, useContext, useState, useEffect, useCallback } from "react";

interface SidebarContextType {
  isCollapsed: boolean;
  toggleSidebar: () => void;
  setCollapsed: (collapsed: boolean) => void;
}

const SidebarContext = createContext<SidebarContextType | undefined>(undefined);

const STORAGE_KEY = "vigil_sidebar_collapsed";

export const SidebarProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isCollapsed, setIsCollapsedState] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved === "true";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(isCollapsed));
    } catch {
      // Ignore storage errors
    }
  }, [isCollapsed]);

  const toggleSidebar = useCallback(() => {
    setIsCollapsedState((prev) => !prev);
  }, []);

  const setCollapsed = useCallback((collapsed: boolean) => {
    setIsCollapsedState(collapsed);
  }, []);

  return (
    <SidebarContext.Provider
      value={{
        isCollapsed,
        toggleSidebar,
        setCollapsed,
      }}
    >
      {children}
    </SidebarContext.Provider>
  );
};

export const useSidebar = (): SidebarContextType => {
  const context = useContext(SidebarContext);
  if (!context) {
    throw new Error("useSidebar must be used within a SidebarProvider");
  }
  return context;
};
