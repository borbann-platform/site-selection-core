import { useState, useCallback, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  DEFAULT_FILTERS,
  type Attachment,
  type SelectionMode,
  type AgentMessage,
  type FilterValues,
} from "@/components/ai";
import type { PropertyFiltersState } from "@/components/PropertyFilters";

// ---- Type definitions ----

export interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
  transitionDuration?: number;
}

export interface OverlayState {
  pois: boolean;
  schools: boolean;
  priceDensity: boolean;
  transitRail: boolean;
  h3Hexagons: boolean;
}

export interface OpenSections {
  filters: boolean;
  stats: boolean;
  overlays: boolean;
}

export interface SelectedProperty {
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
}

export interface DeckGLObject {
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

// ---- Constants ----

export const BANGKOK_LAT = 13.7563;
export const BANGKOK_LON = 100.5018;

// ---- Hook ----

export function usePropertyExplorer(districtFromUrl?: string) {
  // -- View State --
  const [viewState, setViewState] = useState<ViewState>({
    longitude: BANGKOK_LON,
    latitude: BANGKOK_LAT,
    zoom: 12,
    pitch: 0,
    bearing: 0,
  });

  // -- Property Filters --
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

  // -- Overlays --
  const [overlays, setOverlays] = useState<OverlayState>({
    pois: false,
    schools: false,
    priceDensity: false,
    transitRail: false,
    h3Hexagons: false,
  });

  // -- H3 Metric --
  const [h3Metric, setH3Metric] = useState<string>("poi_total");

  // -- AI Chat interaction --
  const [selectionMode, setSelectionMode] = useState<SelectionMode>("none");
  const [chatAttachments, setChatAttachments] = useState<Attachment[]>([]);

  // -- AI state --
  const [isAIExpanded, setIsAIExpanded] = useState(false);
  const [aiInput, setAiInput] = useState("");
  const [aiMessages, setAiMessages] = useState<AgentMessage[]>([]);
  const [aiFilters, setAiFilters] = useState<FilterValues>(DEFAULT_FILTERS);
  const [isAIRunning, setIsAIRunning] = useState(false);

  // -- Bbox selection (4-click polygon) --
  const [bboxCorners, setBboxCorners] = useState<[number, number][]>([]);

  // -- Property popup --
  const [selectedProperty, setSelectedProperty] =
    useState<SelectedProperty | null>(null);
  const [popupPosition, setPopupPosition] = useState<{
    x: number;
    y: number;
  } | null>(null);

  // -- Collapsible sections --
  const [openSections, setOpenSections] = useState<OpenSections>({
    filters: true,
    stats: true,
    overlays: false,
  });

  // ---- Data fetching ----

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

  const { data: transitLines } = useQuery({
    queryKey: ["transitLines", "rail"],
    queryFn: async () => {
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

  const { data: h3Data } = useQuery({
    queryKey: ["h3Hexagons", h3Metric, viewState.zoom],
    queryFn: () =>
      api.getH3Hexagons({
        metric: h3Metric,
        resolution: viewState.zoom < 12 ? 7 : viewState.zoom < 14 ? 9 : 11,
      }),
    enabled: overlays.h3Hexagons,
    staleTime: 1000 * 60 * 5,
  });

  // ---- Handlers ----

  const handleAISubmit = useCallback(async () => {
    if (!aiInput.trim() || isAIRunning) return;

    setIsAIRunning(true);
    setIsAIExpanded(true);

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

    const userMsgId = `msg-${Date.now()}`;
    const userMessage: AgentMessage = {
      id: userMsgId,
      role: "user",
      content: aiInput,
    };

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

    const attachmentsToSend =
      chatAttachments.length > 0 ? [...chatAttachments] : undefined;

    setChatAttachments([]);
    setBboxCorners([]);

    try {
      const chatMessages = aiMessages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({ role: m.role, content: m.content }));

      chatMessages.push({ role: "user" as const, content: fullMessage });

      for await (const event of api.streamAgentChat(
        chatMessages,
        attachmentsToSend
      )) {
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
              steps[existingIdx] = {
                ...steps[existingIdx],
                status: stepData.status as "running" | "complete" | "error",
                output: stepData.output,
                endTime: stepData.end_time,
              };
            } else {
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

    setAiFilters(DEFAULT_FILTERS);
    setIsAIRunning(false);
  }, [aiInput, isAIRunning, aiFilters, chatAttachments, aiMessages]);

  const sanitizePropertyData = useCallback(
    (data: Record<string, unknown>): Record<string, unknown> => {
      const sanitized: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(data)) {
        if (value === undefined) {
          continue;
        }
        if (typeof value === "number" && !Number.isFinite(value)) {
          sanitized[key] = null;
        } else if (typeof value === "object" && value !== null) {
          sanitized[key] = sanitizePropertyData(
            value as Record<string, unknown>
          );
        } else {
          sanitized[key] = value;
        }
      }
      return sanitized;
    },
    []
  );

  const handleMapClick = useCallback(
    (info: {
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
          setBboxCorners(newCorners);
        } else {
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

        const rawId = obj.id || props.id;
        const propertyData: SelectedProperty = {
          id:
            typeof rawId === "string" || typeof rawId === "number"
              ? rawId
              : undefined,
          total_price:
            obj.total_price || Number(props.total_price) || undefined,
          building_area:
            obj.building_area || Number(props.building_area) || undefined,
          amphur: obj.amphur || String(props.amphur || ""),
          tumbon: obj.tumbon || String(props.tumbon || ""),
          building_style_desc:
            obj.building_style_desc ||
            String(props.building_style_desc || ""),
          no_of_floor:
            obj.no_of_floor || Number(props.no_of_floor) || undefined,
          building_age:
            obj.building_age || Number(props.building_age) || undefined,
          lat: obj.lat || obj.geometry?.coordinates[1],
          lon: obj.lon || obj.geometry?.coordinates[0],
        };

        if (propertyData.total_price || propertyData.id) {
          setSelectedProperty(propertyData);
          setPopupPosition({
            x: info.x || 0,
            y: info.y || 0,
          });
        }
      }
    },
    [selectionMode, bboxCorners, selectedProperty]
  );

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
        data: sanitizePropertyData(property as Record<string, unknown>),
        label: `${name}${price ? ` - ${price}` : ""}${district ? ` (${district})` : ""}`,
      };
      setChatAttachments((prev) => [...prev, attachment]);
      setSelectedProperty(null);
      setPopupPosition(null);
    },
    [sanitizePropertyData]
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape" && selectionMode !== "none") {
        setSelectionMode("none");
        setBboxCorners([]);
      }
    },
    [selectionMode]
  );

  // Escape key listener
  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // ---- Return ----

  return {
    // View state
    viewState,
    setViewState,

    // Property filters
    propertyFilters,
    setPropertyFilters,

    // Overlays
    overlays,
    setOverlays,
    h3Metric,
    setH3Metric,

    // AI
    selectionMode,
    setSelectionMode,
    chatAttachments,
    setChatAttachments,
    isAIExpanded,
    setIsAIExpanded,
    aiInput,
    setAiInput,
    aiMessages,
    aiFilters,
    setAiFilters,
    isAIRunning,

    // Bbox
    bboxCorners,

    // Property popup
    selectedProperty,
    setSelectedProperty,
    popupPosition,
    setPopupPosition,

    // Panel sections
    openSections,
    setOpenSections,

    // Data
    housePrices,
    schools,
    transitLines,
    h3Data,

    // Handlers
    handleAISubmit,
    handleMapClick,
    handleAddPropertyToChat,
  };
}
