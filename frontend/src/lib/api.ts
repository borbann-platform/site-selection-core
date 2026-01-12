const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
export const API_URL = BASE_URL.endsWith("/api/v1")
  ? BASE_URL
  : `${BASE_URL}/api/v1`;

export interface Coordinates {
  latitude: number;
  longitude: number;
}

export interface SiteAnalysisRequest {
  latitude: number;
  longitude: number;
  radius_meters?: number;
  target_category: string;
}

export interface SiteAnalysisResponse {
  site_score: number;
  summary: {
    competitors_count: number;
    magnets_count: number;
    traffic_potential: string;
    total_population: number;
  };
  details: {
    nearby_competitors: string[];
    nearby_magnets: string[];
  };
  location_warning?: string | null;
}

export interface IsochroneRequest {
  latitude: number;
  longitude: number;
  minutes: number;
  mode: "walk" | "drive";
}

export interface IsochroneResponse {
  type: "FeatureCollection";
  features: any[];
}

export interface NearbyRequest {
  latitude: number;
  longitude: number;
  radius_meters: number;
  categories: string[];
}

export interface NearbyResponse {
  type: "FeatureCollection";
  features: any[];
}

export interface HexagonData {
  position: number[];
  value: number;
}

export interface GridResponse {
  hexagons: HexagonData[];
}

export interface SiteDetailsResponse {
  site_score: number;
  summary: {
    competitors_count: number;
    magnets_count: number;
    traffic_potential: string;
  };
  details: {
    nearby_competitors: string[];
    nearby_magnets: string[];
  };
  location_warning?: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  messages: ChatMessage[];
}

// Agent Streaming Event Types
export type AgentEventType =
  | "thinking"
  | "tool_call"
  | "tool_result"
  | "token"
  | "final"
  | "error";

export interface AgentThinkingEvent {
  type: "thinking";
  content: string;
}

export interface AgentToolCallEvent {
  type: "tool_call";
  content: {
    id: string;
    name: string;
    input: Record<string, unknown>;
  };
}

export interface AgentToolResultEvent {
  type: "tool_result";
  content: {
    id: string;
    name: string;
    result: string;
    success: boolean;
  };
}

export interface AgentTokenEvent {
  type: "token";
  content: string;
}

export interface AgentFinalEvent {
  type: "final";
  content: string;
}

export interface AgentErrorEvent {
  type: "error";
  content: string;
}

export type AgentEvent =
  | AgentThinkingEvent
  | AgentToolCallEvent
  | AgentToolResultEvent
  | AgentTokenEvent
  | AgentFinalEvent
  | AgentErrorEvent;

// Agent step for UI rendering
export type AgentStepStatus = "running" | "complete" | "error";

export interface AgentStep {
  id: string;
  type: "tool_call" | "thinking";
  name: string;
  status: AgentStepStatus;
  input?: Record<string, unknown>;
  output?: string;
  startTime: number;
  endTime?: number;
}

export interface HousePriceItem {
  id: number;
  updated_date: string | null;
  land_type_desc: string | null;
  building_style_desc: string | null;
  tumbon: string | null;
  amphur: string | null;
  village: string | null;
  building_age: number | null;
  land_area: number | null;
  building_area: number | null;
  no_of_floor: number | null;
  total_price: number | null;
  lat: number;
  lon: number;
}

export interface HousePriceListResponse {
  count: number;
  items: HousePriceItem[];
}

export interface HousePriceFilters {
  amphur?: string;
  tumbon?: string;
  building_style?: string;
  min_price?: number;
  max_price?: number;
  min_area?: number;
  max_area?: number;
  limit?: number;
  offset?: number;
}

export interface DistrictOption {
  amphur: string;
  count: number;
}

export interface BuildingStyleOption {
  building_style_desc: string;
  count: number;
}

export interface DistrictStats {
  amphur: string;
  count: number;
  avg_price: number;
  min_price: number;
  max_price: number;
  avg_price_per_sqm: number | null;
}

export interface BuildingStyleStats {
  building_style_desc: string;
  count: number;
  avg_price: number;
}

export interface HousePriceStatsResponse {
  total_count: number;
  by_district: DistrictStats[];
  by_building_style: BuildingStyleStats[];
}

// Location Intelligence Types
export interface TransitDetail {
  name: string;
  type: string;
  distance_m: number;
}

export interface TransitScore {
  score: number;
  nearest_rail: TransitDetail | null;
  bus_stops_500m: number;
  ferry_access: TransitDetail | null;
  description: string;
}

export interface SchoolDetail {
  name: string;
  level: string;
  distance_m: number;
}

export interface SchoolsScore {
  score: number;
  total_within_2km: number;
  by_level: Record<string, number>;
  nearest: SchoolDetail | null;
  description: string;
}

export interface WalkabilityCategory {
  category: string;
  count: number;
  examples: string[];
}

export interface WalkabilityScore {
  score: number;
  categories: WalkabilityCategory[];
  total_amenities: number;
  description: string;
}

export interface FloodRiskScore {
  level: "low" | "medium" | "high" | "unknown";
  risk_group: number | null;
  district_warnings: string[];
  description: string;
}

export interface NoiseScore {
  level: "quiet" | "moderate" | "busy" | "unknown";
  nearest_highway_m: number | null;
  nearest_major_road_m: number | null;
  description: string;
}

export interface LocationIntelligenceResponse {
  transit: TransitScore;
  schools: SchoolsScore;
  walkability: WalkabilityScore;
  flood_risk: FloodRiskScore;
  noise: NoiseScore;
  composite_score: number;
  location: { lat: number; lon: number };
}

export interface LocationIntelligenceRequest {
  latitude: number;
  longitude: number;
  radius_meters?: number;
}

// Price Explanation Types
export interface FeatureContribution {
  feature: string;
  feature_display: string;
  value: number;
  contribution: number;
  direction: "positive" | "negative";
}

export interface PriceExplanationResponse {
  property_id: number;
  predicted_price: number;
  base_price: number;
  actual_price: number | null;
  feature_contributions: FeatureContribution[];
  district_avg_price: number;
  price_vs_district: number;
}

// Transit Types
export interface TransitLineProperties {
  shape_id: string;
  route_id: string;
  route_short_name: string | null;
  route_long_name: string | null;
  route_type: number | null;
  route_color: string | null;
  agency_id: string | null;
}

export interface TransitLineFeature {
  type: "Feature";
  properties: TransitLineProperties;
  geometry: {
    type: "LineString";
    coordinates: [number, number][];
  };
}

export interface TransitLinesResponse {
  type: "FeatureCollection";
  features: TransitLineFeature[];
}

export const api = {
  analyzeSite: async (
    data: SiteAnalysisRequest
  ): Promise<SiteAnalysisResponse> => {
    const res = await fetch(`${API_URL}/site/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Failed to analyze site");
    return res.json();
  },

  getIsochrone: async (data: IsochroneRequest): Promise<IsochroneResponse> => {
    const res = await fetch(`${API_URL}/catchment/isochrone`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Failed to get isochrone");
    return res.json();
  },

  getNearby: async (data: NearbyRequest): Promise<NearbyResponse> => {
    const res = await fetch(`${API_URL}/site/nearby`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Failed to get nearby places");
    return res.json();
  },

  getGrid: async (): Promise<GridResponse> => {
    const res = await fetch(`${API_URL}/analytics/grid`);
    if (!res.ok) throw new Error("Failed to get grid data");
    return res.json();
  },

  getSiteDetails: async (siteId: string): Promise<SiteDetailsResponse> => {
    const res = await fetch(`${API_URL}/site/${siteId}`);
    if (!res.ok) throw new Error("Failed to get site details");
    return res.json();
  },

  getHousePrices: async (
    filters: HousePriceFilters = {}
  ): Promise<HousePriceListResponse> => {
    const params = new URLSearchParams();
    if (filters.amphur) params.set("amphur", filters.amphur);
    if (filters.tumbon) params.set("tumbon", filters.tumbon);
    if (filters.building_style)
      params.set("building_style", filters.building_style);
    if (filters.min_price !== undefined)
      params.set("min_price", String(filters.min_price));
    if (filters.max_price !== undefined)
      params.set("max_price", String(filters.max_price));
    if (filters.min_area !== undefined)
      params.set("min_area", String(filters.min_area));
    if (filters.max_area !== undefined)
      params.set("max_area", String(filters.max_area));
    if (filters.limit !== undefined) params.set("limit", String(filters.limit));
    if (filters.offset !== undefined)
      params.set("offset", String(filters.offset));

    const url = `${API_URL}/house-prices${params.toString() ? `?${params}` : ""}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to get house prices");
    return res.json();
  },

  getDistricts: async (): Promise<DistrictOption[]> => {
    const res = await fetch(`${API_URL}/house-prices/districts`);
    if (!res.ok) throw new Error("Failed to get districts");
    return res.json();
  },

  getBuildingStyles: async (): Promise<BuildingStyleOption[]> => {
    const res = await fetch(`${API_URL}/house-prices/building-styles`);
    if (!res.ok) throw new Error("Failed to get building styles");
    return res.json();
  },

  getHousePriceStats: async (): Promise<HousePriceStatsResponse> => {
    const res = await fetch(`${API_URL}/house-prices/stats`);
    if (!res.ok) throw new Error("Failed to get house price stats");
    return res.json();
  },

  getPropertyById: async (id: number): Promise<HousePriceItem> => {
    const res = await fetch(`${API_URL}/house-prices/${id}`);
    if (!res.ok) throw new Error("Failed to get property");
    return res.json();
  },

  getNearbyProperties: async (params: {
    lat: number;
    lon: number;
    radius_m?: number;
    building_style?: string;
    limit?: number;
  }): Promise<{
    center: { lat: number; lon: number };
    radius_m: number;
    count: number;
    items: (HousePriceItem & { distance_m: number })[];
  }> => {
    const searchParams = new URLSearchParams();
    searchParams.set("lat", String(params.lat));
    searchParams.set("lon", String(params.lon));
    if (params.radius_m) searchParams.set("radius_m", String(params.radius_m));
    if (params.building_style)
      searchParams.set("building_style", params.building_style);
    if (params.limit) searchParams.set("limit", String(params.limit));

    const res = await fetch(`${API_URL}/house-prices/nearby?${searchParams}`);
    if (!res.ok) throw new Error("Failed to get nearby properties");
    return res.json();
  },

  /**
   * Stream chat response from the AI agent.
   * Returns an async generator that yields text chunks.
   */
  streamChat: async function* (
    messages: ChatMessage[]
  ): AsyncGenerator<string, void, unknown> {
    const res = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    });

    if (!res.ok) throw new Error("Failed to start chat stream");
    if (!res.body) throw new Error("No response body");

    const reader = res.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split("\n");

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (data === "[DONE]") return;
          yield data;
        }
      }
    }
  },

  getLocationIntelligence: async (
    params: LocationIntelligenceRequest
  ): Promise<LocationIntelligenceResponse> => {
    const res = await fetch(`${API_URL}/location-intelligence/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    if (!res.ok) throw new Error("Failed to get location intelligence");
    return res.json();
  },

  getPriceExplanation: async (
    propertyId: number
  ): Promise<PriceExplanationResponse> => {
    const res = await fetch(`${API_URL}/house-prices/${propertyId}/explain`);
    if (!res.ok) {
      if (res.status === 503) {
        throw new Error("Model not trained yet");
      }
      throw new Error("Failed to get price explanation");
    }
    return res.json();
  },

  /**
   * Get transit lines as GeoJSON FeatureCollection.
   * @param routeType - Filter by type: 0=BTS, 1=MRT, 2=Rail, 3=Bus
   */
  getTransitLines: async (
    routeType?: number
  ): Promise<TransitLinesResponse> => {
    const params = new URLSearchParams();
    if (routeType !== undefined) params.set("route_type", String(routeType));
    const url = `${API_URL}/transit/lines${params.toString() ? `?${params}` : ""}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to get transit lines");
    return res.json();
  },
};
