export type DataSourceStatus = "linked" | "placeholder";

export interface DataSourceSpec {
  id: string;
  label: string;
  citation: string;
  url?: string;
  status: DataSourceStatus;
}

export const DATA_SOURCES = {
  housePrices: {
    id: "house-prices",
    label: "House prices",
    citation: "Internal baseline house price dataset (see project data catalog)",
    url: "https://github.com/borbann-platform/site-selection-core/blob/main/gis-server/data/DATA_CATALOG.md",
    status: "linked",
  },
  scrapedListings: {
    id: "scraped-listings",
    label: "Scraped listings",
    citation:
      "Baania/Hipflat scraped project listings with optional MinIO image sync",
    url: "https://github.com/borbann-platform/site-selection-core/blob/main/gis-server/docs/data_processing.md",
    status: "linked",
  },
  osmPoi: {
    id: "osm-poi",
    label: "OSM POIs",
    citation: "OpenStreetMap points of interest",
    url: "https://www.openstreetmap.org/copyright",
    status: "linked",
  },
  railGtfs: {
    id: "rail-gtfs",
    label: "Rail transit",
    citation: "Bangkok rail GTFS feed (documented in project data catalog)",
    url: "https://github.com/borbann-platform/site-selection-core/blob/main/gis-server/data/DATA_CATALOG.md",
    status: "linked",
  },
  floodRisk: {
    id: "flood-risk",
    label: "Flood risk",
    citation: "Flood-warning district dataset",
    url: "https://github.com/borbann-platform/site-selection-core/blob/main/gis-server/data/DATA_CATALOG.md",
    status: "linked",
  },
  noiseRoads: {
    id: "noise-roads",
    label: "Noise / roads",
    citation: "Major road distance source link pending",
    status: "placeholder",
  },
  districtTrend: {
    id: "district-trend",
    label: "District trend",
    citation: "District growth trend source link pending",
    status: "placeholder",
  },
} satisfies Record<string, DataSourceSpec>;
