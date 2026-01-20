import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

export interface FilterValues {
  budgetMin: number | null;
  budgetMax: number | null;
  areaMin: number | null;
  distanceToBTS: number | null;
  undervaluedOnly: boolean;
  highGrowthOnly: boolean;
  excludeFloodZones: boolean;
  maxBuildingAge: number | null;
}

export const DEFAULT_FILTERS: FilterValues = {
  budgetMin: null,
  budgetMax: null,
  areaMin: null,
  distanceToBTS: null,
  undervaluedOnly: false,
  highGrowthOnly: false,
  excludeFloodZones: false,
  maxBuildingAge: null,
};

interface QuickFiltersProps {
  values: FilterValues;
  onChange: (values: FilterValues) => void;
}

export function QuickFilters({ values, onChange }: QuickFiltersProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const updateFilter = <K extends keyof FilterValues>(
    key: K,
    value: FilterValues[K]
  ) => {
    onChange({ ...values, [key]: value });
  };

  const hasActiveFilters = Object.entries(values).some(([key, value]) => {
    if (key === "budgetMin" || key === "budgetMax" || key === "areaMin" || key === "distanceToBTS" || key === "maxBuildingAge") {
      return value !== null;
    }
    return value === true;
  });

  return (
    <div className="border-t border-border">
      {/* Header - Collapsible */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">Quick Filters</span>
          {hasActiveFilters && (
            <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-[10px] rounded-full">
              Active
            </span>
          )}
        </div>
        {isExpanded ? (
          <ChevronUp size={14} className="text-muted-foreground/60" />
        ) : (
          <ChevronDown size={14} className="text-muted-foreground/60" />
        )}
      </button>

      {/* Filter Controls */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-3">
          {/* Budget Range */}
          <div className="space-y-1">
            <div className="text-[11px] text-muted-foreground font-medium">
              Budget Range (฿)
            </div>
            <div className="flex gap-2">
              <input
                type="number"
                placeholder="Min"
                value={values.budgetMin ?? ""}
                onChange={(e) =>
                  updateFilter(
                    "budgetMin",
                    e.target.value ? Number(e.target.value) : null
                  )
                }
                className="flex-1 bg-muted/50 border border-border rounded px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-emerald-500/50"
                aria-label="Minimum budget"
              />
              <span className="text-muted-foreground/50 self-center">–</span>
              <input
                type="number"
                placeholder="Max"
                value={values.budgetMax ?? ""}
                onChange={(e) =>
                  updateFilter(
                    "budgetMax",
                    e.target.value ? Number(e.target.value) : null
                  )
                }
                className="flex-1 bg-muted/50 border border-border rounded px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-emerald-500/50"
                aria-label="Maximum budget"
              />
            </div>
          </div>

          {/* Area & Distance Row */}
          <div className="grid grid-cols-2 gap-2">
            {/* Area Min */}
            <div className="space-y-1">
              <div className="text-[11px] text-muted-foreground font-medium">
                Min Area (sqw)
              </div>
              <input
                type="number"
                placeholder="e.g., 120"
                value={values.areaMin ?? ""}
                onChange={(e) =>
                  updateFilter(
                    "areaMin",
                    e.target.value ? Number(e.target.value) : null
                  )
                }
                className="w-full bg-muted/50 border border-border rounded px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-emerald-500/50"
                aria-label="Minimum area"
              />
            </div>

            {/* Distance to BTS */}
            <div className="space-y-1">
              <div className="text-[11px] text-muted-foreground font-medium">
                Max Dist to BTS (km)
              </div>
              <select
                value={values.distanceToBTS ?? ""}
                onChange={(e) =>
                  updateFilter(
                    "distanceToBTS",
                    e.target.value ? Number(e.target.value) : null
                  )
                }
                className="w-full bg-muted/50 border border-border rounded px-2 py-1.5 text-xs text-foreground focus:outline-none focus:border-emerald-500/50"
                aria-label="Maximum distance to BTS"
              >
                <option value="">Any</option>
                <option value="0.5">0.5 km</option>
                <option value="1">1 km</option>
                <option value="2">2 km</option>
                <option value="3">3 km</option>
                <option value="5">5 km</option>
              </select>
            </div>
          </div>

          {/* Building Age */}
          <div className="space-y-1">
            <div className="text-[11px] text-muted-foreground font-medium">
              Max Building Age (years)
            </div>
            <input
              type="number"
              placeholder="e.g., 10"
              value={values.maxBuildingAge ?? ""}
              onChange={(e) =>
                updateFilter(
                  "maxBuildingAge",
                  e.target.value ? Number(e.target.value) : null
                )
              }
              className="w-full bg-muted/50 border border-border rounded px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-emerald-500/50"
              aria-label="Maximum building age"
            />
          </div>

          {/* Boolean Filters */}
          <div className="space-y-2 pt-2">
            <label className="flex items-center gap-2 cursor-pointer group">
              <input
                type="checkbox"
                checked={values.undervaluedOnly}
                onChange={(e) => updateFilter("undervaluedOnly", e.target.checked)}
                className="w-3.5 h-3.5 rounded bg-muted/50 border border-border checked:bg-emerald-500 checked:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
              />
              <span className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">
                Undervalued properties only
              </span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer group">
              <input
                type="checkbox"
                checked={values.highGrowthOnly}
                onChange={(e) => updateFilter("highGrowthOnly", e.target.checked)}
                className="w-3.5 h-3.5 rounded bg-muted/50 border border-border checked:bg-emerald-500 checked:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
              />
              <span className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">
                High growth neighborhoods (&gt;5%)
              </span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer group">
              <input
                type="checkbox"
                checked={values.excludeFloodZones}
                onChange={(e) => updateFilter("excludeFloodZones", e.target.checked)}
                className="w-3.5 h-3.5 rounded bg-muted/50 border border-border checked:bg-emerald-500 checked:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
              />
              <span className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">
                Exclude flood risk zones
              </span>
            </label>
          </div>

          {/* Clear Filters */}
          {hasActiveFilters && (
            <button
              type="button"
              onClick={() => onChange(DEFAULT_FILTERS)}
              className="w-full mt-2 px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded transition-colors"
            >
              Clear all filters
            </button>
          )}
        </div>
      )}
    </div>
  );
}
