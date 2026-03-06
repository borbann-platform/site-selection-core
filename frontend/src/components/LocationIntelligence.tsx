import type { LocationIntelligenceResponse } from "@/lib/api";
import {
  Train,
  Bus,
  Footprints,
  GraduationCap,
  Droplets,
  Volume2,
  MapPin,
} from "lucide-react";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { SourceTooltip } from "@/components/ui/source-tooltip";
import { DATA_SOURCES } from "@/lib/dataSources";
import { SCORE_METHODOLOGY } from "@/lib/scoreMethodology";

interface LocationScoreCardProps {
  label: string;
  score: number;
  icon: React.ReactNode;
  methodology: string;
}

const getScoreColor = (score: number): string => {
  if (score >= 80) return "text-success";
  if (score >= 60) return "text-warning";
  if (score >= 40) return "text-orange-500";
  return "text-destructive";
};

const getScoreBg = (score: number): string => {
  if (score >= 80) return "bg-success/20";
  if (score >= 60) return "bg-warning/20";
  if (score >= 40) return "bg-orange-500/20";
  return "bg-destructive/20";
};

export function LocationScoreCard({
  label,
  score,
  icon,
  methodology,
}: LocationScoreCardProps) {
  const colorClass = getScoreColor(score);
  const bgClass = getScoreBg(score);

  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-border bg-muted/50 p-3">
      <div className={`rounded-full p-2 ${bgClass}`}>{icon}</div>
      <div className={`text-2xl font-bold ${colorClass}`}>{score}</div>
      <div className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground">
        <span>{label}</span>
        <InfoTooltip title={`${label} scoring`} description={methodology} />
      </div>
    </div>
  );
}

interface RiskBadgeProps {
  level: "low" | "medium" | "high" | "quiet" | "moderate" | "busy" | "unknown";
  label: string;
}

export function RiskBadge({ level, label }: RiskBadgeProps) {
  const config = {
    low: { bg: "bg-success/20", text: "text-success", icon: "✓" },
    quiet: { bg: "bg-success/20", text: "text-success", icon: "✓" },
    medium: { bg: "bg-warning/20", text: "text-warning", icon: "⚠" },
    moderate: { bg: "bg-warning/20", text: "text-warning", icon: "~" },
    high: { bg: "bg-destructive/20", text: "text-destructive", icon: "!" },
    busy: { bg: "bg-orange-500/20", text: "text-orange-500", icon: "!" },
    unknown: { bg: "bg-muted", text: "text-muted-foreground", icon: "?" },
  };

  const { bg, text, icon } = config[level] || config.unknown;

  return (
    <div
      className={`flex items-center gap-2 rounded-lg border border-border ${bg} px-3 py-2`}
    >
      <span className={`text-sm ${text}`}>{icon}</span>
      <div className="flex flex-col">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className={`text-sm font-medium capitalize ${text}`}>
          {level}
        </span>
      </div>
    </div>
  );
}

interface LocationIntelligencePanelProps {
  data: LocationIntelligenceResponse;
  isLoading?: boolean;
}

export function LocationIntelligencePanel({
  data,
  isLoading,
}: LocationIntelligencePanelProps) {
  if (isLoading) {
    return (
      <div className="space-y-4 p-4">
        <div className="h-6 w-48 animate-pulse rounded bg-muted" />
        <div className="grid grid-cols-3 gap-3">
          {[1, 2, 3].map((n) => (
            <div
              key={`score-skeleton-${n}`}
              className="h-24 animate-pulse rounded-lg bg-muted"
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with composite score */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MapPin className="h-5 w-5 text-brand" />
          <h2 className="font-semibold text-foreground">Location Intelligence</h2>
          <InfoTooltip
            title="Composite score"
            description={SCORE_METHODOLOGY.composite}
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Overall</span>
          <span
            className={`text-xl font-bold ${getScoreColor(data.composite_score)}`}
          >
            {data.composite_score}
          </span>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-muted/40 p-2">
        <div className="text-[11px] font-medium text-muted-foreground mb-1">
          Score color legend
        </div>
        <div className="grid grid-cols-2 gap-1 text-[10px] text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            80-100 strong
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-amber-500" />
            60-79 moderate
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-orange-500" />
            40-59 watch
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-red-500" />
            0-39 limited
          </span>
        </div>
      </div>

      {/* Score cards grid */}
      <div className="grid grid-cols-3 gap-3">
        <LocationScoreCard
          label="Transit"
          score={data.transit.score}
          icon={
            <Train className={`h-4 w-4 ${getScoreColor(data.transit.score)}`} />
          }
          methodology={SCORE_METHODOLOGY.transit}
        />
        <LocationScoreCard
          label="Walkability"
          score={data.walkability.score}
          icon={
            <Footprints
              className={`h-4 w-4 ${getScoreColor(data.walkability.score)}`}
            />
          }
          methodology={SCORE_METHODOLOGY.walkability}
        />
        <LocationScoreCard
          label="Schools"
          score={data.schools.score}
          icon={
            <GraduationCap
              className={`h-4 w-4 ${getScoreColor(data.schools.score)}`}
            />
          }
          methodology={SCORE_METHODOLOGY.schools}
        />
      </div>

      {/* Risk badges */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
            <span>Flood Risk</span>
            <InfoTooltip title="Flood risk method" description={SCORE_METHODOLOGY.floodRisk} />
          </div>
          <RiskBadge level={data.flood_risk.level} label="Flood Risk" />
        </div>
        <div className="space-y-1">
          <div className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
            <span>Noise Level</span>
            <InfoTooltip title="Noise method" description={SCORE_METHODOLOGY.noise} />
          </div>
          <RiskBadge level={data.noise.level} label="Noise Level" />
        </div>
      </div>

      {/* Details */}
      <div className="space-y-2 rounded-lg border border-border bg-muted/50 p-3">
        <h3 className="text-sm font-medium text-muted-foreground">Details</h3>

        {/* Transit details */}
        {data.transit.nearest_rail && (
          <div className="flex items-center gap-2 text-sm">
            <Train className="h-3 w-3 text-muted-foreground" />
            <span className="text-muted-foreground">
              {data.transit.nearest_rail.name} -{" "}
              {Math.round(data.transit.nearest_rail.distance_m)}m
            </span>
            <SourceTooltip source={DATA_SOURCES.railGtfs} />
          </div>
        )}

        {data.transit.bus_stops_500m > 0 && (
          <div className="flex items-center gap-2 text-sm">
            <Bus className="h-3 w-3 text-muted-foreground" />
            <span className="text-muted-foreground">
              {data.transit.bus_stops_500m} bus stops within 500m
            </span>
          </div>
        )}

        {/* Schools details */}
        {data.schools.total_within_2km > 0 && (
          <div className="flex items-center gap-2 text-sm">
            <GraduationCap className="h-3 w-3 text-muted-foreground" />
            <span className="text-muted-foreground">
              {data.schools.total_within_2km} schools within 2km
            </span>
            <SourceTooltip source={DATA_SOURCES.osmPoi} />
          </div>
        )}

        {/* Walkability summary */}
        {data.walkability.total_amenities > 0 && (
          <div className="flex items-center gap-2 text-sm">
            <Footprints className="h-3 w-3 text-muted-foreground" />
            <span className="text-muted-foreground">
              {data.walkability.total_amenities} amenities nearby
            </span>
          </div>
        )}

        {/* Flood warning */}
        {data.flood_risk.district_warnings.length > 0 && (
          <div className="flex items-start gap-2 text-sm">
            <Droplets className="mt-0.5 h-3 w-3 text-warning" />
            <span className="text-warning">
              {data.flood_risk.district_warnings.length} flood warning zones in
              district
            </span>
            <SourceTooltip source={DATA_SOURCES.floodRisk} />
          </div>
        )}

        {/* Noise info */}
        {data.noise.nearest_major_road_m && (
          <div className="flex items-center gap-2 text-sm">
            <Volume2 className="h-3 w-3 text-muted-foreground" />
            <span className="text-muted-foreground">
              Major road {Math.round(data.noise.nearest_major_road_m)}m away
            </span>
            <SourceTooltip source={DATA_SOURCES.noiseRoads} />
          </div>
        )}
      </div>
    </div>
  );
}
