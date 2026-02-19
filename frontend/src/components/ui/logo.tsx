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
          "flex items-center justify-center rounded-md bg-gradient-to-br from-brand via-brand to-brand/70 font-bold text-brand-foreground glow-brand-sm shadow-sm",
          sizeClasses[size],
        )}
      >
        B
      </div>
      {showText && (
        <div className="flex flex-col gap-0.5 leading-none">
          <span className="font-semibold tracking-tight">Borbann</span>
          <span className="text-[10px] text-muted-foreground/70 tracking-wide uppercase">Platform</span>
        </div>
      )}
    </div>
  );
}
