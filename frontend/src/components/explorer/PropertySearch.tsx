import { useState, useCallback, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, X, MapPin, Home, ExternalLink, Loader2 } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { cn } from "@/lib/utils";
import { api, type ListingItem } from "@/lib/api";

interface PropertySearchProps {
  className?: string;
  onResultClick?: (listing: ListingItem) => void;
}

function formatPrice(price: number | null): string {
  if (price === null || !Number.isFinite(price)) return "";
  if (price >= 1_000_000) return `฿${(price / 1_000_000).toFixed(1)}M`;
  if (price >= 1_000) return `฿${(price / 1_000).toFixed(0)}K`;
  return `฿${price.toLocaleString("th-TH")}`;
}

function getSourceBadge(sourceType: ListingItem["source_type"]): string {
  if (sourceType === "house_price") return "Appraisal";
  if (sourceType === "scraped_project") return "Scraped";
  if (sourceType === "market_listing") return "Market";
  return "Condo";
}

export function PropertySearch({ className, onResultClick }: PropertySearchProps) {
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [debouncedQuery, setDebouncedQuery] = useState("");

  // Debounce search query
  useEffect(() => {
    if (!query.trim()) {
      setDebouncedQuery("");
      return;
    }
    const timeoutId = window.setTimeout(() => {
      setDebouncedQuery(query.trim());
    }, 300);
    return () => window.clearTimeout(timeoutId);
  }, [query]);

  const { data: results, isFetching } = useQuery({
    queryKey: ["search-listings", debouncedQuery],
    queryFn: () => api.searchListings(debouncedQuery, 15),
    enabled: debouncedQuery.length > 0,
    staleTime: 1000 * 30,
    placeholderData: (prev) => prev,
  });

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Keyboard shortcut: Cmd/Ctrl+K to focus
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setIsOpen(true);
      }
      if (e.key === "Escape") {
        inputRef.current?.blur();
        setIsOpen(false);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleClear = useCallback(() => {
    setQuery("");
    setDebouncedQuery("");
    inputRef.current?.focus();
  }, []);

  const handleResultClick = useCallback(
    (listing: ListingItem) => {
      setIsOpen(false);
      setQuery("");
      setDebouncedQuery("");
      onResultClick?.(listing);
    },
    [onResultClick]
  );

  const items = results?.items ?? [];
  const totalCount = results?.count ?? 0;
  const showDropdown = isOpen && debouncedQuery.length > 0;

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      {/* Search input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          placeholder="Search by ID, name, district..."
          className="w-full h-9 pl-9 pr-16 rounded-lg border border-border bg-background text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-colors"
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {isFetching && (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
          )}
          {query && (
            <button
              type="button"
              onClick={handleClear}
              className="p-0.5 rounded text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Clear search"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          <kbd className="hidden sm:inline-flex h-5 items-center gap-0.5 rounded border border-border bg-muted px-1.5 text-[10px] font-medium text-muted-foreground">
            <span className="text-xs">⌘</span>K
          </kbd>
        </div>
      </div>

      {/* Results dropdown */}
      {showDropdown && (
        <div className="absolute z-50 mt-1 w-full max-h-[400px] overflow-auto rounded-xl border border-border bg-card shadow-xl backdrop-blur-xl">
          {items.length === 0 && !isFetching && (
            <div className="px-4 py-6 text-center text-sm text-muted-foreground">
              No properties found for "{debouncedQuery}"
            </div>
          )}
          {items.length === 0 && isFetching && (
            <div className="px-4 py-6 text-center text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin inline-block mr-2" />
              Searching...
            </div>
          )}
          {items.length > 0 && (
            <>
              <div className="px-3 py-2 border-b border-border/60 flex items-center justify-between">
                <span className="text-[11px] font-medium text-muted-foreground">
                  {totalCount} result{totalCount !== 1 ? "s" : ""} found
                </span>
              </div>
              <div className="py-1">
                {items.map((listing) => (
                  <SearchResultItem
                    key={listing.listing_key}
                    listing={listing}
                    onClick={() => handleResultClick(listing)}
                  />
                ))}
              </div>
              {totalCount > items.length && (
                <div className="px-3 py-2 border-t border-border/60 text-center text-[11px] text-muted-foreground">
                  Showing {items.length} of {totalCount} results. Refine your search for more specific results.
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function SearchResultItem({
  listing,
  onClick,
}: {
  listing: ListingItem;
  onClick: () => void;
}) {
  const isHousePrice = listing.source_type === "house_price";
  const isHousePriceWithId = isHousePrice && Number.isFinite(Number(listing.source_id));

  return (
    <Link
      to={isHousePriceWithId
        ? "/property/$propertyId"
        : "/listing/$listingKey"
      }
      params={
        isHousePriceWithId
          ? { propertyId: String(Number(listing.source_id)) }
          : { listingKey: listing.listing_key }
      }
      onClick={() => {
        onClick();
      }}
      className="flex items-start gap-3 px-3 py-2.5 hover:bg-muted/60 transition-colors cursor-pointer"
    >
      <div className="mt-0.5 rounded-md bg-brand/10 p-1.5 shrink-0">
        <Home className="h-3.5 w-3.5 text-brand" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground truncate">
            {listing.title || listing.building_style_desc || "Property"}
          </span>
          <span className="shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground border border-border/60">
            {getSourceBadge(listing.source_type)}
          </span>
        </div>
        <div className="flex items-center gap-3 mt-0.5 text-[11px] text-muted-foreground">
          {listing.total_price != null && (
            <span className="font-semibold text-foreground/80">
              {formatPrice(listing.total_price)}
            </span>
          )}
          {(listing.tumbon || listing.amphur) && (
            <span className="flex items-center gap-0.5 truncate">
              <MapPin className="h-3 w-3 shrink-0" />
              {[listing.tumbon, listing.amphur].filter(Boolean).join(", ")}
            </span>
          )}
          {listing.building_area != null && (
            <span>{listing.building_area} sqm</span>
          )}
        </div>
        <div className="mt-0.5 text-[10px] text-muted-foreground/60">
          ID: {listing.source_id} | Key: {listing.listing_key}
        </div>
      </div>
      <ExternalLink className="h-3.5 w-3.5 text-muted-foreground/40 mt-1 shrink-0" />
    </Link>
  );
}
