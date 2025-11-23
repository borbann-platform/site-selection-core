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
};
