import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { MapContainer } from "../components/MapContainer";
import { Shell } from "../components/Shell";
import { HexagonLayer } from "@deck.gl/aggregation-layers";
import { ScatterplotLayer } from "@deck.gl/layers";
import { MVTLayer } from "@deck.gl/geo-layers";
import { GeoJsonLayer } from "@deck.gl/layers";
import { Eye, EyeOff } from "lucide-react";
import { cn } from "../lib/utils";
import { api, API_URL } from "../lib/api";

export const Route = createFileRoute("/")({
  component: GodMode,
});

const BANGKOK_LAT = 13.7563;
const BANGKOK_LON = 100.5018;

function GodMode() {
  const navigate = useNavigate();
  const [viewState, setViewState] = useState<any>({
    longitude: BANGKOK_LON,
    latitude: BANGKOK_LAT,
    zoom: 11,
    pitch: 45,
    bearing: 0,
  });

  const [filters, setFilters] = useState({
    competitors: true,
    schools: false,
    traffic: true,
    allPois: false,
    residential: false,
  });

  const [hexSettings, setHexSettings] = useState({
    radius: 200,
    coverage: 0.9,
    upperPercentile: 100,
  });

  const [mode, setMode] = useState<"hex" | "iso">("hex");
  const [isoCenter, setIsoCenter] = useState<{
    lat: number;
    lon: number;
  } | null>(null);
  const [isoSettings, setIsoSettings] = useState({
    minutes: 15,
    mode: "drive" as "walk" | "drive",
  });

  // Fetch Grid Data
  const { data: gridData } = useQuery({
    queryKey: ["grid"],
    queryFn: api.getGrid,
    enabled: mode === "hex",
  });

  // Fetch Isochrone
  const { data: isoData } = useQuery({
    queryKey: [
      "isochrone",
      isoCenter?.lat,
      isoCenter?.lon,
      isoSettings.minutes,
      isoSettings.mode,
    ],
    queryFn: () =>
      isoCenter
        ? api.getIsochrone({
            latitude: isoCenter.lat,
            longitude: isoCenter.lon,
            minutes: isoSettings.minutes,
            mode: isoSettings.mode,
          })
        : Promise.resolve(null),
    enabled: mode === "iso" && !!isoCenter,
  });

  // Fetch Competitors
  const { data: competitors } = useQuery({
    queryKey: ["nearby", "competitors"],
    queryFn: () =>
      api.getNearby({
        latitude: BANGKOK_LAT,
        longitude: BANGKOK_LON,
        radius_meters: 5000,
        categories: ["competitor"],
      }),
    enabled: filters.competitors,
  });

  // Fetch Schools
  const { data: schools } = useQuery({
    queryKey: ["nearby", "schools"],
    queryFn: () =>
      api.getNearby({
        latitude: BANGKOK_LAT,
        longitude: BANGKOK_LON,
        radius_meters: 5000,
        categories: ["school"],
      }),
    enabled: filters.schools,
  });

  const layers = useMemo(() => {
    return [
      mode === "hex" &&
        gridData &&
        new HexagonLayer({
          id: "heatmap",
          data: gridData.hexagons,
          getPosition: (d: any) => d.position,
          getElevationWeight: (d: any) => d.value,
          getColorWeight: (d: any) => d.value,
          elevationScale: 0,
          extruded: false,
          radius: hexSettings.radius,
          coverage: hexSettings.coverage,
          upperPercentile: hexSettings.upperPercentile,
          material: {
            ambient: 0.64,
            diffuse: 0.6,
            shininess: 32,
            specularColor: [51, 51, 51],
          },
          colorRange: [
            [26, 152, 80], // Low - Green
            [145, 207, 96],
            [217, 239, 139],
            [254, 224, 139],
            [252, 141, 89],
            [215, 48, 39], // High - Red
          ],
          pickable: true,
          opacity: 0.6,
        }),
      mode === "iso" &&
        isoData &&
        new GeoJsonLayer({
          id: "iso-layer",
          data: isoData,
          stroked: true,
          filled: true,
          lineWidthMinPixels: 2,
          getFillColor: [0, 100, 255, 40],
          getLineColor: [0, 100, 255, 200],
        }),
      mode === "iso" &&
        isoCenter &&
        new ScatterplotLayer({
          id: "iso-center",
          data: [{ position: [isoCenter.lon, isoCenter.lat] }],
          getPosition: (d: any) => d.position,
          getFillColor: [255, 255, 255],
          getLineColor: [0, 0, 0],
          stroked: true,
          getRadius: 100,
          lineWidthMinPixels: 2,
        }),
      // POI Vector Tiles (Zoomed In)
      new MVTLayer({
        id: "all-pois-layer",
        data: `${API_URL}/analytics/all-pois/tile/{z}/{x}/{y}`,
        minZoom: 13,
        maxZoom: 20,
        visible: filters.allPois,
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 100],
        pointRadiusMinPixels: 3,
        pointRadiusScale: 1,
        getPointRadius: 4,
        getFillColor: (d: any) => {
          const type = d.properties.type;
          if (type === "school") return [0, 128, 255]; // Blue
          if (type === "police_station") return [0, 0, 128]; // Navy
          if (type === "museum") return [128, 0, 128]; // Purple
          if (type === "gas_station") return [255, 165, 0]; // Orange
          if (type === "traffic_point") return [255, 0, 0]; // Red
          if (type === "water_transport") return [0, 255, 255]; // Cyan
          if (type === "tourist_attraction") return [255, 105, 180]; // Pink
          if (type === "bus_shelter") return [0, 255, 0]; // Green
          if (type === "transit_stop") return [255, 215, 0]; // Gold
          return [120, 120, 120]; // Grey default
        },
      }),
      new MVTLayer({
        id: "residential-layer",
        data: `${API_URL}/analytics/residential/tile/{z}/{x}/{y}`,
        minZoom: 13,
        maxZoom: 20,
        visible: filters.residential,
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 100],
        pointRadiusMinPixels: 3,
        pointRadiusScale: 1,
        getPointRadius: 4,
        getFillColor: (d: any) => {
          const type = d.properties.type;
          if (type === "condo_project") return [255, 215, 0]; // Gold
          if (type === "listing") return [0, 255, 255]; // Cyan
          return [120, 120, 120];
        },
      }),
      filters.competitors &&
        competitors &&
        new ScatterplotLayer({
          id: "competitors",
          data: competitors.features,
          getPosition: (d: any) => d.geometry.coordinates,
          getFillColor: [255, 0, 0],
          getRadius: 100,
          pickable: true,
          opacity: 0.8,
        }),
      filters.schools &&
        schools &&
        new ScatterplotLayer({
          id: "schools",
          data: schools.features,
          getPosition: (d: any) => d.geometry.coordinates,
          getFillColor: [0, 100, 255],
          getRadius: 150,
          pickable: true,
          opacity: 0.8,
        }),
    ].filter(Boolean);
  }, [filters, gridData, competitors, schools, hexSettings]);

  const getTooltip = ({ object }: any) => {
    if (!object) return null;

    // Hexagon Layer Tooltip
    if (object.points) {
      return {
        html: `<div class="p-3 bg-zinc-900/90 border border-zinc-700 text-white rounded-lg shadow-xl backdrop-blur-md">
          <div class="font-bold text-emerald-400 mb-1 text-sm">Opportunity Zone</div>
          <div class="text-xs text-zinc-300">Density Score: <span class="font-mono font-bold text-white">${object.points.length}</span></div>
          <div class="text-[10px] text-zinc-500 mt-1">Hexagon Aggregation</div>
        </div>`,
      };
    }

    // MVT Layer (POI) Tooltip
    if (object.properties) {
      const props = object.properties;
      const name = props.name || "Unnamed Location";
      const type = props.type || "Unknown Type";
      const source = props.source || "Unknown Source";
      const price = props.price ? `Price: ${props.price}` : "";

      return {
        html: `<div class="p-3 bg-zinc-900/90 border border-zinc-700 text-white rounded-lg shadow-xl backdrop-blur-md min-w-[200px]">
          <div class="font-bold text-sm mb-1">${name}</div>
          <div class="text-xs font-medium text-zinc-400 mb-2">${type}</div>
          ${price ? `<div class="text-xs text-emerald-400 mb-1">${price}</div>` : ""}
          <div class="grid grid-cols-2 gap-2 text-[10px] text-zinc-400 border-t border-zinc-800 pt-2">
            <div>Source:</div><div class="text-right font-mono text-zinc-500">${source}</div>
          </div>
        </div>`,
      };
    }

    return null;
  };

  const handleMapClick = (info: any) => {
    if (info.coordinate) {
      if (mode === "hex") {
        console.log("Clicked:", info.coordinate);
        navigate({
          to: "/site/$siteId",
          params: { siteId: "new" },
          search: { lat: info.coordinate[1], lon: info.coordinate[0] },
        });
      } else {
        setIsoCenter({ lat: info.coordinate[1], lon: info.coordinate[0] });
      }
    }
  };

  const PanelContent = (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white mb-1">Layers</h2>
        <p className="text-xs text-white/50">Manage map visibility</p>
      </div>

      <div className="space-y-2">
        <LayerToggle
          label="Competitors"
          active={filters.competitors}
          color="bg-red-500"
          onClick={() =>
            setFilters((f) => ({ ...f, competitors: !f.competitors }))
          }
        />
        <LayerToggle
          label="Schools"
          active={filters.schools}
          color="bg-blue-500"
          onClick={() => setFilters((f) => ({ ...f, schools: !f.schools }))}
        />
        <LayerToggle
          label="Traffic Flow"
          active={filters.traffic}
          color="bg-yellow-500"
          onClick={() => setFilters((f) => ({ ...f, traffic: !f.traffic }))}
        />
        <LayerToggle
          label="All POIs"
          active={filters.allPois}
          color="bg-purple-500"
          onClick={() => setFilters((f) => ({ ...f, allPois: !f.allPois }))}
        />
        <LayerToggle
          label="Residential Supply"
          active={filters.residential}
          color="bg-cyan-500"
          onClick={() =>
            setFilters((f) => ({ ...f, residential: !f.residential }))
          }
        />
      </div>

      <div className="pt-6 border-t border-white/10">
        <h3 className="text-sm font-bold text-white mb-3">Analysis Mode</h3>
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => setMode("hex")}
            className={cn(
              "p-3 rounded text-left transition-colors border",
              mode === "hex"
                ? "bg-white/10 border-emerald-500/50"
                : "bg-black/40 hover:bg-white/10 border-white/5"
            )}
          >
            <div
              className={cn(
                "font-bold text-lg",
                mode === "hex" ? "text-emerald-400" : "text-white/40"
              )}
            >
              Hex
            </div>
            <div className="text-[10px] text-white/60">Opportunity Grid</div>
          </button>
          <button
            onClick={() => setMode("iso")}
            className={cn(
              "p-3 rounded text-left transition-colors border",
              mode === "iso"
                ? "bg-white/10 border-emerald-500/50"
                : "bg-black/40 hover:bg-white/10 border-white/5"
            )}
          >
            <div
              className={cn(
                "font-bold text-lg",
                mode === "iso" ? "text-emerald-400" : "text-white/40"
              )}
            >
              Iso
            </div>
            <div className="text-[10px] text-white/60">Travel Time</div>
          </button>
        </div>
      </div>

      {mode === "hex" ? (
        <div className="pt-6 border-t border-white/10">
          <h3 className="text-sm font-bold text-white mb-3">
            Hexagon Settings
          </h3>
          <div className="space-y-4">
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-white/60">
                <span>Radius</span>
                <span>{hexSettings.radius}m</span>
              </div>
              <input
                type="range"
                min="50"
                max="1000"
                step="50"
                value={hexSettings.radius}
                onChange={(e) =>
                  setHexSettings((s) => ({
                    ...s,
                    radius: Number(e.target.value),
                  }))
                }
                className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-emerald-500"
              />
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-white/60">
                <span>Coverage</span>
                <span>{Math.round(hexSettings.coverage * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={hexSettings.coverage}
                onChange={(e) =>
                  setHexSettings((s) => ({
                    ...s,
                    coverage: Number(e.target.value),
                  }))
                }
                className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-emerald-500"
              />
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-white/60">
                <span>Percentile</span>
                <span>{hexSettings.upperPercentile}%</span>
              </div>
              <input
                type="range"
                min="80"
                max="100"
                step="1"
                value={hexSettings.upperPercentile}
                onChange={(e) =>
                  setHexSettings((s) => ({
                    ...s,
                    upperPercentile: Number(e.target.value),
                  }))
                }
                className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-emerald-500"
              />
            </div>
          </div>
        </div>
      ) : (
        <div className="pt-6 border-t border-white/10">
          <h3 className="text-sm font-bold text-white mb-3">
            Isochrone Settings
          </h3>
          <div className="space-y-4">
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-white/60">
                <span>Travel Time</span>
                <span>{isoSettings.minutes} min</span>
              </div>
              <input
                type="range"
                min="5"
                max="60"
                step="5"
                value={isoSettings.minutes}
                onChange={(e) =>
                  setIsoSettings((s) => ({
                    ...s,
                    minutes: Number(e.target.value),
                  }))
                }
                className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-emerald-500"
              />
            </div>
            <div className="flex bg-black/50 rounded-lg p-1 border border-white/10">
              <button
                onClick={() => setIsoSettings((s) => ({ ...s, mode: "walk" }))}
                className={cn(
                  "flex-1 px-3 py-1 rounded text-xs font-bold transition-colors",
                  isoSettings.mode === "walk"
                    ? "bg-white/20 text-white"
                    : "text-white/40 hover:text-white"
                )}
              >
                Walk
              </button>
              <button
                onClick={() => setIsoSettings((s) => ({ ...s, mode: "drive" }))}
                className={cn(
                  "flex-1 px-3 py-1 rounded text-xs font-bold transition-colors",
                  isoSettings.mode === "drive"
                    ? "bg-white/20 text-white"
                    : "text-white/40 hover:text-white"
                )}
              >
                Drive
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="pt-6 border-t border-white/10">
        <h3 className="text-sm font-bold text-white mb-3">Legend</h3>
        <div className="space-y-3">
          <div className="space-y-2">
            <div className="text-xs text-white/40 uppercase tracking-wider font-bold">
              Opportunity Heatmap
            </div>
            <div className="h-2 w-full rounded-full bg-linear-to-r from-green-500 via-yellow-400 to-red-500 opacity-80" />
            <div className="flex justify-between text-[10px] text-white/40">
              <span>Low Density</span>
              <span>High Density</span>
            </div>
          </div>

          <div className="space-y-2 pt-2">
            <div className="text-xs text-white/40 uppercase tracking-wider font-bold">
              Points of Interest
            </div>
            <div className="grid grid-cols-2 gap-2">
              <LegendItem color="bg-pink-500" label="Magnets (Malls)" />
              <LegendItem color="bg-orange-500" label="Transport" />
              <LegendItem color="bg-blue-500" label="Education" />
              <LegendItem color="bg-red-500" label="Health" />
              <LegendItem color="bg-green-500" label="Competitors" />
              <LegendItem color="bg-zinc-500" label="Others" />
            </div>
          </div>
        </div>
      </div>

      <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded text-xs text-blue-200">
        <span className="font-bold">Hint:</span>{" "}
        {mode === "hex"
          ? "Zoom in to see individual POI dots. The heatmap shows aggregated density of opportunities."
          : "Click anywhere on the map to generate a travel-time isochrone from that point."}
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
          onClick={handleMapClick}
        />

        {/* Header Overlay */}
        <div className="absolute top-0 left-0 w-full p-6 bg-linear-to-b from-black/80 to-transparent pointer-events-none pl-24">
          {/* Removed Header Content */}
        </div>
      </div>
    </Shell>
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

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className={cn("w-2 h-2 rounded-full", color)} />
      <span className="text-[10px] text-white/60">{label}</span>
    </div>
  );
}
