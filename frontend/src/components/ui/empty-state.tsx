/**
 * Unified empty state component.
 * Provides consistent empty/no-data/no-results messaging.
 */

import type { LucideIcon } from "lucide-react";
import { SearchX, Inbox, FileQuestion, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "./button";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-12 px-6 text-center",
        className
      )}
    >
      <div className="flex items-center justify-center size-14 rounded-2xl bg-muted/50 mb-4">
        <Icon className="size-7 text-muted-foreground" />
      </div>
      <h3 className="text-base font-semibold text-foreground mb-1">{title}</h3>
      {description && (
        <p className="text-sm text-muted-foreground max-w-sm">{description}</p>
      )}
      {action && (
        <Button
          variant="outline"
          size="sm"
          onClick={action.onClick}
          className="mt-4"
        >
          {action.label}
        </Button>
      )}
    </div>
  );
}

/* Pre-configured variants */

export function NoResults({
  query,
  onClear,
}: {
  query?: string;
  onClear?: () => void;
}) {
  return (
    <EmptyState
      icon={SearchX}
      title="No results found"
      description={
        query
          ? `No matches for "${query}". Try adjusting your filters.`
          : "Try adjusting your search or filters."
      }
      action={onClear ? { label: "Clear filters", onClick: onClear } : undefined}
    />
  );
}

export function NoData({ message }: { message?: string }) {
  return (
    <EmptyState
      icon={FileQuestion}
      title="No data available"
      description={message ?? "There's nothing here yet. Data will appear once available."}
    />
  );
}

export function ErrorEmpty({
  message,
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <EmptyState
      icon={AlertTriangle}
      title="Something went wrong"
      description={message ?? "An error occurred while loading data."}
      action={onRetry ? { label: "Try again", onClick: onRetry } : undefined}
    />
  );
}
