import type { FeatureCollection, GeoJsonProperties, Geometry } from "geojson";
import type { AgentRuntimeConfig } from "./agentRuntimeConfig";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
export const API_URL = BASE_URL.endsWith("/api/v1")
	? BASE_URL
	: `${BASE_URL}/api/v1`;

// ============= Auth Token Utilities =============

const AUTH_TOKENS_KEY = "auth_tokens";

/**
 * Get the current access token from localStorage.
 * Reads from the "auth_tokens" JSON object stored by AuthContext.
 */
export function getAccessToken(): string | null {
	const stored = localStorage.getItem(AUTH_TOKENS_KEY);
	if (!stored) return null;
	try {
		const tokens = JSON.parse(stored);
		return tokens.access_token || null;
	} catch {
		return null;
	}
}

/**
 * Get the current refresh token from localStorage.
 */
export function getRefreshToken(): string | null {
	const stored = localStorage.getItem(AUTH_TOKENS_KEY);
	if (!stored) return null;
	try {
		const tokens = JSON.parse(stored);
		return tokens.refresh_token || null;
	} catch {
		return null;
	}
}

/**
 * Clear auth tokens and redirect to login page.
 */
export function clearAuthAndRedirect(): void {
	localStorage.removeItem(AUTH_TOKENS_KEY);
	// Only redirect if we're in a browser context and not already on login page
	if (
		typeof window !== "undefined" &&
		!window.location.pathname.includes("/login")
	) {
		window.location.href = "/login";
	}
}

/**
 * Authenticated fetch wrapper that:
 * 1. Automatically attaches Authorization header with Bearer token
 * 2. Handles 401 responses by attempting token refresh
 * 3. Clears tokens and redirects to login if refresh fails
 */
export async function authenticatedFetch(
	url: string,
	options: RequestInit = {},
): Promise<Response> {
	const token = getAccessToken();
	const headers = new Headers(options.headers);

	if (token) {
		headers.set("Authorization", `Bearer ${token}`);
	}

	// Make the initial request
	let response = await fetch(url, { ...options, headers });

	// If we get a 401, try to refresh the token
	if (response.status === 401 && token) {
		const refreshToken = getRefreshToken();
		if (refreshToken) {
			try {
				// Attempt to refresh the token
				const refreshResponse = await fetch(`${API_URL}/auth/refresh`, {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ refresh_token: refreshToken }),
				});

				if (refreshResponse.ok) {
					// Store new tokens
					const newTokens = await refreshResponse.json();
					localStorage.setItem(AUTH_TOKENS_KEY, JSON.stringify(newTokens));

					// Retry the original request with new token
					headers.set("Authorization", `Bearer ${newTokens.access_token}`);
					response = await fetch(url, { ...options, headers });
				} else {
					// Refresh failed - clear tokens and redirect
					clearAuthAndRedirect();
				}
			} catch {
				// Refresh request failed - clear tokens and redirect
				clearAuthAndRedirect();
			}
		} else {
			// No refresh token - clear tokens and redirect
			clearAuthAndRedirect();
		}
	}

	return response;
}

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

export type GeoJsonFeatureCollection = FeatureCollection<
	Geometry,
	GeoJsonProperties
>;

export type IsochroneResponse = GeoJsonFeatureCollection;

export interface NearbyRequest {
	latitude: number;
	longitude: number;
	radius_meters: number;
	categories: string[];
}

export type NearbyResponse = GeoJsonFeatureCollection;

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

// Attachment types for spatial context
export type AttachmentType = "location" | "bbox" | "property";

export interface Attachment {
	id: string;
	type: AttachmentType;
	data: Record<string, unknown>;
	label: string;
}

export interface ChatRequest {
	messages: ChatMessage[];
	session_id?: string;
	attachments?: Attachment[];
	runtime?: AgentRuntimeConfig;
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
	event: "thinking" | "step" | "token" | "error" | "done";
	data: AgentStreamEventData | null;
}

export interface AgentRuntimeError {
	title: string;
	message: string;
	statusCode?: number;
	providerCode?: string;
	rawMessage?: string;
	retryable?: boolean;
}

export interface AgentStreamEventData {
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
	title?: string;
	message?: string;
	status_code?: number;
	provider_code?: string;
	raw_message?: string;
	retryable?: boolean;
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

export interface ListingItem {
  listing_key: string;
  source_type:
    | "house_price"
    | "scraped_project"
    | "market_listing"
    | "condo_project";
  source: string;
  source_id: string;
  title: string | null;
  building_style_desc: string | null;
  amphur: string | null;
  tumbon: string | null;
  total_price: number | null;
  building_area: number | null;
  no_of_floor: number | null;
  building_age: number | null;
  lat: number;
  lon: number;
  image_url: string | null;
  image_status: string | null;
  has_image: boolean;
  detail_url: string | null;
}

export interface ListingListResponse {
  count: number;
  items: ListingItem[];
}

export interface ListingFilters {
  amphur?: string;
  building_style?: string;
  min_price?: number;
  max_price?: number;
  min_area?: number;
  max_area?: number;
  limit?: number;
  offset?: number;
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

export interface ResolveLocationResponse {
	amphur: string;
	tumbon: string | null;
	village: string | null;
	distance_m: number;
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
	direction: "positive" | "negative";
	contribution: number;
	contribution_kind: string;
	contribution_display?: string | null;
}

export interface PriceExplanationResponse {
	property_id: number;
	predicted_price: number;
	actual_price: number | null;
	feature_contributions: FeatureContribution[];
	explanation_title: string;
	explanation_summary: string;
	explanation_disclaimer: string;
	explanation_method: string;
	explanation_narrative?: string | null;
	district_avg_price: number | null;
	price_vs_district: number | null;
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
			const error = await res
				.json()
				.catch(() => ({ detail: "Registration failed" }));
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
		data: SiteAnalysisRequest,
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
		filters: HousePriceFilters = {},
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

	getListings: async (
		filters: ListingFilters = {},
	): Promise<ListingListResponse> => {
		const params = new URLSearchParams();
		if (filters.amphur) params.set("amphur", filters.amphur);
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

		const url = `${API_URL}/listings${params.toString() ? `?${params}` : ""}`;
		const res = await fetch(url);
		if (!res.ok) throw new Error("Failed to get listings");
		return res.json();
	},

	getListingByKey: async (listingKey: string): Promise<ListingItem> => {
		const res = await fetch(`${API_URL}/listings/${encodeURIComponent(listingKey)}`);
		if (!res.ok) throw new Error("Failed to get listing");
		return res.json();
	},

	getDistricts: async (): Promise<DistrictOption[]> => {
		const res = await fetch(`${API_URL}/listings/districts`);
		if (!res.ok) throw new Error("Failed to get listing districts");
		return res.json();
	},

	getBuildingStyles: async (): Promise<BuildingStyleOption[]> => {
		const res = await fetch(`${API_URL}/listings/building-styles`);
		if (!res.ok) throw new Error("Failed to get listing building styles");
		return res.json();
	},

	getHousePriceDistricts: async (): Promise<DistrictOption[]> => {
		const res = await fetch(`${API_URL}/house-prices/districts`);
		if (!res.ok) throw new Error("Failed to get districts");
		return res.json();
	},

	getHousePriceBuildingStyles: async (): Promise<BuildingStyleOption[]> => {
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

	resolveLocation: async (params: {
		lat: number;
		lon: number;
	}): Promise<ResolveLocationResponse> => {
		const searchParams = new URLSearchParams();
		searchParams.set("lat", String(params.lat));
		searchParams.set("lon", String(params.lon));

		const res = await fetch(
			`${API_URL}/house-prices/resolve-location?${searchParams}`,
		);
		if (!res.ok) throw new Error("Failed to resolve location");
		return res.json();
	},

	/**
	 * Stream chat response from the AI agent.
	 * Returns an async generator that yields text chunks.
	 */
	streamChat: async function* (
		messages: ChatMessage[],
	): AsyncGenerator<string, void, unknown> {
		const token = getAccessToken();
		const headers: HeadersInit = { "Content-Type": "application/json" };
		if (token) {
			headers.Authorization = `Bearer ${token}`;
		}

		const res = await fetch(`${API_URL}/chat`, {
			method: "POST",
			headers,
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
	 *
	 * @param messages - Chat message history
	 * @param attachments - Optional spatial attachments (bbox, location, property)
	 */
	streamAgentChat: async function* (
		messages: ChatMessage[],
		attachments?: Attachment[],
	): AsyncGenerator<AgentStreamEvent, void, unknown> {
		const token = getAccessToken();
		const headers: HeadersInit = { "Content-Type": "application/json" };
		if (token) {
			headers.Authorization = `Bearer ${token}`;
		}

		const res = await fetch(`${API_URL}/chat/agent`, {
			method: "POST",
			headers,
			body: JSON.stringify({ messages, attachments }),
		});

		if (!res.ok) {
			const error = await res
				.json()
				.catch(() => ({ detail: "Failed to start agent stream" }));
			throw new Error(error.detail || `HTTP ${res.status}`);
		}
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
		params: LocationIntelligenceRequest,
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
		propertyId: number,
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
		routeType?: number,
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
		params: H3HexagonParams = {},
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

	// ============= Property Valuation =============

	/**
	 * Get AI-powered property valuation.
	 * Uses real ML models (LightGBM baseline or HGT Graph Neural Network)
	 * to predict property values based on location and property features.
	 */
	getPropertyValuation: async (
		data: PropertyUploadRequest,
		options?: { saveProperty?: boolean; userId?: string },
	): Promise<ValuationResponse> => {
		const requestBody = {
			building_style: data.building_style,
			building_area: data.building_area,
			land_area: data.land_area,
			no_of_floor: data.no_of_floor,
			building_age: data.building_age,
			amphur: data.amphur,
			tumbon: data.tumbon,
			village: data.village,
			latitude: data.latitude,
			longitude: data.longitude,
			asking_price: data.asking_price,
			save_property: options?.saveProperty ?? false,
			user_id: options?.userId,
		};

		const res = await fetch(`${API_URL}/valuation`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(requestBody),
		});

		if (!res.ok) {
			const error = await res
				.json()
				.catch(() => ({ detail: "Valuation failed" }));
			throw new Error(error.detail || "Failed to get property valuation");
		}

		return res.json();
	},

	/**
	 * Get available valuation models.
	 */
	getValuationModels: async (): Promise<{
		models: Array<{ model_type: string; available: boolean }>;
		default: string | null;
	}> => {
		const res = await fetch(`${API_URL}/valuation/models`);
		if (!res.ok) throw new Error("Failed to get valuation models");
		return res.json();
	},

	/**
	 * List user properties with their valuations.
	 */
	listUserProperties: async (
		userId?: string,
		limit = 20,
		offset = 0,
	): Promise<
		Array<{
			id: string;
			building_style: string | null;
			building_area: number | null;
			estimated_price: number | null;
			confidence: string | null;
			created_at: string;
		}>
	> => {
		const params = new URLSearchParams();
		if (userId) params.append("user_id", userId);
		params.append("limit", limit.toString());
		params.append("offset", offset.toString());

		const res = await fetch(`${API_URL}/valuation/user-properties?${params}`);
		if (!res.ok) throw new Error("Failed to list user properties");
		return res.json();
	},

	/**
	 * Get details of a specific user property.
	 */
	getUserProperty: async (
		propertyId: string,
	): Promise<{
		id: string;
		user_id: string | null;
		building_style: string | null;
		building_area: number | null;
		land_area: number | null;
		no_of_floor: number | null;
		building_age: number | null;
		amphur: string | null;
		tumbon: string | null;
		village: string | null;
		asking_price: number | null;
		estimated_price: number | null;
		confidence: string | null;
		confidence_score: number | null;
		model_type: string | null;
		h3_index: string | null;
		is_cold_start: boolean | null;
		valuation_factors: ValuationFactor[] | null;
		market_insights: {
			district_avg_price: number;
			district_price_trend: number;
			days_on_market_avg: number;
		} | null;
		latitude: number | null;
		longitude: number | null;
		created_at: string;
		updated_at: string;
	}> => {
		const res = await fetch(
			`${API_URL}/valuation/user-properties/${propertyId}`,
		);
		if (!res.ok) throw new Error("Failed to get user property");
		return res.json();
	},
};
