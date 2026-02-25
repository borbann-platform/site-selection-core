import { cn } from "@/lib/utils";

interface ProgressBarProps {
  value: number;
  max?: number;
  color?: "primary" | "success" | "warning" | "destructive";
  className?: string;
}

export function ProgressBar({
  value,
  max = 100,
  color = "primary",
  className,
}: ProgressBarProps) {
  const percentage = Math.min((value / max) * 100, 100);

  const colors = {
    primary: "bg-primary",
    success: "bg-success",
    warning: "bg-warning",
    destructive: "bg-destructive",
  };

  return (
    <div
      className={cn(
        "w-full h-2 bg-secondary rounded-full overflow-hidden",
        className
      )}
    >
      <div
        className={cn(
          "h-full rounded-full transition-all duration-500 ease-out",
          colors[color]
        )}
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
}
