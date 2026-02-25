import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowUp,
  ArrowDown,
  Building2,
  TrendingUp,
  Home,
  Search,
  BarChart3,
  ChevronDown,
  MapPin,
} from "lucide-react";
import { useState, useMemo } from "react";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/ui/error-state";
import { StatCard } from "@/components/ui/stat-card";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export const Route = createFileRoute("/_authenticated/districts")({
  component: DistrictsPage,
});

type SortKey = "amphur" | "count" | "avg_price" | "avg_price_per_sqm";
type SortOrder = "asc" | "desc";

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "count", label: "Property Count" },
  { key: "avg_price", label: "Average Price" },
  { key: "avg_price_per_sqm", label: "Price / sqm" },
  { key: "amphur", label: "Name" },
];

const formatPrice = (price: number): string => {
  if (price >= 1_000_000) return `฿${(price / 1_000_000).toFixed(1)}M`;
  if (price >= 1_000) return `฿${(price / 1_000).toFixed(0)}K`;
  return `฿${price.toFixed(0)}`;
};

const formatPricePerSqm = (price: number | null): string => {
  if (price === null) return "-";
  return `฿${price.toLocaleString("th-TH", { maximumFractionDigits: 0 })}/sqm`;
};

function DistrictsPage() {
  const [sortKey, setSortKey] = useState<SortKey>("count");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [searchQuery, setSearchQuery] = useState("");

  const {
    data: stats,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["housePriceStats"],
    queryFn: () => api.getHousePriceStats(),
    staleTime: 1000 * 60 * 5,
  });

  const sortedDistricts = useMemo(() => {
    if (!stats?.by_district) return [];
    return [...stats.by_district].sort((a, b) => {
      const aVal = a[sortKey] ?? 0;
      const bVal = b[sortKey] ?? 0;
      if (typeof aVal === "string" && typeof bVal === "string") {
        return sortOrder === "asc"
          ? aVal.localeCompare(bVal, "th")
          : bVal.localeCompare(aVal, "th");
      }
      return sortOrder === "asc"
        ? (aVal as number) - (bVal as number)
        : (bVal as number) - (aVal as number);
    });
  }, [stats?.by_district, sortKey, sortOrder]);

  const filteredDistricts = useMemo(() => {
    if (!searchQuery.trim()) return sortedDistricts;
    const query = searchQuery.trim().toLowerCase();
    return sortedDistricts.filter((d) =>
      d.amphur.toLowerCase().includes(query)
    );
  }, [sortedDistricts, searchQuery]);

  const maxAvgPrice = useMemo(
    () => Math.max(...(stats?.by_district.map((d) => d.avg_price) ?? [1])),
    [stats?.by_district]
  );

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortOrder("desc");
    }
  };

  const activeSortLabel = SORT_OPTIONS.find((o) => o.key === sortKey)?.label;

  return (
    <div className="min-h-full bg-background">
      {/* Page Header */}
      <div className="border-b border-border bg-background/95 backdrop-blur-sm px-6 py-6">
        <div className="max-w-screen-xl mx-auto">
          <div className="flex items-center gap-3 mb-1">
            <div className="h-9 w-9 rounded-lg bg-primary/10 flex items-center justify-center">
              <Building2 className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-xl font-semibold">District Analytics</h1>
              <p className="text-sm text-muted-foreground">
                Property market statistics by Bangkok district
              </p>
            </div>
          </div>

          {/* Summary Stats */}
          {stats && (
            <div className="mt-5 grid grid-cols-3 gap-4">
              <StatCard
                icon={Home}
                label="Total Properties"
                value={stats.total_count.toLocaleString()}
              />
              <StatCard
                icon={BarChart3}
                label="Avg Price"
                value={formatPrice(
                  stats.by_district.reduce((sum, d) => sum + d.avg_price, 0) /
                    stats.by_district.length
                )}
              />
              <StatCard
                icon={TrendingUp}
                label="Total Districts"
                value={stats.by_district.length}
              />
            </div>
          )}
        </div>
      </div>

      {/* Toolbar */}
      <div className="sticky top-16 z-10 bg-background/95 backdrop-blur-sm border-b border-border px-6 py-3">
        <div className="max-w-screen-xl mx-auto flex items-center gap-3">
          {/* Search */}
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search districts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 bg-background"
            />
          </div>

          {/* Sort dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border bg-background text-sm font-medium hover:bg-muted/50 transition-colors">
                Sort: {activeSortLabel}
                {sortOrder === "desc" ? (
                  <ArrowDown className="h-3.5 w-3.5 text-muted-foreground" />
                ) : (
                  <ArrowUp className="h-3.5 w-3.5 text-muted-foreground" />
                )}
                <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {SORT_OPTIONS.map((opt) => (
                <DropdownMenuItem
                  key={opt.key}
                  onClick={() => handleSort(opt.key)}
                  className={cn(
                    "cursor-pointer",
                    sortKey === opt.key && "text-primary font-medium"
                  )}
                >
                  {opt.label}
                  {sortKey === opt.key && (
                    sortOrder === "desc"
                      ? <ArrowDown className="ml-auto h-3.5 w-3.5" />
                      : <ArrowUp className="ml-auto h-3.5 w-3.5" />
                  )}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          {filteredDistricts.length > 0 && (
            <span className="text-sm text-muted-foreground ml-1">
              {filteredDistricts.length} districts
            </span>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="px-6 py-6">
        <div className="max-w-screen-xl mx-auto">
          {isLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {Array.from({ length: 12 }).map((_, i) => (
                <Skeleton key={`skeleton-${i}`} className="h-48 w-full rounded-xl" />
              ))}
            </div>
          ) : isError ? (
            <ErrorState
              title="Failed to load"
              message="Failed to load district statistics"
            />
          ) : filteredDistricts.length === 0 ? (
            <div className="text-center py-20 text-muted-foreground">
              No districts match "{searchQuery}"
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filteredDistricts.map((district) => (
                <DistrictCard key={district.amphur} district={district} maxAvgPrice={maxAvgPrice} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function DistrictCard({
  district,
  maxAvgPrice,
}: {
  district: {
    amphur: string;
    count: number;
    avg_price: number;
    min_price: number;
    max_price: number;
    avg_price_per_sqm: number | null;
  };
  maxAvgPrice: number;
}) {
  return (
    <div className="glass rounded-xl p-5 border border-border hover:ring-2 hover:ring-primary/30 transition-all group">
      {/* District name + link */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0">
          <Link
            to="/"
            search={{ district: district.amphur }}
            className="font-semibold text-lg text-foreground hover:text-primary transition-colors line-clamp-2 leading-tight"
          >
            {district.amphur}
          </Link>
          <div className="flex items-center gap-1 mt-1">
            <MapPin className="h-3 w-3 text-muted-foreground shrink-0" />
            <span className="text-xs text-muted-foreground">
              {district.count.toLocaleString()} properties
            </span>
          </div>
        </div>
        <div className="ml-2 shrink-0">
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary">
            {district.count.toLocaleString()}
          </span>
        </div>
      </div>

      {/* Price stats */}
      <div className="space-y-3">
        <div>
          <div className="text-xs text-muted-foreground mb-0.5">Avg Price</div>
          <div className="text-xl font-bold text-foreground">
            {formatPrice(district.avg_price)}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="text-xs text-muted-foreground mb-0.5">฿/sqm</div>
            <div className="text-sm font-semibold text-foreground">
              {formatPricePerSqm(district.avg_price_per_sqm)}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground mb-0.5">Range</div>
            <div className="text-xs text-foreground/80 leading-tight">
              {formatPrice(district.min_price)}
              <span className="text-muted-foreground mx-0.5">–</span>
              {formatPrice(district.max_price)}
            </div>
          </div>
        </div>

        {/* Price range bar */}
        <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-primary to-sky-300"
            style={{
              width: `${Math.min(100, Math.max(10, (district.avg_price / maxAvgPrice) * 100))}%`,
            }}
          />
        </div>
      </div>

      {/* View on map link */}
      <div className="mt-4 pt-3 border-t border-border/50">
        <Link
          to="/"
          search={{ district: district.amphur }}
          className="text-xs font-medium text-primary hover:text-primary-hover transition-colors"
        >
          View on map →
        </Link>
      </div>
    </div>
  );
}
