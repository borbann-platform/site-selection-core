import { createFileRoute } from "@tanstack/react-router";
import {
  Settings as SettingsIcon,
  Database,
  Bell,
  Shield,
  User,
  RefreshCw,
  Trash2,
  Loader2,
  CheckCircle,
  XCircle,
  LogOut,
} from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import { api, type AdminCacheStatusResponse } from "../../lib/api";
import { useAuth } from "../../contexts/AuthContext";

export const Route = createFileRoute("/_authenticated/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  const { user, logout } = useAuth();
  const [cacheStatus, setCacheStatus] =
    useState<AdminCacheStatusResponse | null>(null);
  const [isRefreshingPOIs, setIsRefreshingPOIs] = useState(false);
  const [isClearingCache, setIsClearingCache] = useState(false);
  const [lastAction, setLastAction] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  // Fetch cache status on mount and after actions
  const fetchCacheStatus = useCallback(async () => {
    try {
      const status = await api.getCacheStatus();
      setCacheStatus(status);
    } catch (e) {
      console.error("Failed to fetch cache status:", e);
    }
  }, []);

  useEffect(() => {
    fetchCacheStatus();
  }, [fetchCacheStatus]);

  const handleRefreshPOIs = async () => {
    setIsRefreshingPOIs(true);
    setLastAction(null);
    try {
      const result = await api.refreshPOIs();
      setLastAction({ type: "success", message: result.message });
      fetchCacheStatus();
    } catch (e) {
      setLastAction({
        type: "error",
        message: e instanceof Error ? e.message : "Failed to refresh POI data",
      });
    } finally {
      setIsRefreshingPOIs(false);
    }
  };

  const handleClearCache = async () => {
    setIsClearingCache(true);
    setLastAction(null);
    try {
      const result = await api.clearTileCache();
      setLastAction({ type: "success", message: result.message });
      fetchCacheStatus();
    } catch (e) {
      setLastAction({
        type: "error",
        message: e instanceof Error ? e.message : "Failed to clear cache",
      });
    } finally {
      setIsClearingCache(false);
    }
  };

  return (
    <div className="h-full w-full bg-background text-foreground overflow-y-auto custom-scrollbar">
        <div className="max-w-4xl mx-auto py-12 px-6">
          <div className="flex items-center gap-4 mb-8">
            <div className="p-3 bg-muted rounded-xl">
              <SettingsIcon size={32} className="text-emerald-400" />
            </div>
            <div>
              <h1 className="text-3xl font-bold">Settings</h1>
              <p className="text-muted-foreground">
                Manage your preferences and account
              </p>
            </div>
          </div>

          <div className="grid gap-8">
            {/* Profile & Account */}
            <section className="space-y-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <User size={20} className="text-blue-400" />
                Profile & Account
              </h2>
              <div className="bg-card border border-border rounded-2xl overflow-hidden">
                <div className="p-6 border-b border-border flex items-center justify-between">
                  <div>
                    <div className="font-medium">Display Name</div>
                    <div className="text-sm text-muted-foreground">
                      How you appear to others
                    </div>
                  </div>
                  <div className="text-muted-foreground">
                    {user?.first_name} {user?.last_name}
                  </div>
                </div>
                <div className="p-6 border-b border-border flex items-center justify-between">
                  <div>
                    <div className="font-medium">Email Address</div>
                    <div className="text-sm text-muted-foreground">
                      Used for notifications
                    </div>
                  </div>
                  <div className="text-muted-foreground">{user?.email}</div>
                </div>
                <div className="p-6 flex items-center justify-between">
                  <div>
                    <div className="font-medium">Sign Out</div>
                    <div className="text-sm text-muted-foreground">
                      End your current session
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={logout}
                    className="flex items-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg text-sm font-medium transition-colors"
                  >
                    <LogOut size={16} />
                    Sign Out
                  </button>
                </div>
              </div>
            </section>

            {/* Data Preferences */}
            <section className="space-y-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Database size={20} className="text-purple-400" />
                Data & Analysis
              </h2>
              <div className="bg-card border border-border rounded-2xl overflow-hidden">
                <div className="p-6 border-b border-border flex items-center justify-between">
                  <div>
                    <div className="font-medium">Default Search Radius</div>
                    <div className="text-sm text-muted-foreground">
                      Base radius for site analysis
                    </div>
                  </div>
                  <select className="bg-input border border-border rounded px-3 py-1 text-sm">
                    <option>1 km</option>
                    <option>2 km</option>
                    <option>5 km</option>
                  </select>
                </div>
                <div className="p-6 flex items-center justify-between">
                  <div>
                    <div className="font-medium">Isochrone Mode</div>
                    <div className="text-sm text-muted-foreground">
                      Default travel mode for catchments
                    </div>
                  </div>
                  <div className="flex bg-input rounded-lg p-1 border border-border">
                    <button
                      type="button"
                      className="px-3 py-1 rounded bg-muted text-xs font-bold"
                    >
                      Walk
                    </button>
                    <button
                      type="button"
                      className="px-3 py-1 rounded text-muted-foreground text-xs font-bold hover:text-foreground"
                    >
                      Drive
                    </button>
                  </div>
                </div>
              </div>
            </section>

            {/* Notifications */}
            <section className="space-y-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Bell size={20} className="text-yellow-400" />
                Notifications
              </h2>
              <div className="bg-card border border-border rounded-2xl overflow-hidden">
                <div className="p-6 flex items-center justify-between">
                  <div>
                    <div className="font-medium">Report Ready Alerts</div>
                    <div className="text-sm text-muted-foreground">
                      Email me when large reports are done
                    </div>
                  </div>
                  <div className="w-10 h-6 bg-emerald-500 rounded-full relative cursor-pointer">
                    <div className="absolute right-1 top-1 w-4 h-4 bg-white rounded-full shadow-sm" />
                  </div>
                </div>
              </div>
            </section>

            {/* Security */}
            <section className="space-y-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Shield size={20} className="text-red-400" />
                Security
              </h2>
              <div className="bg-card border border-border rounded-2xl overflow-hidden">
                <div className="p-6 flex items-center justify-between">
                  <div>
                    <div className="font-medium">API Keys</div>
                    <div className="text-sm text-muted-foreground">
                      Manage access tokens
                    </div>
                  </div>
                  <button
                    type="button"
                    className="text-sm font-bold text-muted-foreground hover:text-foreground"
                  >
                    Manage
                  </button>
                </div>
              </div>
            </section>

            {/* Data Management (Admin) */}
            <section className="space-y-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <RefreshCw size={20} className="text-cyan-400" />
                Data Management
              </h2>

              {/* Status message */}
              {lastAction && (
                <div
                  className={`flex items-center gap-2 p-3 rounded-lg ${
                    lastAction.type === "success"
                      ? "bg-emerald-500/20 text-emerald-400"
                      : "bg-red-500/20 text-red-400"
                  }`}
                >
                  {lastAction.type === "success" ? (
                    <CheckCircle size={16} />
                  ) : (
                    <XCircle size={16} />
                  )}
                  <span className="text-sm">{lastAction.message}</span>
                </div>
              )}

              <div className="bg-card border border-border rounded-2xl overflow-hidden">
                {/* Cache Status */}
                <div className="p-6 border-b border-border flex items-center justify-between">
                  <div>
                    <div className="font-medium">Tile Cache Status</div>
                    <div className="text-sm text-muted-foreground">
                      Cached tiles for faster map loading
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-mono text-emerald-400">
                      {cacheStatus?.tile_cache_size ?? "—"}
                    </div>
                    <div className="text-xs text-muted-foreground">tiles cached</div>
                  </div>
                </div>

                {/* Refresh POI Data */}
                <div className="p-6 border-b border-border flex items-center justify-between">
                  <div>
                    <div className="font-medium">Refresh POI Data</div>
                    <div className="text-sm text-muted-foreground">
                      Update materialized view from source tables
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={handleRefreshPOIs}
                    disabled={isRefreshingPOIs}
                    className="flex items-center gap-2 px-4 py-2 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-400 rounded-lg text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {isRefreshingPOIs ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <RefreshCw size={16} />
                    )}
                    {isRefreshingPOIs ? "Refreshing..." : "Refresh POIs"}
                  </button>
                </div>

                {/* Clear Tile Cache */}
                <div className="p-6 flex items-center justify-between">
                  <div>
                    <div className="font-medium">Clear Tile Cache</div>
                    <div className="text-sm text-muted-foreground">
                      Force fresh tile generation on next load
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={handleClearCache}
                    disabled={isClearingCache}
                    className="flex items-center gap-2 px-4 py-2 bg-orange-500/20 hover:bg-orange-500/30 text-orange-400 rounded-lg text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {isClearingCache ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <Trash2 size={16} />
                    )}
                    {isClearingCache ? "Clearing..." : "Clear Cache"}
                  </button>
                </div>
              </div>
            </section>
          </div>
        </div>
    </div>
  );
}
