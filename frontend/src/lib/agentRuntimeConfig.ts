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

export function maskApiKey(value: string | undefined): string {
  if (!value) {
    return "";
  }
  if (value.length <= 8) {
    return `${value.slice(0, 2)}***`;
  }
  return `${value.slice(0, 4)}...${value.slice(-4)}`;
}
