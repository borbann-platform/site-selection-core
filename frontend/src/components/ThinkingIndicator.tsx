import { useEffect, useMemo, useState } from "react";
import { Activity, Binary, Orbit, Search, Sparkles } from "lucide-react";
import { cn } from "../lib/utils";

interface ThinkingProcessProps {
  className?: string;
  startTime?: number;
}

const PROCESS_STEPS = [
  { label: "Parsing prompt geometry", icon: Search },
  { label: "Reconciling market evidence", icon: Activity },
  { label: "Cross-checking tool outputs", icon: Binary },
  { label: "Composing final answer", icon: Sparkles },
  { label: "Aligning spatial context", icon: Orbit },
] as const;

function formatElapsed(ms: number) {
  const seconds = ms / 1000;
  return `${seconds.toFixed(seconds >= 10 ? 0 : 1)}s`;
}

export function ThinkingProcess({ className, startTime }: ThinkingProcessProps) {
  const [elapsed, setElapsed] = useState(0);
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (!startTime) {
      return undefined;
    }

    const interval = window.setInterval(() => {
      setElapsed(Date.now() - startTime);
    }, 120);

    return () => window.clearInterval(interval);
  }, [startTime]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setStepIndex((current) => (current + 1) % PROCESS_STEPS.length);
    }, 1800);

    return () => window.clearInterval(interval);
  }, []);

  const visibleSteps = useMemo(() => {
    return PROCESS_STEPS.map((step, index) => ({
      ...step,
      state:
        index < stepIndex ? "complete" : index === stepIndex ? "active" : "idle",
    }));
  }, [stepIndex]);

  const ActiveIcon = PROCESS_STEPS[stepIndex]?.icon ?? Activity;

  return (
    <div
      className={cn(
        "rounded-[1.25rem] border border-black/8 bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(250,247,242,0.96))] p-3 shadow-[0_14px_32px_rgba(23,27,33,0.08)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(24,28,33,0.92),rgba(15,17,20,0.96))] dark:shadow-[0_18px_44px_rgba(0,0,0,0.35)]",
        className
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.28em] text-foreground/45">
            Live Reasoning
          </div>
          <div className="mt-1 flex items-center gap-2 text-sm font-medium text-foreground">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-brand/20 bg-brand/10 text-brand">
              <ActiveIcon className="h-4 w-4" />
            </span>
            <span>{PROCESS_STEPS[stepIndex]?.label}</span>
          </div>
        </div>

        <div className="rounded-full border border-black/8 bg-black/[0.03] px-3 py-1 text-[11px] font-medium text-foreground/55 dark:border-white/10 dark:bg-white/[0.05]">
          {formatElapsed(elapsed)}
        </div>
      </div>

      <div className="mt-3 grid gap-1.5">
        {visibleSteps.map((step) => {
          const Icon = step.icon;
          return (
            <div
              key={step.label}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2 transition-all",
                step.state === "active" &&
                  "bg-black/[0.045] text-foreground dark:bg-white/[0.07]",
                step.state === "complete" &&
                  "text-foreground/62 dark:text-foreground/70",
                step.state === "idle" && "text-foreground/38"
              )}
            >
              <span
                className={cn(
                  "relative flex h-7 w-7 items-center justify-center rounded-full border transition-all",
                  step.state === "active" &&
                    "border-brand/30 bg-brand/12 text-brand shadow-[0_0_0_6px_rgba(24,163,127,0.08)]",
                  step.state === "complete" &&
                    "border-black/8 bg-black/[0.04] text-foreground/70 dark:border-white/10 dark:bg-white/[0.04]",
                  step.state === "idle" &&
                    "border-black/6 bg-transparent text-foreground/35 dark:border-white/8"
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {step.state === "active" && (
                  <span className="absolute inset-0 rounded-full border border-brand/30 animate-ping" />
                )}
              </span>
              <span className="text-[13px] font-medium">{step.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ThinkingIndicator({ className }: { className?: string }) {
  return <ThinkingProcess className={className} startTime={Date.now()} />;
}

export function ThinkingDots({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-xs text-muted-foreground", className)}>
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand/40" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-brand/80" />
      </span>
      processing
    </span>
  );
}

interface StreamingTextProps {
  text: string;
  isStreaming?: boolean;
  className?: string;
}

export function StreamingText({
  text,
  isStreaming = false,
  className,
}: StreamingTextProps) {
  const [showCursor, setShowCursor] = useState(true);

  useEffect(() => {
    if (!isStreaming) {
      setShowCursor(false);
      return undefined;
    }

    const interval = window.setInterval(() => {
      setShowCursor((current) => !current);
    }, 520);

    return () => window.clearInterval(interval);
  }, [isStreaming]);

  return (
    <span className={className}>
      {text}
      {isStreaming && (
        <span
          className={cn(
            "ml-1 inline-block h-4 w-2 rounded-full bg-brand/70 align-middle transition-opacity",
            showCursor ? "opacity-100" : "opacity-0"
          )}
        />
      )}
    </span>
  );
}
