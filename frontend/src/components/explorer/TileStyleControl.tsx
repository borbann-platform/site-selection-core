import { cn } from "@/lib/utils";
import type { MapTileStyle } from "@/components/MapContainer";

export interface TileStyleControlProps {
  tileStyle: MapTileStyle;
  setTileStyle: (style: MapTileStyle) => void;
}

const TILE_OPTIONS: { value: MapTileStyle; label: string }[] = [
  { value: "auto", label: "Auto" },
  { value: "dark", label: "Dark" },
  { value: "light", label: "Light" },
  { value: "streets", label: "Streets" },
];

export function TileStyleControl({
  tileStyle,
  setTileStyle,
}: TileStyleControlProps) {
  return (
    <div className="flex items-center gap-1">
      {TILE_OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => setTileStyle(option.value)}
          title={`${option.label} map style`}
          className={cn(
            "px-2.5 py-1.5 min-h-[32px] rounded-lg text-xs font-medium transition-all",
            tileStyle === option.value
              ? "bg-foreground/10 text-foreground border border-border"
              : "text-muted-foreground hover:text-foreground hover:bg-foreground/5"
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
