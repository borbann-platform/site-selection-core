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

interface LocationScoreCardProps {
  label: string;
  score: number;
  icon: React.ReactNode;
  description?: string;
  color?: string;
}

const getScoreColor = (score: number): string => {
  if (score >= 80) return "text-emerald-400";
  if (score >= 60) return "text-yellow-400";
  if (score >= 40) return "text-orange-400";
  return "text-rose-400";
};

const getScoreBg = (score: number): string => {
  if (score >= 80) return "bg-emerald-400/20";
  if (score >= 60) return "bg-yellow-400/20";
  if (score >= 40) return "bg-orange-400/20";
  return "bg-rose-400/20";
};

export function LocationScoreCard({
  label,
  score,
  icon,
  description,
}: LocationScoreCardProps) {
  const colorClass = getScoreColor(score);
  const bgClass = getScoreBg(score);

  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-white/10 bg-white/5 p-3">
      <div className={`rounded-full p-2 ${bgClass}`}>{icon}</div>
      <div className={`text-2xl font-bold ${colorClass}`}>{score}</div>
      <div className="text-xs font-medium text-white/70">{label}</div>
      {description && (
        <div className="text-center text-xs text-white/50">{description}</div>
      )}
    </div>
  );
}

interface RiskBadgeProps {
  level: "low" | "medium" | "high" | "quiet" | "moderate" | "busy" | "unknown";
  label: string;
}

export function RiskBadge({ level, label }: RiskBadgeProps) {
  const config = {
    low: { bg: "bg-emerald-500/20", text: "text-emerald-400", icon: "✓" },
    quiet: { bg: "bg-emerald-500/20", text: "text-emerald-400", icon: "✓" },
    medium: { bg: "bg-yellow-500/20", text: "text-yellow-400", icon: "⚠" },
    moderate: { bg: "bg-yellow-500/20", text: "text-yellow-400", icon: "~" },
    high: { bg: "bg-rose-500/20", text: "text-rose-400", icon: "!" },
    busy: { bg: "bg-orange-500/20", text: "text-orange-400", icon: "!" },
    unknown: { bg: "bg-white/10", text: "text-white/50", icon: "?" },
  };

  const { bg, text, icon } = config[level] || config.unknown;

  return (
    <div
      className={`flex items-center gap-2 rounded-lg border border-white/10 ${bg} px-3 py-2`}
    >
      <span className={`text-sm ${text}`}>{icon}</span>
      <div className="flex flex-col">
        <span className="text-xs text-white/50">{label}</span>
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
        <div className="h-6 w-48 animate-pulse rounded bg-white/10" />
        <div className="grid grid-cols-3 gap-3">
          {[1, 2, 3].map((n) => (
            <div
              key={`score-skeleton-${n}`}
              className="h-24 animate-pulse rounded-lg bg-white/10"
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
          <MapPin className="h-5 w-5 text-emerald-400" />
          <h2 className="font-semibold text-white">Location Intelligence</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-white/50">Overall</span>
          <span
            className={`text-xl font-bold ${getScoreColor(data.composite_score)}`}
          >
            {data.composite_score}
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
        />
        <LocationScoreCard
          label="Walkability"
          score={data.walkability.score}
          icon={
            <Footprints
              className={`h-4 w-4 ${getScoreColor(data.walkability.score)}`}
            />
          }
        />
        <LocationScoreCard
          label="Schools"
          score={data.schools.score}
          icon={
            <GraduationCap
              className={`h-4 w-4 ${getScoreColor(data.schools.score)}`}
            />
          }
        />
      </div>

      {/* Risk badges */}
      <div className="grid grid-cols-2 gap-3">
        <RiskBadge level={data.flood_risk.level} label="Flood Risk" />
        <RiskBadge level={data.noise.level} label="Noise Level" />
      </div>

      {/* Details */}
      <div className="space-y-2 rounded-lg border border-white/10 bg-white/5 p-3">
        <h3 className="text-sm font-medium text-white/70">Details</h3>

        {/* Transit details */}
        {data.transit.nearest_rail && (
          <div className="flex items-center gap-2 text-sm">
            <Train className="h-3 w-3 text-white/40" />
            <span className="text-white/70">
              {data.transit.nearest_rail.name} -{" "}
              {Math.round(data.transit.nearest_rail.distance_m)}m
            </span>
          </div>
        )}

        {data.transit.bus_stops_500m > 0 && (
          <div className="flex items-center gap-2 text-sm">
            <Bus className="h-3 w-3 text-white/40" />
            <span className="text-white/70">
              {data.transit.bus_stops_500m} bus stops within 500m
            </span>
          </div>
        )}

        {/* Schools details */}
        {data.schools.total_within_2km > 0 && (
          <div className="flex items-center gap-2 text-sm">
            <GraduationCap className="h-3 w-3 text-white/40" />
            <span className="text-white/70">
              {data.schools.total_within_2km} schools within 2km
            </span>
          </div>
        )}

        {/* Walkability summary */}
        {data.walkability.total_amenities > 0 && (
          <div className="flex items-center gap-2 text-sm">
            <Footprints className="h-3 w-3 text-white/40" />
            <span className="text-white/70">
              {data.walkability.total_amenities} amenities nearby
            </span>
          </div>
        )}

        {/* Flood warning */}
        {data.flood_risk.district_warnings.length > 0 && (
          <div className="flex items-start gap-2 text-sm">
            <Droplets className="mt-0.5 h-3 w-3 text-yellow-400" />
            <span className="text-yellow-400/80">
              {data.flood_risk.district_warnings.length} flood warning zones in
              district
            </span>
          </div>
        )}

        {/* Noise info */}
        {data.noise.nearest_major_road_m && (
          <div className="flex items-center gap-2 text-sm">
            <Volume2 className="h-3 w-3 text-white/40" />
            <span className="text-white/70">
              Major road {Math.round(data.noise.nearest_major_road_m)}m away
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
