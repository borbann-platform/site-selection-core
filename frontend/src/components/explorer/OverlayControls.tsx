import { Train, MapPin, GraduationCap, Hexagon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { OverlayState } from "@/hooks/usePropertyExplorer";

export interface OverlayControlsProps {
  overlays: OverlayState;
  setOverlays: React.Dispatch<React.SetStateAction<OverlayState>>;
}

interface ToggleButtonProps {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}

function ToggleButton({ active, onClick, icon, label }: ToggleButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      className={cn(
        "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all",
        active
          ? "bg-foreground/10 text-foreground border border-border"
          : "text-muted-foreground hover:text-foreground hover:bg-foreground/5"
      )}
    >
      {icon}
      <span className="hidden lg:inline">{label}</span>
    </button>
  );
}

export function OverlayControls({
  overlays,
  setOverlays,
}: OverlayControlsProps) {
  return (
    <div className="absolute top-6 right-4 z-40 flex items-center gap-1 bg-card/90 backdrop-blur-md border border-border rounded-full px-2 py-1 shadow-lg">
      <ToggleButton
        active={overlays.transitRail}
        onClick={() =>
          setOverlays((o) => ({ ...o, transitRail: !o.transitRail }))
        }
        icon={<Train className="w-3.5 h-3.5" />}
        label="Transit"
      />
      <ToggleButton
        active={overlays.pois}
        onClick={() => setOverlays((o) => ({ ...o, pois: !o.pois }))}
        icon={<MapPin className="w-3.5 h-3.5" />}
        label="POIs"
      />
      <ToggleButton
        active={overlays.schools}
        onClick={() =>
          setOverlays((o) => ({ ...o, schools: !o.schools }))
        }
        icon={<GraduationCap className="w-3.5 h-3.5" />}
        label="Schools"
      />
      <ToggleButton
        active={overlays.h3Hexagons}
        onClick={() =>
          setOverlays((o) => ({ ...o, h3Hexagons: !o.h3Hexagons }))
        }
        icon={<Hexagon className="w-3.5 h-3.5" />}
        label="H3"
      />
    </div>
  );
}
