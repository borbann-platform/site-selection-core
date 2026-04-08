import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Wrench } from "lucide-react";
import { Buildings, CompassRose, HouseLine, Robot, UserCircle } from "@phosphor-icons/react";
import { Link } from "@tanstack/react-router";
import { cn } from "@/lib/utils";
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
    <div className="fixed bottom-[17.5rem] left-1/2 z-40 w-[min(calc(100vw-1.5rem),56rem)] -translate-x-1/2 sm:bottom-[18rem] sm:w-[min(calc(100vw-2rem),56rem)] md:bottom-[13.5rem] lg:w-[min(calc(100vw-34rem),56rem)] xl:w-[min(calc(100vw-38rem),58rem)]">
      <div className="overflow-hidden rounded-2xl border border-border/90 bg-card/95 shadow-xl backdrop-blur-xl">
        <div className="flex items-start justify-between gap-4 border-b border-border/60 px-5 py-3.5">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
               Execution Trace
            </div>
            <div className="mt-1 max-w-2xl text-[13px] leading-6 text-muted-foreground">
              Live reasoning, retrieved evidence, and property references from this session.
            </div>
          </div>
          <div className="rounded-full border border-border/70 bg-muted/35 px-3 py-1 text-[11px] font-medium text-muted-foreground">
            {messages.length} {messages.length === 1 ? "message" : "messages"}
          </div>
        </div>

        <div className="max-h-[52vh] overflow-y-auto px-5 py-4 custom-scrollbar sm:max-h-[58vh] sm:px-6 sm:py-5">
          <div className="space-y-5">
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
      <div className="flex max-w-[92%] items-start gap-3 sm:max-w-[80%]">
        <div className="rounded-[1.25rem] border border-border/70 bg-card/95 px-4 py-3.5 text-[14px] leading-7 text-foreground shadow-lg sm:px-5">
          <div className="whitespace-pre-wrap break-words">{message.content}</div>
        </div>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border/70 bg-card text-foreground shadow-md">
          <UserCircle className="h-4 w-4" weight="duotone" />
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
  const latestStep = message.steps?.at(-1);
  const runningStep = message.steps?.find((step) => step.status === "running");
  const activeStep = runningStep || latestStep;
  const activeStepLabel = activeStep
    ? activeStep.type === "tool_call"
      ? `Running ${activeStep.name}`
      : activeStep.output || activeStep.name
    : undefined;

  return (
    <div className="flex items-start gap-3.5">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border/70 bg-card text-brand shadow-md">
        <Robot className="h-4 w-4" weight="duotone" />
      </div>

      <div className="min-w-0 flex-1 space-y-3">
        {message.isThinking && !message.content && (
          <ThinkingProcess
            startTime={message.thinkingStartTime || Date.now()}
            statusLabel={activeStepLabel || "Reasoning through the request"}
            mode={activeStep?.type === "tool_call" ? "tool" : "thinking"}
          />
        )}

        {hasSteps && (
          <div className="rounded-[1.2rem] border border-border/70 bg-card/80 px-4 py-3 shadow-md">
            <button
              type="button"
              onClick={() => setShowSteps((current) => !current)}
              className="flex w-full items-center justify-between gap-3 text-left"
            >
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  Reasoning Trail
                </div>
                <div className="mt-1 flex items-center gap-2 text-[13px] text-muted-foreground">
                  {activeStep?.type === "tool_call" ? (
                    <Wrench className="h-3.5 w-3.5 text-brand" />
                  ) : null}
                  <span>
                    {activeStepLabel || `Used ${stepsCount} steps in this answer.`}
                  </span>
                </div>
              </div>

              <div className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-muted/35 px-3 py-1 text-[11px] font-medium text-muted-foreground">
                {showSteps ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                {showSteps ? "Hide" : `${stepsCount} ${stepsCount === 1 ? "step" : "steps"}`}
              </div>
            </button>

            {showSteps ? (
              <div className="mt-3 space-y-2">
                {message.steps?.map((step) => (
                  <AgentStepCard key={step.id} step={step} />
                ))}
              </div>
            ) : (
              <div className="mt-3 flex items-center justify-between gap-3 rounded-xl border border-border/60 bg-muted/25 px-3 py-2">
                <div className="min-w-0">
                  {activeStep ? (
                    <AgentStepBadge step={activeStep} onClick={() => setShowSteps(true)} />
                  ) : null}
                </div>
                <div className="shrink-0 text-[11px] text-muted-foreground">
                  Full trace on demand
                </div>
              </div>
            )}
          </div>
        )}

        {message.error && <AgentErrorCard error={message.error} />}

        {cleanContent && (
          <div className="rounded-[1.25rem] border border-border/70 bg-card/95 px-4 py-4 shadow-md sm:px-5 sm:py-5">
            <StreamingMarkdown
              content={cleanContent}
              isStreaming={message.isStreaming}
              className="max-w-none text-[15px] leading-8"
            />

            {references.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2 border-t border-border/60 pt-4">
                {references.map((reference) => (
                  <ReferenceChip key={`inline-${reference.key}`} reference={reference} />
                ))}
              </div>
            )}
          </div>
        )}

        {references.length > 0 && (
          <div className="rounded-[1.2rem] border border-border/70 bg-muted/25 px-4 py-3">
            <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              <CompassRose className="h-3.5 w-3.5" weight="duotone" />
              Referenced Links
            </div>
            <div className="flex flex-wrap gap-2">
              {references.map((reference) => (
                <ReferenceChip key={reference.key} reference={reference} />
              ))}
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

function ReferenceChip({ reference }: { reference: { key: string; label: string; kind: "property" | "listing"; propertyId?: string; listingKey?: string; note?: string } }) {
  const content = (
    <>
      {reference.kind === "listing" ? (
        <Buildings className="h-3.5 w-3.5 text-brand" weight="duotone" />
      ) : (
        <HouseLine className="h-3.5 w-3.5 text-brand" weight="duotone" />
      )}
      <span className="max-w-[18rem] truncate">{reference.label}</span>
      {reference.note ? (
        <span className="truncate text-muted-foreground">{reference.note}</span>
      ) : null}
    </>
  );

  const className = cn(
    "inline-flex max-w-full items-center gap-2 rounded-full border border-border/70 bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted"
  );

  if (reference.kind === "listing" && reference.listingKey) {
    return (
      <Link
        to="/listing/$listingKey"
        params={{ listingKey: reference.listingKey }}
        className={className}
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
        className={className}
        title={`Open property ${reference.propertyId}`}
      >
        {content}
      </Link>
    );
  }

  return null;
}
