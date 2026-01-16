const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
export const API_URL = BASE_URL.endsWith("/api/v1")
  ? BASE_URL
  : `${BASE_URL}/api/v1`;

// Auth Types
export interface UserRegisterRequest {
  email: string;
  password: string;
  confirm_password: string;
  first_name: string;
  last_name: string;
}

export interface UserLoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  created_at: string | null;
}

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

// H3 Hexagon Overlay Types
export interface H3HexagonItem {
  h3_index: string;
  value: number;
  label?: string;
}

export interface H3HexagonResponse {
  metric: string;
  resolution: number;
  count: number;
  min_value: number;
  max_value: number;
  hexagons: H3HexagonItem[];
}

export interface H3HexagonParams {
  metric?: string;
  resolution?: number;
  min_lat?: number;
  max_lat?: number;
  min_lon?: number;
  max_lon?: number;
  limit?: number;
}

// Admin API Types
export interface AdminRefreshResponse {
  success: boolean;
  message: string;
  timestamp: string;
  details?: {
    view_name?: string;
    tiles_cleared?: number;
  };
}

export interface AdminCacheStatusResponse {
  tile_cache_size: number;
  timestamp: string;
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
export type AgentStepStatus =
  | "pending"
  | "running"
  | "complete"
  | "error"
  | "waiting";
export type AgentStepType = "tool_call" | "thinking" | "waiting_user";

export interface AgentStepWaitingFor {
  type: "location" | "bbox" | "property" | "confirmation" | "text";
  prompt: string;
}

export interface AgentStep {
  id: string;
  type: AgentStepType;
  name: string;
  description?: string;
  status: AgentStepStatus;
  input?: Record<string, unknown>;
  output?: string;
  startTime: number;
  endTime?: number;
  // For waiting_user steps - defines what input is expected
  waitingFor?: AgentStepWaitingFor;
}

// Agent stream event from /chat/agent endpoint
export interface AgentStreamEvent {
  event: "thinking" | "step" | "token" | "done";
  data: {
    thinking?: boolean;
    id?: string;
    type?: string;
    name?: string;
    status?: string;
    input?: Record<string, unknown>;
    output?: string;
    start_time?: number;
    end_time?: number;
    token?: string;
  } | null;
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

// Property Upload & Valuation Types
export interface PropertyUploadRequest {
  building_style: string;
  building_area: number;
  land_area?: number;
  no_of_floor: number;
  building_age: number;
  amphur: string;
  tumbon?: string;
  village?: string;
  latitude: number;
  longitude: number;
  asking_price?: number;
}

export interface ValuationFactor {
  name: string;
  display_name: string;
  impact: number;
  direction: "positive" | "negative" | "neutral";
  description: string;
}

export interface ValuationComparable {
  id: number;
  price: number;
  building_style_desc: string;
  building_area: number;
  distance_m: number;
  similarity_score: number;
}

export interface ValuationResponse {
  estimated_price: number;
  price_range: { min: number; max: number };
  confidence: "high" | "medium" | "low";
  price_per_sqm: number;
  factors: ValuationFactor[];
  comparable_properties: ValuationComparable[];
  market_insights: {
    district_avg_price: number;
    district_price_trend: number;
    days_on_market_avg: number;
  };
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
  // ============= Auth APIs =============

  register: async (data: UserRegisterRequest): Promise<UserResponse> => {
    const res = await fetch(`${API_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Registration failed" }));
      throw new Error(error.detail || "Registration failed");
    }
    return res.json();
  },

  login: async (data: UserLoginRequest): Promise<TokenResponse> => {
    const formData = new URLSearchParams();
    formData.append("username", data.email);
    formData.append("password", data.password);

    const res = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData,
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Login failed" }));
      throw new Error(error.detail || "Login failed");
    }
    return res.json();
  },

  refreshToken: async (refreshToken: string): Promise<TokenResponse> => {
    const res = await fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) {
      throw new Error("Token refresh failed");
    }
    return res.json();
  },

  getCurrentUser: async (accessToken: string): Promise<UserResponse> => {
    const res = await fetch(`${API_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) {
      throw new Error("Failed to get current user");
    }
    return res.json();
  },

  // ============= Site APIs =============

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

  /**
   * Stream agent chat response with structured tool steps.
   * Returns an async generator that yields AgentStreamEvent objects.
   */
  streamAgentChat: async function* (
    messages: ChatMessage[]
  ): AsyncGenerator<AgentStreamEvent, void, unknown> {
    const res = await fetch(`${API_URL}/chat/agent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    });

    if (!res.ok) throw new Error("Failed to start agent stream");
    if (!res.body) throw new Error("No response body");

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || ""; // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const jsonStr = line.slice(6);
          try {
            const event = JSON.parse(jsonStr) as AgentStreamEvent;
            yield event;
            if (event.event === "done") return;
          } catch {
            // Skip malformed JSON
          }
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

  /**
   * Get H3 hexagon data for overlay visualization.
   */
  getH3Hexagons: async (
    params: H3HexagonParams = {}
  ): Promise<H3HexagonResponse> => {
    const searchParams = new URLSearchParams();
    if (params.metric) searchParams.set("metric", params.metric);
    if (params.resolution)
      searchParams.set("resolution", String(params.resolution));
    if (params.min_lat !== undefined)
      searchParams.set("min_lat", String(params.min_lat));
    if (params.max_lat !== undefined)
      searchParams.set("max_lat", String(params.max_lat));
    if (params.min_lon !== undefined)
      searchParams.set("min_lon", String(params.min_lon));
    if (params.max_lon !== undefined)
      searchParams.set("max_lon", String(params.max_lon));
    if (params.limit !== undefined)
      searchParams.set("limit", String(params.limit));
    const url = `${API_URL}/analytics/h3-hexagons${searchParams.toString() ? `?${searchParams}` : ""}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to get H3 hexagons");
    return res.json();
  },

  // ============= Admin APIs =============

  /**
   * Refresh the POI materialized view.
   * Call this after POI data is updated.
   */
  refreshPOIs: async (): Promise<AdminRefreshResponse> => {
    const res = await fetch(`${API_URL}/admin/refresh-pois`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Failed to refresh POI data");
    return res.json();
  },

  /**
   * Clear the server-side tile cache.
   */
  clearTileCache: async (): Promise<AdminRefreshResponse> => {
    const res = await fetch(`${API_URL}/admin/clear-tile-cache`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Failed to clear tile cache");
    return res.json();
  },

  /**
   * Get current cache status.
   */
  getCacheStatus: async (): Promise<AdminCacheStatusResponse> => {
    const res = await fetch(`${API_URL}/admin/cache-status`);
    if (!res.ok) throw new Error("Failed to get cache status");
    return res.json();
  },

  // ============= Property Valuation (Mock) =============

  /**
   * Get property valuation based on input data.
   * This is a mock implementation that simulates the valuation model.
   * In production, this would call the actual ML model endpoint.
   */
  getPropertyValuation: async (
    data: PropertyUploadRequest
  ): Promise<ValuationResponse> => {
    // Simulate API delay
    await new Promise((resolve) => setTimeout(resolve, 1500));

    // District price multipliers (mock data)
    const districtMultipliers: Record<string, number> = {
      วัฒนา: 1.8,
      ปทุมวัน: 1.7,
      คลองเตย: 1.3,
      พระโขนง: 1.2,
      สวนหลวง: 1.1,
      บางกะปิ: 0.95,
      ลาดพร้าว: 1.05,
      จตุจักร: 1.15,
      บางนา: 1.0,
      ห้วยขวาง: 1.1,
    };

    // Building style base prices per sqm
    const styleBasePrices: Record<string, number> = {
      บ้านเดี่ยว: 45000,
      ทาวน์เฮ้าส์: 35000,
      บ้านแฝด: 38000,
      อาคารพาณิชย์: 42000,
      ตึกแถว: 32000,
    };

    const basePrice = styleBasePrices[data.building_style] || 40000;
    const districtMultiplier = districtMultipliers[data.amphur] || 1.0;

    // Calculate base estimated price
    let estimatedPrice = basePrice * data.building_area * districtMultiplier;

    // Apply modifiers
    const factors: ValuationFactor[] = [];

    // Land area bonus
    if (data.land_area && data.land_area > 0) {
      const landBonus = data.land_area * 8000 * districtMultiplier;
      estimatedPrice += landBonus;
      factors.push({
        name: "land_area",
        display_name: "Land Area",
        impact: landBonus,
        direction: "positive",
        description: `${data.land_area} sqm of land adds significant value`,
      });
    }

    // Building age depreciation
    if (data.building_age > 0) {
      const depreciation = Math.min(data.building_age * 0.015, 0.3); // Max 30% depreciation
      const depreciationAmount = estimatedPrice * depreciation;
      estimatedPrice -= depreciationAmount;
      factors.push({
        name: "building_age",
        display_name: "Building Age",
        impact: -depreciationAmount,
        direction: "negative",
        description: `${data.building_age} years old (${(depreciation * 100).toFixed(0)}% depreciation)`,
      });
    }

    // Floor bonus
    if (data.no_of_floor > 1) {
      const floorBonus = (data.no_of_floor - 1) * 200000;
      estimatedPrice += floorBonus;
      factors.push({
        name: "floors",
        display_name: "Number of Floors",
        impact: floorBonus,
        direction: "positive",
        description: `${data.no_of_floor} floors provides more living space`,
      });
    }

    // Location quality factor (based on coordinates - simplified)
    const locationScore = 70 + Math.random() * 25;
    const locationImpact = estimatedPrice * ((locationScore - 70) / 100);
    estimatedPrice += locationImpact;
    factors.push({
      name: "location",
      display_name: "Location Quality",
      impact: locationImpact,
      direction: locationImpact >= 0 ? "positive" : "negative",
      description: `Location score: ${locationScore.toFixed(0)}/100`,
    });

    // District premium
    if (districtMultiplier > 1.0) {
      const premiumAmount = estimatedPrice * (districtMultiplier - 1) * 0.3;
      factors.push({
        name: "district",
        display_name: "District Premium",
        impact: premiumAmount,
        direction: "positive",
        description: `${data.amphur} commands a ${((districtMultiplier - 1) * 100).toFixed(0)}% premium`,
      });
    }

    // Round to nearest 100,000
    estimatedPrice = Math.round(estimatedPrice / 100000) * 100000;

    // Calculate confidence based on data completeness
    const dataPoints = [
      data.building_area > 0,
      data.land_area && data.land_area > 0,
      data.building_age >= 0,
      data.no_of_floor > 0,
      data.amphur,
      data.tumbon,
    ].filter(Boolean).length;

    const confidence: "high" | "medium" | "low" =
      dataPoints >= 5 ? "high" : dataPoints >= 3 ? "medium" : "low";

    // Price range based on confidence
    const rangePercent = confidence === "high" ? 0.08 : confidence === "medium" ? 0.12 : 0.18;

    // Mock comparable properties
    const comparables: ValuationComparable[] = [
      {
        id: 1001,
        price: Math.round(estimatedPrice * (0.9 + Math.random() * 0.2)),
        building_style_desc: data.building_style,
        building_area: data.building_area + Math.round(Math.random() * 40 - 20),
        distance_m: 200 + Math.round(Math.random() * 600),
        similarity_score: 85 + Math.round(Math.random() * 10),
      },
      {
        id: 1002,
        price: Math.round(estimatedPrice * (0.85 + Math.random() * 0.3)),
        building_style_desc: data.building_style,
        building_area: data.building_area + Math.round(Math.random() * 60 - 30),
        distance_m: 400 + Math.round(Math.random() * 800),
        similarity_score: 75 + Math.round(Math.random() * 15),
      },
      {
        id: 1003,
        price: Math.round(estimatedPrice * (0.8 + Math.random() * 0.4)),
        building_style_desc: data.building_style,
        building_area: data.building_area + Math.round(Math.random() * 80 - 40),
        distance_m: 600 + Math.round(Math.random() * 1000),
        similarity_score: 65 + Math.round(Math.random() * 20),
      },
    ];

    return {
      estimated_price: estimatedPrice,
      price_range: {
        min: Math.round(estimatedPrice * (1 - rangePercent)),
        max: Math.round(estimatedPrice * (1 + rangePercent)),
      },
      confidence,
      price_per_sqm: Math.round(estimatedPrice / data.building_area),
      factors: factors.sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact)),
      comparable_properties: comparables,
      market_insights: {
        district_avg_price: Math.round(basePrice * districtMultiplier * 150),
        district_price_trend: 4 + Math.random() * 6,
        days_on_market_avg: 30 + Math.round(Math.random() * 40),
      },
    };
  },
};
