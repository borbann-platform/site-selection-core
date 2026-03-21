import { createFileRoute } from "@tanstack/react-router";
import {
  KeyRound,
  Loader2,
  LogOut,
  Shield,
  Sparkles,
  Trash2,
  User,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "../../contexts/AuthContext";
import {
  type AgentProvider,
  type AgentRuntimeConfig,
  maskApiKey,
} from "../../lib/agentRuntimeConfig";
import { chatApi, type ProviderCatalogResponse } from "../../lib/chatApi";

export const Route = createFileRoute("/_authenticated/settings")({
  component: SettingsPage,
});

const DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite";
const DEFAULT_OPENAI_COMPAT_MODEL = "deepseek-chat";
const DEFAULT_OPENAI_COMPAT_BASE_URL = "https://api.deepseek.com/v1";

function getDefaultRuntimeConfig(
  provider: AgentProvider = "openai_compatible",
): AgentRuntimeConfig {
  if (provider === "gemini") {
    return {
      provider: "gemini",
      model: DEFAULT_GEMINI_MODEL,
      api_key: "",
      reasoning_mode: "hybrid",
      use_vertex_ai: false,
      vertex_location: "us-central1",
    };
  }

  return {
    provider: "openai_compatible",
    model: DEFAULT_OPENAI_COMPAT_MODEL,
    base_url: DEFAULT_OPENAI_COMPAT_BASE_URL,
    api_key: "",
    reasoning_mode: "hybrid",
    use_vertex_ai: false,
  };
}

function SettingsPage() {
  const { user, logout } = useAuth();
  const [providerCatalog, setProviderCatalog] =
    useState<ProviderCatalogResponse | null>(null);
  const [isSavingProvider, setIsSavingProvider] = useState(false);
  const [isValidatingProvider, setIsValidatingProvider] = useState(false);
  const [runtimeConfigSource, setRuntimeConfigSource] = useState<
    "database" | "environment" | "none"
  >("none");
  const [savedApiKeyMask, setSavedApiKeyMask] = useState("");
  const [runtimeConfig, setRuntimeConfig] = useState<AgentRuntimeConfig>(
    getDefaultRuntimeConfig(),
  );

  const fetchProviderCatalog = useCallback(async () => {
    try {
      const catalog = await chatApi.getProviderCatalog();
      setProviderCatalog(catalog);
    } catch {
      // no-op
    }
  }, []);

  useEffect(() => {
    const loadRuntimeConfig = async () => {
      try {
        const [catalog, saved] = await Promise.all([
          chatApi.getProviderCatalog(),
          chatApi.getRuntimeConfig(),
        ]);
        setProviderCatalog(catalog);
        setRuntimeConfigSource(saved.source);
        setSavedApiKeyMask(saved.api_key_masked || "");
        const provider = (saved.runtime.provider ||
          catalog.default_provider) as AgentProvider;
        const mergedConfig: AgentRuntimeConfig = {
          ...getDefaultRuntimeConfig(provider),
          ...saved.runtime,
          provider,
          api_key: "",
        };
        setRuntimeConfig(mergedConfig);
      } catch {
        fetchProviderCatalog();
      }
    };

    loadRuntimeConfig();
  }, [fetchProviderCatalog]);

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
    setIsSavingProvider(true);
    chatApi
      .saveRuntimeConfig(runtimeConfig)
      .then((saved) => {
        setRuntimeConfigSource(saved.source);
        setSavedApiKeyMask(saved.api_key_masked || "");
        setRuntimeConfig((prev) => ({
          ...prev,
          ...saved.runtime,
          api_key: "",
        }));
        toast.success("Provider config saved securely");
      })
      .catch((error) => {
        toast.error(
          error instanceof Error
            ? error.message
            : "Failed to save provider config",
        );
      })
      .finally(() => {
        setIsSavingProvider(false);
      });
  };

  const handleClearRuntimeConfig = () => {
    chatApi
      .clearRuntimeConfig()
      .then(() => {
        const fallbackProvider = (providerCatalog?.default_provider ||
          "openai_compatible") as AgentProvider;
        setRuntimeConfig(getDefaultRuntimeConfig(fallbackProvider));
        setSavedApiKeyMask("");
        setRuntimeConfigSource("none");
        toast.success("Stored provider config cleared");
      })
      .catch((error) => {
        toast.error(
          error instanceof Error
            ? error.message
            : "Failed to clear provider config",
        );
      });
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
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to validate provider config",
      );
    } finally {
      setIsValidatingProvider(false);
    }
  };

  const isOpenAICompatible = runtimeConfig.provider === "openai_compatible";
  const maskedKey = maskApiKey(runtimeConfig.api_key) || savedApiKeyMask;

  return (
    <div className="min-h-[calc(100vh-4rem)] w-full overflow-y-auto bg-background text-foreground custom-scrollbar">
      <div className="mx-auto grid max-w-4xl gap-8 px-6 py-12">
        <section className="space-y-4">
          <h2 className="flex items-center gap-2 text-xl font-semibold">
            <User size={20} className="text-brand" />
            Profile & Account
          </h2>
          <div className="overflow-hidden rounded-2xl border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border p-6">
              <div>
                <div className="font-medium">Display Name</div>
                <div className="text-sm text-muted-foreground">
                  How your account appears in the workspace
                </div>
              </div>
              <div className="text-muted-foreground">
                {user?.first_name} {user?.last_name}
              </div>
            </div>
            <div className="flex items-center justify-between border-b border-border p-6">
              <div>
                <div className="font-medium">Email Address</div>
                <div className="text-sm text-muted-foreground">
                  Used for account access
                </div>
              </div>
              <div className="text-muted-foreground">{user?.email}</div>
            </div>
            <div className="flex items-center justify-between p-6">
              <div>
                <div className="font-medium">Sign Out</div>
                <div className="text-sm text-muted-foreground">
                  End your current session on this device
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
          <h2 className="flex items-center gap-2 text-xl font-semibold">
            <Sparkles size={20} className="text-ai-accent" />
            AI Provider (BYOK)
          </h2>
          <div className="overflow-hidden rounded-2xl border border-border bg-card">
            <div className="space-y-4 border-b border-border p-6">
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
                      OpenAI-Compatible (Ollama/vLLM/Groq/DeepSeek)
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <div className="text-sm font-medium">Model</div>
                <Input
                  value={runtimeConfig.model || ""}
                  onChange={(event) =>
                    setRuntimeConfig((prev) => ({
                      ...prev,
                      model: event.target.value,
                    }))
                  }
                  placeholder={
                    isOpenAICompatible
                      ? DEFAULT_OPENAI_COMPAT_MODEL
                      : DEFAULT_GEMINI_MODEL
                  }
                />
              </div>

              <div className="grid gap-2">
                <div className="text-sm font-medium">API Key</div>
                <Input
                  type="password"
                  value={runtimeConfig.api_key || ""}
                  onChange={(event) =>
                    setRuntimeConfig((prev) => ({
                      ...prev,
                      api_key: event.target.value,
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

              {isOpenAICompatible ? (
                <>
                  <div className="grid gap-2">
                    <div className="text-sm font-medium">Base URL</div>
                    <Input
                      value={runtimeConfig.base_url || ""}
                      onChange={(event) =>
                        setRuntimeConfig((prev) => ({
                          ...prev,
                          base_url: event.target.value,
                        }))
                      }
                      placeholder={DEFAULT_OPENAI_COMPAT_BASE_URL}
                    />
                  </div>

                  <div className="grid gap-2">
                    <div className="text-sm font-medium">
                      Organization (optional)
                    </div>
                    <Input
                      value={runtimeConfig.organization || ""}
                      onChange={(event) =>
                        setRuntimeConfig((prev) => ({
                          ...prev,
                          organization: event.target.value,
                        }))
                      }
                      placeholder="org_xxx"
                    />
                  </div>
                </>
              ) : (
                <div className="grid gap-2 md:grid-cols-2 md:gap-3">
                  <div className="grid gap-2">
                    <div className="text-sm font-medium">GCP Project ID</div>
                    <Input
                      value={runtimeConfig.vertex_project || ""}
                      onChange={(event) =>
                        setRuntimeConfig((prev) => ({
                          ...prev,
                          vertex_project: event.target.value,
                        }))
                      }
                      placeholder="my-gcp-project"
                    />
                  </div>
                  <div className="grid gap-2">
                    <div className="text-sm font-medium">Vertex Location</div>
                    <Input
                      value={runtimeConfig.vertex_location || ""}
                      onChange={(event) =>
                        setRuntimeConfig((prev) => ({
                          ...prev,
                          vertex_location: event.target.value,
                        }))
                      }
                      placeholder="us-central1"
                    />
                  </div>
                </div>
              )}

              <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                API keys are encrypted and stored in your account runtime
                profile. They are never returned in plaintext.
              </div>
              <div className="text-xs text-muted-foreground">
                Source: {runtimeConfigSource}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 p-6">
              <Button
                type="button"
                onClick={handleSaveRuntimeConfig}
                disabled={isSavingProvider}
              >
                {isSavingProvider ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <KeyRound size={16} />
                )}
                {isSavingProvider ? "Saving..." : "Save Provider Config"}
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
              <Button
                type="button"
                variant="ghost"
                onClick={handleClearRuntimeConfig}
              >
                <Trash2 size={16} />
                Clear
              </Button>
            </div>
          </div>

          {providerCatalog ? (
            <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
              Supported providers:{" "}
              {providerCatalog.supported_providers
                .map((provider) => provider.label)
                .join(", ")}
            </div>
          ) : null}
        </section>

        <section className="space-y-4">
          <h2 className="flex items-center gap-2 text-xl font-semibold">
            <Shield size={20} className="text-destructive" />
            Security
          </h2>
          <div className="overflow-hidden rounded-2xl border border-border bg-card">
            <div className="flex items-center justify-between p-6">
              <div>
                <div className="font-medium">API Keys</div>
                <div className="text-sm text-muted-foreground">
                  Provider credentials are managed in your BYOK section above
                </div>
              </div>
              <span className="text-xs text-muted-foreground">
                Managed above
              </span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
