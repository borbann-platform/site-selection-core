import { useEffect, useState } from "react";
import { Brain, Loader2 } from "lucide-react";
import { cn } from "../lib/utils";

interface ThinkingIndicatorProps {
  className?: string;
  startTime?: number;
  message?: string;
}

export function ThinkingIndicator({
  className,
  startTime,
  message = "Thinking",
}: ThinkingIndicatorProps) {
  const [dots, setDots] = useState("");
  const [elapsed, setElapsed] = useState(0);

  // Animate dots
  useEffect(() => {
    const interval = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? "" : `${prev}.`));
    }, 400);
    return () => clearInterval(interval);
  }, []);

  // Track elapsed time
  useEffect(() => {
    if (!startTime) return;
    const interval = setInterval(() => {
      setElapsed(Date.now() - startTime);
    }, 100);
    return () => clearInterval(interval);
  }, [startTime]);

  const formatElapsed = () => {
    if (!startTime || elapsed < 1000) return null;
    return `${(elapsed / 1000).toFixed(1)}s`;
  };

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 px-3 py-2 rounded-lg",
        "bg-purple-500/10 border border-purple-500/20",
        className
      )}
    >
      <div className="relative">
        <Brain size={16} className="text-purple-400" />
        <div className="absolute inset-0 animate-ping">
          <Brain size={16} className="text-purple-400 opacity-50" />
        </div>
      </div>
      <span className="text-xs text-purple-300 font-medium min-w-16">
        {message}
        {dots}
      </span>
      {formatElapsed() && (
        <span className="text-[10px] text-purple-400/60">
          {formatElapsed()}
        </span>
      )}
    </div>
  );
}

// Minimal inline version
export function ThinkingDots({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-white/50 text-sm",
        className
      )}
    >
      <Loader2 size={12} className="animate-spin" />
      <span className="text-xs">Thinking</span>
    </span>
  );
}

// Streaming text with cursor
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
      return;
    }
    const interval = setInterval(() => {
      setShowCursor((prev) => !prev);
    }, 530);
    return () => clearInterval(interval);
  }, [isStreaming]);

  return (
    <span className={className}>
      {text}
      {isStreaming && (
        <span
          className={cn(
            "inline-block w-0.5 h-4 bg-emerald-400 ml-0.5 align-middle",
            showCursor ? "opacity-100" : "opacity-0"
          )}
        />
      )}
    </span>
  );
}
