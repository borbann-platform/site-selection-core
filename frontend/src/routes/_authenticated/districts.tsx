import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Building2,
  TrendingUp,
  Home,
  Search,
  BarChart3,
} from "lucide-react";
import { useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/ui/error-state";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatCard } from "@/components/ui/stat-card";

export const Route = createFileRoute("/_authenticated/districts")({
  component: DistrictsPage,
});

type SortKey = "amphur" | "count" | "avg_price" | "avg_price_per_sqm";
type SortOrder = "asc" | "desc";

function SortIcon({
  columnKey,
  sortKey,
  sortOrder,
}: {
  columnKey: SortKey;
  sortKey: SortKey;
  sortOrder: SortOrder;
}) {
  if (sortKey !== columnKey) return <ArrowUpDown className="ml-1 h-3 w-3" />;
  return sortOrder === "asc" ? (
    <ArrowUp className="ml-1 h-3 w-3" />
  ) : (
    <ArrowDown className="ml-1 h-3 w-3" />
  );
}

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

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortOrder("desc");
    }
  };

  return (
    <div className="flex h-full flex-col overflow-hidden bg-background text-foreground">
        {/* Header */}
        <div className="border-b border-border/40 bg-background px-6 py-4">
          <PageHeader
            icon={Building2}
            title="District Analytics"
            subtitle="Property market statistics by Bangkok district"
          />

          {/* Summary Stats */}
          {stats && (
            <div className="mt-4 flex gap-4 overflow-x-auto pb-2 sm:grid sm:grid-cols-3 sm:overflow-x-visible sm:pb-0">
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

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                <Skeleton
                  key={`district-skeleton-row-${n}`}
                  className="h-12 w-full"
                />
              ))}
            </div>
          ) : isError ? (
            <ErrorState
              title="Failed to load"
              message="Failed to load district statistics"
            />
          ) : (
            <>
            <div className="mb-4 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search districts..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 max-w-sm bg-surface-1 border-white/[0.1] focus:border-brand/40 placeholder:text-muted-foreground/50"
              />
            </div>
            <div className="rounded-xl border border-white/[0.07] bg-surface-1 overflow-x-auto">
              <Table className="min-w-[600px]">
                <TableHeader>
                  <TableRow className="border-white/[0.05] bg-white/[0.02]">
                    <TableHead className="w-50 text-muted-foreground">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="-ml-3 h-8 text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
                        onClick={() => handleSort("amphur")}
                      >
                        District
                    <SortIcon
                      columnKey="amphur"
                      sortKey={sortKey}
                      sortOrder={sortOrder}
                    />
                      </Button>
                    </TableHead>
                    <TableHead className="text-right text-muted-foreground">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="-mr-3 h-8 text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
                        onClick={() => handleSort("count")}
                      >
                        Properties
                    <SortIcon
                      columnKey="count"
                      sortKey={sortKey}
                      sortOrder={sortOrder}
                    />
                      </Button>
                    </TableHead>
                    <TableHead className="text-right text-muted-foreground">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="-mr-3 h-8 text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
                        onClick={() => handleSort("avg_price")}
                      >
                        Avg Price
                    <SortIcon
                      columnKey="avg_price"
                      sortKey={sortKey}
                      sortOrder={sortOrder}
                    />
                      </Button>
                    </TableHead>
                    <TableHead className="text-right text-muted-foreground">
                      Price Range
                    </TableHead>
                    <TableHead className="text-right text-muted-foreground">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="-mr-3 h-8 text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
                        onClick={() => handleSort("avg_price_per_sqm")}
                      >
                        Avg ฿/sqm
                    <SortIcon
                      columnKey="avg_price_per_sqm"
                      sortKey={sortKey}
                      sortOrder={sortOrder}
                    />
                      </Button>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredDistricts.map((district) => (
                    <TableRow
                      key={district.amphur}
                      className="cursor-pointer border-white/[0.04] hover:bg-white/[0.04] transition-colors duration-100"
                    >
                      <TableCell>
                        <Link
                          to="/"
                          search={{ district: district.amphur }}
                          className="font-medium text-brand hover:text-brand/80 hover:underline underline-offset-2 transition-colors"
                        >
                          {district.amphur}
                        </Link>
                      </TableCell>
                      <TableCell className="text-right text-foreground/80">
                        {district.count.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right font-medium text-foreground">
                        {formatPrice(district.avg_price)}
                      </TableCell>
                      <TableCell className="text-right text-sm text-muted-foreground">
                        {formatPrice(district.min_price)} –{" "}
                        {formatPrice(district.max_price)}
                      </TableCell>
                      <TableCell className="text-right text-foreground/80">
                        {formatPricePerSqm(district.avg_price_per_sqm)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            </>
          )}
        </div>
    </div>
  );
}
