import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState, useMemo, useEffect } from "react";
import { MapContainer } from "../../components/MapContainer";
import { Shell } from "../../components/Shell";
import { GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import { FlyToInterpolator } from "@deck.gl/core";
import { api } from "../../lib/api";

import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import {
  User,
  Briefcase,
  GraduationCap,
  AlertTriangle,
  CheckCircle,
  MapPin,
  Eye,
  EyeOff,
  Download,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { Skeleton } from "../../components/ui/skeleton";

interface SiteSearch {
  lat: number;
  lon: number;
}

export const Route = createFileRoute("/site/$siteId")({
  component: SiteInspector,
  validateSearch: (search: Record<string, unknown>): SiteSearch => {
    return {
      lat: Number(search.lat) || 13.7563,
      lon: Number(search.lon) || 100.5018,
    };
  },
});

const MAGNET_CATEGORIES = [
  "mall",
  "marketplace",
  "attraction",
  "park",
  "train_station",
  "subway_station",
  "hospital",
  "university",
];

function SiteInspector() {
  const { siteId } = Route.useParams();
  const { lat, lon } = Route.useSearch();

  const [viewState, setViewState] = useState<any>({
    longitude: lon,
    latitude: lat,
    zoom: 14,
    pitch: 45,
    bearing: 0,
  });

  // Sync viewState with URL params
  useEffect(() => {
    setViewState((prev: any) => {
      if (
        Math.abs(prev.latitude - lat) < 0.00001 &&
        Math.abs(prev.longitude - lon) < 0.00001
      ) {
        return prev;
      }
      return {
        ...prev,
        longitude: lon,
        latitude: lat,
        transitionDuration: 1000,
        transitionInterpolator: new FlyToInterpolator(),
      };
    });
  }, [lat, lon]);

  const [showCompetitors, setShowCompetitors] = useState(true);
  const [showMagnets, setShowMagnets] = useState(true);

  // Fetch Site Analysis
  const { data: analysis, isLoading: isAnalysisLoading } = useQuery({
    queryKey: ["site", lat, lon],
    queryFn: () =>
      api.analyzeSite({
        latitude: lat,
        longitude: lon,
        target_category: "competitor", // Default category
      }),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  // Fetch Isochrone
  const { data: isochrone } = useQuery({
    queryKey: ["isochrone", lat, lon],
    queryFn: () =>
      api.getIsochrone({
        latitude: lat,
        longitude: lon,
        minutes: 15,
        mode: "walk",
      }),
    enabled: !!lat && !!lon,
    staleTime: 1000 * 60 * 60, // 1 hour
  });

  // Fetch Nearby Competitors
  const { data: competitors } = useQuery({
    queryKey: ["nearby", lat, lon, "competitor"],
    queryFn: () =>
      api.getNearby({
        latitude: lat,
        longitude: lon,
        radius_meters: 2000,
        categories: ["competitor", "cafe", "coffee_shop"],
      }),
    enabled: showCompetitors && !!lat && !!lon,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  // Fetch Nearby Magnets
  const { data: magnets } = useQuery({
    queryKey: ["nearby", lat, lon, "magnet"],
    queryFn: () =>
      api.getNearby({
        latitude: lat,
        longitude: lon,
        radius_meters: 2000,
        categories: MAGNET_CATEGORIES,
      }),
    enabled: showMagnets && !!lat && !!lon,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  const layers = useMemo(() => {
    return [
      isochrone &&
        new GeoJsonLayer({
          id: "isochrone",
          data: isochrone,
          stroked: true,
          filled: true,
          lineWidthMinPixels: 2,
          getFillColor: [0, 100, 255, 40],
          getLineColor: [0, 100, 255, 200],
          pickable: true,
        }),
      showMagnets &&
        magnets &&
        new ScatterplotLayer({
          id: "magnets",
          data: magnets.features,
          getPosition: (d: any) => d.geometry.coordinates,
          getFillColor: [255, 0, 128], // Pink
          getRadius: 30,
          pickable: true,
          opacity: 0.8,
          stroked: true,
          getLineColor: [255, 255, 255],
          lineWidthMinPixels: 1,
        }),
      showCompetitors &&
        competitors &&
        new ScatterplotLayer({
          id: "competitors",
          data: competitors.features,
          getPosition: (d: any) => d.geometry.coordinates,
          getFillColor: [50, 200, 50], // Green
          getRadius: 25,
          pickable: true,
          opacity: 0.8,
          stroked: true,
          getLineColor: [255, 255, 255],
          lineWidthMinPixels: 1,
        }),
      new GeoJsonLayer({
        id: "site-marker",
        data: {
          type: "Feature",
          geometry: { type: "Point", coordinates: [lon, lat] },
        } as any,
        pointRadiusMinPixels: 10,
        getFillColor: [255, 255, 255],
        getLineColor: [0, 0, 0],
        stroked: true,
        lineWidthMinPixels: 2,
      }),
    ].filter(Boolean);
  }, [isochrone, lat, lon, competitors, magnets, showCompetitors, showMagnets]);

  const getTooltip = ({ object }: any) => {
    if (!object) return null;
    if (object.properties?.name) {
      return {
        html: `<div class="p-2 bg-black/80 text-white rounded text-xs">
          <div class="font-bold">${object.properties.name}</div>
          <div class="text-white/60">${object.properties.amenity}</div>
        </div>`,
      };
    }
    return null;
  };

  const handleExportReport = () => {
    if (!analysis) return;

    const reportData = {
      siteId: siteId === "new" ? "Draft Site" : siteId,
      coordinates: { lat, lon },
      score: analysis.site_score,
      traffic_potential: analysis.summary.traffic_potential,
      population: analysis.summary.total_population,
      competitors: analysis.summary.competitors_count,
      magnets: analysis.summary.magnets_count,
      location_warning: analysis.location_warning || "None",
      generated_at: new Date().toISOString(),
    };

    const blob = new Blob([JSON.stringify(reportData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `site-report-${siteId}-${new Date().toISOString().split("T")[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const PanelContent = (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex justify-between items-start">
          <div>
            <div className="text-xs font-bold text-white/40 uppercase tracking-widest mb-1">
              Site Inspector
            </div>
            <h2 className="text-2xl font-bold text-white flex items-center gap-2">
              <MapPin className="text-emerald-400" />
              Site #{siteId === "new" ? "Draft" : siteId}
            </h2>
            <p className="text-white/60 text-sm mt-1">
              Lat: {lat.toFixed(4)}, Lon: {lon.toFixed(4)}
            </p>
          </div>
          <button
            onClick={handleExportReport}
            className="p-2 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors"
            title="Export Report"
          >
            <Download size={20} />
          </button>
        </div>
      </div>

      {/* Location Warning */}
      {analysis?.location_warning && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          <div>
            <h4 className="text-red-400 font-medium text-sm">
              Accessibility Issue
            </h4>
            <p className="text-red-400/80 text-xs mt-1">
              {analysis.location_warning}
            </p>
          </div>
        </div>
      )}

      {/* Demographics Card */}
      <div className="bg-white/5 rounded-2xl p-6 border border-white/10">
        <h3 className="text-lg font-semibold text-white mb-4">Demographics</h3>
        <div className="space-y-4">
          {isAnalysisLoading ? (
            <>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-16" />
                </div>
                <Skeleton className="h-2 w-full rounded-full" />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-16" />
                </div>
                <Skeleton className="h-2 w-full rounded-full" />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-16" />
                </div>
                <Skeleton className="h-2 w-full rounded-full" />
              </div>
            </>
          ) : (
            <>
              <DemographicRow
                label="Residents"
                count={Math.round(
                  (analysis?.summary.total_population || 0) * 0.6
                )}
                total={analysis?.summary.total_population || 1}
                icon={User}
                color="text-blue-400"
                bg="bg-blue-400"
              />
              <DemographicRow
                label="Workers"
                count={Math.round(
                  (analysis?.summary.total_population || 0) * 0.3
                )}
                total={analysis?.summary.total_population || 1}
                icon={Briefcase}
                color="text-purple-400"
                bg="bg-purple-400"
              />
              <DemographicRow
                label="Students"
                count={Math.round(
                  (analysis?.summary.total_population || 0) * 0.1
                )}
                total={analysis?.summary.total_population || 1}
                icon={GraduationCap}
                color="text-yellow-400"
                bg="bg-yellow-400"
              />
            </>
          )}
        </div>
      </div>

      {/* Friction / Risks */}
      <div className="bg-white/5 rounded-2xl p-6 border border-white/10">
        <h3 className="text-lg font-semibold text-white mb-4">Risk Factors</h3>
        <div className="space-y-3">
          <RiskItem label="High Competition" status="warning" />
          <RiskItem label="Flood Zone" status="safe" />
          <RiskItem label="Visibility" status="safe" />
        </div>
      </div>

      {/* Layers Control */}
      <div className="bg-white/5 rounded-2xl p-6 border border-white/10">
        <h3 className="text-lg font-semibold text-white mb-4">Map Layers</h3>
        <div className="space-y-2">
          <LayerToggle
            label="Competitors"
            active={showCompetitors}
            color="bg-green-500"
            onClick={() => setShowCompetitors(!showCompetitors)}
          />
          <LayerToggle
            label="Magnets (Traffic)"
            active={showMagnets}
            color="bg-pink-500"
            onClick={() => setShowMagnets(!showMagnets)}
          />
        </div>

        <div className="mt-4 pt-4 border-t border-white/10">
          <div className="text-xs font-bold text-white/40 uppercase tracking-widest mb-2">
            Legend
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-white border border-black" />
              <span className="text-xs text-white/60">Selected Site</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded bg-blue-500/20 border border-blue-500" />
              <span className="text-xs text-white/60">
                15min Walk Isochrone
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <Shell panelContent={PanelContent}>
      <div className="w-full h-full bg-black relative overflow-hidden">
        <MapContainer
          viewState={viewState}
          onViewStateChange={(e) => setViewState(e.viewState)}
          layers={layers}
          getTooltip={getTooltip}
        />

        {/* Floating Score Card (Always Visible) */}
        <div className="absolute top-6 right-6 w-64 bg-black/80 backdrop-blur-xl border border-white/10 rounded-2xl p-6 shadow-2xl z-50">
          <div className="flex justify-between items-start mb-4">
            <h3 className="text-lg font-semibold text-white">
              Potential Score
            </h3>
            <div className="text-3xl font-bold text-emerald-400">
              {analysis?.site_score}/100
            </div>
          </div>

          <div className="h-32 w-full relative">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={[
                    { value: analysis?.site_score },
                    { value: 100 - (analysis?.site_score || 0) },
                  ]}
                  cx="50%"
                  cy="100%"
                  startAngle={180}
                  endAngle={0}
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={0}
                  dataKey="value"
                >
                  <Cell fill="#34d399" />
                  <Cell fill="#333" />
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-white/40 text-xs">
              AI Confidence: 92%
            </div>
          </div>

          <div className="mt-4 text-sm text-white/70 bg-white/5 p-3 rounded border border-white/5">
            <span className="text-emerald-400 font-bold">Why?</span> Boosted by
            high student traffic, penalized by{" "}
            {analysis?.summary.competitors_count} nearby rivals.
          </div>
        </div>
      </div>
    </Shell>
  );
}

function DemographicRow({ label, count, total, icon: Icon, color, bg }: any) {
  const percentage = Math.round((count / total) * 100);
  return (
    <div>
      <div className="flex justify-between text-sm text-white/80 mb-1">
        <div className="flex items-center gap-2">
          <Icon size={14} className={color} />
          {label}
        </div>
        <span>
          {count.toLocaleString()} ({percentage}%)
        </span>
      </div>
      <div className="h-2 w-full bg-white/10 rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full", bg)}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

function LayerToggle({
  label,
  active,
  color,
  onClick,
}: {
  label: string;
  active: boolean;
  color: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full flex items-center justify-between p-3 rounded-lg transition-all border",
        active
          ? "bg-white/10 border-white/10"
          : "bg-transparent border-transparent hover:bg-white/5"
      )}
    >
      <div className="flex items-center gap-3">
        <div
          className={cn(
            "w-3 h-3 rounded-full shadow-[0_0_10px_currentColor]",
            color,
            !active && "opacity-20 shadow-none"
          )}
        />
        <span
          className={cn(
            "text-sm font-medium",
            active ? "text-white" : "text-white/50"
          )}
        >
          {label}
        </span>
      </div>
      {active ? (
        <Eye size={16} className="text-white/70" />
      ) : (
        <EyeOff size={16} className="text-white/30" />
      )}
    </button>
  );
}

function RiskItem({
  label,
  status,
}: {
  label: string;
  status: "safe" | "warning" | "danger";
}) {
  return (
    <div className="flex items-center justify-between p-3 bg-black/20 rounded border border-white/5">
      <span className="text-white/80 text-sm">{label}</span>
      {status === "safe" && (
        <div className="flex items-center gap-1 text-emerald-400 text-xs font-bold">
          <CheckCircle size={14} /> LOW RISK
        </div>
      )}
      {status === "warning" && (
        <div className="flex items-center gap-1 text-yellow-400 text-xs font-bold">
          <AlertTriangle size={14} /> MEDIUM
        </div>
      )}
      {status === "danger" && (
        <div className="flex items-center gap-1 text-red-400 text-xs font-bold">
          <AlertTriangle size={14} /> HIGH RISK
        </div>
      )}
    </div>
  );
}
