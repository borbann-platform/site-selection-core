/**
 * Unified loading state components.
 * Replaces inconsistent Loader2 spinners and custom pulse divs.
 */

import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Skeleton } from "./skeleton";

/* ----------------------------------------
   Spinner - Inline loading indicator
   ---------------------------------------- */
interface SpinnerProps {
  size?: "xs" | "sm" | "md" | "lg";
  className?: string;
}

const SPINNER_SIZES = {
  xs: "size-3",
  sm: "size-4",
  md: "size-6",
  lg: "size-8",
} as const;

export function Spinner({ size = "sm", className }: SpinnerProps) {
  return (
    <Loader2
      className={cn("animate-spin text-muted-foreground", SPINNER_SIZES[size], className)}
    />
  );
}

/* ----------------------------------------
   ContentLoader - Shimmer line placeholders
   ---------------------------------------- */
interface ContentLoaderProps {
  lines?: number;
  className?: string;
}

export function ContentLoader({ lines = 3, className }: ContentLoaderProps) {
  const lineNumbers = Array.from({ length: lines }, (_, idx) => idx + 1);

  return (
    <div className={cn("space-y-3", className)}>
      {lineNumbers.map((lineNumber) => (
        <Skeleton
          key={`content-line-${lineNumber}`}
          className={cn("h-4", lineNumber === lines ? "w-2/3" : "w-full")}
        />
      ))}
    </div>
  );
}

/* ----------------------------------------
   PageSkeleton - Full-page loading variants
   ---------------------------------------- */
interface PageSkeletonProps {
  variant?: "map" | "table" | "form" | "detail";
}

export function PageSkeleton({ variant = "detail" }: PageSkeletonProps) {
  switch (variant) {
    case "map":
      return (
        <div className="h-full w-full relative">
          <Skeleton className="absolute inset-0" />
          {/* Fake panel */}
          <div className="absolute top-4 left-4 w-80 space-y-3">
            <Skeleton className="h-10 w-full rounded-xl" />
            <Skeleton className="h-32 w-full rounded-xl" />
            <Skeleton className="h-24 w-full rounded-xl" />
          </div>
        </div>
      );

    case "table":
      return (
        <div className="p-6 space-y-6">
          {/* Header stats */}
          <div className="grid grid-cols-3 gap-4">
            {Array.from({ length: 3 }, (_, idx) => idx + 1).map((item) => (
              <Skeleton key={`table-header-${item}`} className="h-24 rounded-xl" />
            ))}
          </div>
          {/* Table header */}
          <Skeleton className="h-10 w-full rounded-lg" />
          {/* Table rows */}
          {Array.from({ length: 8 }, (_, idx) => idx + 1).map((item) => (
            <Skeleton key={`table-row-${item}`} className="h-12 w-full rounded-lg" />
          ))}
        </div>
      );

    case "form":
      return (
        <div className="max-w-2xl mx-auto p-6 space-y-6">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-72" />
          <div className="space-y-4 mt-8">
            {Array.from({ length: 4 }, (_, idx) => idx + 1).map((item) => (
              <div key={`form-field-${item}`} className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-10 w-full rounded-lg" />
              </div>
            ))}
          </div>
          <Skeleton className="h-10 w-32 rounded-lg" />
        </div>
      );
    default:
      return (
        <div className="p-6 space-y-6">
          <div className="flex items-center gap-4">
            <Skeleton className="h-6 w-6 rounded" />
            <Skeleton className="h-8 w-64" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Skeleton className="h-40 rounded-xl" />
            <Skeleton className="h-40 rounded-xl" />
          </div>
          <ContentLoader lines={5} />
        </div>
      );
  }
}

/* ----------------------------------------
   FullPageSpinner - Centered spinner
   ---------------------------------------- */
interface FullPageSpinnerProps {
  message?: string;
}

export function FullPageSpinner({ message = "Loading..." }: FullPageSpinnerProps) {
  return (
    <div className="flex-1 flex items-center justify-center min-h-[50vh]">
      <div className="flex flex-col items-center gap-3">
        <Spinner size="lg" className="text-brand" />
        <p className="text-sm text-muted-foreground">{message}</p>
      </div>
    </div>
  );
}
