import { useQuery } from "@tanstack/react-query";
import { api, type HousePriceStatsResponse } from "../lib/api";
import { TrendingUp, Home, MapPin, Loader2 } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { useTheme } from "@/contexts/ThemeContext";

interface MarketStatsProps {
  filters?: {
    district: string | null;
    buildingStyle: string | null;
  };
}

const formatPriceShort = (value: number): string => {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }
  return `${(value / 1_000).toFixed(0)}K`;
};

export function MarketStats({ filters }: MarketStatsProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const { data: stats, isLoading } = useQuery({
    queryKey: ["housePriceStats"],
    queryFn: api.getHousePriceStats,
    staleTime: 1000 * 60 * 5, // 5 min cache
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!stats) return null;

  // Filter stats if district is selected
  const filteredStats: HousePriceStatsResponse = filters?.district
    ? {
        ...stats,
        by_district: stats.by_district.filter(
          (d) => d.amphur === filters.district
        ),
      }
    : stats;

  const totalCount = filteredStats.by_district.reduce(
    (sum, d) => sum + d.count,
    0
  );
  const avgPrice =
    filteredStats.by_district.reduce(
      (sum, d) => sum + d.avg_price * d.count,
      0
    ) / (totalCount || 1);
  const avgPricePerSqm =
    filteredStats.by_district.reduce(
      (sum, d) => sum + (d.avg_price_per_sqm || 0) * d.count,
      0
    ) / (totalCount || 1);

  // Top 5 districts for chart
  const topDistricts = stats.by_district.slice(0, 5).map((d) => ({
    name: d.amphur.length > 10 ? `${d.amphur.slice(0, 10)}...` : d.amphur,
    fullName: d.amphur,
    count: d.count,
    avgPrice: d.avg_price,
  }));

  // Chart colors based on theme
  const axisTextColor = isDark ? "rgba(255,255,255,0.5)" : "rgba(0,0,0,0.5)";

  return (
    <div className="space-y-4">
      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-muted/50 rounded-lg p-3 text-center">
          <Home className="w-4 h-4 mx-auto mb-1 text-brand" />
          <div className="text-lg font-bold text-foreground">
            {totalCount.toLocaleString()}
          </div>
          <div className="text-[10px] text-muted-foreground">Properties</div>
        </div>
        <div className="bg-muted/50 rounded-lg p-3 text-center">
          <TrendingUp className="w-4 h-4 mx-auto mb-1 text-amber-500 dark:text-amber-400" />
          <div className="text-lg font-bold text-foreground">
            {formatPriceShort(avgPrice)}
          </div>
          <div className="text-[10px] text-muted-foreground">Avg Price</div>
        </div>
        <div className="bg-muted/50 rounded-lg p-3 text-center">
          <MapPin className="w-4 h-4 mx-auto mb-1 text-blue-500 dark:text-blue-400" />
          <div className="text-lg font-bold text-foreground">
            {formatPriceShort(avgPricePerSqm)}
          </div>
          <div className="text-[10px] text-muted-foreground">/sqm</div>
        </div>
      </div>

      {/* Top Districts Chart */}
      {!filters?.district && (
        <div className="space-y-2">
          <div className="text-xs text-muted-foreground font-medium">
            Top Districts by Count
          </div>
          <div className="h-32">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={topDistricts}
                layout="vertical"
                margin={{ left: 0, right: 10, top: 0, bottom: 0 }}
              >
                <XAxis type="number" hide />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={80}
                  tick={{ fill: axisTextColor, fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {topDistricts.map((district, index) => (
                    <Cell
                      key={district.name}
                      fill={`rgba(16, 185, 129, ${1 - index * 0.15})`}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Building Type Breakdown */}
      <div className="space-y-2">
        <div className="text-xs text-muted-foreground font-medium">
          By Building Type
        </div>
        <div className="space-y-1">
          {stats.by_building_style.slice(0, 4).map((style) => {
            const pct = (style.count / stats.total_count) * 100;
            return (
              <div key={style.building_style_desc} className="space-y-1">
                <div className="flex justify-between text-[11px]">
                  <span className="text-muted-foreground truncate max-w-[140px]">
                    {style.building_style_desc}
                  </span>
                  <span className="text-muted-foreground/70">{style.count}</span>
                </div>
                <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-amber-500/70 rounded-full"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
