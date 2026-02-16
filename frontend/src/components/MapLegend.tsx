import { useState } from "react";
import {
  Home,
  GraduationCap,
  Train,
  Bus,
  Shield,
  Landmark,
  Waves,
  Fuel,
  AlertTriangle,
  Camera,
  ChevronDown,
  ChevronUp,
  MapPin,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface MapLegendProps {
  className?: string;
  showHouses?: boolean;
  showPOIs?: boolean;
}

const POI_TYPES = [
  { icon: GraduationCap, color: "#8B5CF6", label: "School" },
  { icon: Train, color: "#EAB308", label: "Transit Station" },
  { icon: Bus, color: "#22C55E", label: "Bus Stop" },
  { icon: Shield, color: "#1E3A8A", label: "Police Station" },
  { icon: Landmark, color: "#9333EA", label: "Museum" },
  { icon: Waves, color: "#06B6D4", label: "Water Transport" },
  { icon: Fuel, color: "#F97316", label: "Gas Station" },
  { icon: AlertTriangle, color: "#EF4444", label: "Traffic Point" },
  { icon: Camera, color: "#EC4899", label: "Tourist Attraction" },
];

export function MapLegend({
  className,
  showHouses = true,
  showPOIs = false,
}: MapLegendProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  // Don't show legend if nothing to display
  if (!showHouses && !showPOIs) return null;

  return (
    <div
      className={cn(
        "absolute bottom-6 left-6 z-40",
        "bg-card/92 backdrop-blur-lg border border-border rounded-xl shadow-lg animate-fade-in",
        "transition-all duration-200",
        className
      )}
    >
      {/* Header */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-xs font-medium text-foreground hover:bg-muted/50 rounded-t-xl transition-colors"
      >
        <div className="flex items-center gap-2">
          <MapPin size={14} className="text-muted-foreground" />
          <span>Map Legend</span>
        </div>
        {isExpanded ? (
          <ChevronDown size={14} className="text-muted-foreground" />
        ) : (
          <ChevronUp size={14} className="text-muted-foreground" />
        )}
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="px-3 pb-3 space-y-3 animate-in slide-in-from-top-1 fade-in duration-200">
          {/* House Price Gradient */}
          {showHouses && (
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5 text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                <Home size={12} />
                <span>Property Prices</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="flex-1 h-2 rounded-full bg-gradient-to-r from-green-500 via-yellow-500 to-red-500" />
              </div>
              <div className="flex justify-between text-[9px] text-muted-foreground">
                <span>Low</span>
                <span>High</span>
              </div>
            </div>
          )}

          {/* POI Types */}
          {showPOIs && (
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5 text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                <MapPin size={12} />
                <span>Points of Interest</span>
              </div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                {POI_TYPES.map(({ icon: Icon, color, label }) => (
                  <div
                    key={label}
                    className="flex items-center gap-1.5 text-[10px] text-foreground/80"
                  >
                    <div
                      className="w-3 h-3 rounded-full flex items-center justify-center"
                      style={{ backgroundColor: color }}
                    >
                      <Icon size={8} className="text-white" />
                    </div>
                    <span className="truncate">{label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
