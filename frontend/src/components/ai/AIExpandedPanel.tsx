import { useRef, useEffect, useState } from "react";
import { Bot, User, ChevronDown, ChevronUp } from "lucide-react";
import { ThinkingProcess } from "../ThinkingIndicator";
import { StreamingMarkdown } from "../ui/markdown";
import { AgentStepCard, AgentStepBadge } from "../AgentStepCard";
import {
  PropertyResultsCard,
  parsePropertyResults,
  cleanContentFromPropertyMarkers,
} from "./PropertyResultsCard";
import type { AgentStep, AgentRuntimeError } from "../../lib/api";
import { AgentErrorCard } from "../AgentErrorCard";
import { cn } from "../../lib/utils";

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

interface AIExpandedPanelProps {
  isExpanded: boolean;
  messages: AgentMessage[];
  onPropertyClick?: (property: { lat?: number; lon?: number; id: string | number }) => void;
}

export function AIExpandedPanel({
  isExpanded,
  messages,
  onPropertyClick,
}: AIExpandedPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesLengthRef = useRef(messages.length);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (isExpanded && messagesEndRef.current && messages.length > messagesLengthRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
    messagesLengthRef.current = messages.length;
  }, [isExpanded, messages]);

  if (!isExpanded) {
    return null;
  }

  return (
    <div className="fixed inset-x-0 bottom-28 z-40 mx-auto w-full max-w-3xl px-3 sm:px-4">
      <div className="glass-panel rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[64vh]">
        <div className="flex items-center justify-between px-4 py-2 border-b border-white/[0.06] bg-white/[0.02]">
          <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60">
            AI Agent
          </p>
          <span className="text-[11px] text-muted-foreground/80">
            {messages.length} {messages.length === 1 ? "message" : "messages"}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-3 sm:px-4 sm:py-4 space-y-4 custom-scrollbar">
          {messages.length === 0 && (
            <div className="rounded-xl border border-dashed border-white/10 bg-white/[0.02] p-4 text-sm text-muted-foreground/60">
              Start with a prompt below. Use map attachments when you need the
              agent to ground analysis to a location, area, or selected property.
            </div>
          )}

          {messages.map((message) =>
            message.role === "user" ? (
              <UserMessage key={message.id} message={message} />
            ) : (
              <AssistantMessage
                key={message.id}
                message={message}
                onPropertyClick={onPropertyClick}
              />
            )
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>
    </div>
  );
}

// User Message Component
function UserMessage({ message }: { message: AgentMessage }) {
  return (
    <div className="flex gap-2 justify-end">
      <div className="flex-1 min-w-0 flex justify-end">
        <div className="max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm bg-gradient-to-br from-brand to-brand/80 text-brand-foreground shadow-sm">
          <div className="whitespace-pre-wrap break-words">{message.content}</div>
        </div>
      </div>
      <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-gradient-to-br from-brand to-brand/70 shadow-sm">
        <User size={12} className="text-white" />
      </div>
    </div>
  );
}

// Assistant Message Component with rich UI
interface AssistantMessageProps {
  message: AgentMessage;
  onPropertyClick?: (property: { lat?: number; lon?: number; id: string | number }) => void;
}

function AssistantMessage({ message, onPropertyClick }: AssistantMessageProps) {
  const [showSteps, setShowSteps] = useState(false);
  const hasSteps = message.steps && message.steps.length > 0;
  const stepsCount = message.steps?.length || 0;
  const thinkingCount =
    message.steps?.filter((s) => s.type === "thinking").length || 0;
  const toolCount =
    message.steps?.filter((s) => s.type === "tool_call").length || 0;

  // Parse property results from content
  const propertyResults = message.content ? parsePropertyResults(message.content) : null;
  const cleanContent = message.content ? cleanContentFromPropertyMarkers(message.content) : "";

  // Check if any step is still running
  const hasRunningStep = message.steps?.some((s) => s.status === "running");

  return (
    <div className="flex gap-2">
      <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-ai-surface border border-ai-border">
        <Bot size={12} className="text-ai-accent" />
      </div>
      <div className="flex-1 space-y-2 min-w-0">
        {/* Thinking indicator with rich animation */}
        {message.isThinking && !message.content && (
          <ThinkingProcess
            startTime={message.thinkingStartTime || Date.now()}
            className="max-w-full"
          />
        )}

        {/* Tool steps section */}
        {hasSteps && (
          <div className="space-y-1">
            {/* Collapsible header */}
            <button
              type="button"
              onClick={() => setShowSteps(!showSteps)}
              className={cn(
                "flex items-center gap-1.5 text-[10px] transition-colors",
                showSteps ? "text-muted-foreground" : "text-muted-foreground/70 hover:text-muted-foreground"
              )}
            >
              {showSteps ? (
                <ChevronUp size={12} />
              ) : (
                <ChevronDown size={12} />
              )}
              <span>
                {hasRunningStep
                  ? "Thinking and executing..."
                  : thinkingCount > 0
                    ? `Thinking sequence (${thinkingCount}) + ${toolCount} tool${toolCount !== 1 ? "s" : ""}`
                    : `Used ${stepsCount} tool${stepsCount !== 1 ? "s" : ""}`}
              </span>
            </button>

            {/* Expanded steps view */}
            {showSteps && (
              <div className="space-y-1.5 animate-in slide-in-from-top-1 fade-in duration-200">
                {message.steps?.map((step) => (
                  <AgentStepCard key={step.id} step={step} />
                ))}
              </div>
            )}

            {/* Collapsed badge view */}
            {!showSteps && stepsCount > 0 && (
              <div className="flex flex-wrap gap-1">
                {message.steps?.slice(0, 3).map((step) => (
                  <AgentStepBadge
                    key={step.id}
                    step={step}
                    onClick={() => setShowSteps(true)}
                  />
                ))}
                {stepsCount > 3 && (
                  <button
                    type="button"
                    onClick={() => setShowSteps(true)}
                    className="text-[10px] text-muted-foreground/60 hover:text-muted-foreground px-2"
                  >
                    +{stepsCount - 3} more
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Message content with streaming cursor and markdown rendering */}
        {message.error && <AgentErrorCard error={message.error} />}

        {cleanContent && (
          <div className="max-w-full rounded-xl px-3.5 py-2.5 text-sm bg-surface-1 border border-white/[0.06]">
            <StreamingMarkdown content={cleanContent} isStreaming={message.isStreaming} />
          </div>
        )}

        {/* Property results card */}
        {propertyResults && propertyResults.length > 0 && (
          <PropertyResultsCard
            results={propertyResults}
            totalCount={propertyResults.length}
            priceRange={
              propertyResults.length > 0
                ? {
                    min: Math.min(...propertyResults.map((p) => p.price)),
                    max: Math.max(...propertyResults.map((p) => p.price)),
                  }
                : undefined
            }
            onPropertyClick={(p) =>
              onPropertyClick?.({ lat: p.lat, lon: p.lon, id: p.id })
            }
            className="mt-2"
          />
        )}
      </div>
    </div>
  );
}
