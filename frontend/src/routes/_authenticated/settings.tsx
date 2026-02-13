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
  LogOut,
} from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import { api, type AdminCacheStatusResponse } from "../../lib/api";
import { useAuth } from "../../contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";

export const Route = createFileRoute("/_authenticated/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  const { user, logout } = useAuth();
  const [cacheStatus, setCacheStatus] =
    useState<AdminCacheStatusResponse | null>(null);
  const [isRefreshingPOIs, setIsRefreshingPOIs] = useState(false);
  const [isClearingCache, setIsClearingCache] = useState(false);
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [isochroneMode, setIsochroneMode] = useState<"walk" | "drive">("walk");

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
    try {
      const result = await api.refreshPOIs();
      toast.success(result.message);
      fetchCacheStatus();
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "Failed to refresh POI data"
      );
    } finally {
      setIsRefreshingPOIs(false);
    }
  };

  const handleClearCache = async () => {
    setIsClearingCache(true);
    try {
      const result = await api.clearTileCache();
      toast.success(result.message);
      fetchCacheStatus();
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "Failed to clear cache"
      );
    } finally {
      setIsClearingCache(false);
    }
  };

  return (
    <div className="h-full w-full bg-background text-foreground overflow-y-auto custom-scrollbar">
        <div className="max-w-4xl mx-auto py-12 px-6">
          <div className="flex items-center gap-4 mb-8">
            <div className="p-3 bg-muted rounded-xl">
              <SettingsIcon size={32} className="text-brand" />
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
                <User size={20} className="text-brand" />
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
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={logout}
                  >
                    <LogOut size={16} />
                    Sign Out
                  </Button>
                </div>
              </div>
            </section>

            {/* Data Preferences */}
            <section className="space-y-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Database size={20} className="text-ai-accent" />
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
                  <Select defaultValue="1">
                    <SelectTrigger size="sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">1 km</SelectItem>
                      <SelectItem value="2">2 km</SelectItem>
                      <SelectItem value="5">5 km</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="p-6 flex items-center justify-between">
                  <div>
                    <div className="font-medium">Isochrone Mode</div>
                    <div className="text-sm text-muted-foreground">
                      Default travel mode for catchments
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <Button
                      variant={isochroneMode === "walk" ? "secondary" : "ghost"}
                      size="sm"
                      onClick={() => setIsochroneMode("walk")}
                    >
                      Walk
                    </Button>
                    <Button
                      variant={isochroneMode === "drive" ? "secondary" : "ghost"}
                      size="sm"
                      onClick={() => setIsochroneMode("drive")}
                    >
                      Drive
                    </Button>
                  </div>
                </div>
              </div>
            </section>

            {/* Notifications */}
            <section className="space-y-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Bell size={20} className="text-warning" />
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
                  <Switch
                    checked={notificationsEnabled}
                    onCheckedChange={setNotificationsEnabled}
                  />
                </div>
              </div>
            </section>

            {/* Security */}
            <section className="space-y-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Shield size={20} className="text-destructive" />
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
                <RefreshCw size={20} className="text-brand" />
                Data Management
              </h2>

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
                    <div className="text-lg font-mono text-brand">
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
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRefreshPOIs}
                    disabled={isRefreshingPOIs}
                  >
                    {isRefreshingPOIs ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <RefreshCw size={16} />
                    )}
                    {isRefreshingPOIs ? "Refreshing..." : "Refresh POIs"}
                  </Button>
                </div>

                {/* Clear Tile Cache */}
                <div className="p-6 flex items-center justify-between">
                  <div>
                    <div className="font-medium">Clear Tile Cache</div>
                    <div className="text-sm text-muted-foreground">
                      Force fresh tile generation on next load
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleClearCache}
                    disabled={isClearingCache}
                    className="text-destructive"
                  >
                    {isClearingCache ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <Trash2 size={16} />
                    )}
                    {isClearingCache ? "Clearing..." : "Clear Cache"}
                  </Button>
                </div>
              </div>
            </section>
          </div>
        </div>
    </div>
  );
}
