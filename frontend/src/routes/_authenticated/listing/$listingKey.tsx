import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState, lazy, Suspense } from "react";
import type { MapViewState } from "@deck.gl/core";
import { ScatterplotLayer } from "@deck.gl/layers";
import {
  ArrowLeft,
  Building2,
  ExternalLink,
  Home,
  Layers,
  MapPin,
  Navigation,
  Globe,
} from "lucide-react";
import { MapContainer } from "@/components/MapContainer";
import { api, type HousePriceItem, type ListingItem } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { LocationIntelligencePanel } from "@/components/LocationIntelligence";
import { PropertyImageFrame } from "@/components/property/PropertyImageFrame";
import { keepPreviousViewStateIfSame } from "@/lib/mapViewState";

const ComprehensivePriceReport = lazy(() =>
  import("@/components/ComprehensivePriceReport").then((m) => ({
    default: m.ComprehensivePriceReport,
  }))
);

export const Route = createFileRoute("/_authenticated/listing/$listingKey")({
  component: ListingDetailPage,
});

type MapPropertyItem =
  | { id: number; lat: number; lon: number; kind: "nearby" }
  | { lat: number; lon: number; kind: "current" };

function formatPrice(price: number | null): string {
  if (price === null || !Number.isFinite(price)) {
    return "Price unavailable";
  }
  return `฿${price.toLocaleString("th-TH")}`;
}

function getSourceLabel(sourceType: ListingItem["source_type"]): string {
  if (sourceType === "house_price") return "Appraisal";
  if (sourceType === "scraped_project") return "Scraped Listing";
  if (sourceType === "market_listing") return "Market Listing";
  return "Condo Project";
}

function toHousePriceItem(listing: ListingItem): HousePriceItem {
  return {
    id: 0,
    updated_date: null,
    land_type_desc: null,
    building_style_desc: listing.building_style_desc,
    tumbon: listing.tumbon,
    amphur: listing.amphur,
    village: null,
    building_age: listing.building_age,
    land_area: null,
    building_area: listing.building_area,
    no_of_floor: listing.no_of_floor,
    total_price: listing.total_price,
    lat: listing.lat,
    lon: listing.lon,
  };
}

function ListingDetailPage() {
  const { listingKey } = Route.useParams();
  const navigate = useNavigate();
  const [viewState, setViewState] = useState<MapViewState | null>(null);

  const {
    data: listing,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["listing-detail", listingKey],
    queryFn: () => api.getListingByKey(listingKey),
    staleTime: 1000 * 60 * 5,
  });

  const { data: nearbyData } = useQuery({
    queryKey: ["listing-nearby-properties", listing?.lat, listing?.lon],
    queryFn: () => {
      if (!listing) throw new Error("No listing");
      return api.getNearbyProperties({
        lat: listing.lat,
        lon: listing.lon,
        radius_m: 1000,
        limit: 20,
      });
    },
    enabled: !!listing,
    staleTime: 1000 * 60 * 5,
  });

  const { data: locationIntelligence, isLoading: isLocationLoading } = useQuery({
    queryKey: ["listing-location-intelligence", listing?.lat, listing?.lon],
    queryFn: () => {
      if (!listing) throw new Error("No listing");
      return api.getLocationIntelligence({
        latitude: listing.lat,
        longitude: listing.lon,
        radius_meters: 1000,
      });
    },
    enabled: !!listing,
    staleTime: 1000 * 60 * 10,
  });

  const initialViewState = useMemo(() => {
    if (!listing) return null;
    return {
      longitude: listing.lon,
      latitude: listing.lat,
      zoom: 15,
      pitch: 0,
      bearing: 0,
    };
  }, [listing]);

  const mapLayers = useMemo(() => {
    if (!listing) return [];

    const currentListingLayer = new ScatterplotLayer<MapPropertyItem>({
      id: "current-listing",
      data: [{ lat: listing.lat, lon: listing.lon, kind: "current" }],
      getPosition: (d) => [d.lon, d.lat] as [number, number],
      getFillColor: [16, 185, 129, 255],
      getRadius: 40,
      radiusMinPixels: 10,
      radiusMaxPixels: 20,
      pickable: true,
    });

    const nearbyLayer = nearbyData
      ? new ScatterplotLayer<MapPropertyItem>({
          id: "listing-nearby-properties",
          data: nearbyData.items.map((p) => ({
            id: p.id,
            lat: p.lat,
            lon: p.lon,
            kind: "nearby" as const,
          })),
          getPosition: (d) => [d.lon, d.lat] as [number, number],
          getFillColor: [255, 255, 255, 140],
          getRadius: 25,
          radiusMinPixels: 6,
          radiusMaxPixels: 12,
          pickable: true,
        })
      : null;

    return nearbyLayer ? [nearbyLayer, currentListingLayer] : [currentListingLayer];
  }, [listing, nearbyData]);

  if (isError) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center bg-background text-foreground">
        <ErrorState
          title="Listing not found"
          message="The listing could not be loaded or no longer exists."
        />
        <Link to="/" search={{ district: undefined }} className="mt-3">
          <Button variant="outline">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Explorer
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col md:flex-row bg-background text-foreground">
      <div className="w-full md:w-100 md:shrink-0 overflow-auto border-b md:border-b-0 md:border-r border-border bg-background">
        <div className="border-b border-border p-4">
          <Link to="/" search={{ district: undefined }}>
            <Button
              variant="ghost"
              size="sm"
              className="-ml-2 text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Explorer
            </Button>
          </Link>
        </div>

        {isLoading || !listing ? (
          <div className="space-y-4 p-6">
            <Skeleton className="h-8 w-3/4" />
            <Skeleton className="h-6 w-1/2" />
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : (
          <div className="p-6">
            <div className="mb-6">
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-brand/15 p-2">
                  <Home className="h-5 w-5 text-brand" />
                </div>
                <div>
                  <h1 className="text-lg font-semibold">
                    {listing.title || listing.building_style_desc || "Listing"}
                  </h1>
                  <p className="text-sm text-muted-foreground">
                    {getSourceLabel(listing.source_type)}
                  </p>
                </div>
              </div>

              <div className="mt-4">
                <p className="text-2xl font-bold text-brand">
                  {formatPrice(listing.total_price)}
                </p>
                {listing.building_area && listing.total_price && (
                  <p className="text-sm text-muted-foreground">
                    ฿{Math.round(listing.total_price / listing.building_area).toLocaleString()} / sqm
                  </p>
                )}
              </div>
            </div>

            <div className="space-y-4">
              <DetailRow
                icon={MapPin}
                label="Location"
                value={
                  [listing.tumbon, listing.amphur].filter(Boolean).join(", ") ||
                  "Location unavailable"
                }
              />
              <DetailRow
                icon={Building2}
                label="Building Type"
                value={listing.building_style_desc || "-"}
              />
              <DetailRow
                icon={Layers}
                label="Building Area"
                value={
                  listing.building_area
                    ? `${listing.building_area.toLocaleString("th-TH")} sqm`
                    : "-"
                }
              />
            </div>

            <PropertyImageFrame
              imageUrl={listing.image_url}
              title={listing.title || listing.building_style_desc || "Listing"}
              subtitle={[listing.tumbon, listing.amphur].filter(Boolean).join(", ")}
              badge={getSourceLabel(listing.source_type)}
              className="mt-6"
              aspectClassName="aspect-[16/10]"
            />

            <div className="mt-4 flex flex-wrap gap-2">
              {listing.source_type === "house_price" && Number.isFinite(Number(listing.source_id)) ? (
                <Link
                  to="/property/$propertyId"
                  params={{ propertyId: String(Number(listing.source_id)) }}
                >
                  <Button variant="outline" size="sm">
                    <Navigation className="mr-2 h-4 w-4" />
                    Open Full Property Detail
                  </Button>
                </Link>
              ) : null}
              {listing.detail_url ? (
                <a href={listing.detail_url} target="_blank" rel="noopener noreferrer">
                  <Button variant="outline" size="sm">
                    <ExternalLink className="mr-2 h-4 w-4" />
                    Open Source Listing
                  </Button>
                </a>
              ) : null}
              {Number.isFinite(listing.lat) && Number.isFinite(listing.lon) ? (
                <a
                  href={`https://www.google.com/maps/search/?api=1&query=${listing.lat},${listing.lon}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Button variant="outline" size="sm">
                    <Globe className="mr-2 h-4 w-4" />
                    Open in Google Maps
                  </Button>
                </a>
              ) : null}
            </div>

            <div className="mt-8 border-t border-border pt-6">
              {locationIntelligence ? (
                <LocationIntelligencePanel
                  data={locationIntelligence}
                  isLoading={isLocationLoading}
                />
              ) : null}
              {isLocationLoading && !locationIntelligence ? (
                <div className="space-y-4">
                  <div className="h-6 w-48 animate-pulse rounded bg-muted" />
                  <div className="grid grid-cols-3 gap-3">
                    {[1, 2, 3].map((n) => (
                      <div
                        key={`listing-li-skeleton-${n}`}
                        className="h-24 animate-pulse rounded-lg bg-muted"
                      />
                    ))}
                  </div>
                </div>
              ) : null}
            </div>

            <div className="mt-6">
              <Suspense fallback={
                <div className="space-y-4">
                  <div className="bg-card border border-border rounded-lg p-4 animate-pulse">
                    <div className="flex items-center justify-between mb-4">
                      <div className="h-5 bg-muted/50 rounded w-2/5" />
                      <div className="h-6 bg-muted/50 rounded-full w-20" />
                    </div>
                    <div className="h-4 bg-muted/50 rounded w-full mb-2" />
                    <div className="h-4 bg-muted/50 rounded w-3/4 mb-4" />
                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div className="rounded-lg p-3 bg-muted/30 h-20" />
                      <div className="rounded-lg p-3 bg-muted/30 h-20" />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="rounded-lg p-3 bg-muted/30 h-14" />
                      <div className="rounded-lg p-3 bg-muted/30 h-14" />
                    </div>
                  </div>
                  <div className="bg-card border border-border rounded-lg p-4 animate-pulse">
                    <div className="h-5 bg-muted/50 rounded w-1/3" />
                  </div>
                </div>
              }>
                <ComprehensivePriceReport
                  property={toHousePriceItem(listing)}
                  propertyId={
                    listing.source_type === "house_price" && Number.isFinite(Number(listing.source_id))
                      ? Number(listing.source_id)
                      : undefined
                  }
                  predictionRequest={{
                    lat: listing.lat,
                    lon: listing.lon,
                    ...(listing.building_area ? { building_area: listing.building_area } : {}),
                    ...(listing.no_of_floor ? { no_of_floor: listing.no_of_floor } : {}),
                    ...(listing.building_age ? { building_age: listing.building_age } : {}),
                    ...(listing.building_style_desc
                      ? { building_style: listing.building_style_desc }
                      : {}),
                  }}
                />
              </Suspense>
            </div>
          </div>
        )}
      </div>

      <div className="relative flex-1 h-64 md:h-auto">
        {initialViewState ? (
          <MapContainer
            viewState={viewState || initialViewState}
            onViewStateChange={({ viewState: next }) =>
              setViewState((previous) =>
                previous ? keepPreviousViewStateIfSame(previous, next) : next
              )
            }
            layers={mapLayers}
            onClick={(info) => {
              const clicked = info.object as MapPropertyItem | null | undefined;
              if (!clicked || clicked.kind !== "nearby") return;
              navigate({
                to: "/property/$propertyId",
                params: { propertyId: String(clicked.id) },
              });
            }}
            getTooltip={(info) => {
              const clicked = info.object as MapPropertyItem | null | undefined;
              if (!clicked || clicked.kind !== "nearby") return null;
              const nearby = nearbyData?.items.find((item) => item.id === clicked.id);
              if (!nearby) return null;
              return {
                html: `<div style="padding:8px; background: rgba(0,0,0,0.9); border-radius:4px;">
                  <div style="font-weight:600; color:white;">฿${(nearby.total_price || 0).toLocaleString()}</div>
                  <div style="font-size:11px; color: rgba(255,255,255,0.7);">${nearby.building_style_desc || "Comparable"}</div>
                  <div style="font-size:10px; color: rgba(255,255,255,0.5); margin-top:4px;">Click to view full details</div>
                </div>`,
                style: { background: "transparent", border: "none" },
              };
            }}
          />
        ) : (
          <div className="flex h-full items-center justify-center bg-background">
            <Skeleton className="h-full w-full" />
          </div>
        )}
      </div>
    </div>
  );
}

function DetailRow({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-border bg-muted/50 p-3">
      <Icon className="mt-0.5 h-4 w-4 text-muted-foreground" />
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-sm font-medium text-foreground">{value}</p>
      </div>
    </div>
  );
}
