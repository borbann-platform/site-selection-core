import { useState } from "react";
import {
  Home,
  MapPin,
  TrendingUp,
  ChevronDown,
  ChevronUp,
  ExternalLink,
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { cn } from "@/lib/utils";

export interface PropertyResult {
  id: string | number;
  listing_key?: string;
  source_type?: "house_price" | "scraped_project" | "market_listing" | "condo_project";
  price: number;
  district: string;
  area?: number;
  style?: string;
  priceChange?: number;
  lat?: number;
  lon?: number;
}

interface PropertyResultsCardProps {
  results: PropertyResult[];
  totalCount?: number;
  priceRange?: { min: number; max: number };
  onPropertyClick?: (property: PropertyResult) => void;
  className?: string;
}

export function PropertyResultsCard({
  results,
  totalCount,
  priceRange,
  onPropertyClick,
  className,
}: PropertyResultsCardProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const displayCount = isExpanded ? Math.min(results.length, 6) : 3;
  const displayResults = results.slice(0, displayCount);
  const hasMore = results.length > displayCount;

  const formatPrice = (price: number) => {
    if (price >= 1_000_000) {
      return `฿${(price / 1_000_000).toFixed(1)}M`;
    }
    return `฿${(price / 1_000).toFixed(0)}K`;
  };

  return (
    <div
      className={cn(
        "rounded-xl border border-amber-500/20 bg-amber-500/5 overflow-hidden",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-amber-500/10 border-b border-amber-500/20">
        <div className="flex items-center gap-2">
          <Home size={14} className="text-amber-500 dark:text-amber-400" />
          <span className="text-xs font-semibold text-amber-600 dark:text-amber-300">
            {totalCount || results.length} Properties Found
          </span>
        </div>
        {priceRange && (
          <span className="text-[10px] text-amber-500/70 dark:text-amber-400/70">
            {formatPrice(priceRange.min)} - {formatPrice(priceRange.max)}
          </span>
        )}
      </div>

      {/* Results Grid */}
      <div className="p-2 grid grid-cols-2 gap-2">
        {displayResults.map((property) => (
          <PropertyMiniCard
            key={property.id}
            property={property}
            onClick={() => onPropertyClick?.(property)}
          />
        ))}
      </div>

      {/* Footer */}
      {(hasMore || results.length > 3) && (
        <div className="px-3 py-2 border-t border-amber-500/10 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1 text-[10px] text-amber-500/70 dark:text-amber-400/70 hover:text-amber-600 dark:hover:text-amber-400 transition-colors"
          >
            {isExpanded ? (
              <>
                <ChevronUp size={12} />
                Show less
              </>
            ) : (
              <>
                <ChevronDown size={12} />
                Show {Math.min(results.length - 3, 3)} more
              </>
            )}
          </button>

          {totalCount && totalCount > results.length && (
            <span className="text-[10px] text-muted-foreground">
              +{totalCount - results.length} more
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// Mini property card for grid display
function PropertyMiniCard({
  property,
  onClick,
}: {
  property: PropertyResult;
  onClick?: () => void;
}) {
  const formatPrice = (price: number) => {
    if (price >= 1_000_000) {
      return `฿${(price / 1_000_000).toFixed(1)}M`;
    }
    return `฿${(price / 1_000).toFixed(0)}K`;
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex flex-col gap-1 p-2 rounded-lg text-left transition-all",
        "bg-muted/50 hover:bg-muted border border-border/50 hover:border-amber-500/30",
        "group"
      )}
    >
      {/* Price */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-bold text-foreground">
          {formatPrice(property.price)}
        </span>
        {property.priceChange !== undefined && (
          <span
            className={cn(
              "flex items-center gap-0.5 text-[9px] font-medium",
              property.priceChange >= 0 ? "text-success" : "text-destructive"
            )}
          >
            <TrendingUp
              size={10}
              className={property.priceChange < 0 ? "rotate-180" : ""}
            />
            {Math.abs(property.priceChange)}%
          </span>
        )}
      </div>

      {/* Style */}
      <div className="text-[11px] text-muted-foreground truncate">
        {property.style || "Property"}
      </div>

      {/* Location & Area */}
      <div className="flex items-center gap-2 text-[10px] text-muted-foreground/70">
        <span className="flex items-center gap-0.5 truncate">
          <MapPin size={10} />
          {property.district}
        </span>
        {property.area && <span>{property.area} sqm</span>}
      </div>

      {/* View link - appears on hover */}
      {property.source_type && property.source_type !== "house_price" && property.listing_key ? (
        <Link
          to="/listing/$listingKey"
          params={{ listingKey: property.listing_key }}
          onClick={(e) => e.stopPropagation()}
          className="mt-1 flex items-center gap-1 text-[10px] text-brand opacity-0 group-hover:opacity-100 transition-opacity"
        >
          View details
          <ExternalLink size={10} />
        </Link>
      ) : (
        <Link
          to="/property/$propertyId"
          params={{ propertyId: String(property.id) }}
          onClick={(e) => e.stopPropagation()}
          className="mt-1 flex items-center gap-1 text-[10px] text-brand opacity-0 group-hover:opacity-100 transition-opacity"
        >
          View details
          <ExternalLink size={10} />
        </Link>
      )}
    </button>
  );
}

// Parse property results from AI response content
export function parsePropertyResults(content: string): PropertyResult[] | null {
  // Look for JSON block between markers
  const startMarker = "<!--PROPERTIES_START-->";
  const endMarker = "<!--PROPERTIES_END-->";

  const startIdx = content.indexOf(startMarker);
  const endIdx = content.indexOf(endMarker);

  if (startIdx === -1 || endIdx === -1 || startIdx >= endIdx) {
    return null;
  }

  try {
    const jsonStr = content.slice(startIdx + startMarker.length, endIdx).trim();
    const data = JSON.parse(jsonStr);

    if (Array.isArray(data)) {
      return data.map((item) => ({
        id: item.id || `prop-${Math.random().toString(36).slice(2, 8)}`,
        listing_key:
          typeof item.listing_key === "string" ? item.listing_key : undefined,
        source_type:
          item.source_type === "scraped_project" ||
          item.source_type === "market_listing" ||
          item.source_type === "condo_project"
            ? item.source_type
            : "house_price",
        price: Number(item.price) || Number(item.total_price) || 0,
        district: item.district || item.amphur || "Unknown",
        area: item.area || item.building_area,
        style: item.style || item.building_style_desc,
        priceChange: item.priceChange || item.price_change,
        lat: item.lat,
        lon: item.lon,
      }));
    }
  } catch {
    return null;
  }

  return null;
}

// Remove property markers from content for clean display
export function cleanContentFromPropertyMarkers(content: string): string {
  const startMarker = "<!--PROPERTIES_START-->";
  const endMarker = "<!--PROPERTIES_END-->";

  const startIdx = content.indexOf(startMarker);
  const endIdx = content.indexOf(endMarker);

  if (startIdx === -1 || endIdx === -1) {
    return content;
  }

  return (
    content.slice(0, startIdx) + content.slice(endIdx + endMarker.length)
  ).trim();
}
