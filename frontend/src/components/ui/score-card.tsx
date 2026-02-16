import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface ScoreCardProps {
  score: number; // 0-100
  label: string;
  icon?: LucideIcon;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const sizeConfig = {
  sm: { svgSize: 64, radius: 26, stroke: 5, fontSize: "text-sm", labelSize: "text-xs" },
  md: { svgSize: 96, radius: 40, stroke: 6, fontSize: "text-xl", labelSize: "text-sm" },
  lg: { svgSize: 128, radius: 54, stroke: 7, fontSize: "text-2xl", labelSize: "text-sm" },
} as const;

function getScoreColor(score: number): string {
  if (score >= 80) return "text-success";
  if (score >= 60) return "text-warning";
  if (score >= 40) return "text-brand";
  return "text-destructive";
}

function getStrokeColor(score: number): string {
  if (score >= 80) return "stroke-success";
  if (score >= 60) return "stroke-warning";
  if (score >= 40) return "stroke-brand";
  return "stroke-destructive";
}

export function ScoreCard({
  score,
  label,
  icon: Icon,
  size = "md",
  className,
}: ScoreCardProps) {
  const config = sizeConfig[size];
  const circumference = 2 * Math.PI * config.radius;
  const clampedScore = Math.max(0, Math.min(100, score));
  const dashOffset = circumference - (clampedScore / 100) * circumference;
  const center = config.svgSize / 2;

  return (
    <div className={cn("flex flex-col items-center gap-2", className)}>
      <div className="relative">
        <svg
          width={config.svgSize}
          height={config.svgSize}
          viewBox={`0 0 ${config.svgSize} ${config.svgSize}`}
          className="-rotate-90"
        >
          {/* Background track */}
          <circle
            cx={center}
            cy={center}
            r={config.radius}
            fill="none"
            className="stroke-muted"
            strokeWidth={config.stroke}
          />
          {/* Progress arc */}
          <circle
            cx={center}
            cy={center}
            r={config.radius}
            fill="none"
            className={cn("transition-all duration-700 ease-out", getStrokeColor(clampedScore))}
            strokeWidth={config.stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
          />
        </svg>
        {/* Centered score text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {Icon && <Icon className={cn("mb-0.5", size === "sm" ? "size-3" : "size-4", getScoreColor(clampedScore))} />}
          <span className={cn("font-bold", config.fontSize, getScoreColor(clampedScore))}>
            {Math.round(clampedScore)}
          </span>
        </div>
      </div>
      <span className={cn("text-muted-foreground font-medium", config.labelSize)}>
        {label}
      </span>
    </div>
  );
}
