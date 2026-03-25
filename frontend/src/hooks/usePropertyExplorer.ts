import { useState, useCallback, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { MapViewState, PickingInfo } from "@deck.gl/core";
import { api } from "@/lib/api";
import { toast } from "sonner";
import type {
  Attachment,
  SelectionMode,
} from "@/components/ai";
import type { PropertyFiltersState } from "@/components/PropertyFilters";
import {
  buildBBoxAttachment,
  buildClickGrounding,
  buildLocationAttachment,
  buildViewportMetrics,
  resolveHouseReference,
} from "@/lib/uiGrounding";
import type { MapTileStyle } from "@/components/MapContainer";
import { useExplorerChatStore } from "@/stores/explorerChatStore";

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
  source_type?:
    | "house_price"
    | "scraped_project"
    | "market_listing"
    | "condo_project";
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
  source_type?:
    | "house_price"
    | "scraped_project"
    | "market_listing"
    | "condo_project";
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
const FILTER_DEBOUNCE_MS = 250;
const RECENT_MAP_SELECTIONS_STORAGE_KEY = "borban.recent-map-selections";
const MAP_VIEW_STATE_STORAGE_KEY = "borban.map-view-state";
const MAP_TILE_STYLE_STORAGE_KEY = "borban.map-tile-style";
const MAX_RECENT_MAP_SELECTIONS = 6;
const VIEW_STATE_SAVE_DEBOUNCE_MS = 1000;

function isAttachmentRecord(value: unknown): value is Attachment {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.id === "string" &&
    (candidate.type === "location" || candidate.type === "bbox") &&
    typeof candidate.label === "string" &&
    typeof candidate.data === "object" &&
    candidate.data !== null
  );
}

function getAttachmentHistoryKey(attachment: Attachment): string {
  if (attachment.type === "location") {
    const lat = typeof attachment.data.lat === "number" ? attachment.data.lat.toFixed(6) : "";
    const lon = typeof attachment.data.lon === "number" ? attachment.data.lon.toFixed(6) : "";
    return `location:${lat}:${lon}`;
  }

  if (attachment.type === "bbox") {
    const minLat = typeof attachment.data.minLat === "number" ? attachment.data.minLat.toFixed(6) : "";
    const minLon = typeof attachment.data.minLon === "number" ? attachment.data.minLon.toFixed(6) : "";
    const maxLat = typeof attachment.data.maxLat === "number" ? attachment.data.maxLat.toFixed(6) : "";
    const maxLon = typeof attachment.data.maxLon === "number" ? attachment.data.maxLon.toFixed(6) : "";
    return `bbox:${minLat}:${minLon}:${maxLat}:${maxLon}`;
  }

  return `${attachment.type}:${attachment.label}`;
}

function cloneAttachmentForReuse(attachment: Attachment): Attachment {
  return {
    ...attachment,
    id: `${attachment.type}-${Date.now()}`,
    data: { ...attachment.data },
  };
}

function toFiniteNumber(value: unknown): number | undefined {
  const num = Number(value);
  return Number.isFinite(num) ? num : undefined;
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setDebouncedValue(value);
    }, delayMs);

    return () => window.clearTimeout(timeoutId);
  }, [value, delayMs]);

  return debouncedValue;
}

// ---- Hook ----

export function usePropertyExplorer(districtFromUrl?: string) {
  // -- View State (restored from localStorage if available) --
  const [viewState, setViewState] = useState<ViewState>(() => {
    try {
      const stored = window.localStorage.getItem(MAP_VIEW_STATE_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (
          typeof parsed.longitude === "number" &&
          typeof parsed.latitude === "number" &&
          typeof parsed.zoom === "number" &&
          Number.isFinite(parsed.longitude) &&
          Number.isFinite(parsed.latitude) &&
          Number.isFinite(parsed.zoom)
        ) {
          return {
            longitude: parsed.longitude,
            latitude: parsed.latitude,
            zoom: parsed.zoom,
            pitch: typeof parsed.pitch === "number" && Number.isFinite(parsed.pitch) ? parsed.pitch : 0,
            bearing: typeof parsed.bearing === "number" && Number.isFinite(parsed.bearing) ? parsed.bearing : 0,
          };
        }
      }
    } catch {
      // Ignore parse errors
    }
    return {
      longitude: BANGKOK_LON,
      latitude: BANGKOK_LAT,
      zoom: 12,
      pitch: 0,
      bearing: 0,
    };
  });

  // Persist camera view state to localStorage (debounced)
  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      try {
        window.localStorage.setItem(
          MAP_VIEW_STATE_STORAGE_KEY,
          JSON.stringify({
            longitude: viewState.longitude,
            latitude: viewState.latitude,
            zoom: viewState.zoom,
            pitch: viewState.pitch,
            bearing: viewState.bearing,
          })
        );
      } catch {
        // Ignore storage errors
      }
    }, VIEW_STATE_SAVE_DEBOUNCE_MS);
    return () => window.clearTimeout(timeoutId);
  }, [viewState]);

  // -- Map Tile Style --
  const [tileStyle, setTileStyle] = useState<MapTileStyle>(() => {
    try {
      const stored = window.localStorage.getItem(MAP_TILE_STYLE_STORAGE_KEY);
      if (stored === "dark" || stored === "light" || stored === "streets" || stored === "satellite") {
        return stored;
      }
    } catch {
      // Ignore
    }
    return "auto";
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(MAP_TILE_STYLE_STORAGE_KEY, tileStyle);
    } catch {
      // Ignore storage errors
    }
  }, [tileStyle]);

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
  const [recentMapSelections, setRecentMapSelections] = useState<Attachment[]>([]);

  // -- AI state (global store — survives navigation) --
  const aiMessages = useExplorerChatStore((s) => s.messages);
  const isAIRunning = useExplorerChatStore((s) => s.isRunning);
  const explorerSendMessage = useExplorerChatStore((s) => s.sendMessage);
  const explorerStopStreaming = useExplorerChatStore((s) => s.stopStreaming);

  // -- AI local UI state --
  const [isAIExpanded, setIsAIExpanded] = useState(false);
  const [aiInput, setAiInput] = useState("");

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

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(RECENT_MAP_SELECTIONS_STORAGE_KEY);
      if (!stored) {
        return;
      }

      const parsed = JSON.parse(stored);
      if (!Array.isArray(parsed)) {
        return;
      }

      setRecentMapSelections(parsed.filter(isAttachmentRecord).slice(0, MAX_RECENT_MAP_SELECTIONS));
    } catch {
      return;
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        RECENT_MAP_SELECTIONS_STORAGE_KEY,
        JSON.stringify(recentMapSelections)
      );
    } catch {
      return;
    }
  }, [recentMapSelections]);

  // ---- Data fetching ----

  const debouncedFilters = useDebouncedValue(propertyFilters, FILTER_DEBOUNCE_MS);
  const zoomTier = viewState.zoom < 13 ? "low" : "high";
  const listingLimit = zoomTier === "low" ? 1000 : 250;
  const listingsQueryKey = useMemo(
    () => [
      "listings",
      debouncedFilters.district ?? "all",
      debouncedFilters.buildingStyle ?? "all",
      debouncedFilters.minPrice,
      debouncedFilters.maxPrice,
      debouncedFilters.minArea,
      debouncedFilters.maxArea,
      listingLimit,
    ],
    [debouncedFilters, listingLimit]
  );

  const { data: listings } = useQuery({
    queryKey: listingsQueryKey,
    queryFn: () =>
      api.getListings({
        amphur: debouncedFilters.district || undefined,
        building_style: debouncedFilters.buildingStyle || undefined,
        min_price: debouncedFilters.minPrice,
        max_price: debouncedFilters.maxPrice,
        min_area: debouncedFilters.minArea,
        max_area: debouncedFilters.maxArea,
        limit: listingLimit,
      }),
    staleTime: 1000 * 30,
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
    staleTime: 1000 * 60 * 30,
    gcTime: 1000 * 60 * 60,
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
    staleTime: 1000 * 60 * 30,
    gcTime: 1000 * 60 * 60,
  });

  // Derive the H3 resolution from the current zoom level so that the query
  // key only changes when we actually need a different resolution (not on
  // every fractional zoom change).
  const h3Resolution = viewState.zoom < 12 ? 7 : viewState.zoom < 14 ? 9 : 11;

  const { data: h3Data, isFetching: isH3Fetching } = useQuery({
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

    setIsAIExpanded(true);

    const attachmentsToSend =
      chatAttachments.length > 0 ? [...chatAttachments] : undefined;

    const inputToSend = aiInput;
    setAiInput("");
    setChatAttachments([]);
    setBboxCorners([]);

    await explorerSendMessage(inputToSend, attachmentsToSend);
  }, [aiInput, isAIRunning, chatAttachments, explorerSendMessage]);

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

  const rememberRecentMapSelection = useCallback((attachment: Attachment) => {
    if (attachment.type !== "location" && attachment.type !== "bbox") {
      return;
    }

    const nextKey = getAttachmentHistoryKey(attachment);
    setRecentMapSelections((prev) => {
      const filtered = prev.filter(
        (item) => getAttachmentHistoryKey(item) !== nextKey
      );
      return [attachment, ...filtered].slice(0, MAX_RECENT_MAP_SELECTIONS);
    });
  }, []);

  const handleReuseRecentSelection = useCallback((attachmentId: string) => {
    setRecentMapSelections((prev) => {
      const target = prev.find((item) => item.id === attachmentId);
      if (!target) {
        return prev;
      }

      setChatAttachments((current) => [...current, cloneAttachmentForReuse(target)]);

      const targetKey = getAttachmentHistoryKey(target);
      const reordered = prev.filter(
        (item) => getAttachmentHistoryKey(item) !== targetKey
      );
      return [target, ...reordered].slice(0, MAX_RECENT_MAP_SELECTIONS);
    });
  }, []);

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
        rememberRecentMapSelection(newAttachment);
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
          rememberRecentMapSelection(newAttachment);
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
          sourceTypeRaw === "scraped_project" ||
          sourceTypeRaw === "market_listing" ||
          sourceTypeRaw === "condo_project"
            ? sourceTypeRaw
            : "house_price";
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
    [selectionMode, bboxCorners, selectedProperty, rememberRecentMapSelection]
  );

  const handleAddPropertyToChat = useCallback(
    (property: {
      id?: string | number;
      listing_key?: string;
      source_type?:
        | "house_price"
        | "scraped_project"
        | "market_listing"
        | "condo_project";
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
      const isHouse = property.source_type === "house_price";
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
    recentMapSelections,
    isAIExpanded,
    setIsAIExpanded,
    aiInput,
    setAiInput,
    aiMessages,
    isAIRunning,
    stopStreaming: explorerStopStreaming,

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
    isH3Fetching,

    // Map tile style
    tileStyle,
    setTileStyle,

    // Handlers
    handleAISubmit,
    handleMapClick,
    handleAddPropertyToChat,
    handleReuseRecentSelection,
  };
}
