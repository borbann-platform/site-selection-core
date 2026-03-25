/**
 * Explorer Chat Store - Zustand store for the map explorer's AI chat.
 *
 * Lifts the previously component-local AI state (messages, streaming status,
 * session ID) into a global singleton so that:
 * 1. In-flight streams continue even when the user navigates away from `/`.
 * 2. Returning to `/` restores the conversation and streaming indicator.
 * 3. The user can stop a running stream via an AbortController.
 */

import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";
import { chatApi } from "../lib/chatApi";
import type {
  ChatMessage,
  Attachment,
  AgentStep,
  AgentRuntimeError,
} from "../lib/api";

// Re-use the same shape the AIExpandedPanel already consumes
export interface AgentMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  steps?: AgentStep[];
  error?: AgentRuntimeError;
  isStreaming?: boolean;
  isThinking?: boolean;
  thinkingStartTime?: number;
}

// ---- State & Actions ----

interface ExplorerChatState {
  messages: AgentMessage[];
  isRunning: boolean;
  sessionId: string | undefined;
}

interface ExplorerChatActions {
  sendMessage: (
    userInput: string,
    attachments?: Attachment[],
  ) => Promise<void>;
  stopStreaming: () => void;
  reset: () => void;
}

type ExplorerChatStore = ExplorerChatState & ExplorerChatActions;

// ---- Module-level abort controller ----

let activeController: AbortController | null = null;

// ---- Initial state ----

const initialState: ExplorerChatState = {
  messages: [],
  isRunning: false,
  sessionId: undefined,
};

// ---- Store ----

export const useExplorerChatStore = create<ExplorerChatStore>()(
  subscribeWithSelector((set, get) => ({
    ...initialState,

    sendMessage: async (userInput: string, attachments?: Attachment[]) => {
      if (!userInput.trim() || get().isRunning) return;

      // Cancel any previous stream
      if (activeController) {
        activeController.abort();
        activeController = null;
      }

      const controller = new AbortController();
      activeController = controller;

      const { messages: previousMessages, sessionId } = get();

      const attachmentContext = attachments
        ? attachments.map((a) => `[${a.type}: ${a.label}]`).join(" ")
        : "";
      const fullMessage = [userInput, attachmentContext]
        .filter(Boolean)
        .join(" ");

      const userMsgId = `msg-${Date.now()}`;
      const userMessage: AgentMessage = {
        id: userMsgId,
        role: "user",
        content: userInput,
      };

      const assistantMsgId = `msg-${Date.now() + 1}`;
      const assistantMessage: AgentMessage = {
        id: assistantMsgId,
        role: "assistant",
        content: "",
        steps: [],
        isThinking: true,
        isStreaming: false,
      };

      set({
        messages: [...previousMessages, userMessage, assistantMessage],
        isRunning: true,
      });

      try {
        const chatMessages: ChatMessage[] = previousMessages
          .filter((m) => m.role === "user" || m.role === "assistant")
          .map((m) => ({ role: m.role, content: m.content }));
        chatMessages.push({ role: "user" as const, content: fullMessage });

        for await (const event of chatApi.streamAgentChatWithSession(
          chatMessages,
          {
            sessionId,
            attachments,
            signal: controller.signal,
            onSessionId: (id) => {
              set((state) => ({
                sessionId: state.sessionId ?? id,
              }));
            },
          },
        )) {
          if (controller.signal.aborted) break;

          set((state) => {
            const updated = [...state.messages];
            const lastIdx = updated.length - 1;
            const lastMsg = { ...updated[lastIdx] };

            if (event.event === "thinking") {
              lastMsg.isThinking = event.data?.thinking ?? true;
              if (event.data?.thinking) {
                lastMsg.thinkingStartTime = Date.now();
              }
            } else if (event.event === "step" && event.data) {
              const steps = [...(lastMsg.steps ?? [])];
              const stepData = event.data;
              const existingIdx = steps.findIndex(
                (s) => s.id === stepData.id,
              );

              const step: AgentStep = {
                id: stepData.id || `step-${Date.now()}`,
                type:
                  (stepData.type as AgentStep["type"]) || "tool_call",
                name: stepData.name || "Unknown",
                status: stepData.status as AgentStep["status"],
                input: stepData.input,
                output: stepData.output,
                startTime: stepData.start_time || Date.now(),
                endTime: stepData.end_time,
              };

              if (existingIdx >= 0) {
                steps[existingIdx] = step;
              } else {
                steps.push(step);
              }
              lastMsg.steps = steps;
            } else if (event.event === "token" && event.data?.token) {
              lastMsg.content += event.data.token;
              lastMsg.isStreaming = true;
              lastMsg.isThinking = false;
              lastMsg.error = undefined;
            } else if (event.event === "error" && event.data) {
              lastMsg.error = {
                title: event.data.title || "Model request failed",
                message:
                  event.data.message ||
                  "The model provider returned an error. Please check your settings.",
                statusCode: event.data.status_code,
                providerCode: event.data.provider_code,
                rawMessage: event.data.raw_message,
                retryable: event.data.retryable,
              };
              lastMsg.isStreaming = false;
              lastMsg.isThinking = false;
            } else if (event.event === "done") {
              lastMsg.isStreaming = false;
              lastMsg.isThinking = false;
            }

            updated[lastIdx] = lastMsg;
            return { messages: updated };
          });

          if (event.event === "done" || event.event === "error") {
            set({ isRunning: false });
          }
        }

        // If the stream ended without a "done" event (e.g. aborted)
        if (get().isRunning) {
          set((state) => ({
            isRunning: false,
            messages: state.messages.map((m) =>
              m.isStreaming || m.isThinking
                ? { ...m, isStreaming: false, isThinking: false }
                : m,
            ),
          }));
        }
      } catch (error) {
        if (
          error instanceof DOMException &&
          error.name === "AbortError"
        ) {
          set((state) => ({
            isRunning: false,
            messages: state.messages.map((m) =>
              m.isStreaming || m.isThinking
                ? { ...m, isStreaming: false, isThinking: false }
                : m,
            ),
          }));
          return;
        }

        set((state) => ({
          isRunning: false,
          messages: state.messages.map((m) => {
            if (!m.isStreaming && !m.isThinking) return m;
            return {
              ...m,
              error: {
                title: "Request failed",
                message:
                  error instanceof Error
                    ? error.message
                    : "Sorry, I encountered an error. Please try again.",
              },
              isStreaming: false,
              isThinking: false,
            };
          }),
        }));
      } finally {
        if (activeController === controller) {
          activeController = null;
        }
      }
    },

    stopStreaming: () => {
      if (activeController) {
        activeController.abort();
        activeController = null;
      }
      set((state) => ({
        isRunning: false,
        messages: state.messages.map((m) =>
          m.isStreaming || m.isThinking
            ? { ...m, isStreaming: false, isThinking: false }
            : m,
        ),
      }));
    },

    reset: () => {
      if (activeController) {
        activeController.abort();
        activeController = null;
      }
      set(initialState);
    },
  })),
);
