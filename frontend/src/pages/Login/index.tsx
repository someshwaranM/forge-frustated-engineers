// frontend/src/pages/Login/index.tsx
import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../context/ThemeContext";
import {
  Shield,
  Lock,
  User,
  Eye,
  EyeOff,
  CheckCircle2,
  AlertCircle,
  Loader2,
  KeyRound,
  ShieldCheck,
  Building2,
  Sun,
  Moon,
} from "lucide-react";

export const Login: React.FC = () => {
  const { login, isAuthenticated } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // If already authenticated, redirect immediately
  React.useEffect(() => {
    if (isAuthenticated) {
      const origin = (location.state as any)?.from?.pathname || "/";
      navigate(origin, { replace: true });
    }
  }, [isAuthenticated, navigate, location]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError("Please enter both username/email and password.");
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      await login({
        username: username.trim(),
        password,
      });

      const origin = (location.state as any)?.from?.pathname || "/";
      navigate(origin, { replace: true });
    } catch (err: any) {
      const message =
        err?.data?.message ||
        err?.message ||
        "Invalid username or password. Please verify your credentials.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const fillDemoCredentials = () => {
    setUsername("admin");
    setPassword("admin12345");
    setError(null);
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 relative overflow-hidden selection:bg-red-500 selection:text-white px-4 py-8 transition-colors duration-200">
      {/* Dynamic Background Glows */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-red-500/10 dark:bg-red-600/15 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-[400px] h-[400px] bg-blue-500/10 dark:bg-blue-600/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#64748b0d_1px,transparent_1px),linear-gradient(to_bottom,#64748b0d_1px,transparent_1px)] dark:bg-[linear-gradient(to_right,#1e293b1a_1px,transparent_1px),linear-gradient(to_bottom,#1e293b1a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

      {/* Top Bar Floating Controls */}
      <div className="absolute top-6 right-6 flex items-center gap-3 z-20">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400 font-mono shadow-sm backdrop-blur-md">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Surveillance Engine v1.0</span>
        </div>
        <button
          onClick={toggleTheme}
          type="button"
          className="p-2 rounded-full bg-white/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 transition-colors shadow-sm backdrop-blur-md cursor-pointer"
          title={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
        >
          {isDark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-slate-600" />}
        </button>
      </div>

      {/* Main Login Container */}
      <div className="w-full max-w-md relative z-10">
        <div className="bg-white/90 dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800/90 rounded-2xl shadow-xl dark:shadow-2xl backdrop-blur-xl p-8 relative">
          {/* Header Brand */}
          <div className="flex flex-col items-center text-center mb-8">
            <div className="relative mb-3">
              <div className="w-14 h-14 rounded-xl bg-slate-100 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 flex items-center justify-center shadow-md">
                <Shield className="w-7 h-7 text-red-500" />
              </div>
              <span className="absolute -bottom-1 -right-1 flex h-4 w-4">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-4 w-4 bg-red-500 border-2 border-white dark:border-slate-900" />
              </span>
            </div>

            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-2xl font-bold tracking-wider text-slate-900 dark:text-slate-100 font-sans">
                VIGIL <span className="text-xs font-mono px-2 py-0.5 rounded bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400">AUDIT</span>
              </h1>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium tracking-tight">
              AI Surveillance & Compliance Enforcement System
            </p>
          </div>

          {/* User Role Quick Setup Card */}
          <div className="mb-6 p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800/80 text-left relative overflow-hidden group">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400 font-semibold flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  Designated Officer Session
                </span>
                <p className="text-xs font-semibold text-slate-900 dark:text-slate-200 mt-0.5">Audit Officer</p>
                <div className="flex items-center gap-2 mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                  <span className="flex items-center gap-1">
                    <Building2 className="w-3 h-3 text-slate-400 dark:text-slate-500" /> Compliance
                  </span>
                  <span>•</span>
                  <span className="font-mono text-emerald-600 dark:text-emerald-400 font-medium">Access: All</span>
                </div>
              </div>
              <button
                type="button"
                onClick={fillDemoCredentials}
                className="px-2.5 py-1 text-[11px] font-medium bg-red-500/10 hover:bg-red-500/20 text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 border border-red-500/30 rounded-md transition-all active:scale-95 cursor-pointer"
                title="Fill demo username and password"
              >
                Auto-Fill
              </button>
            </div>
          </div>

          {/* Error Notice */}
          {error && (
            <div className="mb-5 p-3 rounded-lg bg-red-500/10 border border-red-500/30 flex items-start gap-2.5 text-xs text-red-600 dark:text-red-300 animate-in fade-in">
              <AlertCircle className="w-4 h-4 shrink-0 text-red-500 dark:text-red-400 mt-0.5" />
              <div className="flex-1 leading-relaxed">{error}</div>
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Username / Email Field */}
            <div className="space-y-1.5 text-left">
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                Username or Email
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400 dark:text-slate-500">
                  <User className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="admin or audit.officer@vigil.com"
                  autoComplete="username"
                  required
                  className="w-full pl-10 pr-3.5 py-2.5 bg-white dark:bg-slate-950/80 border border-slate-300 dark:border-slate-800 rounded-lg text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-red-500/60 focus:ring-1 focus:ring-red-500/60 transition-all font-mono"
                />
              </div>
            </div>

            {/* Password Field */}
            <div className="space-y-1.5 text-left">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                  Password
                </label>
              </div>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400 dark:text-slate-500">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  autoComplete="current-password"
                  required
                  className="w-full pl-10 pr-10 py-2.5 bg-white dark:bg-slate-950/80 border border-slate-300 dark:border-slate-800 rounded-lg text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-red-500/60 focus:ring-1 focus:ring-red-500/60 transition-all font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300 transition-colors cursor-pointer"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Remember Me Toggle */}
            <div className="flex items-center justify-between pt-1">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="w-3.5 h-3.5 rounded bg-white dark:bg-slate-950 border-slate-300 dark:border-slate-800 text-red-600 focus:ring-0 focus:ring-offset-0 cursor-pointer accent-red-600"
                />
                <span className="text-xs text-slate-600 dark:text-slate-400">Remember session</span>
              </label>
              <span className="text-[11px] text-slate-400 dark:text-slate-500 font-mono">
                Audit Token: 24h
              </span>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full mt-2 py-2.5 px-4 rounded-lg bg-red-600 hover:bg-red-500 active:bg-red-700 text-white text-sm font-semibold tracking-wide shadow-lg shadow-red-600/20 transition-all flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed group cursor-pointer"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-white" />
                  <span>Authenticating Session...</span>
                </>
              ) : (
                <>
                  <KeyRound className="w-4 h-4 transition-transform group-hover:rotate-12" />
                  <span>Sign In to Surveillance Console</span>
                </>
              )}
            </button>
          </form>

          {/* Compliance & Security Guarantee Badges */}
          <div className="mt-8 pt-6 border-t border-slate-200 dark:border-slate-800/80">
            <div className="flex items-center justify-center gap-4 text-[10px] text-slate-500 dark:text-slate-400 font-mono">
              <span className="flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                SEBI Surveillance
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                AMFI Compliant
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                Audit Logs
              </span>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <p className="text-[11px] text-slate-400 dark:text-slate-600 text-center mt-6 font-mono">
          Vigil AI Compliance Surveillance Engine · Secure Enterprise Session
        </p>
      </div>
    </div>
  );
};
