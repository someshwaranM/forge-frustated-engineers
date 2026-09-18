// frontend/src/components/auth/ProtectedRoute.tsx
import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { Shield, Loader2 } from "lucide-react";

interface ProtectedRouteProps {
  children?: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen w-full flex flex-col items-center justify-center bg-slate-950 text-slate-100 p-6">
        <div className="relative flex items-center justify-center mb-6">
          <div className="w-16 h-16 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center shadow-2xl relative z-10">
            <Shield className="w-8 h-8 text-red-500 animate-pulse" />
          </div>
          <div className="absolute inset-0 w-16 h-16 rounded-xl bg-red-500/20 blur-xl animate-pulse" />
        </div>
        <div className="flex items-center gap-2.5 text-slate-300 font-mono text-sm">
          <Loader2 className="w-4 h-4 animate-spin text-red-500" />
          <span>Verifying Vigil Surveillance Session...</span>
        </div>
        <p className="text-xs text-slate-500 mt-2 font-mono">SEBI / AMFI Real-Time Compliance</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children ? <>{children}</> : null;
};
