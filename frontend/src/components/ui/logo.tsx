import { cn } from "@/lib/utils";

interface LogoProps {
  size?: "sm" | "md" | "lg";
  showText?: boolean;
  className?: string;
}

const sizeClasses = {
  sm: "size-8 text-sm",
  md: "size-10 text-base",
  lg: "size-12 text-lg",
} as const;

export function Logo({ size = "md", showText = false, className }: LogoProps) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div
        className={cn(
          "flex items-center justify-center rounded-lg bg-gradient-to-br from-brand to-brand/80 font-bold text-brand-foreground",
          sizeClasses[size],
        )}
      >
        B
      </div>
      {showText && (
        <div className="flex flex-col gap-0.5 leading-none">
          <span className="font-semibold">Borbann</span>
          <span className="text-xs text-muted-foreground">Site Selection</span>
        </div>
      )}
    </div>
  );
}
