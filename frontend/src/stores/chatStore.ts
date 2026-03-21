/**
 * Chat Store - Zustand store for managing chat session state
 */

import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";
import {
  chatApi,
  groupSessions,
  type ChatSession,
  type GroupedSessions,
} from "../lib/chatApi";
import type {
  ChatMessage,
  Attachment,
  AgentStep,
  AgentRuntimeError,
} from "../lib/api";

// ============= Types =============

export interface LocalMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  attachments?: Attachment[];
  isStreaming?: boolean;
  steps?: AgentStep[];
  error?: AgentRuntimeError;
  createdAt: Date;
}

interface ChatState {
  // Session list
  sessions: ChatSession[];
  groupedSessions: GroupedSessions;
  sessionsLoading: boolean;
  sessionsError: string | null;
  searchQuery: string;
  hasMore: boolean;
  totalSessions: number;

  // Current session
  currentSessionId: string | null;
  currentSession: ChatSession | null;
  messages: LocalMessage[];
  messagesLoading: boolean;

  // UI state
  isStreaming: boolean;
  sidebarOpen: boolean;
  searchOpen: boolean;
}

interface ChatActions {
  // Session list actions
  loadSessions: (reset?: boolean) => Promise<void>;
  loadMoreSessions: () => Promise<void>;
  setSearchQuery: (query: string) => void;
  searchSessions: (query: string) => Promise<void>;

  // Session CRUD
  createSession: (title?: string) => Promise<ChatSession>;
  selectSession: (sessionId: string) => Promise<void>;
  renameSession: (sessionId: string, title: string) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  generateSessionTitle: (sessionId: string) => Promise<void>;

  // Message actions
  sendMessage: (content: string, attachments?: Attachment[]) => Promise<void>;
  clearMessages: () => void;

  // UI actions
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  toggleSearch: () => void;
  setSearchOpen: (open: boolean) => void;

  // Reset
  reset: () => void;
}

type ChatStore = ChatState & ChatActions;

// ============= Initial State =============

const initialState: ChatState = {
  sessions: [],
  groupedSessions: {
    today: [],
    yesterday: [],
    last_7_days: [],
    last_30_days: [],
    older: [],
  },
  sessionsLoading: false,
  sessionsError: null,
  searchQuery: "",
  hasMore: false,
  totalSessions: 0,

  currentSessionId: null,
  currentSession: null,
  messages: [],
  messagesLoading: false,

  isStreaming: false,
  sidebarOpen: true,
  searchOpen: false,
};

// ============= Store =============

export const useChatStore = create<ChatStore>()(
  subscribeWithSelector((set, get) => ({
    ...initialState,

    // ============= Session List Actions =============

    loadSessions: async (_reset = true) => {
      const { searchQuery } = get();
      set({ sessionsLoading: true, sessionsError: null });

      try {
        const response = await chatApi.listSessions({
          limit: 50,
          offset: 0,
          search: searchQuery || undefined,
        });

        set({
          sessions: response.items,
          groupedSessions: groupSessions(response.items),
          hasMore: response.has_more,
          totalSessions: response.total,
          sessionsLoading: false,
        });
      } catch (error) {
        set({
          sessionsError: error instanceof Error ? error.message : "Failed to load sessions",
          sessionsLoading: false,
        });
      }
    },

    loadMoreSessions: async () => {
      const { sessions, hasMore, sessionsLoading, searchQuery } = get();
      if (!hasMore || sessionsLoading) return;

      set({ sessionsLoading: true });

      try {
        const response = await chatApi.listSessions({
          limit: 50,
          offset: sessions.length,
          search: searchQuery || undefined,
        });

        const newSessions = [...sessions, ...response.items];
        set({
          sessions: newSessions,
          groupedSessions: groupSessions(newSessions),
          hasMore: response.has_more,
          sessionsLoading: false,
        });
      } catch (error) {
        set({
          sessionsError: error instanceof Error ? error.message : "Failed to load more sessions",
          sessionsLoading: false,
        });
      }
    },

    setSearchQuery: (query: string) => {
      set({ searchQuery: query });
    },

    searchSessions: async (query: string) => {
      set({ searchQuery: query });
      await get().loadSessions(true);
    },

    // ============= Session CRUD =============

    createSession: async (title?: string) => {
      const session = await chatApi.createSession({ title });

      // Add to beginning of sessions list
      const { sessions } = get();
      const newSessions = [session, ...sessions];
      set({
        sessions: newSessions,
        groupedSessions: groupSessions(newSessions),
        currentSessionId: session.id,
        currentSession: session,
        messages: [],
        totalSessions: get().totalSessions + 1,
      });

      return session;
    },

    selectSession: async (sessionId: string) => {
      const { currentSessionId } = get();
      if (currentSessionId === sessionId) return;

      set({ messagesLoading: true, currentSessionId: sessionId });

      try {
        const sessionWithMessages = await chatApi.getSession(sessionId);

        // Convert API messages to local messages
        const localMessages: LocalMessage[] = sessionWithMessages.messages.map((msg) => ({
          id: msg.id,
          role: msg.role as "user" | "assistant",
          content: msg.content,
          attachments: msg.attachments as Attachment[] | undefined,
          steps: Array.isArray(msg.tool_calls)
            ? msg.tool_calls.map((toolCall, index) => ({
                id:
                  typeof toolCall.id === "string"
                    ? toolCall.id
                    : `${msg.id}-step-${index}`,
                type:
                  (typeof toolCall.type === "string"
                    ? toolCall.type
                    : "tool_call") as AgentStep["type"],
                name:
                  typeof toolCall.name === "string"
                    ? toolCall.name
                    : "Tool",
                status:
                  (typeof toolCall.status === "string"
                    ? toolCall.status
                    : "complete") as AgentStep["status"],
                input:
                  toolCall.input && typeof toolCall.input === "object"
                    ? (toolCall.input as Record<string, unknown>)
                    : undefined,
                output:
                  typeof toolCall.output === "string"
                    ? toolCall.output
                    : undefined,
                startTime:
                  typeof toolCall.start_time === "number"
                    ? toolCall.start_time
                    : Date.now(),
                endTime:
                  typeof toolCall.end_time === "number"
                    ? toolCall.end_time
                    : undefined,
              }))
            : undefined,
          createdAt: msg.created_at ? new Date(msg.created_at) : new Date(),
        }));

        set({
          currentSession: sessionWithMessages,
          messages: localMessages,
          messagesLoading: false,
        });
      } catch (error) {
        set({
          messagesLoading: false,
          currentSession: null,
          messages: [],
        });
        throw error;
      }
    },

    renameSession: async (sessionId: string, title: string) => {
      await chatApi.updateSession(sessionId, { title });

      // Update in sessions list
      const { sessions, currentSession } = get();
      const newSessions = sessions.map((s) =>
        s.id === sessionId ? { ...s, title } : s
      );
      set({
        sessions: newSessions,
        groupedSessions: groupSessions(newSessions),
        currentSession:
          currentSession?.id === sessionId
            ? { ...currentSession, title }
            : currentSession,
      });
    },

    deleteSession: async (sessionId: string) => {
      await chatApi.deleteSession(sessionId);

      const { sessions, currentSessionId } = get();
      const newSessions = sessions.filter((s) => s.id !== sessionId);

      set({
        sessions: newSessions,
        groupedSessions: groupSessions(newSessions),
        totalSessions: get().totalSessions - 1,
        // Clear current session if it was deleted
        ...(currentSessionId === sessionId
          ? {
              currentSessionId: null,
              currentSession: null,
              messages: [],
            }
          : {}),
      });
    },

    generateSessionTitle: async (sessionId: string) => {
      try {
        const result = await chatApi.generateTitle(sessionId);
        if (result.success && result.title) {
          const { sessions, currentSession } = get();
          const newSessions = sessions.map((s) =>
            s.id === sessionId ? { ...s, title: result.title } : s
          );
          set({
            sessions: newSessions,
            groupedSessions: groupSessions(newSessions),
            currentSession:
              currentSession?.id === sessionId
                ? { ...currentSession, title: result.title }
                : currentSession,
          });
        }
      } catch (error) {
        // Silently fail title generation
        console.error("Failed to generate title:", error);
      }
    },

    // ============= Message Actions =============

    sendMessage: async (content: string, attachments?: Attachment[]) => {
      const { currentSessionId, messages, currentSession } = get();

      // Create user message
      const userMessage: LocalMessage = {
        id: `temp-${Date.now()}`,
        role: "user",
        content,
        attachments,
        createdAt: new Date(),
      };

      // Create placeholder assistant message
      const assistantMessage: LocalMessage = {
        id: `temp-assistant-${Date.now()}`,
        role: "assistant",
        content: "",
        isStreaming: true,
        steps: [],
        createdAt: new Date(),
      };

      set({
        messages: [...messages, userMessage, assistantMessage],
        isStreaming: true,
      });

      try {
        // Build messages for API
        const apiMessages: ChatMessage[] = messages
          .filter((m) => !m.isStreaming)
          .map((m) => ({
            role: m.role,
            content: m.content,
          }));
        apiMessages.push({ role: "user", content });

        // Stream response
        let fullContent = "";
        const steps: AgentStep[] = [];

        for await (const event of chatApi.streamAgentChatWithSession(apiMessages, {
          sessionId: currentSessionId || undefined,
          attachments,
          onSessionId: (sessionId) => {
            if (!get().currentSessionId) {
              set({ currentSessionId: sessionId });
            }
          },
        })) {
          const { messages: currentMessages } = get();
          const lastMessage = currentMessages[currentMessages.length - 1];

          if (event.event === "token" && event.data?.token) {
            fullContent += event.data.token;
            set({
              messages: currentMessages.map((m) =>
                m.id === lastMessage.id
                  ? { ...m, content: fullContent, error: undefined }
                  : m
              ),
            });
          } else if (event.event === "step" && event.data) {
            const step: AgentStep = {
              id: event.data.id || `step-${Date.now()}`,
              type: (event.data.type as AgentStep["type"]) || "tool_call",
              name: event.data.name || "Unknown",
              status: (event.data.status as AgentStep["status"]) || "pending",
              input: event.data.input,
              output: event.data.output,
              startTime: event.data.start_time || Date.now(),
              endTime: event.data.end_time,
            };

            // Update or add step
            const existingIndex = steps.findIndex((s) => s.id === step.id);
            if (existingIndex >= 0) {
              steps[existingIndex] = step;
            } else {
              steps.push(step);
            }

            set({
              messages: currentMessages.map((m) =>
                m.id === lastMessage.id
                  ? { ...m, steps: [...steps] }
                  : m
              ),
            });
          } else if (event.event === "error" && event.data) {
            const streamError: AgentRuntimeError = {
              title: event.data.title || "Model request failed",
              message:
                event.data.message ||
                "The model provider returned an error. Please check your settings.",
              statusCode: event.data.status_code,
              providerCode: event.data.provider_code,
              rawMessage: event.data.raw_message,
              retryable: event.data.retryable,
            };
            set({
              messages: currentMessages.map((m) =>
                m.id === lastMessage.id
                  ? { ...m, isStreaming: false, error: streamError }
                  : m
              ),
              isStreaming: false,
            });
          } else if (event.event === "done") {
            // Mark message as complete
            set({
              messages: get().messages.map((m) =>
                m.id === lastMessage.id
                  ? { ...m, isStreaming: false }
                  : m
              ),
              isStreaming: false,
            });

            // Generate title if this is the first message exchange
            if (currentSessionId && currentSession && !currentSession.title) {
              get().generateSessionTitle(currentSessionId);
            }

            // Refresh sessions to update last_message_at
            get().loadSessions(true);
          }
        }
      } catch (error) {
        // Mark streaming as complete on error
        set({
          isStreaming: false,
          messages: get().messages.map((m) =>
            m.isStreaming
              ? {
                  ...m,
                  isStreaming: false,
                  content: m.content,
                  error: {
                    title: "Request failed",
                    message:
                      error instanceof Error
                        ? error.message
                        : "An error occurred while generating the response.",
                  },
                }
              : m
          ),
        });
        throw error;
      }
    },

    clearMessages: () => {
      set({ messages: [] });
    },

    // ============= UI Actions =============

    toggleSidebar: () => {
      set({ sidebarOpen: !get().sidebarOpen });
    },

    setSidebarOpen: (open: boolean) => {
      set({ sidebarOpen: open });
    },

    toggleSearch: () => {
      set({ searchOpen: !get().searchOpen });
    },

    setSearchOpen: (open: boolean) => {
      set({ searchOpen: open });
    },

    // ============= Reset =============

    reset: () => {
      set(initialState);
    },
  }))
);

// ============= Selectors =============

export const selectCurrentMessages = (state: ChatStore) => state.messages;
export const selectIsStreaming = (state: ChatStore) => state.isStreaming;
export const selectGroupedSessions = (state: ChatStore) => state.groupedSessions;
export const selectCurrentSession = (state: ChatStore) => state.currentSession;
