import { useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  X,
  Home,
  MessageSquarePlus,
  ArrowRight,
  MapPinned,
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { PropertyImageFrame } from "@/components/property/PropertyImageFrame";

interface PropertyData {
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

interface PropertyPopupProps {
  property: PropertyData | null;
  position: { x: number; y: number } | null;
  onClose: () => void;
  onAddToChat?: (property: PropertyData) => void;
}

export function PropertyPopup({
  property,
  position,
  onClose,
  onAddToChat,
}: PropertyPopupProps) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [panelSize, setPanelSize] = useState({ width: 288, height: 320 });
  const hasActivePopup = Boolean(property && position);

  const formatPrice = (p: number) =>
    new Intl.NumberFormat("th-TH", {
      style: "currency",
      currency: "THB",
      maximumFractionDigits: 0,
    }).format(p);

  const price =
    typeof property?.total_price === "number" && property.total_price > 0
      ? property.total_price
      : undefined;
  const pricePerSqm =
    property?.building_area && price !== undefined
      ? formatPrice(price / property.building_area)
      : "N/A";
  const propertyReference =
    property?.house_ref ||
    (property?.id !== undefined ? `house:${property.id}` : undefined);
  const hasCoordinates =
    typeof property?.lat === "number" &&
    Number.isFinite(property.lat) &&
    typeof property?.lon === "number" &&
    Number.isFinite(property.lon);
  const googleMapsUrl = hasCoordinates
    ? `https://www.google.com/maps/search/?api=1&query=${property.lat},${property.lon}`
    : null;

  const handleAddToChat = () => {
    if (!property) return;
    onAddToChat?.(property);
    onClose();
  };

  useLayoutEffect(() => {
    if (!hasActivePopup || !panelRef.current) return;
    const rect = panelRef.current.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    setPanelSize((prev) => {
      if (
        Math.abs(prev.width - rect.width) < 1 &&
        Math.abs(prev.height - rect.height) < 1
      ) {
        return prev;
      }
      return { width: rect.width, height: rect.height };
    });
  });

  const popupPlacement = useMemo(() => {
    if (!position) {
      return {
        left: 0,
        top: 0,
        transform: "translate(-50%, -100%) translateY(-10px)",
        placeAbove: true,
      };
    }

    const margin = 12;
    const offset = 10;
    const viewportWidth =
      typeof window !== "undefined" ? window.innerWidth : 0;
    const viewportHeight =
      typeof window !== "undefined" ? window.innerHeight : 0;

    const boundedWidth = Math.min(
      panelSize.width,
      Math.max(1, viewportWidth - margin * 2)
    );
    const halfWidth = boundedWidth / 2;
    const minX = margin + halfWidth;
    const maxX = Math.max(minX, viewportWidth - margin - halfWidth);
    const clampedX =
      viewportWidth > 0 ? Math.min(maxX, Math.max(minX, position.x)) : position.x;

    const spaceAbove = position.y - margin - offset;
    const spaceBelow = viewportHeight - position.y - margin - offset;
    const fitsAbove = spaceAbove >= panelSize.height;
    const fitsBelow = spaceBelow >= panelSize.height;
    const placeAbove = fitsAbove || (!fitsBelow && spaceAbove >= spaceBelow);

    const top = placeAbove ? position.y : position.y;
    const transform = placeAbove
      ? "translate(-50%, -100%) translateY(-10px)"
      : "translate(-50%, 0%) translateY(10px)";

    return {
      left: clampedX,
      top,
      transform,
      placeAbove,
    };
  }, [panelSize.height, panelSize.width, position]);

  if (!property || !position) return null;

  return (
    <div
      className="fixed z-[100] pointer-events-auto animate-fade-in"
      style={{
        left: popupPlacement.left,
        top: popupPlacement.top,
        transform: popupPlacement.transform,
      }}
    >
        <div
          ref={panelRef}
          className="bg-card/95 border border-border rounded-xl shadow-2xl shadow-black/25 backdrop-blur-lg overflow-hidden min-w-72 max-w-80"
        >
        {/* Header */}
        <div className="flex items-center gap-2 px-3 py-2 bg-brand/10 border-b border-border">
          <Home size={14} className="text-brand" />
          <span className="flex-1 font-bold text-sm text-brand truncate">
            {property.title || property.building_style_desc || "Property"}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="p-1 hover:bg-muted rounded text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Close property popup"
          >
            <X size={14} />
          </button>
        </div>

        {/* Content */}
        <div className="p-3">
          <PropertyImageFrame
            imageUrl={property.image_url}
            title={property.title || property.building_style_desc || "Property"}
            subtitle={[property.tumbon, property.amphur].filter(Boolean).join(", ")}
            badge={
              property.source_type === "scraped_project"
                ? "Scraped listing"
                : property.source_type === "market_listing"
                  ? "Market listing"
                  : property.source_type === "condo_project"
                    ? "Condo project"
                    : null
            }
            className="mb-3"
            aspectClassName="aspect-[16/9]"
          />

          {property.source_type && (
            <div className="mb-2 inline-flex rounded-full border border-border/70 bg-muted/40 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              {property.source_type === "scraped_project"
                ? "Scraped Listing"
                : property.source_type === "market_listing"
                  ? "Market Listing"
                  : property.source_type === "condo_project"
                    ? "Condo Project"
                    : "Appraisal"}
            </div>
          )}
          <div className="text-lg font-bold text-foreground mb-2">
            {price !== undefined ? formatPrice(price) : "Price unavailable"}
          </div>
          <div className="grid grid-cols-2 gap-1 text-[11px] text-muted-foreground">
            <div>District:</div>
            <div className="text-right font-medium text-foreground/80">
              {property.amphur || "N/A"}
            </div>
            <div>Sub-district:</div>
            <div className="text-right font-medium text-foreground/80">
              {property.tumbon || "N/A"}
            </div>
            <div>Area:</div>
            <div className="text-right font-medium text-foreground/80">
              {property.building_area ? `${property.building_area} sqm` : "N/A"}
            </div>
            <div>Price/sqm:</div>
            <div className="text-right font-medium text-brand">
              {pricePerSqm}
            </div>
            <div>Floors:</div>
            <div className="text-right font-medium text-foreground/80">
              {property.no_of_floor || "N/A"}
            </div>
            <div>Age:</div>
            <div className="text-right font-medium text-foreground/80">
              {property.building_age ? `${property.building_age} yrs` : "N/A"}
            </div>
          </div>
          {propertyReference && (
            <div className="mt-2 rounded-md border border-border/60 bg-muted/40 px-2 py-1 text-[10px] text-muted-foreground">
              Ref: <span className="font-mono text-foreground/80">{propertyReference}</span>
            </div>
          )}

          {/* View Details button - only show if property has ID */}
          {property.id && property.source_type === "house_price" && (
            <Link
              to="/property/$propertyId"
              params={{ propertyId: String(property.id) }}
              className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 bg-brand hover:bg-brand/90 text-brand-foreground text-xs font-medium rounded-lg transition-colors"
            >
              <ArrowRight size={14} />
              <span>View Details</span>
            </Link>
          )}

          {property.listing_key && property.source_type !== "house_price" && (
            <Link
              to="/listing/$listingKey"
              params={{ listingKey: property.listing_key }}
              className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 bg-brand hover:bg-brand/90 text-brand-foreground text-xs font-medium rounded-lg transition-colors"
            >
              <ArrowRight size={14} />
              <span>View Listing Details</span>
            </Link>
          )}

          {googleMapsUrl && (
            <a
              href={googleMapsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 w-full flex items-center justify-center gap-2 px-3 py-2 border border-border bg-background hover:bg-muted text-foreground text-xs font-medium rounded-lg transition-colors"
            >
              <MapPinned size={14} />
              <span>Open in Google Maps</span>
            </a>
          )}

          {/* Add to Chat button */}
          {onAddToChat && (
            <button
              type="button"
              onClick={handleAddToChat}
              className="mt-2 w-full flex items-center justify-center gap-2 px-3 py-2 border border-border bg-muted/35 hover:bg-muted text-muted-foreground hover:text-foreground text-xs font-medium rounded-lg transition-colors"
            >
              <MessageSquarePlus size={14} />
              <span>Add to Chat</span>
            </button>
          )}
        </div>
      </div>

      {/* Pointer arrow */}
      <div
        className={`absolute left-1/2 -translate-x-1/2 ${
          popupPlacement.placeAbove
            ? "bottom-0 translate-y-full"
            : "top-0 -translate-y-full"
        }`}
      >
        {popupPlacement.placeAbove ? (
          <div className="w-0 h-0 border-l-8 border-r-8 border-t-8 border-l-transparent border-r-transparent border-t-border" />
        ) : (
          <div className="w-0 h-0 border-l-8 border-r-8 border-b-8 border-l-transparent border-r-transparent border-b-border" />
        )}
      </div>
    </div>
  );
}

// Mini property card for inline display in chat
export function PropertyMiniCard({
  property,
  onRemove,
}: {
  property: {
    name?: string;
    price?: number;
    area?: number;
    district?: string;
  };
  onRemove?: () => void;
}) {
  return (
    <div className="flex items-center gap-2 bg-brand/10 border border-brand/25 rounded-lg px-2 py-1.5">
      <Home size={12} className="text-brand" />
      <div className="flex-1 min-w-0">
        <div className="text-xs font-medium text-foreground truncate">
          {property.name || "Property"}
        </div>
        {property.price && (
          <div className="text-[10px] text-brand/90">
            ฿{(property.price / 1000000).toFixed(1)}M
            {property.area && ` • ${property.area}sqm`}
          </div>
        )}
      </div>
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="p-0.5 hover:bg-muted rounded text-muted-foreground hover:text-foreground"
          aria-label="Remove property"
        >
          <X size={12} />
        </button>
      )}
    </div>
  );
}
