export type AgentProvider = "gemini" | "openai_compatible";
export type ReasoningMode = "react" | "cot" | "hybrid";

export interface AgentRuntimeConfig {
  provider: AgentProvider;
  model?: string;
  api_key?: string;
  base_url?: string;
  organization?: string;
  use_vertex_ai?: boolean;
  vertex_project?: string;
  vertex_location?: string;
  reasoning_mode?: ReasoningMode;
  temperature?: number;
  max_tokens?: number;
}

export interface StoredRuntimeConfig {
  config: AgentRuntimeConfig | null;
  source: "session" | "local" | null;
}

const LOCAL_KEY = "agent_runtime_config_v1";
const SESSION_KEY = "agent_runtime_config_session_v1";

function hasBrowserStorage(): boolean {
  return typeof window !== "undefined";
}

function trimOrUndefined(value: string | undefined): string | undefined {
  if (value === undefined) {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

export function sanitizeAgentRuntimeConfig(
  config: AgentRuntimeConfig
): AgentRuntimeConfig {
  return {
    provider: config.provider,
    model: trimOrUndefined(config.model),
    api_key: trimOrUndefined(config.api_key),
    base_url: trimOrUndefined(config.base_url),
    organization: trimOrUndefined(config.organization),
    use_vertex_ai: Boolean(config.use_vertex_ai),
    vertex_project: trimOrUndefined(config.vertex_project),
    vertex_location: trimOrUndefined(config.vertex_location),
    reasoning_mode: config.reasoning_mode,
    temperature: config.temperature,
    max_tokens: config.max_tokens,
  };
}

export function loadAgentRuntimeConfig(): StoredRuntimeConfig {
  if (!hasBrowserStorage()) {
    return { config: null, source: null };
  }

  const sessionRaw = window.sessionStorage.getItem(SESSION_KEY);
  if (sessionRaw) {
    try {
      return {
        config: JSON.parse(sessionRaw) as AgentRuntimeConfig,
        source: "session",
      };
    } catch {
      window.sessionStorage.removeItem(SESSION_KEY);
    }
  }

  const localRaw = window.localStorage.getItem(LOCAL_KEY);
  if (localRaw) {
    try {
      return {
        config: JSON.parse(localRaw) as AgentRuntimeConfig,
        source: "local",
      };
    } catch {
      window.localStorage.removeItem(LOCAL_KEY);
    }
  }

  return { config: null, source: null };
}

export function getAgentRuntimeConfig(): AgentRuntimeConfig | null {
  return loadAgentRuntimeConfig().config;
}

export function saveAgentRuntimeConfig(
  config: AgentRuntimeConfig,
  persistOnDevice: boolean
): void {
  if (!hasBrowserStorage()) {
    return;
  }

  const sanitized = sanitizeAgentRuntimeConfig(config);
  const serialized = JSON.stringify(sanitized);

  window.localStorage.removeItem(LOCAL_KEY);
  window.sessionStorage.removeItem(SESSION_KEY);

  if (persistOnDevice) {
    window.localStorage.setItem(LOCAL_KEY, serialized);
  } else {
    window.sessionStorage.setItem(SESSION_KEY, serialized);
  }
}

export function clearAgentRuntimeConfig(): void {
  if (!hasBrowserStorage()) {
    return;
  }
  window.localStorage.removeItem(LOCAL_KEY);
  window.sessionStorage.removeItem(SESSION_KEY);
}

export function maskApiKey(value: string | undefined): string {
  if (!value) {
    return "";
  }
  if (value.length <= 8) {
    return `${value.slice(0, 2)}***`;
  }
  return `${value.slice(0, 4)}...${value.slice(-4)}`;
}
