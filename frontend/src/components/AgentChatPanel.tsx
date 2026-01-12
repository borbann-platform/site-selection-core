import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  Bot,
  User,
  Loader2,
  MapPin,
  X,
  ChevronDown,
  ChevronUp,
  Sparkles,
} from "lucide-react";
import { cn } from "../lib/utils";
import { api } from "../lib/api";
import type { AgentStep } from "../lib/api";
import { AgentStepCard, AgentStepBadge } from "./AgentStepCard";
import { ThinkingIndicator, StreamingText } from "./ThinkingIndicator";

export type AttachmentType = "location" | "property";

export interface Attachment {
  id: string;
  type: AttachmentType;
  data: Record<string, unknown>;
  label: string;
}

// Extended message with agent steps
interface AgentMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  steps?: AgentStep[];
  isStreaming?: boolean;
  isThinking?: boolean;
}

interface AgentChatPanelProps {
  className?: string;
  attachments?: Attachment[];
  onPickLocation?: () => void;
  onRemoveAttachment?: (id: string) => void;
}

let messageIdCounter = 0;
function generateMessageId(): string {
  return `msg-${++messageIdCounter}-${Date.now()}`;
}

// Real agent stream hook that uses the API
function useAgentStream() {
  const [isRunning, setIsRunning] = useState(false);

  const runAgentStream = useCallback(
    async (
      messages: Array<{ role: "user" | "assistant"; content: string }>,
      onUpdate: (update: {
        thinking?: boolean;
        step?: AgentStep;
        token?: string;
        done?: boolean;
      }) => void
    ) => {
      setIsRunning(true);

      try {
        for await (const event of api.streamAgentChat(messages)) {
          switch (event.event) {
            case "thinking":
              onUpdate({ thinking: event.data?.thinking ?? true });
              break;

            case "step":
              if (event.data) {
                const step: AgentStep = {
                  id: event.data.id || `step-${Date.now()}`,
                  type:
                    (event.data.type as "tool_call" | "thinking") ||
                    "tool_call",
                  name: event.data.name || "unknown",
                  status:
                    (event.data.status as "running" | "complete" | "error") ||
                    "running",
                  input: event.data.input,
                  output: event.data.output,
                  startTime: event.data.start_time || Date.now(),
                  endTime: event.data.end_time,
                };
                onUpdate({ step, thinking: false });
              }
              break;

            case "token":
              if (event.data?.token) {
                onUpdate({ token: event.data.token });
              }
              break;

            case "done":
              onUpdate({ done: true });
              break;
          }
        }
      } catch (error) {
        console.error("Agent stream error:", error);
        onUpdate({ done: true });
      } finally {
        setIsRunning(false);
      }
    },
    []
  );

  return { runAgentStream, isRunning };
}

// Assistant message with steps visualization
interface AssistantMessageProps {
  message: AgentMessage;
}

function AssistantMessage({ message }: AssistantMessageProps) {
  const [showSteps, setShowSteps] = useState(true);
  const hasSteps = message.steps && message.steps.length > 0;
  const completedSteps =
    message.steps?.filter((s) => s.status === "complete") || [];
  const runningStep = message.steps?.find((s) => s.status === "running");

  return (
    <div className="flex gap-2">
      <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-emerald-500/20">
        <Bot size={12} className="text-emerald-400" />
      </div>
      <div className="flex-1 space-y-2 min-w-0">
        {/* Steps section */}
        {hasSteps && (
          <div className="space-y-1.5">
            {/* Toggle button */}
            <button
              type="button"
              onClick={() => setShowSteps(!showSteps)}
              className="flex items-center gap-1.5 text-[10px] text-white/50 hover:text-white/70 transition-colors"
            >
              {showSteps ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              <Sparkles size={10} />
              <span>
                {completedSteps.length} tool
                {completedSteps.length !== 1 ? "s" : ""} used
              </span>
            </button>

            {/* Expanded steps view */}
            {showSteps && (
              <div className="space-y-1.5">
                {message.steps?.map((step) => (
                  <AgentStepCard key={step.id} step={step} />
                ))}
              </div>
            )}

            {/* Collapsed badges view */}
            {!showSteps && (
              <div className="flex flex-wrap gap-1">
                {message.steps?.map((step) => (
                  <AgentStepBadge
                    key={step.id}
                    step={step}
                    onClick={() => setShowSteps(true)}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Thinking indicator */}
        {message.isThinking && !runningStep && (
          <ThinkingIndicator startTime={Date.now()} />
        )}

        {/* Message content */}
        {(message.content || message.isStreaming) && (
          <div className="max-w-full rounded-xl px-3 py-2 text-sm bg-white/5 text-white/90">
            {message.content ? (
              <StreamingText
                text={message.content}
                isStreaming={message.isStreaming}
                className="whitespace-pre-wrap"
              />
            ) : (
              <span className="flex items-center gap-1 text-white/50">
                <Loader2 size={12} className="animate-spin" />
                Generating response...
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function AgentChatPanel({
  className,
  attachments = [],
  onPickLocation,
  onRemoveAttachment,
}: AgentChatPanelProps) {
  const [messages, setMessages] = useState<AgentMessage[]>([
    {
      id: generateMessageId(),
      role: "assistant",
      content:
        "Hello! I'm your real estate AI assistant. I can help you with property prices, market insights, and location analysis. What would you like to know?",
    },
  ]);
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { runAgentStream, isRunning } = useAgentStream();

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((!input.trim() && attachments.length === 0) || isRunning) return;

    let content = input.trim();
    if (attachments.length > 0) {
      const attachmentText = attachments
        .map((a) => `[Attachment: ${a.type} - ${JSON.stringify(a.data)}]`)
        .join("\n");
      content = `${content}\n\n${attachmentText}`.trim();
    }

    const userMessage: AgentMessage = {
      id: generateMessageId(),
      role: "user",
      content,
    };

    const assistantMessageId = generateMessageId();
    const assistantMessage: AgentMessage = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      steps: [],
      isThinking: true,
      isStreaming: false,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput("");

    // Build messages array for API (include conversation history)
    const apiMessages = [...messages, userMessage].map((m) => ({
      role: m.role,
      content: m.content,
    }));

    // Run agent stream via API
    await runAgentStream(apiMessages, (update) => {
      setMessages((prev) => {
        const updated = [...prev];
        const msgIndex = updated.findIndex((m) => m.id === assistantMessageId);
        if (msgIndex === -1) return prev;

        const msg = { ...updated[msgIndex] };

        if (update.thinking !== undefined) {
          msg.isThinking = update.thinking;
        }

        if (update.step) {
          // Update or add step
          const currentStep = update.step;
          const stepIndex = msg.steps?.findIndex(
            (s) => s.id === currentStep.id
          );
          if (stepIndex !== undefined && stepIndex >= 0) {
            msg.steps = [...(msg.steps || [])];
            msg.steps[stepIndex] = update.step;
          } else {
            msg.steps = [...(msg.steps || []), update.step];
          }
        }

        if (update.token) {
          msg.content += update.token;
          msg.isStreaming = true;
          msg.isThinking = false;
        }

        if (update.done) {
          msg.isStreaming = false;
          msg.isThinking = false;
        }

        updated[msgIndex] = msg;
        return updated;
      });
    });

    // Clear attachments
    attachments.forEach((a) => {
      onRemoveAttachment?.(a.id);
    });

    inputRef.current?.focus();
  };

  return (
    <div className={cn("flex flex-col h-full", className)}>
      {/* Header */}
      <div className="flex items-center gap-2 p-3 border-b border-white/10">
        <div className="w-8 h-8 bg-emerald-500/20 rounded-lg flex items-center justify-center">
          <Bot size={18} className="text-emerald-400" />
        </div>
        <div>
          <h3 className="text-sm font-medium text-white">AI Assistant</h3>
          <p className="text-[10px] text-white/50">
            Real Estate Expert • ReAct Agent
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4 custom-scrollbar">
        {messages.map((message) =>
          message.role === "user" ? (
            <div key={message.id} className="flex gap-2 flex-row-reverse">
              <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-blue-500/20">
                <User size={12} className="text-blue-400" />
              </div>
              <div className="max-w-[85%] rounded-xl px-3 py-2 text-sm bg-blue-500/20 text-white">
                {message.content}
              </div>
            </div>
          ) : (
            <AssistantMessage key={message.id} message={message} />
          )
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-white/10">
        {/* Attachments */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {attachments.map((att) => (
              <div
                key={att.id}
                className="flex items-center gap-1 bg-white/10 rounded-full px-2 py-1 text-xs text-white/80"
              >
                <span className="truncate max-w-36">{att.label}</span>
                <button
                  type="button"
                  onClick={() => onRemoveAttachment?.(att.id)}
                  className="hover:text-white"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          <button
            type="button"
            onClick={onPickLocation}
            className="p-2 bg-white/5 hover:bg-white/10 rounded-lg text-white/70 transition-colors"
            title="Pick location on map"
          >
            <MapPin size={18} />
          </button>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about prices, locations, site analysis..."
            disabled={isRunning}
            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-emerald-500/50 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={(!input.trim() && attachments.length === 0) || isRunning}
            className="p-2 bg-emerald-500 hover:bg-emerald-600 disabled:bg-white/10 disabled:text-white/30 rounded-lg text-black transition-colors"
          >
            {isRunning ? (
              <Loader2 size={18} className="animate-spin text-white/50" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
