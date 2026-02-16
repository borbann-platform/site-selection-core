import { useState } from "react";
import {
  Wrench,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ChevronDown,
  ChevronRight,
  Brain,
  MessageCircleQuestion,
} from "lucide-react";
import { cn } from "../lib/utils";
import type { AgentStep, AgentStepStatus } from "../lib/api";
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
  switch (status) {
    case "running":
      return <Loader2 size={14} className="animate-spin text-warning" />;
    case "complete":
      return <CheckCircle2 size={14} className="text-success" />;
    case "error":
      return <AlertCircle size={14} className="text-red-400" />;
    case "waiting":
      return <MessageCircleQuestion size={14} className="text-sky-400" />;
    default:
      return <Loader2 size={14} className="text-muted-foreground" />;
  }
}

function getStepIcon(type: "tool_call" | "thinking" | "waiting_user") {
  if (type === "thinking") {
    return <Brain size={14} className="text-purple-400" />;
  }
  if (type === "waiting_user") {
    return <MessageCircleQuestion size={14} className="text-sky-400" />;
  }
  return <Wrench size={14} className="text-blue-400" />;
}

function formatDuration(startTime: number, endTime?: number): string {
  const end = endTime ?? Date.now();
  const duration = end - startTime;
  if (duration < 1000) return `${duration}ms`;
  return `${(duration / 1000).toFixed(1)}s`;
}

export function AgentStepCard({ step, className }: AgentStepCardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const hasDetails =
    (step.input && Object.keys(step.input).length > 0) || step.output;

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div
        className={cn(
          "rounded-lg border border-border bg-muted/50 overflow-hidden",
          step.status === "running" && "border-amber-500/30",
          step.status === "error" && "border-red-500/30",
          className
        )}
      >
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-muted/50 transition-colors"
          >
            {/* Expand/collapse indicator */}
            {hasDetails ? (
              isOpen ? (
                <ChevronDown size={12} className="text-muted-foreground shrink-0" />
              ) : (
                <ChevronRight size={12} className="text-muted-foreground shrink-0" />
              )
            ) : (
              <div className="w-3" />
            )}

            {/* Step type icon */}
            <div className="shrink-0">{getStepIcon(step.type)}</div>

            {/* Step name */}
            <span className="flex-1 text-xs font-medium text-foreground/90 truncate">
              {step.name}
            </span>

            {/* Duration */}
            <span className="text-[10px] text-muted-foreground shrink-0">
              {formatDuration(step.startTime, step.endTime)}
            </span>

            {/* Status icon */}
            <div className="shrink-0">{getStatusIcon(step.status)}</div>
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="px-3 pb-2 space-y-2 border-t border-border">
            {/* Input parameters */}
            {step.input && Object.keys(step.input).length > 0 && (
              <div className="pt-2">
                <div className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1">
                  Input
                </div>
                <div className="text-xs text-muted-foreground font-mono bg-popover rounded px-2 py-1.5 overflow-x-auto">
                  <pre className="whitespace-pre-wrap break-all">
                    {JSON.stringify(step.input, null, 2)}
                  </pre>
                </div>
              </div>
            )}

            {/* Output/Result */}
            {step.output && (
              <div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1">
                  Result
                </div>
                <div
                  className={cn(
                    "text-xs font-mono bg-popover rounded px-2 py-1.5 overflow-x-auto max-h-32 overflow-y-auto custom-scrollbar",
                    step.status === "error" ? "text-red-300" : "text-muted-foreground"
                  )}
                >
                  <pre className="whitespace-pre-wrap break-all">
                    {step.output}
                  </pre>
                </div>
              </div>
            )}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

// Compact inline badge version for collapsed view
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
        "inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-medium transition-colors",
        "bg-muted/50 border border-border hover:bg-muted",
        step.status === "running" && "border-amber-500/30 bg-amber-500/10",
        step.status === "error" && "border-red-500/30 bg-red-500/10"
      )}
    >
      {getStepIcon(step.type)}
      <span className="text-foreground/80 max-w-20 truncate">{step.name}</span>
      {getStatusIcon(step.status)}
    </button>
  );
}
