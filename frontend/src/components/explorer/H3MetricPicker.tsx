import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, ChevronDown, Loader2 } from "lucide-react";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

// Human-readable labels for known metrics
const METRIC_LABELS: Record<string, string> = {
  poi_total: "Total POIs",
  poi_school: "Schools",
  poi_transit_stop: "Transit Stops",
  poi_restaurant: "Restaurants",
  poi_hospital: "Hospitals",
  poi_cafe: "Cafes",
  poi_bank: "Banks",
  poi_mall: "Malls",
  poi_park: "Parks",
  poi_temple: "Temples",
  avg_price: "Avg Price",
  median_price: "Median Price",
  std_price: "Std Dev Price",
  property_count: "Property Count",
  avg_building_area: "Avg Building Area",
  avg_land_area: "Avg Land Area",
  avg_building_age: "Avg Building Age",
  transit_total: "Transit Accessibility",
  transit_bangkok_gtfs: "Bangkok GTFS",
  transit_longdomap_bus: "Bus Routes",
};

const CATEGORY_LABELS: Record<string, string> = {
  poi: "POI Counts",
  property: "Property",
  transit: "Transit",
  other: "Other",
};

function formatMetricLabel(metric: string): string {
  if (METRIC_LABELS[metric]) return METRIC_LABELS[metric];
  // Fallback: convert snake_case to Title Case
  return metric
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

interface H3MetricPickerProps {
  value: string;
  onChange: (metric: string) => void;
  isLoading?: boolean;
}

export function H3MetricPicker({ value, onChange, isLoading }: H3MetricPickerProps) {
  const [open, setOpen] = useState(false);

  const { data: catalog, isLoading: isCatalogLoading } = useQuery({
    queryKey: ["h3Metrics"],
    queryFn: () => api.getH3Metrics(),
    staleTime: 1000 * 60 * 30, // 30 min — metrics rarely change
  });

  const categories: Record<string, string[]> = catalog?.categories ?? {
    poi: ["poi_total", "poi_school", "poi_transit_stop", "poi_restaurant", "poi_hospital", "poi_cafe", "poi_bank", "poi_mall", "poi_park", "poi_temple"],
    property: ["avg_price", "median_price", "property_count", "avg_building_area", "avg_land_area", "avg_building_age"],
    transit: ["transit_total", "transit_bangkok_gtfs", "transit_longdomap_bus"],
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-expanded={open}
          aria-label="Select H3 analytics metric"
          className={cn(
            "w-full flex items-center justify-between px-3 py-2 min-h-[40px] text-xs rounded-lg border transition-colors",
            "bg-muted/50 border-border text-foreground hover:bg-muted",
          )}
        >
          <span className="truncate">{formatMetricLabel(value)}</span>
          <span className="flex items-center gap-1.5 shrink-0 ml-2">
            {isLoading && (
              <Loader2 size={12} className="animate-spin text-muted-foreground" />
            )}
            <ChevronDown size={14} className="text-muted-foreground" />
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start" sideOffset={4}>
        <Command>
          <CommandInput placeholder="Search metrics..." className="text-xs" />
          <CommandList>
            <CommandEmpty>
              {isCatalogLoading ? "Loading metrics..." : "No metrics found."}
            </CommandEmpty>
            {(["poi", "property", "transit", "other"] as const).map((category) => {
              const metrics = categories[category];
              if (!metrics || metrics.length === 0) return null;
              return (
                <CommandGroup key={category} heading={CATEGORY_LABELS[category] ?? category}>
                  {metrics.map((metric) => (
                    <CommandItem
                      key={metric}
                      value={`${formatMetricLabel(metric)} ${metric}`}
                      onSelect={() => {
                        onChange(metric);
                        setOpen(false);
                      }}
                      className="text-xs"
                    >
                      <Check
                        size={14}
                        className={cn(
                          "mr-1.5 shrink-0",
                          value === metric ? "opacity-100" : "opacity-0",
                        )}
                      />
                      {formatMetricLabel(metric)}
                    </CommandItem>
                  ))}
                </CommandGroup>
              );
            })}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
