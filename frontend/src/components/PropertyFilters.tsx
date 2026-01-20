import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { Slider } from "./ui/slider";
import { Label } from "./ui/label";

export interface PropertyFiltersState {
  district: string | null;
  buildingStyle: string | null;
  minPrice: number;
  maxPrice: number;
  minArea: number;
  maxArea: number;
}

interface PropertyFiltersProps {
  filters: PropertyFiltersState;
  onChange: (filters: PropertyFiltersState) => void;
}

const formatPrice = (value: number): string => {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }
  return `${(value / 1_000).toFixed(0)}K`;
};

export function PropertyFilters({ filters, onChange }: PropertyFiltersProps) {
  const { data: districts } = useQuery({
    queryKey: ["districts"],
    queryFn: api.getDistricts,
    staleTime: 1000 * 60 * 10, // Cache for 10 min
  });

  const { data: buildingStyles } = useQuery({
    queryKey: ["buildingStyles"],
    queryFn: api.getBuildingStyles,
    staleTime: 1000 * 60 * 10,
  });

  return (
    <div className="space-y-5">
      {/* District Select */}
      <div className="space-y-2">
        <Label className="text-xs text-muted-foreground">District (เขต)</Label>
        <Select
          value={filters.district || "all"}
          onValueChange={(value) =>
            onChange({ ...filters, district: value === "all" ? null : value })
          }
        >
          <SelectTrigger className="bg-muted/50 border-border text-foreground">
            <SelectValue placeholder="All Districts" />
          </SelectTrigger>
          <SelectContent className="bg-card border-border">
            <SelectItem value="all" className="text-foreground hover:bg-muted">
              All Districts
            </SelectItem>
            {districts?.map((d) => (
              <SelectItem
                key={d.amphur}
                value={d.amphur}
                className="text-foreground hover:bg-muted"
              >
                {d.amphur} ({d.count})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Building Style Select */}
      <div className="space-y-2">
        <Label className="text-xs text-muted-foreground">Building Type</Label>
        <Select
          value={filters.buildingStyle || "all"}
          onValueChange={(value) =>
            onChange({
              ...filters,
              buildingStyle: value === "all" ? null : value,
            })
          }
        >
          <SelectTrigger className="bg-muted/50 border-border text-foreground">
            <SelectValue placeholder="All Types" />
          </SelectTrigger>
          <SelectContent className="bg-card border-border">
            <SelectItem value="all" className="text-foreground hover:bg-muted">
              All Types
            </SelectItem>
            {buildingStyles?.map((s) => (
              <SelectItem
                key={s.building_style_desc}
                value={s.building_style_desc}
                className="text-foreground hover:bg-muted"
              >
                {s.building_style_desc} ({s.count})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Price Range Slider */}
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <Label className="text-xs text-muted-foreground">Price Range (THB)</Label>
          <span className="text-xs text-emerald-500 dark:text-emerald-400 font-mono">
            {formatPrice(filters.minPrice)} - {formatPrice(filters.maxPrice)}
          </span>
        </div>
        <Slider
          min={500_000}
          max={50_000_000}
          step={500_000}
          value={[filters.minPrice, filters.maxPrice]}
          onValueChange={([min, max]) =>
            onChange({ ...filters, minPrice: min, maxPrice: max })
          }
          className="**:[[role=slider]]:bg-emerald-500"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground/70">
          <span>500K</span>
          <span>50M</span>
        </div>
      </div>

      {/* Area Range Slider */}
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <Label className="text-xs text-muted-foreground">Building Area (sqm)</Label>
          <span className="text-xs text-emerald-500 dark:text-emerald-400 font-mono">
            {filters.minArea} - {filters.maxArea} sqm
          </span>
        </div>
        <Slider
          min={20}
          max={1000}
          step={10}
          value={[filters.minArea, filters.maxArea]}
          onValueChange={([min, max]) =>
            onChange({ ...filters, minArea: min, maxArea: max })
          }
          className="**:[[role=slider]]:bg-emerald-500"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground/70">
          <span>20 sqm</span>
          <span>1000 sqm</span>
        </div>
      </div>
    </div>
  );
}
