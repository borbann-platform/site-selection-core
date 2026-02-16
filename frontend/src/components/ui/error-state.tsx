/**
 * Unified error state component.
 * Provides consistent error display with retry action.
 */

import { AlertTriangle, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "./button";

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
  compact?: boolean;
}

export function ErrorState({
  title = "Error",
  message = "Something went wrong. Please try again.",
  onRetry,
  className,
  compact = false,
}: ErrorStateProps) {
  if (compact) {
    return (
      <div
        className={cn(
          "flex items-center gap-3 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-sm",
          className
        )}
      >
        <AlertTriangle className="size-4 text-destructive shrink-0" />
        <span className="text-foreground flex-1">{message}</span>
        {onRetry && (
          <Button variant="ghost" size="sm" onClick={onRetry} className="shrink-0">
            <RefreshCw className="size-3 mr-1" />
            Retry
          </Button>
        )}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-12 px-6 text-center",
        className
      )}
    >
      <div className="flex items-center justify-center size-14 rounded-2xl bg-destructive/10 mb-4">
        <AlertTriangle className="size-7 text-destructive" />
      </div>
      <h3 className="text-base font-semibold text-foreground mb-1">{title}</h3>
      <p className="text-sm text-muted-foreground max-w-sm">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} className="mt-4">
          <RefreshCw className="size-3 mr-1.5" />
          Try again
        </Button>
      )}
    </div>
  );
}

/* ----------------------------------------
   InlineError - For form fields
   ---------------------------------------- */
interface InlineErrorProps {
  message: string;
  className?: string;
}

export function InlineError({ message, className }: InlineErrorProps) {
  return (
    <div className={cn("flex items-center gap-1.5 text-destructive text-xs mt-1", className)}>
      <AlertTriangle className="size-3 shrink-0" />
      <span>{message}</span>
    </div>
  );
}
