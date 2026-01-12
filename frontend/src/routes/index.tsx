import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { MapContainer } from "../components/MapContainer";
import { Shell } from "../components/Shell";
import type { Attachment } from "../components/ChatPanel";
import { PathLayer, IconLayer, ScatterplotLayer } from "@deck.gl/layers";
import { MVTLayer } from "@deck.gl/geo-layers";
import {
  Eye,
  EyeOff,
  ChevronDown,
  ChevronUp,
  Home,
  BarChart3,
  Train,
} from "lucide-react";
import { cn } from "../lib/utils";
import { api, API_URL } from "../lib/api";
import type { TransitLineFeature } from "../lib/api";
import { generateIconAtlas, getIconNameForType } from "../lib/map-icons";
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
  validateSearch: (search: Record<string, unknown>) => {
    return {
      district:
        typeof search.district === "string" ? search.district : undefined,
    };
  },
});

const BANGKOK_LAT = 13.7563;
const BANGKOK_LON = 100.5018;

function PropertyExplorer() {
  const navigate = useNavigate();
  const { district: districtFromUrl } = Route.useSearch();

  const [viewState, setViewState] = useState<ViewState>({
    longitude: BANGKOK_LON,
    latitude: BANGKOK_LAT,
    zoom: 12,
    pitch: 0,
    bearing: 0,
  });

  // Property filters - main feature
  const [propertyFilters, setPropertyFilters] = useState<PropertyFiltersState>(
    () => ({
      district: districtFromUrl || null,
      buildingStyle: null,
      minPrice: 500_000,
      maxPrice: 50_000_000,
      minArea: 20,
      maxArea: 500,
    })
  );

  // Overlays - secondary features
  const [overlays, setOverlays] = useState({
    pois: false,
    schools: false,
    priceDensity: false,
    transitRail: false,
  });

  // Chat interaction state
  const [selectionMode, setSelectionMode] = useState<"none" | "location">(
    "none"
  );
  const [chatAttachments, setChatAttachments] = useState<Attachment[]>([]);

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
        amphur: propertyFilters.district || undefined,
        building_style: propertyFilters.buildingStyle || undefined,
        min_price: propertyFilters.minPrice,
        max_price: propertyFilters.maxPrice,
        min_area: propertyFilters.minArea,
        max_area: propertyFilters.maxArea,
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

  // Fetch Transit Lines (rail only: BTS=0, MRT=1, ARL=2)
  const { data: transitLines } = useQuery({
    queryKey: ["transitLines", "rail"],
    queryFn: async () => {
      // Fetch BTS (0), MRT (1), and Rail/ARL (2) separately and combine
      const [bts, mrt, rail] = await Promise.all([
        api.getTransitLines(0),
        api.getTransitLines(1),
        api.getTransitLines(2),
      ]);
      return {
        type: "FeatureCollection" as const,
        features: [...bts.features, ...mrt.features, ...rail.features],
      };
    },
    enabled: overlays.transitRail,
  });

  // Generate icon atlas for POIs
  const iconAtlas = useMemo(() => generateIconAtlas(), []);

  const layers = useMemo(() => {
    const layerList = [];

    // Primary: House Prices Layer (always shown when data available)
    if (housePrices && viewState.zoom < 13) {
      // Use IconLayer for low zoom
      layerList.push(
        new IconLayer({
          id: "house-prices-icon",
          data: housePrices.items,
          iconAtlas: iconAtlas.atlas,
          iconMapping: iconAtlas.mapping,
          getIcon: () => "home",
          getPosition: (d: DeckGLObject) => [d.lon || 0, d.lat || 0],
          getColor: (d: DeckGLObject) => {
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
              return [r, 200, 50];
            }
            const g = Math.round((1 - (t - 0.5) * 2) * 200);
            return [255, g, 50];
          },
          getSize: 20,
          sizeScale: 1,
          sizeMinPixels: 12,
          sizeMaxPixels: 30,
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 100],
        })
      );
    }

    // MVT tiles for high zoom - with filter params
    if (viewState.zoom >= 13) {
      // Build filter query string for MVT tiles
      const mvtParams = new URLSearchParams();
      if (propertyFilters.district)
        mvtParams.set("amphur", propertyFilters.district);
      if (propertyFilters.buildingStyle)
        mvtParams.set("building_style", propertyFilters.buildingStyle);
      if (propertyFilters.minPrice !== undefined)
        mvtParams.set("min_price", String(propertyFilters.minPrice));
      if (propertyFilters.maxPrice !== undefined)
        mvtParams.set("max_price", String(propertyFilters.maxPrice));
      if (propertyFilters.minArea !== undefined)
        mvtParams.set("min_area", String(propertyFilters.minArea));
      if (propertyFilters.maxArea !== undefined)
        mvtParams.set("max_area", String(propertyFilters.maxArea));
      const mvtQueryString = mvtParams.toString()
        ? `?${mvtParams.toString()}`
        : "";

      layerList.push(
        new MVTLayer({
          id: "house-prices-mvt",
          data: `${API_URL}/house-prices/tile/{z}/{x}/{y}${mvtQueryString}`,
          minZoom: 13,
          maxZoom: 20,
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 100],
          binary: false,
          renderSubLayers: (props) => {
            return new IconLayer(props, {
              id: `${props.id}-icon`,
              iconAtlas: iconAtlas.atlas,
              iconMapping: iconAtlas.mapping,
              getIcon: () => "home",
              getPosition: (d: DeckGLObject) => d.geometry?.coordinates,
              getSize: 24,
              getColor: (d: DeckGLObject) => {
                const price = d.properties?.total_price || 0;
                const minPrice = propertyFilters.minPrice;
                const maxPrice = propertyFilters.maxPrice;
                const t = Math.min(
                  1,
                  Math.max(0, (price - minPrice) / (maxPrice - minPrice))
                );
                if (t < 0.5) {
                  const r = Math.round(t * 2 * 255);
                  return [r, 200, 50];
                }
                const g = Math.round((1 - (t - 0.5) * 2) * 200);
                return [255, g, 50];
              },
              sizeScale: 1,
              sizeMinPixels: 12,
              sizeMaxPixels: 40,
              pickable: true,
              autoHighlight: true,
              highlightColor: [255, 255, 255, 100],
            });
          },
        })
      );
    }

    // Overlay: POIs with improved styling (Icons)
    if (overlays.pois) {
      layerList.push(
        new MVTLayer({
          id: "all-pois-layer",
          data: `${API_URL}/analytics/all-pois/tile/{z}/{x}/{y}`,
          minZoom: 12,
          maxZoom: 20,
          binary: false,
          renderSubLayers: (props) => {
            return new IconLayer(props, {
              id: `${props.id}-icon`,
              iconAtlas: iconAtlas.atlas,
              iconMapping: iconAtlas.mapping,
              getIcon: (d: DeckGLObject) =>
                getIconNameForType(d.properties?.type || ""),
              getPosition: (d: DeckGLObject) => d.geometry?.coordinates,
              getSize: (d: DeckGLObject) => {
                const type = d.properties?.type;
                if (type === "transit_stop") return 28;
                if (type === "school") return 24;
                return 20;
              },
              getColor: (d: DeckGLObject) => {
                const type = d.properties?.type;
                // Transit - Gold
                if (type === "transit_stop") return [255, 200, 50];
                // Education - Blue
                if (type === "school") return [59, 130, 246];
                // Safety - Navy
                if (type === "police_station") return [30, 58, 138];
                // Culture - Purple
                if (type === "museum") return [147, 51, 234];
                if (type === "tourist_attraction") return [236, 72, 153];
                // Transport - Cyan/Teal
                if (type === "water_transport") return [6, 182, 212];
                if (type === "bus_shelter") return [34, 197, 94];
                // Utilities - Orange
                if (type === "gas_station") return [249, 115, 22];
                // Traffic - Red
                if (type === "traffic_point") return [239, 68, 68];
                // Default gray
                return [148, 163, 184];
              },
              sizeScale: 1,
              sizeMinPixels: 12,
              sizeMaxPixels: 40,
              pickable: true,
              autoHighlight: true,
              highlightColor: [255, 255, 255, 100],
            });
          },
        })
      );
    }

    // Overlay: Schools
    if (overlays.schools && schools) {
      layerList.push(
        new IconLayer({
          id: "schools",
          data: schools.features,
          iconAtlas: iconAtlas.atlas,
          iconMapping: iconAtlas.mapping,
          getIcon: () => "school",
          getPosition: (d: DeckGLObject) => d.geometry?.coordinates || [0, 0],
          getColor: [59, 130, 246], // Blue
          getSize: 32,
          sizeScale: 1,
          sizeMinPixels: 20,
          sizeMaxPixels: 40,
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 100],
        })
      );
    }

    // Overlay: Transit Rail Lines (BTS, MRT, ARL)
    if (overlays.transitRail && transitLines) {
      layerList.push(
        new PathLayer<TransitLineFeature>({
          id: "transit-lines",
          data: transitLines.features,
          getPath: (d) => d.geometry.coordinates,
          getColor: (d) => {
            // Parse route_color from hex or use defaults based on route_type
            const color = d.properties.route_color;
            if (color) {
              const hex = color.replace("#", "");
              const r = Number.parseInt(hex.substring(0, 2), 16);
              const g = Number.parseInt(hex.substring(2, 4), 16);
              const b = Number.parseInt(hex.substring(4, 6), 16);
              return [r, g, b, 220];
            }
            // Fallback colors by route type
            const routeType = d.properties.route_type;
            if (routeType === 0) return [101, 183, 36, 220]; // BTS Green
            if (routeType === 1) return [25, 100, 183, 220]; // MRT Blue
            if (routeType === 2) return [227, 32, 32, 220]; // ARL Red
            return [150, 150, 150, 180];
          },
          getWidth: 4,
          widthMinPixels: 2,
          widthMaxPixels: 8,
          pickable: true,
          capRounded: true,
          jointRounded: true,
        })
      );
    }

    // Overlay: Chat Selection Markers
    const locationAttachments = chatAttachments.filter(
      (a) => a.type === "location"
    );
    if (locationAttachments.length > 0) {
      layerList.push(
        new ScatterplotLayer({
          id: "chat-selection-markers",
          data: locationAttachments,
          getPosition: (d: Attachment) => [d.data.lon, d.data.lat],
          getFillColor: [255, 0, 255], // Magenta
          getRadius: 200,
          pickable: false,
          opacity: 0.8,
          stroked: true,
          getLineColor: [255, 255, 255],
          getLineWidth: 2,
          radiusMinPixels: 5,
        })
      );
    }

    return layerList;
  }, [
    housePrices,
    schools,
    transitLines,
    overlays,
    viewState.zoom,
    propertyFilters,
    iconAtlas,
    chatAttachments,
  ]);

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

    // Transit Line Tooltip
    if (object.properties?.route_short_name !== undefined) {
      const props = object.properties;
      const routeName = props.route_short_name || "Transit Line";
      const longName = props.route_long_name || "";
      const routeType = props.route_type;
      const typeLabel =
        routeType === 0
          ? "🚈 BTS Skytrain"
          : routeType === 1
            ? "🚇 MRT Metro"
            : routeType === 2
              ? "🚆 Rail/ARL"
              : "🚌 Transit";
      const color = props.route_color ? `#${props.route_color}` : "#888";

      return {
        html: `<div class="p-3 bg-zinc-900/90 border border-zinc-700 text-white rounded-lg shadow-xl backdrop-blur-md min-w-50">
          <div class="flex items-center gap-2 mb-1">
            <div class="w-3 h-3 rounded-full" style="background-color: ${color}"></div>
            <span class="font-bold text-sm">${routeName}</span>
          </div>
          <div class="text-xs text-zinc-400 mb-1">${typeLabel}</div>
          ${longName ? `<div class="text-xs text-zinc-500">${longName}</div>` : ""}
        </div>`,
      };
    }

    return null;
  };

  const handleMapClick = (info: {
    coordinate?: [number, number];
    object?: DeckGLObject;
  }) => {
    // Handle Selection Mode
    if (selectionMode === "location" && info.coordinate) {
      const [lon, lat] = info.coordinate;
      const newAttachment: Attachment = {
        id: `loc-${Date.now()}`,
        type: "location",
        data: { lat, lon },
        label: `Location (${lat.toFixed(4)}, ${lon.toFixed(4)})`,
      };
      setChatAttachments((prev) => [...prev, newAttachment]);
      setSelectionMode("none");
      return;
    }

    // Navigate to property details when clicking a property
    const id = info.object?.id || info.object?.properties?.id;
    if (id) {
      navigate({
        to: "/property/$propertyId",
        params: { propertyId: String(id) },
      });
    }
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
                label="Transit Lines (BTS/MRT)"
                active={overlays.transitRail}
                color="bg-emerald-500"
                icon={<Train className="w-4 h-4" />}
                onClick={() =>
                  setOverlays((o) => ({ ...o, transitRail: !o.transitRail }))
                }
              />
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
        <span className="font-bold">💡 Tip:</span> Click on a property to see
        full details. Zoom in past level 13 for MVT tiles.
      </div>

      {/* District Analysis Link */}
      <Link
        to="/districts"
        className="flex items-center justify-center gap-2 w-full py-3 bg-white/5 hover:bg-white/10 rounded-lg text-sm text-white/70 hover:text-white transition-colors border border-white/10"
      >
        <BarChart3 className="w-4 h-4" />
        View District Analysis
      </Link>
    </div>
  );

  return (
    <Shell
      panelContent={PanelContent}
      chatAttachments={chatAttachments}
      onChatPickLocation={() => setSelectionMode("location")}
      onChatRemoveAttachment={(id) =>
        setChatAttachments((prev) => prev.filter((a) => a.id !== id))
      }
    >
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

        {/* Selection Mode Overlay */}
        {selectionMode === "location" && (
          <div className="absolute top-20 left-1/2 -translate-x-1/2 z-50 bg-emerald-500 text-black px-4 py-2 rounded-full font-bold shadow-lg animate-pulse pointer-events-none">
            Click on map to select location
          </div>
        )}
      </div>
    </Shell>
  );
}

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
          ? "bg-white/10 border-white/10"
          : "bg-transparent border-transparent hover:bg-white/5"
      )}
    >
      <div className="flex items-center gap-3">
        {icon ? (
          <span className={cn(active ? "text-white" : "text-white/30")}>
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
