import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { MapContainer } from "../components/MapContainer";
import { Shell } from "../components/Shell";
import { ScatterplotLayer } from "@deck.gl/layers";
import { MVTLayer } from "@deck.gl/geo-layers";
import { Eye, EyeOff, ChevronDown, ChevronUp, Home } from "lucide-react";
import { cn } from "../lib/utils";
import { api, API_URL } from "../lib/api";
import {
  PropertyFilters,
  type PropertyFiltersState,
} from "../components/PropertyFilters";
import { MarketStats } from "../components/MarketStats";
import { PriceLegend } from "../components/PriceLegend";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "../components/ui/collapsible";

// Type definitions
interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

interface DeckGLObject {
  lon?: number;
  lat?: number;
  total_price?: number;
  building_area?: number;
  amphur?: string;
  tumbon?: string;
  building_style_desc?: string;
  no_of_floor?: number;
  building_age?: number;
  properties?: Record<string, unknown>;
  geometry?: { coordinates: [number, number] };
}

export const Route = createFileRoute("/")({
  component: PropertyExplorer,
});

const BANGKOK_LAT = 13.7563;
const BANGKOK_LON = 100.5018;

function PropertyExplorer() {
  const [viewState, setViewState] = useState<ViewState>({
    longitude: BANGKOK_LON,
    latitude: BANGKOK_LAT,
    zoom: 12,
    pitch: 0,
    bearing: 0,
  });

  // Property filters - main feature
  const [propertyFilters, setPropertyFilters] = useState<PropertyFiltersState>({
    district: null,
    buildingStyle: null,
    minPrice: 500_000,
    maxPrice: 50_000_000,
    minArea: 20,
    maxArea: 500,
  });

  // Overlays - secondary features
  const [overlays, setOverlays] = useState({
    pois: false,
    schools: false,
    priceDensity: false,
  });

  // Collapsible sections
  const [openSections, setOpenSections] = useState({
    filters: true,
    stats: true,
    overlays: false,
  });

  // Fetch House Prices with filters
  const { data: housePrices } = useQuery({
    queryKey: ["housePrices", propertyFilters],
    queryFn: () =>
      api.getHousePrices({
        district: propertyFilters.district || undefined,
        buildingStyle: propertyFilters.buildingStyle || undefined,
        minPrice: propertyFilters.minPrice,
        maxPrice: propertyFilters.maxPrice,
        minArea: propertyFilters.minArea,
        maxArea: propertyFilters.maxArea,
        limit: 1000,
      }),
  });

  // Fetch Schools (optional overlay)
  const { data: schools } = useQuery({
    queryKey: ["nearby", "schools"],
    queryFn: () =>
      api.getNearby({
        latitude: BANGKOK_LAT,
        longitude: BANGKOK_LON,
        radius_meters: 10000,
        categories: ["school"],
      }),
    enabled: overlays.schools,
  });

  const layers = useMemo(() => {
    const layerList = [];

    // Primary: House Prices Layer (always shown when data available)
    if (housePrices && viewState.zoom < 13) {
      // Use ScatterplotLayer for low zoom
      layerList.push(
        new ScatterplotLayer({
          id: "house-prices-scatter",
          data: housePrices.items,
          getPosition: (d: DeckGLObject) => [d.lon || 0, d.lat || 0],
          getFillColor: (d: DeckGLObject) => {
            const price = d.total_price || 0;
            const minPrice = propertyFilters.minPrice;
            const maxPrice = propertyFilters.maxPrice;
            const t = Math.min(
              1,
              Math.max(0, (price - minPrice) / (maxPrice - minPrice))
            );
            // Green -> Yellow -> Red gradient
            if (t < 0.5) {
              const r = Math.round(t * 2 * 255);
              return [r, 200, 50, 200];
            }
            const g = Math.round((1 - (t - 0.5) * 2) * 200);
            return [255, g, 50, 200];
          },
          getRadius: 80,
          pickable: true,
          opacity: 0.9,
          radiusMinPixels: 4,
          radiusMaxPixels: 15,
        })
      );
    }

    // MVT tiles for high zoom
    if (viewState.zoom >= 13) {
      layerList.push(
        new MVTLayer({
          id: "house-prices-mvt",
          data: `${API_URL}/house-prices/tile/{z}/{x}/{y}`,
          minZoom: 13,
          maxZoom: 20,
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 100],
          pointRadiusMinPixels: 4,
          pointRadiusScale: 1,
          getPointRadius: 6,
          getFillColor: (d: DeckGLObject) => {
            const price = d.properties?.total_price || 0;
            const minPrice = propertyFilters.minPrice;
            const maxPrice = propertyFilters.maxPrice;
            const t = Math.min(
              1,
              Math.max(0, (price - minPrice) / (maxPrice - minPrice))
            );
            if (t < 0.5) {
              const r = Math.round(t * 2 * 255);
              return [r, 200, 50, 200];
            }
            const g = Math.round((1 - (t - 0.5) * 2) * 200);
            return [255, g, 50, 200];
          },
        })
      );
    }

    // Overlay: POIs
    if (overlays.pois) {
      layerList.push(
        new MVTLayer({
          id: "all-pois-layer",
          data: `${API_URL}/analytics/all-pois/tile/{z}/{x}/{y}`,
          minZoom: 13,
          maxZoom: 20,
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 100],
          pointRadiusMinPixels: 3,
          pointRadiusScale: 1,
          getPointRadius: 4,
          getFillColor: (d: DeckGLObject) => {
            const type = d.properties?.type;
            if (type === "school") return [0, 128, 255];
            if (type === "police_station") return [0, 0, 128];
            if (type === "museum") return [128, 0, 128];
            if (type === "gas_station") return [255, 165, 0];
            if (type === "traffic_point") return [255, 0, 0];
            if (type === "water_transport") return [0, 255, 255];
            if (type === "tourist_attraction") return [255, 105, 180];
            if (type === "bus_shelter") return [0, 255, 0];
            if (type === "transit_stop") return [255, 215, 0];
            return [120, 120, 120];
          },
        })
      );
    }

    // Overlay: Schools
    if (overlays.schools && schools) {
      layerList.push(
        new ScatterplotLayer({
          id: "schools",
          data: schools.features,
          getPosition: (d: DeckGLObject) => d.geometry?.coordinates || [0, 0],
          getFillColor: [0, 100, 255],
          getRadius: 150,
          pickable: true,
          opacity: 0.8,
        })
      );
    }

    return layerList;
  }, [housePrices, schools, overlays, viewState.zoom, propertyFilters]);

  const getTooltip = ({ object }: { object?: DeckGLObject | null }) => {
    if (!object) return null;

    // House Price Tooltip (MVT or Scatterplot)
    const price = object.total_price || object.properties?.total_price;
    if (price !== undefined) {
      const formatPrice = (p: number) =>
        new Intl.NumberFormat("th-TH", {
          style: "currency",
          currency: "THB",
          maximumFractionDigits: 0,
        }).format(p);

      const data = object.properties || object;
      const pricePerSqm =
        data.building_area && price
          ? formatPrice(price / data.building_area)
          : "N/A";

      return {
        html: `<div class="p-3 bg-zinc-900/90 border border-zinc-700 text-white rounded-lg shadow-xl backdrop-blur-md min-w-55">
          <div class="font-bold text-sm mb-1 text-amber-400">🏠 ${data.building_style_desc || "Property"}</div>
          <div class="text-lg font-bold text-white mb-2">${formatPrice(price)}</div>
          <div class="grid grid-cols-2 gap-1 text-[11px] text-zinc-300">
            <div>District:</div><div class="text-right font-medium">${data.amphur || "N/A"}</div>
            <div>Sub-district:</div><div class="text-right font-medium">${data.tumbon || "N/A"}</div>
            <div>Area:</div><div class="text-right font-medium">${data.building_area ? `${data.building_area} sqm` : "N/A"}</div>
            <div>Price/sqm:</div><div class="text-right font-medium text-emerald-400">${pricePerSqm}</div>
            <div>Floors:</div><div class="text-right font-medium">${data.no_of_floor || "N/A"}</div>
            <div>Age:</div><div class="text-right font-medium">${data.building_age ? `${data.building_age} yrs` : "N/A"}</div>
          </div>
        </div>`,
      };
    }

    // POI Tooltip
    if (object.properties?.type) {
      const props = object.properties;
      const name = props.name || "Unnamed Location";
      const type = props.type || "Unknown Type";

      return {
        html: `<div class="p-3 bg-zinc-900/90 border border-zinc-700 text-white rounded-lg shadow-xl backdrop-blur-md min-w-50">
          <div class="font-bold text-sm mb-1">${name}</div>
          <div class="text-xs font-medium text-zinc-400">${type}</div>
        </div>`,
      };
    }

    return null;
  };

  const handleMapClick = (info: { coordinate?: [number, number] }) => {
    // For future: could enable clicking to see property details
    console.log("Clicked:", info);
  };

  const PanelContent = (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Home className="w-5 h-5 text-amber-400" />
          <h2 className="text-xl font-bold text-white">Property Explorer</h2>
        </div>
        <p className="text-xs text-white/50">
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
        <div className="border border-white/10 rounded-lg overflow-hidden">
          <CollapsibleTrigger className="w-full flex items-center justify-between p-3 bg-white/5 hover:bg-white/10 transition-colors">
            <h3 className="text-sm font-bold text-white">Filters</h3>
            {openSections.filters ? (
              <ChevronUp className="w-4 h-4 text-white/50" />
            ) : (
              <ChevronDown className="w-4 h-4 text-white/50" />
            )}
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="p-3 bg-black/20">
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
        onOpenChange={(open) => setOpenSections((s) => ({ ...s, stats: open }))}
      >
        <div className="border border-white/10 rounded-lg overflow-hidden">
          <CollapsibleTrigger className="w-full flex items-center justify-between p-3 bg-white/5 hover:bg-white/10 transition-colors">
            <h3 className="text-sm font-bold text-white">Market Statistics</h3>
            {openSections.stats ? (
              <ChevronUp className="w-4 h-4 text-white/50" />
            ) : (
              <ChevronDown className="w-4 h-4 text-white/50" />
            )}
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="p-3 bg-black/20">
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
        <div className="border border-white/10 rounded-lg overflow-hidden">
          <CollapsibleTrigger className="w-full flex items-center justify-between p-3 bg-white/5 hover:bg-white/10 transition-colors">
            <h3 className="text-sm font-bold text-white">Map Overlays</h3>
            {openSections.overlays ? (
              <ChevronUp className="w-4 h-4 text-white/50" />
            ) : (
              <ChevronDown className="w-4 h-4 text-white/50" />
            )}
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="p-3 bg-black/20 space-y-2">
              <LayerToggle
                label="All POIs"
                active={overlays.pois}
                color="bg-purple-500"
                onClick={() => setOverlays((o) => ({ ...o, pois: !o.pois }))}
              />
              <LayerToggle
                label="Schools"
                active={overlays.schools}
                color="bg-blue-500"
                onClick={() =>
                  setOverlays((o) => ({ ...o, schools: !o.schools }))
                }
              />
            </div>
          </CollapsibleContent>
        </div>
      </Collapsible>

      {/* Info Section */}
      <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded text-xs text-amber-200">
        <span className="font-bold">💡 Tip:</span> Zoom in past level 13 to see
        detailed MVT tiles. Use filters to narrow down properties by district,
        type, price, and area.
      </div>
    </div>
  );

  return (
    <Shell panelContent={PanelContent}>
      <div className="w-full h-full bg-black relative overflow-hidden">
        <MapContainer
          viewState={viewState}
          onViewStateChange={(e) => setViewState(e.viewState)}
          layers={layers}
          getTooltip={getTooltip}
          onClick={handleMapClick}
        />

        {/* Price Legend */}
        <PriceLegend
          minPrice={propertyFilters.minPrice}
          maxPrice={propertyFilters.maxPrice}
        />

        {/* Info Badge */}
        <div className="absolute top-6 left-1/2 -translate-x-1/2 z-40 bg-black/80 backdrop-blur-md border border-white/10 rounded-full px-4 py-2">
          <div className="flex items-center gap-2 text-xs text-white/70">
            <Home className="w-3 h-3" />
            <span>
              {housePrices?.total || 0} properties |{" "}
              {housePrices?.items?.length || 0} shown
            </span>
          </div>
        </div>
      </div>
    </Shell>
  );
}

function LayerToggle({
  label,
  active,
  color,
  onClick,
}: {
  label: string;
  active: boolean;
  color: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full flex items-center justify-between p-3 rounded-lg transition-all border",
        active
          ? "bg-white/10 border-white/10"
          : "bg-transparent border-transparent hover:bg-white/5"
      )}
    >
      <div className="flex items-center gap-3">
        <div
          className={cn(
            "w-3 h-3 rounded-full shadow-[0_0_10px_currentColor]",
            color,
            !active && "opacity-20 shadow-none"
          )}
        />
        <span
          className={cn(
            "text-sm font-medium",
            active ? "text-white" : "text-white/50"
          )}
        >
          {label}
        </span>
      </div>
      {active ? (
        <Eye size={16} className="text-white/70" />
      ) : (
        <EyeOff size={16} className="text-white/30" />
      )}
    </button>
  );
}
