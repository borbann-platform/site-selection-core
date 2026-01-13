import { useEffect, useState } from "react";
import {
  Brain,
  Loader2,
  Search,
  Database,
  Globe,
  Cpu,
} from "lucide-react";
import { cn } from "../lib/utils";

// --- Types ---
interface ThinkingProcessProps {
  className?: string;
  startTime?: number;
  message?: string;
}

const PROCESS_STEPS = [
  { text: "Analyzing user intent...", icon: Brain },
  { text: "Identifying key entities...", icon: Search },
  { text: "Querying spatial database...", icon: Database },
  { text: "Processing geometric constraints...", icon: Globe },
  { text: "Synthesizing market data...", icon: Cpu },
];

export function ThinkingProcess({
  className,
  startTime,
}: ThinkingProcessProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);
  const [elapsed, setElapsed] = useState(0);

  // Cycle through fake "process steps" to show activity
  useEffect(() => {
    const interval = setInterval(() => {
      setStepIndex((prev) => (prev + 1) % PROCESS_STEPS.length);
      setLogs((prev) => {
        const newLog = PROCESS_STEPS[stepIndex % PROCESS_STEPS.length].text;
        return [...prev.slice(-2), newLog]; // Keep last 3 logs
      });
    }, 2000);
    return () => clearInterval(interval);
  }, [stepIndex]);

  // Track elapsed time
  useEffect(() => {
    if (!startTime) return;
    const interval = setInterval(() => {
      setElapsed(Date.now() - startTime);
    }, 100);
    return () => clearInterval(interval);
  }, [startTime]);

  const CurrentIcon = PROCESS_STEPS[stepIndex].icon;

  return (
    <div
      className={cn(
        "flex flex-col gap-2 p-3 rounded-lg",
        "bg-purple-500/5 border border-purple-500/20",
        "animate-in fade-in duration-300",
        className
      )}
    >
      {/* Header with Timer */}
      <div className="flex items-center justify-between text-xs text-purple-300/80">
        <div className="flex items-center gap-2">
          <div className="relative">
            <Loader2 size={14} className="animate-spin text-purple-400" />
            <div className="absolute inset-0 animate-ping opacity-50">
              <div className="w-full h-full rounded-full bg-purple-500/20" />
            </div>
          </div>
          <span className="font-medium tracking-wide">AI REASONING</span>
        </div>
        <span className="font-mono text-purple-400/60">
          {(elapsed / 1000).toFixed(1)}s
        </span>
      </div>

      {/* Dynamic Step Display */}
      <div className="flex items-center gap-3 py-1">
        <div className="w-8 h-8 rounded bg-purple-500/10 flex items-center justify-center shrink-0 border border-purple-500/20">
          <CurrentIcon size={16} className="text-purple-400" />
        </div>
        <div className="flex-1 min-w-0 flex flex-col justify-center h-8">
          <span className="text-xs font-medium text-purple-200 truncate animate-pulse">
            {PROCESS_STEPS[stepIndex].text}
          </span>
          <div className="w-full bg-purple-500/10 h-1 mt-1 rounded-full overflow-hidden">
            <div className="h-full bg-purple-500/50 w-1/3 animate-loading-bar rounded-full" />
          </div>
        </div>
      </div>

      {/* Mini Terminal Log */}
      <div className="mt-1 space-y-0.5 font-mono text-[10px] text-purple-300/50 pl-1 border-l-2 border-purple-500/10">
        {logs.map((log, i) => (
          <div key={i} className="truncate animate-in slide-in-from-left-2 fade-in duration-300">
            <span className="opacity-50 mr-2">{">"}</span>
            {log}
          </div>
        ))}
        <div className="truncate opacity-50">
          <span className="mr-2 animate-pulse">_</span>
        </div>
      </div>
    </div>
  );
}

// Minimal inline version (Legacy support / minimal view)
export function ThinkingIndicator({ className }: { className?: string; startTime?: number; message?: string }) {
  // Legacy wrapper to keep existing code working if it imports ThinkingIndicator
  return <ThinkingProcess className={className} startTime={Date.now()} />;
}

export function ThinkingDots({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-white/50 text-xs font-mono",
        className
      )}
    >
      <Loader2 size={10} className="animate-spin" />
      <span className="animate-pulse">thinking...</span>
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
            "inline-block w-1.5 h-4 bg-emerald-400 ml-0.5 align-middle shadow-[0_0_8px_rgba(52,211,153,0.5)]",
            showCursor ? "opacity-100" : "opacity-0"
          )}
        />
      )}
    </span>
  );
}
