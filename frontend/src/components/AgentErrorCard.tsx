import { AlertTriangle } from "lucide-react";
import type { AgentRuntimeError } from "../lib/api";
import { cn } from "../lib/utils";

interface AgentErrorCardProps {
  error: AgentRuntimeError;
  className?: string;
}

export function AgentErrorCard({ error, className }: AgentErrorCardProps) {
  return (
    <div
      className={cn(
        "rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2.5",
        className
      )}
    >
      <div className="flex items-start gap-2">
        <AlertTriangle size={16} className="text-destructive mt-0.5 shrink-0" />
        <div className="min-w-0">
          <div className="text-sm font-medium text-destructive">
            {error.title || "Model request failed"}
          </div>
          <div className="text-xs text-foreground/90 mt-0.5">{error.message}</div>
          {(error.statusCode || error.providerCode) && (
            <div className="text-[11px] text-muted-foreground mt-1">
              {error.statusCode ? `HTTP ${error.statusCode}` : ""}
              {error.statusCode && error.providerCode ? " • " : ""}
              {error.providerCode ? `Code ${error.providerCode}` : ""}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
