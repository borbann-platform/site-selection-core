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
  KeyRound,
  Sparkles,
} from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import { api, type AdminCacheStatusResponse } from "../../lib/api";
import {
  chatApi,
  type ProviderCatalogResponse,
} from "../../lib/chatApi";
import {
  clearAgentRuntimeConfig,
  loadAgentRuntimeConfig,
  maskApiKey,
  saveAgentRuntimeConfig,
  type AgentProvider,
  type AgentRuntimeConfig,
} from "../../lib/agentRuntimeConfig";
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
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/PageHeader";

export const Route = createFileRoute("/_authenticated/settings")({
  component: SettingsPage,
});

const DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite";
const DEFAULT_OPENAI_COMPAT_MODEL = "glm-4.5";
const DEFAULT_OPENAI_COMPAT_BASE_URL = "https://api.z.ai/api/paas/v4";

function SettingsPage() {
  const { user, logout } = useAuth();
  const [cacheStatus, setCacheStatus] =
    useState<AdminCacheStatusResponse | null>(null);
  const [providerCatalog, setProviderCatalog] =
    useState<ProviderCatalogResponse | null>(null);
  const [isRefreshingPOIs, setIsRefreshingPOIs] = useState(false);
  const [isClearingCache, setIsClearingCache] = useState(false);
  const [isValidatingProvider, setIsValidatingProvider] = useState(false);
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [isochroneMode, setIsochroneMode] = useState<"walk" | "drive">("walk");
  const [rememberOnDevice, setRememberOnDevice] = useState(false);

  const [runtimeConfig, setRuntimeConfig] = useState<AgentRuntimeConfig>({
    provider: "gemini",
    model: DEFAULT_GEMINI_MODEL,
    api_key: "",
    reasoning_mode: "hybrid",
    use_vertex_ai: false,
    vertex_location: "us-central1",
  });

  const fetchCacheStatus = useCallback(async () => {
    try {
      const status = await api.getCacheStatus();
      setCacheStatus(status);
    } catch {
      // no-op
    }
  }, []);

  const fetchProviderCatalog = useCallback(async () => {
    try {
      const catalog = await chatApi.getProviderCatalog();
      setProviderCatalog(catalog);
    } catch {
      // no-op
    }
  }, []);

  useEffect(() => {
    fetchCacheStatus();
    fetchProviderCatalog();

    const stored = loadAgentRuntimeConfig();
    if (stored.config) {
      setRuntimeConfig(stored.config);
      setRememberOnDevice(stored.source === "local");
    }
  }, [fetchCacheStatus, fetchProviderCatalog]);

  const handleRefreshPOIs = async () => {
    setIsRefreshingPOIs(true);
    try {
      const result = await api.refreshPOIs();
      toast.success(result.message);
      fetchCacheStatus();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to refresh POI data");
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
      toast.error(e instanceof Error ? e.message : "Failed to clear cache");
    } finally {
      setIsClearingCache(false);
    }
  };

  const setProvider = (provider: AgentProvider) => {
    if (provider === "openai_compatible") {
      setRuntimeConfig((prev) => ({
        ...prev,
        provider,
        model:
          prev.provider === "openai_compatible"
            ? prev.model || DEFAULT_OPENAI_COMPAT_MODEL
            : DEFAULT_OPENAI_COMPAT_MODEL,
        base_url:
          prev.provider === "openai_compatible"
            ? prev.base_url || DEFAULT_OPENAI_COMPAT_BASE_URL
            : DEFAULT_OPENAI_COMPAT_BASE_URL,
      }));
      return;
    }

    setRuntimeConfig((prev) => ({
      ...prev,
      provider,
      model:
        prev.provider === "gemini"
          ? prev.model || DEFAULT_GEMINI_MODEL
          : DEFAULT_GEMINI_MODEL,
      base_url: undefined,
      organization: undefined,
      use_vertex_ai: Boolean(prev.use_vertex_ai),
      vertex_location: prev.vertex_location || "us-central1",
    }));
  };

  const handleSaveRuntimeConfig = () => {
    saveAgentRuntimeConfig(runtimeConfig, rememberOnDevice);
    toast.success(
      rememberOnDevice
        ? "BYOK model config saved on this device"
        : "BYOK model config saved for this browser session"
    );
  };

  const handleClearRuntimeConfig = () => {
    clearAgentRuntimeConfig();
    setRuntimeConfig({
      provider: "gemini",
      model: DEFAULT_GEMINI_MODEL,
      api_key: "",
      reasoning_mode: "hybrid",
      use_vertex_ai: false,
      vertex_location: "us-central1",
    });
    setRememberOnDevice(false);
    toast.success("BYOK model config cleared");
  };

  const handleValidateRuntimeConfig = async () => {
    setIsValidatingProvider(true);
    try {
      const result = await chatApi.validateProviderConfig(runtimeConfig);
      if (result.valid) {
        toast.success(`Validated ${result.provider} model: ${result.model}`);
      } else {
        toast.error("Provider config is incomplete. Please add credentials.");
      }
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "Failed to validate provider config"
      );
    } finally {
      setIsValidatingProvider(false);
    }
  };

  const isOpenAICompatible = runtimeConfig.provider === "openai_compatible";
  const maskedKey = maskApiKey(runtimeConfig.api_key);

  return (
    <div className="h-full w-full bg-background text-foreground overflow-y-auto custom-scrollbar">
      <div className="max-w-4xl mx-auto py-12 px-6">
        <PageHeader
          icon={SettingsIcon}
          title="Settings"
          subtitle="Manage your preferences, account, and AI provider configuration"
          className="mb-8"
        />

        <div className="grid gap-8">
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
                <Button variant="destructive" size="sm" onClick={logout}>
                  <LogOut size={16} />
                  Sign Out
                </Button>
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <Sparkles size={20} className="text-ai-accent" />
              AI Model Orchestration (BYOK)
            </h2>
            <div className="bg-card border border-border rounded-2xl overflow-hidden">
              <div className="p-6 border-b border-border space-y-4">
                <div className="grid gap-2">
                  <div className="text-sm font-medium">Provider</div>
                  <Select
                    value={runtimeConfig.provider}
                    onValueChange={(value) => setProvider(value as AgentProvider)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="gemini">Google Gemini</SelectItem>
                      <SelectItem value="openai_compatible">
                        OpenAI-Compatible (Ollama/vLLM/Groq/z.ai)
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid gap-2">
                  <div className="text-sm font-medium">Model</div>
                  <Input
                    value={runtimeConfig.model || ""}
                    onChange={(e) =>
                      setRuntimeConfig((prev) => ({
                        ...prev,
                        model: e.target.value,
                      }))
                    }
                    placeholder={
                      isOpenAICompatible ? DEFAULT_OPENAI_COMPAT_MODEL : DEFAULT_GEMINI_MODEL
                    }
                  />
                </div>

                <div className="grid gap-2">
                  <div className="text-sm font-medium">API Key</div>
                  <Input
                    type="password"
                    value={runtimeConfig.api_key || ""}
                    onChange={(e) =>
                      setRuntimeConfig((prev) => ({
                        ...prev,
                        api_key: e.target.value,
                      }))
                    }
                    placeholder="Paste your provider API key"
                  />
                  {maskedKey ? (
                    <div className="text-xs text-muted-foreground">
                      Current key: {maskedKey}
                    </div>
                  ) : null}
                </div>

                {isOpenAICompatible ? (
                  <>
                    <div className="grid gap-2">
                      <div className="text-sm font-medium">OpenAI-Compatible Base URL</div>
                      <Input
                        value={runtimeConfig.base_url || ""}
                        onChange={(e) =>
                          setRuntimeConfig((prev) => ({
                            ...prev,
                            base_url: e.target.value,
                          }))
                        }
                        placeholder={DEFAULT_OPENAI_COMPAT_BASE_URL}
                      />
                    </div>

                    <div className="grid gap-2">
                      <div className="text-sm font-medium">Organization (optional)</div>
                      <Input
                        value={runtimeConfig.organization || ""}
                        onChange={(e) =>
                          setRuntimeConfig((prev) => ({
                            ...prev,
                            organization: e.target.value,
                          }))
                        }
                        placeholder="org_xxx"
                      />
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex items-center justify-between py-1">
                      <div>
                        <div className="text-sm font-medium">Use Vertex AI</div>
                        <div className="text-xs text-muted-foreground">
                          Enable this when authenticating via GCP project/location.
                        </div>
                      </div>
                      <Switch
                        checked={Boolean(runtimeConfig.use_vertex_ai)}
                        onCheckedChange={(checked) =>
                          setRuntimeConfig((prev) => ({
                            ...prev,
                            use_vertex_ai: checked,
                          }))
                        }
                      />
                    </div>

                    {runtimeConfig.use_vertex_ai ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div className="grid gap-2">
                          <div className="text-sm font-medium">GCP Project ID</div>
                          <Input
                            value={runtimeConfig.vertex_project || ""}
                            onChange={(e) =>
                              setRuntimeConfig((prev) => ({
                                ...prev,
                                vertex_project: e.target.value,
                              }))
                            }
                            placeholder="my-gcp-project"
                          />
                        </div>
                        <div className="grid gap-2">
                          <div className="text-sm font-medium">Vertex Location</div>
                          <Input
                            value={runtimeConfig.vertex_location || ""}
                            onChange={(e) =>
                              setRuntimeConfig((prev) => ({
                                ...prev,
                                vertex_location: e.target.value,
                              }))
                            }
                            placeholder="us-central1"
                          />
                        </div>
                      </div>
                    ) : null}
                  </>
                )}

                <div className="grid gap-2">
                  <div className="text-sm font-medium">Reasoning Strategy</div>
                  <Select
                    value={runtimeConfig.reasoning_mode || "hybrid"}
                    onValueChange={(value) =>
                      setRuntimeConfig((prev) => ({
                        ...prev,
                        reasoning_mode: value as "react" | "cot" | "hybrid",
                      }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="hybrid">Hybrid (recommended)</SelectItem>
                      <SelectItem value="react">ReAct (tool-heavy)</SelectItem>
                      <SelectItem value="cot">CoT (logic-heavy)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center justify-between py-1">
                  <div>
                    <div className="text-sm font-medium">Remember on this device</div>
                    <div className="text-xs text-muted-foreground">
                      Off = session-only storage. On = persisted in local browser storage.
                    </div>
                  </div>
                  <Switch
                    checked={rememberOnDevice}
                    onCheckedChange={setRememberOnDevice}
                  />
                </div>

                <div className="text-xs text-muted-foreground bg-muted/40 border border-border rounded-lg px-3 py-2">
                  Keys are stored in your browser and sent only when making chat requests.
                  They are not persisted by the API.
                </div>
              </div>

              <div className="p-6 flex flex-wrap items-center gap-2">
                <Button type="button" onClick={handleSaveRuntimeConfig}>
                  <KeyRound size={16} />
                  Save BYOK Config
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleValidateRuntimeConfig}
                  disabled={isValidatingProvider}
                >
                  {isValidatingProvider ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Sparkles size={16} />
                  )}
                  {isValidatingProvider ? "Validating..." : "Validate Config"}
                </Button>
                <Button type="button" variant="ghost" onClick={handleClearRuntimeConfig}>
                  <Trash2 size={16} />
                  Clear
                </Button>
              </div>
            </div>

            {providerCatalog ? (
              <div className="text-xs text-muted-foreground border border-border rounded-lg p-3 bg-muted/30">
                Supported providers: {providerCatalog.supported_providers.map((p) => p.label).join(", ")}
              </div>
            ) : null}
          </section>

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
                    Manage BYOK credentials for model providers
                  </div>
                </div>
                <span className="text-xs text-muted-foreground">Managed above</span>
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <RefreshCw size={20} className="text-brand" />
              Data Management
            </h2>

            <div className="bg-card border border-border rounded-2xl overflow-hidden">
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
