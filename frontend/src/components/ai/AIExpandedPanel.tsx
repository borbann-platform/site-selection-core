import { useRef, useEffect, useState } from "react";
import { Bot, User, ChevronDown, ChevronUp } from "lucide-react";
import type { FilterValues } from "./QuickFilters";
import { QuickFilters } from "./QuickFilters";
import { ThinkingProcess, StreamingText } from "../ThinkingIndicator";
import { AgentStepCard, AgentStepBadge } from "../AgentStepCard";
import {
  PropertyResultsCard,
  parsePropertyResults,
  cleanContentFromPropertyMarkers,
} from "./PropertyResultsCard";
import type { AgentStep } from "../../lib/api";
import { cn } from "../../lib/utils";

export interface AgentMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  steps?: AgentStep[];
  isStreaming?: boolean;
  isThinking?: boolean;
  thinkingStartTime?: number;
}

interface AIExpandedPanelProps {
  isExpanded: boolean;
  messages: AgentMessage[];
  filterValues: FilterValues;
  onFilterChange: (values: FilterValues) => void;
  onPropertyClick?: (property: { lat?: number; lon?: number; id: string | number }) => void;
}

export function AIExpandedPanel({
  isExpanded,
  messages,
  filterValues,
  onFilterChange,
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
    <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-40 w-full max-w-2xl px-4">
      <div className="bg-zinc-900/95 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[60vh]">
        {/* Conversation History */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 custom-scrollbar">
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

        {/* Quick Filters */}
        <QuickFilters values={filterValues} onChange={onFilterChange} />
      </div>
    </div>
  );
}

// User Message Component
function UserMessage({ message }: { message: AgentMessage }) {
  return (
    <div className="flex gap-2 justify-end">
      <div className="flex-1 min-w-0 flex justify-end">
        <div className="max-w-[85%] rounded-xl px-3 py-2 text-sm bg-emerald-600 text-white">
          <div className="whitespace-pre-wrap break-words">{message.content}</div>
        </div>
      </div>
      <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-emerald-600">
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

  // Parse property results from content
  const propertyResults = message.content ? parsePropertyResults(message.content) : null;
  const cleanContent = message.content ? cleanContentFromPropertyMarkers(message.content) : "";

  // Check if any step is still running
  const hasRunningStep = message.steps?.some((s) => s.status === "running");

  return (
    <div className="flex gap-2">
      <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-emerald-500/20">
        <Bot size={12} className="text-emerald-400" />
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
                showSteps ? "text-white/70" : "text-white/50 hover:text-white/70"
              )}
            >
              {showSteps ? (
                <ChevronUp size={12} />
              ) : (
                <ChevronDown size={12} />
              )}
              <span>
                {hasRunningStep
                  ? `Running tool ${stepsCount}...`
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
                    className="text-[10px] text-white/40 hover:text-white/60 px-2"
                  >
                    +{stepsCount - 3} more
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Message content with streaming cursor */}
        {cleanContent && (
          <div className="max-w-full rounded-xl px-3 py-2 text-sm bg-white/5 text-white/90">
            <div className="whitespace-pre-wrap break-words">
              <StreamingText text={cleanContent} isStreaming={message.isStreaming} />
            </div>
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
