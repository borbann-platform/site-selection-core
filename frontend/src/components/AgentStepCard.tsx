import { useState } from "react";
import {
  Binary,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Loader2,
  MessageCircleQuestion,
  Sparkles,
  Wrench,
  XCircle,
} from "lucide-react";
import { cn } from "../lib/utils";
import type { AgentStep, AgentStepStatus } from "../lib/api";
import { StreamingMarkdown } from "./ui/markdown";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "./ui/collapsible";

interface AgentStepCardProps {
  step: AgentStep;
  className?: string;
}

function getStatusIcon(status: AgentStepStatus) {
  if (status === "running") {
    return <Loader2 size={14} className="animate-spin text-brand" />;
  }
  if (status === "complete") {
    return <CheckCircle2 size={14} className="text-emerald-600 dark:text-emerald-400" />;
  }
  if (status === "error") {
    return <XCircle size={14} className="text-rose-600 dark:text-rose-400" />;
  }
  if (status === "waiting") {
    return <MessageCircleQuestion size={14} className="text-amber-600 dark:text-amber-400" />;
  }
  return <Binary size={14} className="text-muted-foreground" />;
}

function getStepIcon(type: "tool_call" | "thinking" | "waiting_user") {
  if (type === "thinking") {
    return <Sparkles size={14} className="text-brand" />;
  }
  if (type === "waiting_user") {
    return <MessageCircleQuestion size={14} className="text-amber-600 dark:text-amber-400" />;
  }
  return <Wrench size={14} className="text-foreground/72" />;
}

function formatDuration(startTime: number, endTime?: number) {
  const duration = (endTime ?? Date.now()) - startTime;
  if (duration < 1000) {
    return `${duration}ms`;
  }
  return `${(duration / 1000).toFixed(duration >= 10_000 ? 0 : 1)}s`;
}

export function AgentStepCard({ step, className }: AgentStepCardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const hasDetails =
    Boolean(step.output) || Boolean(step.input && Object.keys(step.input).length > 0);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div
        className={cn(
          "overflow-hidden rounded-[1.15rem] border border-border/70 bg-card/90 shadow-sm",
          step.status === "running" &&
            "border-brand/18 bg-brand/[0.045]",
          step.status === "error" && "border-rose-500/18 bg-rose-500/[0.04]",
          className
        )}
      >
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/35"
          >
            {hasDetails ? (
              isOpen ? (
                <ChevronDown size={14} className="shrink-0 text-muted-foreground" />
              ) : (
                <ChevronRight size={14} className="shrink-0 text-muted-foreground" />
              )
            ) : (
              <span className="w-[14px]" />
            )}

            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border/70 bg-muted/35">
              {getStepIcon(step.type)}
            </span>

            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-medium text-foreground">
                {step.name}
              </div>
              <div className="mt-0.5 text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                {step.type === "thinking"
                  ? "reasoning"
                  : step.type === "waiting_user"
                    ? "awaiting input"
                    : "tool execution"}
              </div>
            </div>

            <div className="text-right">
              <div className="text-[11px] font-medium text-foreground/52">
                {formatDuration(step.startTime, step.endTime)}
              </div>
            </div>

            <span className="shrink-0">{getStatusIcon(step.status)}</span>
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="space-y-3 border-t border-border/60 px-4 pb-4 pt-3">
            {step.input && Object.keys(step.input).length > 0 && (
              <section>
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                  Input
                </div>
                <pre className="overflow-x-auto rounded-[0.95rem] border border-border/70 bg-muted/35 px-3 py-2 text-[11px] leading-5 text-foreground/72">
                  {JSON.stringify(step.input, null, 2)}
                </pre>
              </section>
            )}

            {step.output && (
              <section>
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                  Output
                </div>
                {step.type === "thinking" || step.type === "waiting_user" ? (
                  <div className="rounded-[0.95rem] border border-border/70 bg-muted/30 px-3 py-2">
                    <StreamingMarkdown
                      content={step.output}
                      isStreaming={step.status === "running"}
                    />
                  </div>
                ) : (
                  <pre
                    className={cn(
                      "max-h-56 overflow-auto rounded-[0.95rem] border border-border/70 bg-muted/35 px-3 py-2 text-[11px] leading-5 text-foreground/72",
                      step.status === "error" && "text-rose-700 dark:text-rose-300"
                    )}
                  >
                    {step.output}
                  </pre>
                )}
              </section>
            )}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

interface AgentStepBadgeProps {
  step: AgentStep;
  onClick?: () => void;
}

export function AgentStepBadge({ step, onClick }: AgentStepBadgeProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium transition-colors",
        "border-border/70 bg-card text-foreground/72 hover:bg-muted/35",
        step.status === "running" && "border-brand/18 bg-brand/10 text-brand",
        step.status === "error" && "border-rose-500/18 bg-rose-500/10 text-rose-700 dark:text-rose-300"
      )}
    >
      {getStepIcon(step.type)}
      <span className="max-w-28 truncate">{step.name}</span>
      {getStatusIcon(step.status)}
    </button>
  );
}
