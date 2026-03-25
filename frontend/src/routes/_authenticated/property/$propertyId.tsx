import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState, useMemo, lazy, Suspense } from "react";
import type { ComponentType } from "react";
import type { MapViewState } from "@deck.gl/core";
import { MapContainer } from "@/components/MapContainer";
import { api } from "@/lib/api";
import type { HousePriceItem } from "@/lib/api";
import { keepPreviousViewStateIfSame } from "@/lib/mapViewState";
import { Skeleton } from "@/components/ui/skeleton";
import { LocationIntelligencePanel } from "@/components/LocationIntelligence";
import { ScatterplotLayer } from "@deck.gl/layers";
import {
  Home,
  MapPin,
  Ruler,
  Calendar,
  Layers,
  Building2,
  ArrowLeft,
  Navigation,
  Globe,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { ContentLoader } from "@/components/ui/loading";
import { PropertyImageFrame } from "@/components/property/PropertyImageFrame";

const ComprehensivePriceReport = lazy(() =>
  import("@/components/ComprehensivePriceReport").then((m) => ({
    default: m.ComprehensivePriceReport,
  }))
);

export const Route = createFileRoute("/_authenticated/property/$propertyId")({
  component: PropertyDetailPage,
});

const formatPrice = (price: number | null): string => {
  if (price === null) return "-";
  return `฿${price.toLocaleString("th-TH")}`;
};

const formatArea = (area: number | null): string => {
  if (area === null) return "-";
  return `${area.toLocaleString("th-TH")} sqm`;
};

type NearbyProperty = Awaited<
  ReturnType<typeof api.getNearbyProperties>
>["items"][number];
type MapPropertyItem = HousePriceItem | NearbyProperty;

function PropertyDetailPage() {
  const { propertyId } = Route.useParams();
  const id = Number(propertyId);
  const navigate = useNavigate();

  const [viewState, setViewState] = useState<MapViewState | null>(null);

  const {
    data: property,
    isLoading: isPropertyLoading,
    isError: isPropertyError,
  } = useQuery({
    queryKey: ["property", id],
    queryFn: () => api.getPropertyById(id),
    staleTime: 1000 * 60 * 5,
  });

  // Update viewState when property loads
  const initialViewState = useMemo(() => {
    if (!property) return null;
    return {
      longitude: property.lon,
      latitude: property.lat,
      zoom: 15,
      pitch: 0,
      bearing: 0,
    };
  }, [property]);

  // Fetch nearby properties once we have the property location
  const { data: nearbyData } = useQuery({
    queryKey: ["nearbyProperties", property?.lat, property?.lon],
    queryFn: () => {
      if (!property) throw new Error("No property");
      return api.getNearbyProperties({
        lat: property.lat,
        lon: property.lon,
        radius_m: 1000,
        limit: 20,
      });
    },
    enabled: !!property,
    staleTime: 1000 * 60 * 5,
  });

  // Fetch location intelligence
  const { data: locationIntelligence, isLoading: isLocationLoading } = useQuery(
    {
      queryKey: ["locationIntelligence", property?.lat, property?.lon],
      queryFn: () => {
        if (!property) throw new Error("No property");
        return api.getLocationIntelligence({
          latitude: property.lat,
          longitude: property.lon,
          radius_meters: 1000,
        });
      },
      enabled: !!property,
      staleTime: 1000 * 60 * 10, // Cache for 10 minutes
    }
  );

  // Map layers
  const layers = useMemo(() => {
    if (!property) return [];

    const propertyLayer = new ScatterplotLayer<MapPropertyItem>({
      id: "current-property",
      data: [property],
      getPosition: (d) => [d.lon, d.lat] as [number, number],
      // Brand accent (emerald)
      getFillColor: [16, 185, 129, 255],
      getRadius: 40,
      radiusMinPixels: 10,
      radiusMaxPixels: 20,
      pickable: true,
    });

    const nearbyLayer = nearbyData
      ? new ScatterplotLayer<MapPropertyItem>({
          id: "nearby-properties",
          data: nearbyData.items.filter((p) => p.id !== id),
          getPosition: (d) => [d.lon, d.lat] as [number, number],
          // Subtle white markers on dark map
          getFillColor: [255, 255, 255, 140],
          getRadius: 25,
          radiusMinPixels: 6,
          radiusMaxPixels: 12,
          pickable: true,
        })
      : null;

    return nearbyLayer ? [nearbyLayer, propertyLayer] : [propertyLayer];
  }, [property, nearbyData, id]);

  if (isPropertyError) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center bg-background text-foreground">
        <ErrorState
          title="Property not found"
          message="The property you are looking for could not be loaded."
        />
        <Link to="/" search={{ district: undefined }} className="mt-2">
          <Button
            variant="outline"
            className="border-border bg-muted text-foreground hover:bg-muted/80"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Explorer
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col md:flex-row bg-background text-foreground">
        {/* Left Panel - Property Details */}
        <div className="w-full md:w-100 md:shrink-0 overflow-auto border-b md:border-b-0 md:border-r border-border bg-background">
          {/* Back button */}
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

          {isPropertyLoading ? (
            <div className="space-y-4 p-6">
              <Skeleton className="h-8 w-3/4" />
              <Skeleton className="h-6 w-1/2" />
              <div className="space-y-3 pt-4">
                {[1, 2, 3, 4, 5, 6].map((n) => (
                  <Skeleton
                    key={`property-skeleton-row-${n}`}
                    className="h-12 w-full"
                  />
                ))}
              </div>
            </div>
          ) : property ? (
            <div className="p-6">
              {/* Header */}
              <div className="mb-6">
                <div className="flex items-start gap-3">
                  <div className="rounded-lg bg-brand/15 p-2">
                    <Home className="h-5 w-5 text-brand" />
                  </div>
                  <div>
                    <h1 className="text-lg font-semibold">
                      {property.building_style_desc || "Property"}
                    </h1>
                    <p className="text-sm text-muted-foreground">ID: {property.id}</p>
                  </div>
                </div>
                <div className="mt-4">
                  <p className="text-2xl font-bold text-brand">
                    {formatPrice(property.total_price)}
                  </p>
                  {property.building_area && property.total_price && (
                    <p className="text-sm text-muted-foreground">
                      ฿
                      {Math.round(
                        property.total_price / property.building_area
                      ).toLocaleString()}{" "}
                      / sqm
                    </p>
                  )}
                </div>
              </div>

              <PropertyImageFrame
                title={property.building_style_desc || "Property"}
                subtitle={[property.tumbon, property.amphur].filter(Boolean).join(", ")}
                badge={property.village || null}
                className="mb-6"
                aspectClassName="aspect-[16/10]"
              />

              {/* Details Grid */}
              <div className="space-y-4">
                <DetailRow
                  icon={MapPin}
                  label="Location"
                  value={
                    [property.tumbon, property.amphur]
                      .filter(Boolean)
                      .join(", ") || "-"
                  }
                />
                {property.village && (
                  <DetailRow
                    icon={Building2}
                    label="Village/Project"
                    value={property.village}
                  />
                )}
                <DetailRow
                  icon={Ruler}
                  label="Building Area"
                  value={formatArea(property.building_area)}
                />
                <DetailRow
                  icon={Ruler}
                  label="Land Area"
                  value={
                    property.land_area
                      ? `${property.land_area.toLocaleString()} sqm`
                      : "-"
                  }
                />
                <DetailRow
                  icon={Layers}
                  label="Floors"
                  value={property.no_of_floor?.toString() || "-"}
                />
                <DetailRow
                  icon={Calendar}
                  label="Building Age"
                  value={
                    property.building_age
                      ? `${property.building_age} years`
                      : "-"
                  }
                />
                {property.land_type_desc && (
                  <DetailRow
                    icon={Home}
                    label="Land Type"
                    value={property.land_type_desc}
                  />
                )}
              </div>

              {/* Actions */}
              {Number.isFinite(property.lat) && Number.isFinite(property.lon) ? (
                <div className="mt-4">
                  <a
                    href={`https://www.google.com/maps/search/?api=1&query=${property.lat},${property.lon}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Button variant="outline" size="sm">
                      <Globe className="mr-2 h-4 w-4" />
                      Open in Google Maps
                    </Button>
                  </a>
                </div>
              ) : null}

              {/* Nearby Properties */}
              {nearbyData && nearbyData.items.length > 1 && (
                <div className="mt-8">
                  <h2 className="mb-3 flex items-center gap-2 font-semibold">
                    <Navigation className="h-4 w-4" />
                    Nearby Properties ({nearbyData.count - 1})
                  </h2>
                  <div className="space-y-2">
                    {nearbyData.items
                      .filter((p) => p.id !== id)
                      .slice(0, 5)
                      .map((nearby) => (
                        <Link
                          key={nearby.id}
                          to="/property/$propertyId"
                          params={{ propertyId: String(nearby.id) }}
                          className="block rounded-lg border border-border bg-muted/50 p-3 transition-colors hover:bg-muted"
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-sm font-medium">
                                {nearby.building_style_desc || "Property"}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {Math.round(nearby.distance_m)}m away
                              </p>
                            </div>
                            <p className="text-sm font-semibold text-brand">
                              {formatPrice(nearby.total_price)}
                            </p>
                          </div>
                        </Link>
                      ))}
                  </div>
                </div>
              )}

              {/* Location Intelligence */}
              <div className="mt-8 border-t border-border pt-6">
                {locationIntelligence && (
                  <LocationIntelligencePanel
                    data={locationIntelligence}
                    isLoading={isLocationLoading}
                  />
                )}
                {isLocationLoading && !locationIntelligence && (
                  <div className="space-y-4">
                    <div className="h-6 w-48 animate-pulse rounded bg-muted" />
                    <div className="grid grid-cols-3 gap-3">
                      {[1, 2, 3].map((n) => (
                        <div
                          key={`li-skeleton-${n}`}
                          className="h-24 animate-pulse rounded-lg bg-muted"
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Price Explanation */}
              <div className="mt-6">
                <Suspense fallback={<ContentLoader lines={15} />}>
                  <ComprehensivePriceReport
                    propertyId={id}
                    property={property}
                  />
                </Suspense>
              </div>
            </div>
          ) : null}
        </div>

        {/* Right Panel - Map */}
        <div className="relative flex-1 h-64 md:h-auto">
          {initialViewState ? (
            <MapContainer
              viewState={viewState || initialViewState}
              onViewStateChange={({ viewState: next }) =>
                setViewState((previous) =>
                  previous ? keepPreviousViewStateIfSame(previous, next) : next
                )
              }
              layers={layers}
              onClick={(info) => {
                const clicked = info.object as MapPropertyItem | null | undefined;
                // Navigate to clicked nearby property (not current property)
                if (clicked?.id !== undefined && clicked.id !== id) {
                  navigate({
                    to: "/property/$propertyId",
                    params: { propertyId: String(clicked.id) },
                  });
                }
              }}
              getTooltip={(info) => {
                const p = info.object as MapPropertyItem | null | undefined;
                if (!p) return null;
                if (p.id === id) return null; // Skip tooltip for current property
                return {
                  html: `<div style="padding: 8px; background: rgba(0,0,0,0.9); border-radius: 4px;">
                    <div style="font-weight: 600; color: white;">฿${(p.total_price || 0).toLocaleString()}</div>
                    <div style="font-size: 11px; color: rgba(255,255,255,0.7);">${p.building_style_desc || "Property"}</div>
                    <div style="font-size: 10px; color: rgba(255,255,255,0.5); margin-top: 4px;">Click to view details</div>
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

// Helper component for detail rows
function DetailRow({
  icon: Icon,
  label,
  value,
}: {
  icon: ComponentType<{ className?: string }>;
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
