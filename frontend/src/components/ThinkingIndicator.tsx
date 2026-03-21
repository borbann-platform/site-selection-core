import { useEffect, useMemo, useState } from "react";
import { Loader2, Sparkles, Wrench } from "lucide-react";
import { cn } from "../lib/utils";

interface ThinkingProcessProps {
  className?: string;
  startTime?: number;
  statusLabel?: string;
  mode?: "thinking" | "tool";
}

function formatElapsed(ms: number) {
  const seconds = ms / 1000;
  return `${seconds.toFixed(seconds >= 10 ? 0 : 1)}s`;
}

export function ThinkingProcess({
  className,
  startTime,
  statusLabel = "Reasoning through the request",
  mode = "thinking",
}: ThinkingProcessProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!startTime) {
      return undefined;
    }

    const interval = window.setInterval(() => {
      setElapsed(Date.now() - startTime);
    }, 120);

    return () => window.clearInterval(interval);
  }, [startTime]);

  const Icon = useMemo(() => {
    return mode === "tool" ? Wrench : Sparkles;
  }, [mode]);

  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 rounded-xl border border-border/70 bg-card/92 px-3.5 py-2.5 shadow-sm",
        className,
      )}
    >
      <div className="flex min-w-0 items-center gap-3">
        <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border/70 bg-muted/35 text-brand">
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
            Live status
          </div>
          <div className="truncate text-sm font-medium text-foreground">
            {statusLabel}
          </div>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 rounded-full border border-border/70 bg-muted/35 px-3 py-1 text-[11px] font-medium text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        {formatElapsed(elapsed)}
      </div>
    </div>
  );
}

export function ThinkingIndicator({ className }: { className?: string }) {
  return <ThinkingProcess className={className} startTime={Date.now()} />;
}

export function ThinkingDots({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 text-xs text-muted-foreground",
        className,
      )}
    >
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
            showCursor ? "opacity-100" : "opacity-0",
          )}
        />
      )}
    </span>
  );
}
