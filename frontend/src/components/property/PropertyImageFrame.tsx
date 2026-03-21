import { useState } from "react";
import { ImageSquare, MapPinLine } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

interface PropertyImageFrameProps {
  imageUrl?: string | null;
  title: string;
  subtitle?: string | null;
  badge?: string | null;
  className?: string;
  aspectClassName?: string;
}

export function PropertyImageFrame({
  imageUrl,
  title,
  subtitle,
  badge,
  className,
  aspectClassName = "aspect-[16/10]",
}: PropertyImageFrameProps) {
  const [isBroken, setIsBroken] = useState(false);
  const showImage = Boolean(imageUrl) && !isBroken;

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border border-border/70 bg-muted/25",
        aspectClassName,
        className,
      )}
    >
      {showImage ? (
        <img
          src={imageUrl || undefined}
          alt={title}
          className="h-full w-full object-cover"
          onError={() => setIsBroken(true)}
        />
      ) : (
        <div className="flex h-full w-full flex-col justify-between bg-[radial-gradient(circle_at_top_left,rgba(24,163,127,0.18),transparent_38%),radial-gradient(circle_at_bottom_right,rgba(15,23,42,0.14),transparent_34%),linear-gradient(180deg,rgba(255,255,255,0.02),rgba(255,255,255,0))] p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-border/70 bg-card/90 text-brand shadow-sm">
              <ImageSquare size={20} weight="duotone" />
            </div>
            {badge ? (
              <span className="rounded-full border border-border/70 bg-card/90 px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
                {badge}
              </span>
            ) : null}
          </div>

          <div className="space-y-2">
            <div className="flex flex-wrap gap-1.5 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
              <span className="rounded-full border border-border/60 bg-card/70 px-2 py-1">
                Visual pending
              </span>
              <span className="rounded-full border border-border/60 bg-card/70 px-2 py-1">
                Map verified
              </span>
            </div>
            <div>
              <div className="text-sm font-semibold text-foreground">Image unavailable</div>
              <div className="mt-1 text-xs leading-5 text-muted-foreground">
                Location, pricing, and core property data are still available.
              </div>
            </div>

            <div className="rounded-lg border border-border/60 bg-card/80 px-3 py-2">
              <div className="truncate text-sm font-medium text-foreground">{title}</div>
              {subtitle ? (
                <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <MapPinLine size={12} weight="duotone" />
                  <span className="truncate">{subtitle}</span>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
