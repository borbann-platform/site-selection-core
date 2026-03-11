import { useState, useCallback, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import type { MapViewState, PickingInfo } from "@deck.gl/core";
import { api } from "@/lib/api";
import { toast } from "sonner";
import type {
  Attachment,
  SelectionMode,
  AgentMessage,
} from "@/components/ai";
import type { PropertyFiltersState } from "@/components/PropertyFilters";
import {
  buildBBoxAttachment,
  buildClickGrounding,
  buildLocationAttachment,
  buildViewportMetrics,
  resolveHouseReference,
} from "@/lib/uiGrounding";

// ---- Type definitions ----

export type ViewState = MapViewState;

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
  listing_key?: string;
  source_type?: "house_price" | "scraped_project";
  id?: string | number;
  house_ref?: string;
  locator?: string;
  title?: string;
  total_price?: number;
  building_area?: number;
  amphur?: string;
  tumbon?: string;
  building_style_desc?: string;
  no_of_floor?: number;
  building_age?: number;
  lat?: number;
  lon?: number;
  image_url?: string;
  detail_url?: string;
}

export interface DeckGLObject {
  listing_key?: string;
  source_type?: "house_price" | "scraped_project";
  source?: string;
  source_id?: string;
  lon?: number;
  lat?: number;
  title?: string | null;
  image_url?: string | null;
  detail_url?: string | null;
  total_price?: number | null;
  building_area?: number | null;
  amphur?: string | null;
  tumbon?: string | null;
  building_style_desc?: string | null;
  no_of_floor?: number | null;
  building_age?: number | null;
  id?: string | number;
  h3_index?: string;
  value?: number;
  properties?: Record<string, unknown> | null;
  geometry?: { coordinates?: [number, number] | number[] } | null;
}

// ---- Constants ----

export const BANGKOK_LAT = 13.7563;
export const BANGKOK_LON = 100.5018;

function toFiniteNumber(value: unknown): number | undefined {
  const num = Number(value);
  return Number.isFinite(num) ? num : undefined;
}

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

  const { data: listings } = useQuery({
    queryKey: ["listings", propertyFilters],
    queryFn: () =>
      api.getListings({
        amphur: propertyFilters.district || undefined,
        building_style: propertyFilters.buildingStyle || undefined,
        min_price: propertyFilters.minPrice,
        max_price: propertyFilters.maxPrice,
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

  // Derive the H3 resolution from the current zoom level so that the query
  // key only changes when we actually need a different resolution (not on
  // every fractional zoom change).
  const h3Resolution = viewState.zoom < 12 ? 7 : viewState.zoom < 14 ? 9 : 11;

  const { data: h3Data } = useQuery({
    queryKey: ["h3Hexagons", h3Metric, h3Resolution],
    queryFn: async () => {
      const primary = await api.getH3Hexagons({
        metric: h3Metric,
        resolution: h3Resolution,
        limit: 10000,
      });

      // Some environments only have complete data at resolution 9.
      if (primary.hexagons.length > 0 || h3Resolution === 9) {
        return primary;
      }

      return api.getH3Hexagons({
        metric: h3Metric,
        resolution: 9,
        limit: 10000,
      });
    },
    enabled: overlays.h3Hexagons,
    staleTime: 1000 * 60 * 5,
  });

  // ---- Handlers ----

  const handleAISubmit = useCallback(async () => {
    if (!aiInput.trim() || isAIRunning) return;

    setIsAIRunning(true);
    setIsAIExpanded(true);

    const attachmentContext = chatAttachments
      .map((a) => `[${a.type}: ${a.label}]`)
      .join(" ");

    const fullMessage = [aiInput, attachmentContext].filter(Boolean).join(" ");

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
                status: stepData.status as "running" | "complete" | "error" | "waiting",
                output: stepData.output,
                endTime: stepData.end_time,
              };
            } else {
              steps.push({
                id: stepData.id || `step-${Date.now()}`,
                type:
                  (stepData.type as "tool_call" | "thinking" | "waiting_user") ||
                  "tool_call",
                name: stepData.name || "Unknown",
                status: (stepData.status as "running" | "complete" | "error" | "waiting"),
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
            lastMsg.error = undefined;
          } else if (event.event === "error" && event.data) {
            lastMsg.error = {
              title: event.data.title || "Model request failed",
              message:
                event.data.message ||
                "The model provider returned an error. Please check your settings.",
              statusCode: event.data.status_code,
              providerCode: event.data.provider_code,
              rawMessage: event.data.raw_message,
              retryable: event.data.retryable,
            };
            lastMsg.isStreaming = false;
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
          error: {
            title: "Request failed",
            message:
              error instanceof Error
                ? error.message
                : "Sorry, I encountered an error. Please try again.",
          },
          isStreaming: false,
          isThinking: false,
        };
        return updated;
      });
    }

    setIsAIRunning(false);
  }, [aiInput, isAIRunning, chatAttachments, aiMessages]);

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
    (info: PickingInfo<DeckGLObject>) => {
      const coordinate = Array.isArray(info.coordinate) ? info.coordinate : null;
      const viewport = buildViewportMetrics(
        info.viewport?.width,
        info.viewport?.height
      );
      const clickGrounding = buildClickGrounding(
        { x: info.x || 0, y: info.y || 0 },
        viewport
      );

      // Close popup if clicking on empty space
      if (!info.object && selectedProperty) {
        setSelectedProperty(null);
        setPopupPosition(null);
      }

      // Handle Location Selection Mode
      if (selectionMode === "location" && coordinate && coordinate.length >= 2) {
        const [lon, lat] = coordinate;
        const newAttachment = buildLocationAttachment(lat, lon, clickGrounding);
        if (!newAttachment) {
          toast.error("Invalid location selection. Please click again.");
          return;
        }
        setChatAttachments((prev) => [...prev, newAttachment]);
        setSelectionMode("none");
        return;
      }

      // Handle Bbox Selection Mode (4-click polygon)
      if (selectionMode === "bbox" && coordinate && coordinate.length >= 2) {
        const [lon, lat] = coordinate;
        const newCorners = [...bboxCorners, [lon, lat] as [number, number]];

        if (newCorners.length < 4) {
          setBboxCorners(newCorners);
        } else {
          const newAttachment = buildBBoxAttachment(newCorners, clickGrounding);
          if (!newAttachment) {
            toast.error("Invalid area bounds. Please redraw the selection.");
            setBboxCorners([]);
            setSelectionMode("none");
            return;
          }
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
        const coords = obj.geometry?.coordinates;
        const sourceTypeRaw =
          typeof obj.source_type === "string"
            ? obj.source_type
            : typeof props.source_type === "string"
              ? props.source_type
              : "house_price";
        const sourceType =
          sourceTypeRaw === "scraped_project" ? "scraped_project" : "house_price";
        const listingKey =
          typeof obj.listing_key === "string"
            ? obj.listing_key
            : typeof props.listing_key === "string"
              ? props.listing_key
              : undefined;
        const coordLon = toFiniteNumber(coords?.[0]);
        const coordLat = toFiniteNumber(coords?.[1]);
        const totalPrice =
          toFiniteNumber(obj.total_price) ?? toFiniteNumber(props.total_price);
        const buildingArea =
          toFiniteNumber(obj.building_area) ?? toFiniteNumber(props.building_area);
        const floors =
          toFiniteNumber(obj.no_of_floor) ?? toFiniteNumber(props.no_of_floor);
        const buildingAge =
          toFiniteNumber(obj.building_age) ?? toFiniteNumber(props.building_age);

        // Guard against non-property map layers (POIs, transit, H3).
        const isPoiFeature = props.type !== undefined;
        const isTransitFeature = props.route_short_name !== undefined;
        const isH3Feature = typeof obj.h3_index === "string";
        if (isPoiFeature || isTransitFeature || isH3Feature) {
          setSelectedProperty(null);
          setPopupPosition(null);
          return;
        }

        // Prefer feature properties id; MVT object id can be an internal deck id.
        const rawId = props.id || obj.id;
        const hasValidId =
          typeof rawId === "string" || typeof rawId === "number";
        const hasPropertySignals =
          totalPrice !== undefined ||
          props.building_style_desc !== undefined ||
          props.amphur !== undefined ||
          props.tumbon !== undefined;
        if (!hasValidId && !hasPropertySignals) {
          setSelectedProperty(null);
          setPopupPosition(null);
          return;
        }

        const houseRef =
          sourceType === "house_price"
            ? resolveHouseReference(
                hasValidId ? rawId : undefined,
                coordLat,
                coordLon
              )
            : undefined;
        const propertyData: SelectedProperty = {
          listing_key: listingKey,
          source_type: sourceType,
          id: hasValidId ? rawId : undefined,
          house_ref: houseRef,
          locator: listingKey
            ? `listing:${listingKey}`
            : sourceType === "house_price" && hasValidId
              ? `house:${rawId}`
              : undefined,
          title:
            typeof obj.title === "string"
              ? obj.title
              : typeof props.title === "string"
                ? String(props.title)
                : undefined,
          total_price: totalPrice,
          building_area: buildingArea,
          amphur: obj.amphur || String(props.amphur || ""),
          tumbon: obj.tumbon || String(props.tumbon || ""),
          building_style_desc:
            obj.building_style_desc ||
            String(props.building_style_desc || ""),
          no_of_floor: floors,
          building_age: buildingAge,
          lat: obj.lat ?? coordLat,
          lon: obj.lon ?? coordLon,
          image_url:
            typeof obj.image_url === "string"
              ? obj.image_url
              : typeof props.image_url === "string"
                ? String(props.image_url)
                : undefined,
          detail_url:
            typeof obj.detail_url === "string"
              ? obj.detail_url
              : typeof props.detail_url === "string"
                ? String(props.detail_url)
                : undefined,
        };

        if (
          propertyData.total_price ||
          propertyData.id ||
          propertyData.house_ref ||
          propertyData.listing_key
        ) {
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
      listing_key?: string;
      source_type?: "house_price" | "scraped_project";
      house_ref?: string;
      locator?: string;
      title?: string;
      total_price?: number;
      building_style_desc?: string;
      amphur?: string;
      lat?: number;
      lon?: number;
      image_url?: string;
      detail_url?: string;
    }) => {
      const isHouse = property.source_type !== "scraped_project";
      const houseRef = isHouse
        ? property.house_ref ||
          resolveHouseReference(property.id, property.lat, property.lon)
        : undefined;
      const listingRef = property.listing_key || houseRef;
      if (!listingRef) {
        toast.error(
          "Unable to reference this property. Please pick another listing."
        );
        setSelectedProperty(null);
        setPopupPosition(null);
        return;
      }

      const price = property.total_price
        ? `฿${(property.total_price / 1_000_000).toFixed(1)}M`
        : "";
      const name = property.title || property.building_style_desc || "Property";
      const district = property.amphur || "";

      const attachment: Attachment = {
        id: `prop-${Date.now()}`,
        type: "property",
        data: sanitizePropertyData({
          ...property,
          house_ref: houseRef,
          locator:
            property.locator ||
            (property.listing_key
              ? `listing:${property.listing_key}`
              : property.id !== undefined
                ? `house:${property.id}`
                : undefined),
        } as Record<string, unknown>),
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
    listings,
    schools,
    transitLines,
    h3Data,

    // Handlers
    handleAISubmit,
    handleMapClick,
    handleAddPropertyToChat,
  };
}
