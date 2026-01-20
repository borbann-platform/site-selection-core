/**
 * Chat Sessions API - Functions for managing chat sessions and messages
 */

import { API_URL, type ChatMessage, type Attachment, type AgentStreamEvent } from "./api";

// ============= Types =============

export interface ChatSession {
  id: string;
  title: string | null;
  created_at: string | null;
  updated_at: string | null;
  last_message_at: string | null;
  message_count: number;
  is_archived: boolean;
  preview?: string | null;
}

export interface ChatMessageResponse {
  id: string;
  role: "user" | "assistant";
  content: string;
  attachments?: Record<string, unknown>[] | null;
  tool_calls?: Record<string, unknown>[] | null;
  created_at: string | null;
}

export interface SessionWithMessages extends ChatSession {
  messages: ChatMessageResponse[];
}

export interface SessionListResponse {
  items: ChatSession[];
  total: number;
  has_more: boolean;
}

export interface CreateSessionRequest {
  title?: string | null;
}

export interface UpdateSessionRequest {
  title?: string | null;
  is_archived?: boolean | null;
}

export interface GenerateTitleResponse {
  title: string | null;
  success: boolean;
}

// ============= Helper Functions =============

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem("access_token");
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

// ============= Chat Sessions API =============

export const chatApi = {
  /**
   * List chat sessions for the current user.
   */
  listSessions: async (params?: {
    limit?: number;
    offset?: number;
    search?: string;
    include_archived?: boolean;
  }): Promise<SessionListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    if (params?.offset !== undefined) searchParams.set("offset", String(params.offset));
    if (params?.search) searchParams.set("search", params.search);
    if (params?.include_archived) searchParams.set("include_archived", "true");

    const url = `${API_URL}/chat/sessions${searchParams.toString() ? `?${searchParams}` : ""}`;
    const response = await fetch(url, {
      headers: getAuthHeaders(),
    });
    return handleResponse<SessionListResponse>(response);
  },

  /**
   * Create a new chat session.
   */
  createSession: async (data?: CreateSessionRequest): Promise<ChatSession> => {
    const response = await fetch(`${API_URL}/chat/sessions`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify(data || {}),
    });
    return handleResponse<ChatSession>(response);
  },

  /**
   * Get a chat session with all its messages.
   */
  getSession: async (sessionId: string): Promise<SessionWithMessages> => {
    const response = await fetch(`${API_URL}/chat/sessions/${sessionId}`, {
      headers: getAuthHeaders(),
    });
    return handleResponse<SessionWithMessages>(response);
  },

  /**
   * Update a chat session (rename or archive).
   */
  updateSession: async (
    sessionId: string,
    data: UpdateSessionRequest
  ): Promise<ChatSession> => {
    const response = await fetch(`${API_URL}/chat/sessions/${sessionId}`, {
      method: "PATCH",
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<ChatSession>(response);
  },

  /**
   * Delete a chat session and all its messages.
   */
  deleteSession: async (sessionId: string): Promise<void> => {
    const response = await fetch(`${API_URL}/chat/sessions/${sessionId}`, {
      method: "DELETE",
      headers: getAuthHeaders(),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Delete failed" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
  },

  /**
   * Generate an AI-powered title for a session.
   */
  generateTitle: async (sessionId: string): Promise<GenerateTitleResponse> => {
    const response = await fetch(`${API_URL}/chat/sessions/${sessionId}/generate-title`, {
      method: "POST",
      headers: getAuthHeaders(),
    });
    return handleResponse<GenerateTitleResponse>(response);
  },

  /**
   * Stream agent chat response with optional session persistence.
   * If a session_id is provided in the request, messages will be persisted.
   */
  streamAgentChatWithSession: async function* (
    messages: ChatMessage[],
    options?: {
      sessionId?: string;
      attachments?: Attachment[];
    }
  ): AsyncGenerator<AgentStreamEvent, void, unknown> {
    const token = localStorage.getItem("access_token");
    const headers: HeadersInit = {
      "Content-Type": "application/json",
    };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(`${API_URL}/chat/agent`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        messages,
        session_id: options?.sessionId,
        attachments: options?.attachments,
      }),
    });

    if (!response.ok) throw new Error("Failed to start agent stream");
    if (!response.body) throw new Error("No response body");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const jsonStr = line.slice(6);
          try {
            const event = JSON.parse(jsonStr) as AgentStreamEvent;
            yield event;
            if (event.event === "done") return;
          } catch {
            // Skip malformed JSON
          }
        }
      }
    }
  },
};

// ============= Time-based Grouping Utilities =============

export type SessionGroup = "today" | "yesterday" | "last_7_days" | "last_30_days" | "older";

export interface GroupedSessions {
  today: ChatSession[];
  yesterday: ChatSession[];
  last_7_days: ChatSession[];
  last_30_days: ChatSession[];
  older: ChatSession[];
}

export function getSessionGroup(session: ChatSession): SessionGroup {
  const sessionDate = session.last_message_at || session.created_at;
  if (!sessionDate) return "older";

  const date = new Date(sessionDate);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const last7Days = new Date(today);
  last7Days.setDate(last7Days.getDate() - 7);
  const last30Days = new Date(today);
  last30Days.setDate(last30Days.getDate() - 30);

  if (date >= today) return "today";
  if (date >= yesterday) return "yesterday";
  if (date >= last7Days) return "last_7_days";
  if (date >= last30Days) return "last_30_days";
  return "older";
}

export function groupSessions(sessions: ChatSession[]): GroupedSessions {
  const groups: GroupedSessions = {
    today: [],
    yesterday: [],
    last_7_days: [],
    last_30_days: [],
    older: [],
  };

  for (const session of sessions) {
    const group = getSessionGroup(session);
    groups[group].push(session);
  }

  return groups;
}

export const SESSION_GROUP_LABELS: Record<SessionGroup, string> = {
  today: "Today",
  yesterday: "Yesterday",
  last_7_days: "Last 7 Days",
  last_30_days: "Last 30 Days",
  older: "Older",
};
