import { Link } from "@tanstack/react-router";
import {
  Eye,
  EyeOff,
  ChevronDown,
  ChevronUp,
  Home,
  BarChart3,
  Train,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  PropertyFilters,
  type PropertyFiltersState,
} from "@/components/PropertyFilters";
import { MarketStats } from "@/components/MarketStats";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import type { OverlayState, OpenSections } from "@/hooks/usePropertyExplorer";

// ---- LayerToggle (local to this module) ----

function LayerToggle({
  label,
  active,
  color,
  icon,
  onClick,
}: {
  label: string;
  active: boolean;
  color: string;
  icon?: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full flex items-center justify-between p-3 rounded-lg transition-all border",
        active
          ? "bg-muted border-border"
          : "bg-transparent border-transparent hover:bg-muted/50"
      )}
    >
      <div className="flex items-center gap-3">
        {icon ? (
          <span
            className={cn(
              active ? "text-foreground" : "text-muted-foreground/50"
            )}
          >
            {icon}
          </span>
        ) : (
          <div
            className={cn(
              "w-3 h-3 rounded-full shadow-[0_0_10px_currentColor]",
              color,
              !active && "opacity-20 shadow-none"
            )}
          />
        )}
        <span
          className={cn(
            "text-sm font-medium",
            active ? "text-foreground" : "text-muted-foreground"
          )}
        >
          {label}
        </span>
      </div>
      {active ? (
        <Eye size={16} className="text-muted-foreground" />
      ) : (
        <EyeOff size={16} className="text-muted-foreground/50" />
      )}
    </button>
  );
}

// ---- Props ----

export interface ExplorerPanelProps {
  propertyFilters: PropertyFiltersState;
  setPropertyFilters: (filters: PropertyFiltersState) => void;
  openSections: OpenSections;
  setOpenSections: React.Dispatch<React.SetStateAction<OpenSections>>;
  overlays: OverlayState;
  setOverlays: React.Dispatch<React.SetStateAction<OverlayState>>;
  h3Metric: string;
  setH3Metric: (metric: string) => void;
}

// ---- Component ----

export function ExplorerPanel({
  propertyFilters,
  setPropertyFilters,
  openSections,
  setOpenSections,
  overlays,
  setOverlays,
  h3Metric,
  setH3Metric,
}: ExplorerPanelProps) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Home className="w-5 h-5 text-brand" />
          <h2 className="text-xl font-bold text-foreground">
            Property Explorer
          </h2>
        </div>
        <p className="text-xs text-muted-foreground">
          Browse real estate prices in Bangkok
        </p>
      </div>

      {/* Property Filters Section */}
      <Collapsible
        open={openSections.filters}
        onOpenChange={(open) =>
          setOpenSections((s) => ({ ...s, filters: open }))
        }
      >
        <div className="border border-border rounded-lg overflow-hidden">
          <CollapsibleTrigger className="w-full flex items-center justify-between p-3 bg-muted/50 hover:bg-muted transition-colors">
            <h3 className="text-sm font-bold text-foreground">Filters</h3>
            {openSections.filters ? (
              <ChevronUp className="w-4 h-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            )}
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="p-3 bg-muted/30">
              <PropertyFilters
                filters={propertyFilters}
                onChange={setPropertyFilters}
              />
            </div>
          </CollapsibleContent>
        </div>
      </Collapsible>

      {/* Market Stats Section */}
      <Collapsible
        open={openSections.stats}
        onOpenChange={(open) =>
          setOpenSections((s) => ({ ...s, stats: open }))
        }
      >
        <div className="border border-border rounded-lg overflow-hidden">
          <CollapsibleTrigger className="w-full flex items-center justify-between p-3 bg-muted/50 hover:bg-muted transition-colors">
            <h3 className="text-sm font-bold text-foreground">
              Market Statistics
            </h3>
            {openSections.stats ? (
              <ChevronUp className="w-4 h-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            )}
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="p-3 bg-muted/30">
              <MarketStats
                filters={{
                  district: propertyFilters.district,
                  buildingStyle: propertyFilters.buildingStyle,
                }}
              />
            </div>
          </CollapsibleContent>
        </div>
      </Collapsible>

      {/* Map Overlays Section */}
      <Collapsible
        open={openSections.overlays}
        onOpenChange={(open) =>
          setOpenSections((s) => ({ ...s, overlays: open }))
        }
      >
        <div className="border border-border rounded-lg overflow-hidden">
          <CollapsibleTrigger className="w-full flex items-center justify-between p-3 bg-muted/50 hover:bg-muted transition-colors">
            <h3 className="text-sm font-bold text-foreground">Map Overlays</h3>
            {openSections.overlays ? (
              <ChevronUp className="w-4 h-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            )}
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="p-3 bg-muted/30 space-y-2">
              <LayerToggle
                label="Transit Lines (BTS/MRT)"
                active={overlays.transitRail}
                color="bg-brand"
                icon={<Train className="w-4 h-4" />}
                onClick={() =>
                  setOverlays((o) => ({ ...o, transitRail: !o.transitRail }))
                }
              />
              <LayerToggle
                label="All POIs"
                active={overlays.pois}
                color="bg-purple-500"
                onClick={() =>
                  setOverlays((o) => ({ ...o, pois: !o.pois }))
                }
              />
              <LayerToggle
                label="Schools"
                active={overlays.schools}
                color="bg-blue-500"
                onClick={() =>
                  setOverlays((o) => ({ ...o, schools: !o.schools }))
                }
              />
              <LayerToggle
                label="H3 Analytics"
                active={overlays.h3Hexagons}
                color="bg-cyan-500"
                onClick={() =>
                  setOverlays((o) => ({
                    ...o,
                    h3Hexagons: !o.h3Hexagons,
                  }))
                }
              />
              {overlays.h3Hexagons && (
                <select
                  value={h3Metric}
                  onChange={(e) => setH3Metric(e.target.value)}
                  className="w-full px-2 py-2 min-h-[44px] text-xs bg-muted rounded text-foreground border border-border mt-1"
                >
                  <optgroup label="POI Counts">
                    <option value="poi_total">Total POIs</option>
                    <option value="poi_school">Schools</option>
                    <option value="poi_transit_stop">Transit Stops</option>
                    <option value="poi_restaurant">Restaurants</option>
                    <option value="poi_hospital">Hospitals</option>
                    <option value="poi_cafe">Cafes</option>
                    <option value="poi_bank">Banks</option>
                    <option value="poi_mall">Malls</option>
                    <option value="poi_park">Parks</option>
                    <option value="poi_temple">Temples</option>
                  </optgroup>
                  <optgroup label="Property">
                    <option value="avg_price">Avg Price</option>
                    <option value="median_price">Median Price</option>
                    <option value="property_count">Property Count</option>
                    <option value="avg_building_area">
                      Avg Building Area
                    </option>
                    <option value="avg_land_area">Avg Land Area</option>
                    <option value="avg_building_age">
                      Avg Building Age
                    </option>
                  </optgroup>
                  <optgroup label="Transit">
                    <option value="transit_total">
                      Transit Accessibility
                    </option>
                    <option value="transit_bangkok_gtfs">Bangkok GTFS</option>
                    <option value="transit_longdomap_bus">Bus Routes</option>
                  </optgroup>
                </select>
              )}
            </div>
          </CollapsibleContent>
        </div>
      </Collapsible>

      {/* Info Section */}
      <div className="p-3 bg-brand/10 border border-brand/20 rounded text-xs text-brand">
        <span className="font-bold">Tip:</span> Click on a property to see full
        details. Zoom in past level 13 for MVT tiles.
      </div>

      {/* District Analysis Link */}
      <Link
        to="/districts"
        className="flex items-center justify-center gap-2 w-full py-3 bg-muted/50 hover:bg-muted rounded-lg text-sm text-muted-foreground hover:text-foreground transition-colors border border-border"
      >
        <BarChart3 className="w-4 h-4" />
        View District Analysis
      </Link>
    </div>
  );
}
