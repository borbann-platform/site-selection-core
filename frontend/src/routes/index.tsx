import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState, useMemo, useCallback, useEffect } from "react";
import { MapContainer } from "../components/MapContainer";
import { Shell } from "../components/Shell";
import {
  AICommandBar,
  AIExpandedPanel,
  DEFAULT_FILTERS,
  type Attachment,
  type SelectionMode,
  type AgentMessage,
  type FilterValues,
} from "../components/ai";
import { PathLayer, IconLayer, ScatterplotLayer } from "@deck.gl/layers";
import { MVTLayer, H3HexagonLayer } from "@deck.gl/geo-layers";
import {
  Eye,
  EyeOff,
  ChevronDown,
  ChevronUp,
  Home,
  BarChart3,
  Train,
  Target,
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
import { PropertyPopup } from "../components/PropertyPopup";
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
  id?: string | number;
  h3_index?: string;
  value?: number;
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
    h3Hexagons: false,
  });

  // H3 Hexagon metric selection
  const [h3Metric, setH3Metric] = useState<string>("poi_total");

  // AI Chat interaction state
  const [selectionMode, setSelectionMode] = useState<SelectionMode>("none");
  const [chatAttachments, setChatAttachments] = useState<Attachment[]>([]);

  // AI state
  const [isAIExpanded, setIsAIExpanded] = useState(false);
  const [aiInput, setAiInput] = useState("");
  const [aiMessages, setAiMessages] = useState<AgentMessage[]>([]);
  const [aiFilters, setAiFilters] = useState<FilterValues>(DEFAULT_FILTERS);
  const [isAIRunning, setIsAIRunning] = useState(false);

  // Bbox selection state (4-click polygon)
  const [bboxCorners, setBboxCorners] = useState<[number, number][]>([]);

  // Property popup state
  const [selectedProperty, setSelectedProperty] = useState<{
    id?: string | number;
    total_price?: number;
    building_area?: number;
    amphur?: string;
    tumbon?: string;
    building_style_desc?: string;
    no_of_floor?: number;
    building_age?: number;
    lat?: number;
    lon?: number;
  } | null>(null);
  const [popupPosition, setPopupPosition] = useState<{
    x: number;
    y: number;
  } | null>(null);

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

  // Fetch H3 Hexagon Analytics Data
  const { data: h3Data } = useQuery({
    queryKey: ["h3Hexagons", h3Metric, viewState.zoom],
    queryFn: () =>
      api.getH3Hexagons({
        metric: h3Metric,
        resolution: viewState.zoom < 12 ? 7 : viewState.zoom < 14 ? 9 : 11,
      }),
    enabled: overlays.h3Hexagons,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  // Handle AI message submission
  const handleAISubmit = useCallback(async () => {
    if (!aiInput.trim() || isAIRunning) return;

    setIsAIRunning(true);
    setIsAIExpanded(true);

    // Build context from filters and attachments
    const filterContext = Object.entries(aiFilters)
      .filter(
        ([, v]) =>
          v !== null && v !== false && v !== undefined && v !== ""
      )
      .map(([k, v]) => `${k}: ${v}`)
      .join(", ");

    const attachmentContext = chatAttachments
      .map((a) => `[${a.type}: ${a.label}]`)
      .join(" ");

    const fullMessage = [
      aiInput,
      filterContext && `(Filters: ${filterContext})`,
      attachmentContext,
    ]
      .filter(Boolean)
      .join(" ");

    // Add user message
    const userMsgId = `msg-${Date.now()}`;
    const userMessage: AgentMessage = {
      id: userMsgId,
      role: "user",
      content: aiInput,
    };

    // Add placeholder assistant message
    const assistantMsgId = `msg-${Date.now() + 1}`;
    const assistantMessage: AgentMessage = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      steps: [],
      isThinking: true,
      isStreaming: false,
    };

    setAiMessages((prev) => [...prev, userMessage, assistantMessage]);
    setAiInput("");

    // Stream response from real AI agent
    try {
      // Build message history for context
      const chatMessages = aiMessages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({ role: m.role, content: m.content }));
      
      // Add current message
      chatMessages.push({ role: "user" as const, content: fullMessage });

      // Stream from real agent API
      for await (const event of api.streamAgentChat(chatMessages)) {
        setAiMessages((prev) => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          const lastMsg = { ...updated[lastIdx] };

          if (event.event === "thinking") {
            lastMsg.isThinking = event.data?.thinking ?? true;
            if (event.data?.thinking) {
              lastMsg.thinkingStartTime = Date.now();
            }
          } else if (event.event === "step" && event.data) {
            const steps = [...(lastMsg.steps || [])];
            const stepData = event.data;
            const existingIdx = steps.findIndex((s) => s.id === stepData.id);
            
            if (existingIdx >= 0) {
              // Update existing step
              steps[existingIdx] = {
                ...steps[existingIdx],
                status: stepData.status as "running" | "complete" | "error",
                output: stepData.output,
                endTime: stepData.end_time,
              };
            } else {
              // Add new step
              steps.push({
                id: stepData.id || `step-${Date.now()}`,
                type: "tool_call",
                name: stepData.name || "Unknown",
                status: stepData.status as "running" | "complete" | "error",
                input: stepData.input,
                output: stepData.output,
                startTime: stepData.start_time || Date.now(),
                endTime: stepData.end_time,
              });
            }
            lastMsg.steps = steps;
          } else if (event.event === "token" && event.data?.token) {
            lastMsg.content += event.data.token;
            lastMsg.isStreaming = true;
            lastMsg.isThinking = false;
          } else if (event.event === "done") {
            lastMsg.isStreaming = false;
            lastMsg.isThinking = false;
          }

          updated[lastIdx] = lastMsg;
          return updated;
        });
      }
    } catch (error) {
      console.error("Agent stream error:", error);
      setAiMessages((prev) => {
        const updated = [...prev];
        const lastIdx = updated.length - 1;
        updated[lastIdx] = {
          ...updated[lastIdx],
          content: "Sorry, I encountered an error. Please try again.",
          isStreaming: false,
          isThinking: false,
        };
        return updated;
      });
    }

    // Reset filters after each conversation
    setAiFilters(DEFAULT_FILTERS);
    setIsAIRunning(false);
  }, [
    aiInput,
    isAIRunning,
    aiFilters,
    chatAttachments,
    aiMessages,
  ]);

  // Generate icon atlas for POIs
  // Note: Using 'as unknown as string' to satisfy DeckGL typing - canvas works at runtime
  const iconAtlasData = useMemo(() => generateIconAtlas(), []);
  const iconAtlas = useMemo(
    () => ({
      atlas: iconAtlasData.atlas as unknown as string,
      mapping: iconAtlasData.mapping,
    }),
    [iconAtlasData]
  );

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
          sizeMinPixels: 20,
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
              getPosition: (d: DeckGLObject) =>
                d.geometry?.coordinates ?? [0, 0],
              getSize: 24,
              getColor: (d: DeckGLObject) => {
                const price = Number(d.properties?.total_price) || 0;
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
              sizeMinPixels: 20,
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
                getIconNameForType(String(d.properties?.type ?? "")),
              getPosition: (d: DeckGLObject) =>
                d.geometry?.coordinates ?? [0, 0],
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
              sizeMinPixels: 20,
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

    // Overlay: H3 Hexagon Analytics (flood risk, POI density, etc.)
    if (overlays.h3Hexagons && h3Data && h3Data.hexagons.length > 0) {
      layerList.push(
        new H3HexagonLayer({
          id: "h3-hexagons",
          data: h3Data.hexagons,
          pickable: true,
          filled: true,
          extruded: false,
          getHexagon: (d: { h3_index: string }) => d.h3_index,
          getFillColor: (d: { value: number }) => {
            // Normalize value to 0-1 range
            const range = h3Data.max_value - h3Data.min_value || 1;
            const t = (d.value - h3Data.min_value) / range;
            // Blue -> Yellow -> Red gradient
            if (t < 0.5) {
              const r = Math.round(t * 2 * 255);
              const g = Math.round(t * 2 * 200);
              return [r, g, 255, 140];
            }
            const b = Math.round((1 - (t - 0.5) * 2) * 255);
            const g = Math.round((1 - (t - 0.5) * 2) * 200);
            return [255, g, b, 140];
          },
          getLineColor: [255, 255, 255, 100],
          lineWidthMinPixels: 1,
          opacity: 0.6,
        })
      );
    }

    // Overlay: Chat Selection Markers (Location points)
    const locationAttachments = chatAttachments.filter(
      (a) => a.type === "location"
    );
    if (locationAttachments.length > 0) {
      layerList.push(
        new ScatterplotLayer({
          id: "chat-selection-markers",
          data: locationAttachments,
          getPosition: (d: Attachment) => [
            Number(d.data.lon) || 0,
            Number(d.data.lat) || 0,
          ],
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

    // Overlay: Bbox Selection Corners (blue dots while selecting)
    if (selectionMode === "bbox" && bboxCorners.length > 0) {
      layerList.push(
        new ScatterplotLayer({
          id: "bbox-selection-corners",
          data: bboxCorners,
          getPosition: (d: [number, number]) => d,
          getFillColor: [0, 180, 255], // Cyan/Blue
          getRadius: 150,
          pickable: false,
          opacity: 1,
          stroked: true,
          getLineColor: [255, 255, 255],
          getLineWidth: 3,
          radiusMinPixels: 8,
          radiusMaxPixels: 12,
        })
      );
    }

    return layerList;
  }, [
    housePrices,
    schools,
    transitLines,
    h3Data,
    overlays,
    viewState.zoom,
    propertyFilters,
    iconAtlas,
    chatAttachments,
    selectionMode,
    bboxCorners,
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
      const buildingArea = Number(data.building_area) || 0;
      const numericPrice = Number(price) || 0;
      const pricePerSqm =
        buildingArea && numericPrice
          ? formatPrice(numericPrice / buildingArea)
          : "N/A";

      return {
        html: `<div class="p-3 bg-zinc-900/90 border border-zinc-700 text-white rounded-lg shadow-xl backdrop-blur-md min-w-55">
          <div class="font-bold text-sm mb-1 text-amber-400">🏠 ${data.building_style_desc || "Property"}</div>
          <div class="text-lg font-bold text-white mb-2">${formatPrice(numericPrice)}</div>
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

    // H3 Hexagon Tooltip
    if (object.h3_index !== undefined) {
      const metricLabel = h3Metric.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
      const value = typeof object.value === "number" ? object.value.toLocaleString("th-TH", { maximumFractionDigits: 2 }) : object.value;

      return {
        html: `<div class="p-3 bg-zinc-900/90 border border-zinc-700 text-white rounded-lg shadow-xl backdrop-blur-md min-w-50">
          <div class="font-bold text-sm mb-1">📊 ${metricLabel}</div>
          <div class="text-xl font-bold text-cyan-400">${value}</div>
          <div class="text-xs text-zinc-500 mt-1">H3: ${object.h3_index.slice(0, 12)}...</div>
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
    x?: number;
    y?: number;
  }) => {
    // Close popup if clicking on empty space
    if (!info.object && selectedProperty) {
      setSelectedProperty(null);
      setPopupPosition(null);
    }

    // Handle Location Selection Mode
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

    // Handle Bbox Selection Mode (4-click polygon)
    if (selectionMode === "bbox" && info.coordinate) {
      const [lon, lat] = info.coordinate;
      const newCorners = [...bboxCorners, [lon, lat] as [number, number]];

      if (newCorners.length < 4) {
        // Still collecting corners
        setBboxCorners(newCorners);
      } else {
        // 4 corners collected - create bbox attachment
        const lons = newCorners.map((c) => c[0]);
        const lats = newCorners.map((c) => c[1]);
        const minLon = Math.min(...lons);
        const maxLon = Math.max(...lons);
        const minLat = Math.min(...lats);
        const maxLat = Math.max(...lats);

        const newAttachment: Attachment = {
          id: `bbox-${Date.now()}`,
          type: "bbox",
          data: {
            corners: newCorners,
            minLon,
            maxLon,
            minLat,
            maxLat,
          },
          label: `Area (${((maxLon - minLon) * 111).toFixed(1)}km x ${((maxLat - minLat) * 111).toFixed(1)}km)`,
        };
        setChatAttachments((prev) => [...prev, newAttachment]);
        setBboxCorners([]);
        setSelectionMode("none");
      }
      return;
    }

    // Show property popup when clicking a property (not in selection mode)
    if (selectionMode === "none" && info.object) {
      const obj = info.object;
      const props = obj.properties || {};

      // Extract property data from object or its properties
      const rawId = obj.id || props.id;
      const propertyData = {
        id: typeof rawId === "string" || typeof rawId === "number" ? rawId : undefined,
        total_price: obj.total_price || Number(props.total_price) || undefined,
        building_area:
          obj.building_area || Number(props.building_area) || undefined,
        amphur: obj.amphur || String(props.amphur || ""),
        tumbon: obj.tumbon || String(props.tumbon || ""),
        building_style_desc:
          obj.building_style_desc || String(props.building_style_desc || ""),
        no_of_floor: obj.no_of_floor || Number(props.no_of_floor) || undefined,
        building_age:
          obj.building_age || Number(props.building_age) || undefined,
        lat: obj.lat || obj.geometry?.coordinates[1],
        lon: obj.lon || obj.geometry?.coordinates[0],
      };

      // Only show popup if it looks like a property (has price or id)
      if (propertyData.total_price || propertyData.id) {
        setSelectedProperty(propertyData);
        setPopupPosition({
          x: info.x || 0,
          y: info.y || 0,
        });
      }
    }
  };

  // Handle adding property to chat
  const handleAddPropertyToChat = useCallback(
    (property: {
      id?: string | number;
      total_price?: number;
      building_style_desc?: string;
      amphur?: string;
      lat?: number;
      lon?: number;
    }) => {
      const price = property.total_price
        ? `฿${(property.total_price / 1_000_000).toFixed(1)}M`
        : "";
      const name = property.building_style_desc || "Property";
      const district = property.amphur || "";

      const attachment: Attachment = {
        id: `prop-${Date.now()}`,
        type: "property",
        data: {
          ...property,
        },
        label: `${name}${price ? ` - ${price}` : ""}${district ? ` (${district})` : ""}`,
      };
      setChatAttachments((prev) => [...prev, attachment]);
      setSelectedProperty(null);
      setPopupPosition(null);
    },
    []
  );

  // Handle Escape key to cancel selection
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape" && selectionMode !== "none") {
        setSelectionMode("none");
        setBboxCorners([]);
      }
    },
    [selectionMode]
  );

  // Set up escape key listener
  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

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
              <LayerToggle
                label="H3 Analytics"
                active={overlays.h3Hexagons}
                color="bg-cyan-500"
                onClick={() =>
                  setOverlays((o) => ({ ...o, h3Hexagons: !o.h3Hexagons }))
                }
              />
              {overlays.h3Hexagons && (
                <select
                  value={h3Metric}
                  onChange={(e) => setH3Metric(e.target.value)}
                  className="w-full px-2 py-1 text-xs bg-zinc-700 rounded text-white border border-zinc-600 mt-1"
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
                    <option value="avg_building_area">Avg Building Area</option>
                    <option value="avg_land_area">Avg Land Area</option>
                    <option value="avg_building_age">Avg Building Age</option>
                  </optgroup>
                  <optgroup label="Transit">
                    <option value="transit_total">Transit Accessibility</option>
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
    <>
      <Shell panelContent={PanelContent}>
        <div className="w-full h-full bg-black relative overflow-hidden">
          <MapContainer
            viewState={viewState}
            onViewStateChange={(e) => setViewState(e.viewState)}
            layers={layers}
            getTooltip={getTooltip}
            onClick={handleMapClick}
            selectionMode={selectionMode}
          />

          {/* Price Legend */}
          <PriceLegend
            minPrice={propertyFilters.minPrice}
            maxPrice={propertyFilters.maxPrice}
          />

          {/* Property Popup */}
          <PropertyPopup
            property={selectedProperty}
            position={popupPosition}
            onClose={() => {
              setSelectedProperty(null);
              setPopupPosition(null);
            }}
            onAddToChat={handleAddPropertyToChat}
          />

          {/* Info Badge */}
          <div className="absolute top-6 left-1/2 -translate-x-1/2 z-40 bg-black/80 backdrop-blur-md border border-white/10 rounded-full px-4 py-2">
            <div className="flex items-center gap-2 text-xs text-white/70">
              <Home className="w-3 h-3" />
              <span>
                {housePrices?.count || 0} properties |{" "}
                {housePrices?.items?.length || 0} shown
              </span>
            </div>
          </div>

          {/* Selection Mode Overlay */}
          {selectionMode !== "none" && (
            <div className="pointer-events-none fixed inset-0 z-[100] flex items-center justify-center">
              <div
                className={cn(
                  "absolute top-24 left-1/2 -translate-x-1/2 px-6 py-3 rounded-full font-bold shadow-2xl backdrop-blur-md border-2 animate-bounce-slight transition-colors",
                  selectionMode === "location"
                    ? "bg-emerald-500/90 border-emerald-300 text-black shadow-emerald-500/20"
                    : "bg-cyan-500/90 border-cyan-300 text-black shadow-cyan-500/20"
                )}
              >
                <div className="flex items-center gap-2">
                  <Target size={20} className="animate-ping absolute opacity-50" />
                  <Target size={20} />
                  <span>
                    {selectionMode === "location"
                      ? "CLICK EXACT LOCATION"
                      : `CLICK CORNER ${bboxCorners.length + 1} OF 4`}
                  </span>
                </div>
                <div className="text-[10px] font-normal opacity-80 text-center mt-1">
                  Press ESC to cancel
                </div>
              </div>
            </div>
          )}
        </div>
      </Shell>

      {/* AI Command Bar - Always Visible at Bottom */}
      <AICommandBar
        input={aiInput}
        onInputChange={setAiInput}
        onSubmit={handleAISubmit}
        attachments={chatAttachments}
        selectionMode={selectionMode}
        isExpanded={isAIExpanded}
        isRunning={isAIRunning}
        onToggleExpanded={() => setIsAIExpanded(!isAIExpanded)}
        onPickLocation={() => setSelectionMode("location")}
        onPickBbox={() => setSelectionMode("bbox")}
        onRemoveAttachment={(id) =>
          setChatAttachments((prev) => prev.filter((a) => a.id !== id))
        }
      />

      {/* AI Expanded Panel - Conversation History + Filters */}
      <AIExpandedPanel
        isExpanded={isAIExpanded}
        messages={aiMessages}
        filterValues={aiFilters}
        onFilterChange={setAiFilters}
        onPropertyClick={(property) => {
          // Pan to property location if lat/lon available
          if (property.lat && property.lon) {
            setViewState((prev) => ({
              ...prev,
              latitude: property.lat!,
              longitude: property.lon!,
              zoom: 15,
              transitionDuration: 500,
            }));
          }
        }}
      />
    </>
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
