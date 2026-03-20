import { useEffect, useMemo, useRef, useState } from "react";
import { Bot, ChevronDown, ChevronUp, Compass, User } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { ThinkingProcess } from "../ThinkingIndicator";
import { StreamingMarkdown } from "../ui/markdown";
import { AgentStepBadge, AgentStepCard } from "../AgentStepCard";
import {
  PropertyResultsCard,
  cleanContentFromPropertyMarkers,
  parsePropertyResults,
  type PropertyResult,
} from "./PropertyResultsCard";
import type { AgentStep, AgentRuntimeError } from "../../lib/api";
import { AgentErrorCard } from "../AgentErrorCard";
import {
  extractChatEntityReferences,
  parseStructuredPropertyReferences,
  stripStructuredChatMarkers,
} from "../../lib/chatReferences";

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
  const previousLengthRef = useRef(messages.length);

  useEffect(() => {
    if (isExpanded && messages.length > previousLengthRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
    previousLengthRef.current = messages.length;
  }, [isExpanded, messages.length]);

  if (!isExpanded) {
    return null;
  }

  return (
    <div className="fixed inset-x-0 bottom-28 z-40 mx-auto w-full max-w-4xl px-3 sm:px-4">
      <div className="overflow-hidden rounded-[1.5rem] border border-black/8 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(248,246,241,0.96))] shadow-[0_24px_80px_rgba(23,27,33,0.16)] backdrop-blur-xl dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(23,27,31,0.96),rgba(14,17,20,0.98))]">
        <div className="flex items-center justify-between border-b border-black/6 px-4 py-3 dark:border-white/8">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.28em] text-foreground/40">
              Execution Trace
            </div>
            <div className="mt-0.5 text-[13px] text-foreground/68">
              Live reasoning, retrieved evidence, and property references from this session.
            </div>
          </div>
          <div className="rounded-full border border-black/8 bg-black/[0.03] px-3 py-1 text-[11px] font-medium text-foreground/55 dark:border-white/10 dark:bg-white/[0.05]">
            {messages.length} {messages.length === 1 ? "message" : "messages"}
          </div>
        </div>

        <div className="max-h-[46vh] overflow-y-auto px-4 py-3 custom-scrollbar">
          <div className="space-y-4">
            {messages.length === 0 ? (
              <div className="rounded-[1.25rem] border border-dashed border-black/10 bg-black/[0.02] px-5 py-6 text-center text-sm text-foreground/58 dark:border-white/12 dark:bg-white/[0.03]">
                Start with a prompt, attach a map location when useful, and the trace will show how the assistant reasons through the task.
              </div>
            ) : (
              messages.map((message) =>
                message.role === "user" ? (
                  <UserMessage key={message.id} message={message} />
                ) : (
                  <AssistantMessage
                    key={message.id}
                    message={message}
                    onPropertyClick={onPropertyClick}
                  />
                )
              )
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>
      </div>
    </div>
  );
}

function UserMessage({ message }: { message: AgentMessage }) {
  return (
    <div className="flex justify-end">
      <div className="flex max-w-[86%] items-start gap-3">
        <div className="rounded-[1.6rem] bg-[linear-gradient(180deg,#19212b,#0f1720)] px-4 py-3 text-[15px] leading-7 text-white shadow-[0_16px_40px_rgba(15,23,42,0.2)]">
          <div className="whitespace-pre-wrap break-words">{message.content}</div>
        </div>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-black/10 bg-white text-foreground shadow-[0_10px_28px_rgba(15,23,42,0.08)] dark:border-white/10 dark:bg-white/[0.07] dark:text-foreground">
          <User className="h-4 w-4" />
        </div>
      </div>
    </div>
  );
}

interface AssistantMessageProps {
  message: AgentMessage;
  onPropertyClick?: (property: { lat?: number; lon?: number; id: string | number }) => void;
}

function AssistantMessage({ message, onPropertyClick }: AssistantMessageProps) {
  const [showSteps, setShowSteps] = useState(false);
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

  const hasSteps = Boolean(message.steps?.length);
  const stepsCount = message.steps?.length ?? 0;
  const thinkingCount = message.steps?.filter((step) => step.type === "thinking").length ?? 0;
  const toolCount = message.steps?.filter((step) => step.type === "tool_call").length ?? 0;
  const hasRunningStep = message.steps?.some((step) => step.status === "running");

  return (
    <div className="flex items-start gap-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-brand/16 bg-brand/10 text-brand shadow-[0_10px_28px_rgba(24,163,127,0.12)]">
        <Bot className="h-4 w-4" />
      </div>

      <div className="min-w-0 flex-1 space-y-2.5">
        {message.isThinking && !message.content && (
          <ThinkingProcess startTime={message.thinkingStartTime || Date.now()} />
        )}

        {hasSteps && (
          <div className="rounded-[1.35rem] border border-black/8 bg-white/72 px-4 py-3 shadow-[0_14px_40px_rgba(15,23,42,0.05)] dark:border-white/10 dark:bg-white/[0.035] dark:shadow-none">
            <button
              type="button"
              onClick={() => setShowSteps((current) => !current)}
              className="flex w-full items-center justify-between gap-3 text-left"
            >
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-foreground/42">
                  Reasoning Trail
                </div>
                <div className="mt-1 text-sm text-foreground/74">
                  {hasRunningStep
                    ? "The model is still reasoning through the next step."
                    : thinkingCount > 0
                      ? `${thinkingCount} reasoning notes and ${toolCount} executed tools.`
                      : `Used ${stepsCount} tools.`}
                </div>
              </div>

              <div className="inline-flex items-center gap-2 rounded-full border border-black/8 bg-black/[0.03] px-3 py-1 text-[11px] font-medium text-foreground/55 dark:border-white/10 dark:bg-white/[0.04]">
                {showSteps ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                {showSteps ? "Hide" : "Reveal"}
              </div>
            </button>

            {showSteps ? (
              <div className="mt-3 space-y-2">
                {message.steps?.map((step) => (
                  <AgentStepCard key={step.id} step={step} />
                ))}
              </div>
            ) : (
              <div className="mt-3 flex flex-wrap gap-2">
                {message.steps?.slice(0, 4).map((step) => (
                  <AgentStepBadge
                    key={step.id}
                    step={step}
                    onClick={() => setShowSteps(true)}
                  />
                ))}
                {stepsCount > 4 && (
                  <button
                    type="button"
                    onClick={() => setShowSteps(true)}
                    className="rounded-full border border-black/8 px-3 py-1 text-[10px] font-medium text-foreground/55 transition-colors hover:bg-black/[0.03] dark:border-white/10 dark:hover:bg-white/[0.04]"
                  >
                    +{stepsCount - 4} more
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {message.error && <AgentErrorCard error={message.error} />}

        {cleanContent && (
          <div className="rounded-[1.35rem] border border-black/8 bg-white/86 px-4 py-3 shadow-[0_18px_44px_rgba(15,23,42,0.06)] dark:border-white/10 dark:bg-white/[0.04] dark:shadow-none">
            <StreamingMarkdown content={cleanContent} isStreaming={message.isStreaming} />
          </div>
        )}

        {references.length > 0 && (
          <div className="rounded-[1.25rem] border border-black/8 bg-black/[0.02] px-4 py-3 dark:border-white/10 dark:bg-white/[0.03]">
            <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.22em] text-foreground/42">
              <Compass className="h-3.5 w-3.5" />
              Referenced Properties
            </div>
            <div className="flex flex-wrap gap-2">
              {references.map((reference) =>
                reference.kind === "listing" && reference.listingKey ? (
                  <Link
                    key={reference.key}
                    to="/listing/$listingKey"
                    params={{ listingKey: reference.listingKey }}
                    className="inline-flex items-center gap-2 rounded-full border border-brand/20 bg-brand/10 px-3 py-1.5 text-xs font-medium text-brand transition-colors hover:bg-brand/16"
                  >
                    <span>{reference.label}</span>
                    {reference.note ? <span className="text-brand/70">{reference.note}</span> : null}
                  </Link>
                ) : reference.propertyId ? (
                  <Link
                    key={reference.key}
                    to="/property/$propertyId"
                    params={{ propertyId: reference.propertyId }}
                    className="inline-flex items-center gap-2 rounded-full border border-brand/20 bg-brand/10 px-3 py-1.5 text-xs font-medium text-brand transition-colors hover:bg-brand/16"
                  >
                    <span>{reference.label}</span>
                    {reference.note ? <span className="text-brand/70">{reference.note}</span> : null}
                  </Link>
                ) : null
              )}
            </div>
          </div>
        )}

        {propertyResults && propertyResults.length > 0 && (
          <PropertyResultsCard
            results={propertyResults}
            totalCount={propertyResults.length}
            priceRange={{
              min: Math.min(...propertyResults.map((property) => property.price)),
              max: Math.max(...propertyResults.map((property) => property.price)),
            }}
            onPropertyClick={(property) =>
              onPropertyClick?.({ lat: property.lat, lon: property.lon, id: property.id })
            }
          />
        )}
      </div>
    </div>
  );
}
