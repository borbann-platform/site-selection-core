import type { LucideIcon } from "lucide-react";
import { ArrowUp, ArrowDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  trend?: { value: number; label: string };
  className?: string;
}

export function StatCard({ icon: Icon, label, value, trend, className }: StatCardProps) {
  return (
    <div className={cn("bg-surface-1 border border-white/[0.07] rounded-xl p-4 hover:border-white/[0.13] transition-colors group", className)}>
      <div className="flex items-start gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-brand-surface border border-brand-border text-brand group-hover:glow-brand-sm transition-all">
          <Icon className="size-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-2xl font-bold tracking-tight text-foreground">{value}</div>
          <div className="text-sm text-muted-foreground">{label}</div>
        </div>
      </div>
      {trend && (
        <div className="mt-3 flex items-center gap-1.5">
          {trend.value >= 0 ? (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-success/[0.12] border border-success/20 px-2 py-0.5 text-xs font-medium text-success">
              <ArrowUp className="size-3" />
              {Math.abs(trend.value)}%
            </span>
          ) : (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-destructive/[0.12] border border-destructive/20 px-2 py-0.5 text-xs font-medium text-destructive">
              <ArrowDown className="size-3" />
              {Math.abs(trend.value)}%
            </span>
          )}
          <span className="text-xs text-muted-foreground">{trend.label}</span>
        </div>
      )}
    </div>
  );
}
