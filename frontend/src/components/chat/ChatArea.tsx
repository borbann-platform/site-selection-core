/**
 * ChatArea - Main chat message display and input area
 */

import { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { Send, Square, Bot, User, Loader2, ChevronDown, ChevronUp, Sparkles } from "lucide-react";
import { Buildings, CompassRose, HouseLine } from "@phosphor-icons/react";
import { Link } from "@tanstack/react-router";
import { cn } from "../../lib/utils";
import { useChatStore, type LocalMessage } from "../../stores/chatStore";
import { StreamingMarkdown } from "../ui/markdown";
import { AgentStepCard, AgentStepBadge } from "../AgentStepCard";
import { AgentErrorCard } from "../AgentErrorCard";
import { ThinkingProcess } from "../ThinkingIndicator";
import {
  PropertyResultsCard,
  cleanContentFromPropertyMarkers,
  parsePropertyResults,
  type PropertyResult,
} from "../ai/PropertyResultsCard";
import {
  extractChatEntityReferences,
  parseStructuredPropertyReferences,
  stripStructuredChatMarkers,
  type ChatEntityReference,
} from "../../lib/chatReferences";

export function ChatArea() {
  const {
    messages,
    currentSessionId,
    messagesLoading,
    isStreaming,
    sendMessage,
    stopStreaming,
  } = useChatStore();

  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messageCount = messages.length;
  const activeSessionId = currentSessionId;

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (messageCount === 0) return;
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messageCount]);

  // Focus input on session change
  useEffect(() => {
    if (!activeSessionId) return;
    inputRef.current?.focus();
  }, [activeSessionId]);

  const handleSubmit = useCallback(async () => {
    const trimmedInput = input.trim();
    if (!trimmedInput || isStreaming) return;

    setInput("");
    try {
      await sendMessage(trimmedInput);
    } catch (error) {
      console.error("Failed to send message:", error);
    }
  }, [input, isStreaming, sendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Auto-resize textarea
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    // Reset height to auto to get the correct scrollHeight
    e.target.style.height = "auto";
    // Set height to scrollHeight, but max at 200px
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
  };

  if (!currentSessionId) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
        <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center mb-4">
          <Sparkles className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-xl font-semibold mb-2">Welcome to Bangkok Real Estate AI</h2>
        <p className="text-muted-foreground max-w-md mb-6">
          Ask me anything about Bangkok real estate - property prices, market trends,
          neighborhood analysis, and more.
        </p>
        <div className="flex flex-wrap gap-2 justify-center max-w-lg">
          {[
            "What are the average property prices in Sukhumvit?",
            "Find affordable condos near BTS stations",
            "Compare Thonglor vs Ekkamai neighborhoods",
          ].map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => setInput(suggestion)}
              className="px-3 py-2 text-sm bg-muted hover:bg-muted/80 rounded-lg transition-colors text-left"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (messagesLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <p className="text-muted-foreground">
                Start a conversation by sending a message below.
              </p>
            </div>
          ) : (
            messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="border-t border-border p-4">
        <div className="max-w-3xl mx-auto">
          <div className="relative flex items-end bg-input-background rounded-xl border border-border focus-within:ring-2 focus-within:ring-ring">
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Ask about Bangkok real estate..."
              rows={1}
              disabled={isStreaming}
              className="flex-1 bg-transparent px-4 py-3 text-sm resize-none focus:outline-none disabled:opacity-50 min-h-[44px] max-h-[200px]"
              style={{ height: "44px" }}
            />
            {isStreaming ? (
              <button
                type="button"
                onClick={stopStreaming}
                className="p-2 m-1.5 rounded-xl transition-colors bg-destructive text-destructive-foreground hover:bg-destructive/90"
                title="Stop generating"
                aria-label="Stop generating"
              >
                <Square className="w-5 h-5" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={!input.trim()}
                className={cn(
                  "p-2 m-1.5 rounded-xl transition-colors",
                  input.trim()
                    ? "bg-primary text-primary-foreground hover:bg-primary/90"
                    : "bg-muted-foreground/20 text-muted-foreground cursor-not-allowed"
                )}
                aria-label="Send message"
              >
                <Send className="w-5 h-5" />
              </button>
            )}
          </div>
          <p className="text-xs text-muted-foreground text-center mt-2">
            Press Enter to send, Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  );
}

// Message Bubble Component
function MessageBubble({ message }: { message: LocalMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex gap-3 justify-end">
        <div className="max-w-[85%] rounded-2xl px-4 py-2.5 bg-primary text-primary-foreground">
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center flex-shrink-0">
          <User className="w-4 h-4 text-white" />
        </div>
      </div>
    );
  }

  return <AssistantMessage message={message} />;
}

// Assistant Message with tool steps and property references
function AssistantMessage({ message }: { message: LocalMessage }) {
  const [showSteps, setShowSteps] = useState(false);
  const hasSteps = message.steps && message.steps.length > 0;
  const stepsCount = message.steps?.length || 0;
  const hasRunningStep = message.steps?.some((s) => s.status === "running");
  const thinkingCount =
    message.steps?.filter((s) => s.type === "thinking").length || 0;
  const toolCount =
    message.steps?.filter((s) => s.type === "tool_call").length || 0;

  // Parse property references from message content
  const structuredPropertyResults = message.content
    ? parseStructuredPropertyReferences(message.content)
    : [];
  const propertyResults: PropertyResult[] | null =
    structuredPropertyResults.length > 0
      ? structuredPropertyResults.map((property) => ({
          id: property.id,
          listing_key: property.listing_key,
          source_type:
            property.source_type === "scraped_project" ||
            property.source_type === "market_listing" ||
            property.source_type === "condo_project"
              ? property.source_type
              : ("house_price" as const),
          price: property.price ?? property.total_price ?? 0,
          district: property.district ?? property.amphur ?? "Unknown",
          area: property.area ?? property.building_area,
          style: property.style ?? property.building_style_desc,
          lat: property.lat,
          lon: property.lon,
        }))
      : message.content
        ? parsePropertyResults(message.content)
        : null;
  const cleanContent = message.content
    ? stripStructuredChatMarkers(
        cleanContentFromPropertyMarkers(message.content)
      )
    : "";
  const references = useMemo(() => {
    return extractChatEntityReferences(cleanContent, propertyResults ?? []);
  }, [cleanContent, propertyResults]);

  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
        <Bot className="w-4 h-4 text-primary-foreground" />
      </div>
      <div className="flex-1 space-y-2 min-w-0 max-w-[85%]">
        {/* Thinking indicator */}
        {message.isStreaming && !message.content && (
          <ThinkingProcess startTime={Date.now()} />
        )}

        {/* Tool steps */}
        {hasSteps && (
          <div className="space-y-1">
            <button
              type="button"
              onClick={() => setShowSteps(!showSteps)}
              className={cn(
                "flex items-center gap-1.5 text-xs transition-colors",
                showSteps
                  ? "text-muted-foreground"
                  : "text-muted-foreground/70 hover:text-muted-foreground"
              )}
            >
              {showSteps ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              <span>
                {hasRunningStep
                  ? "Thinking and executing..."
                  : thinkingCount > 0
                    ? `Thinking sequence (${thinkingCount}) + ${toolCount} tool${toolCount !== 1 ? "s" : ""}`
                    : `Used ${stepsCount} tool${stepsCount !== 1 ? "s" : ""}`}
              </span>
            </button>

            {showSteps && (
              <div className="space-y-1.5 animate-in slide-in-from-top-1 fade-in duration-200">
                {message.steps?.map((step) => (
                  <AgentStepCard key={step.id} step={step} />
                ))}
              </div>
            )}

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
                    className="text-xs text-muted-foreground/60 hover:text-muted-foreground px-2"
                  >
                    +{stepsCount - 3} more
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Message content */}
        {message.error && <AgentErrorCard error={message.error} />}

        {cleanContent && (
          <div className="rounded-2xl px-4 py-2.5 glass border border-border/50">
            <StreamingMarkdown
              content={cleanContent}
              isStreaming={message.isStreaming}
            />

            {/* Inline reference chips */}
            {references.length > 0 && !message.isStreaming && (
              <div className="mt-3 flex flex-wrap gap-1.5 border-t border-border/50 pt-3">
                {references.map((reference) => (
                  <ReferenceChip key={`inline-${reference.key}`} reference={reference} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Property results card */}
        {propertyResults && propertyResults.length > 0 && !message.isStreaming && (
          <PropertyResultsCard
            results={propertyResults}
            totalCount={propertyResults.length}
            priceRange={{
              min: Math.min(...propertyResults.map((p) => p.price)),
              max: Math.max(...propertyResults.map((p) => p.price)),
            }}
          />
        )}

        {/* Referenced links section */}
        {references.length > 0 && !message.isStreaming && (
          <div className="rounded-xl border border-border/50 bg-muted/25 px-3 py-2">
            <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              <CompassRose className="h-3 w-3" weight="duotone" />
              Referenced Properties
            </div>
            <div className="flex flex-wrap gap-1.5">
              {references.map((reference) => (
                <ReferenceChip key={reference.key} reference={reference} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Reference chip component for linking to properties/listings
function ReferenceChip({ reference }: { reference: ChatEntityReference }) {
  const content = (
    <>
      {reference.kind === "listing" ? (
        <Buildings className="h-3 w-3 text-brand" weight="duotone" />
      ) : (
        <HouseLine className="h-3 w-3 text-brand" weight="duotone" />
      )}
      <span className="max-w-[14rem] truncate">{reference.label}</span>
      {reference.note ? (
        <span className="truncate text-muted-foreground">{reference.note}</span>
      ) : null}
    </>
  );

  const chipClassName = cn(
    "inline-flex max-w-full items-center gap-1.5 rounded-full border border-border/70 bg-card px-2.5 py-1 text-[11px] font-medium text-foreground transition-colors hover:bg-muted"
  );

  if (reference.kind === "listing" && reference.listingKey) {
    return (
      <Link
        to="/listing/$listingKey"
        params={{ listingKey: reference.listingKey }}
        className={chipClassName}
        title={`Open listing ${reference.listingKey}`}
      >
        {content}
      </Link>
    );
  }

  if (reference.propertyId) {
    return (
      <Link
        to="/property/$propertyId"
        params={{ propertyId: reference.propertyId }}
        className={chipClassName}
        title={`Open property ${reference.propertyId}`}
      >
        {content}
      </Link>
    );
  }

  return null;
}
