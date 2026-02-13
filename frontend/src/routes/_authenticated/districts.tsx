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
} from "lucide-react";
import { useState, useMemo } from "react";
import { Button } from "@/components/ui/button";

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
        <div className="border-b border-border bg-background px-6 py-4">
          <div className="flex items-center gap-3">
            <Building2 className="h-6 w-6 text-emerald-400" />
            <div>
              <h1 className="text-xl font-semibold">District Analytics</h1>
              <p className="text-sm text-muted-foreground">
                Property market statistics by Bangkok district
              </p>
            </div>
          </div>

          {/* Summary Stats */}
          {stats && (
            <div className="mt-4 flex gap-6">
              <div className="flex items-center gap-2">
                <Home className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">
                    {stats.total_count.toLocaleString()}
                  </span>{" "}
                  properties
                </span>
              </div>
              <div className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">
                    {stats.by_district.length}
                  </span>{" "}
                  districts
                </span>
              </div>
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
            <div className="flex h-full items-center justify-center">
              <p className="text-rose-400">
                Failed to load district statistics
              </p>
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-card">
              <Table>
                <TableHeader>
                  <TableRow className="border-border">
                    <TableHead className="w-50 text-muted-foreground">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="-ml-3 h-8 text-muted-foreground hover:bg-muted hover:text-foreground"
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
                        className="-mr-3 h-8 text-muted-foreground hover:bg-muted hover:text-foreground"
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
                        className="-mr-3 h-8 text-muted-foreground hover:bg-muted hover:text-foreground"
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
                        className="-mr-3 h-8 text-muted-foreground hover:bg-muted hover:text-foreground"
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
                  {sortedDistricts.map((district) => (
                    <TableRow
                      key={district.amphur}
                      className="cursor-pointer border-border hover:bg-muted/50"
                    >
                      <TableCell>
                        <Link
                          to="/"
                          search={{ district: district.amphur }}
                          className="font-medium text-emerald-400 hover:text-emerald-300 hover:underline"
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
          )}
        </div>
    </div>
  );
}
