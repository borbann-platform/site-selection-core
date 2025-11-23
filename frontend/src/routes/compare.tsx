import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQueries } from "@tanstack/react-query";
import { MapContainer } from "../components/MapContainer";
import { Shell } from "../components/Shell";
import {
  Trophy,
  Download,
  MapPin,
  MousePointerClick,
  X,
  AlertTriangle,
} from "lucide-react";
import { GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";

import { cn } from "../lib/utils";
import { useState, useMemo, useEffect } from "react";
import { api } from "../lib/api";

interface CompareSearch {
  lat1: number;
  lon1: number;
  lat2: number;
  lon2: number;
}

export const Route = createFileRoute("/compare")({
  component: BattleRoom,
  validateSearch: (search: Record<string, unknown>): CompareSearch => {
    const getNum = (val: unknown, fallback: number) => {
      const n = Number(val);
      return !isNaN(n) && n !== 0 ? n : fallback;
    };
    return {
      lat1: getNum(search.lat1, 13.7444),
      lon1: getNum(search.lon1, 100.5349),
      lat2: getNum(search.lat2, 13.78),
      lon2: getNum(search.lon2, 100.5449),
    };
  },
});

function BattleRoom() {
  const navigate = useNavigate();
  const { lat1, lon1, lat2, lon2 } = Route.useSearch();
  const [pickingMode, setPickingMode] = useState<"A" | "B" | null>(null);

  const [viewStateA, setViewStateA] = useState<any>({
    longitude: lon1,
    latitude: lat1,
    zoom: 13,
    pitch: 0,
    bearing: 0,
  });

  const [viewStateB, setViewStateB] = useState<any>({
    longitude: lon2,
    latitude: lat2,
    zoom: 13,
    pitch: 0,
    bearing: 0,
  });

  // Sync view state when props change (e.g. after picking new location)
  useEffect(() => {
    setViewStateA((prev: any) => ({
      ...prev,
      longitude: lon1,
      latitude: lat1,
    }));
  }, [lon1, lat1]);

  useEffect(() => {
    setViewStateB((prev: any) => ({
      ...prev,
      longitude: lon2,
      latitude: lat2,
    }));
  }, [lon2, lat2]);

  const handleMapClick = (side: "A" | "B", info: any) => {
    if (pickingMode === side && info.coordinate) {
      const [lon, lat] = info.coordinate;
      navigate({
        search: (prev) => ({
          ...prev,
          [side === "A" ? "lat1" : "lat2"]: lat,
          [side === "A" ? "lon1" : "lon2"]: lon,
        }),
      });
      setPickingMode(null);
    }
  };

  // Fetch data for both sites
  const results = useQueries({
    queries: [
      // Site Details (Analyze instead of getSiteDetails)
      {
        queryKey: ["analyze", lat1, lon1],
        queryFn: () =>
          api.analyzeSite({
            latitude: lat1,
            longitude: lon1,
            target_category: "competitor",
            radius_meters: 2000,
          }),
      },
      {
        queryKey: ["analyze", lat2, lon2],
        queryFn: () =>
          api.analyzeSite({
            latitude: lat2,
            longitude: lon2,
            target_category: "competitor",
            radius_meters: 2000,
          }),
      },
      // Isochrones
      {
        queryKey: ["isochrone", lat1, lon1],
        queryFn: () =>
          api.getIsochrone({
            latitude: lat1,
            longitude: lon1,
            minutes: 15,
            mode: "walk",
          }),
      },
      {
        queryKey: ["isochrone", lat2, lon2],
        queryFn: () =>
          api.getIsochrone({
            latitude: lat2,
            longitude: lon2,
            minutes: 15,
            mode: "walk",
          }),
      },
      // Competitors
      {
        queryKey: ["nearby", lat1, lon1, "competitors"],
        queryFn: () =>
          api.getNearby({
            latitude: lat1,
            longitude: lon1,
            radius_meters: 2000,
            categories: ["competitor"],
          }),
      },
      {
        queryKey: ["nearby", lat2, lon2, "competitors"],
        queryFn: () =>
          api.getNearby({
            latitude: lat2,
            longitude: lon2,
            radius_meters: 2000,
            categories: ["competitor"],
          }),
      },
      // Magnets
      {
        queryKey: ["nearby", lat1, lon1, "magnets"],
        queryFn: () =>
          api.getNearby({
            latitude: lat1,
            longitude: lon1,
            radius_meters: 2000,
            categories: ["mall", "train_station", "university"],
          }),
      },
      {
        queryKey: ["nearby", lat2, lon2, "magnets"],
        queryFn: () =>
          api.getNearby({
            latitude: lat2,
            longitude: lon2,
            radius_meters: 2000,
            categories: ["mall", "train_station", "university"],
          }),
      },
    ],
  });

  const siteA = results[0].data;
  const siteB = results[1].data;
  const isochroneA = results[2].data;
  const isochroneB = results[3].data;
  const competitorsA = results[4].data;
  const competitorsB = results[5].data;
  const magnetsA = results[6].data;
  const magnetsB = results[7].data;

  const isLoading = results.some((r) => r.isLoading);

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

  const layersA = useMemo(() => {
    return [
      isochroneA &&
        new GeoJsonLayer({
          id: "isochrone-a",
          data: isochroneA,
          stroked: true,
          filled: true,
          lineWidthMinPixels: 2,
          getFillColor: [0, 100, 255, 40],
          getLineColor: [0, 100, 255, 200],
        }),
      competitorsA &&
        new ScatterplotLayer({
          id: "competitors-a",
          data: competitorsA.features,
          getPosition: (d: any) => d.geometry.coordinates,
          getFillColor: [50, 200, 50], // Green
          getRadius: 30,
          opacity: 0.8,
        }),
      magnetsA &&
        new ScatterplotLayer({
          id: "magnets-a",
          data: magnetsA.features,
          getPosition: (d: any) => d.geometry.coordinates,
          getFillColor: [255, 0, 128], // Pink
          getRadius: 40,
          opacity: 0.8,
        }),
      new GeoJsonLayer({
        id: "site-marker-a",
        data: {
          type: "Feature",
          geometry: {
            type: "Point",
            coordinates: [lon1, lat1],
          },
        } as any,
        pointRadiusMinPixels: 10,
        getFillColor: [255, 255, 255],
        getLineColor: [0, 0, 0],
        stroked: true,
        lineWidthMinPixels: 2,
      }),
    ].filter(Boolean);
  }, [isochroneA, competitorsA, magnetsA, lat1, lon1]);

  const layersB = useMemo(() => {
    return [
      isochroneB &&
        new GeoJsonLayer({
          id: "isochrone-b",
          data: isochroneB,
          stroked: true,
          filled: true,
          lineWidthMinPixels: 2,
          getFillColor: [0, 100, 255, 40],
          getLineColor: [0, 100, 255, 200],
        }),
      competitorsB &&
        new ScatterplotLayer({
          id: "competitors-b",
          data: competitorsB.features,
          getPosition: (d: any) => d.geometry.coordinates,
          getFillColor: [50, 200, 50], // Green
          getRadius: 30,
          opacity: 0.8,
        }),
      magnetsB &&
        new ScatterplotLayer({
          id: "magnets-b",
          data: magnetsB.features,
          getPosition: (d: any) => d.geometry.coordinates,
          getFillColor: [255, 0, 128], // Pink
          getRadius: 40,
          opacity: 0.8,
        }),
      new GeoJsonLayer({
        id: "site-marker-b",
        data: {
          type: "Feature",
          geometry: {
            type: "Point",
            coordinates: [lon2, lat2],
          },
        } as any,
        pointRadiusMinPixels: 10,
        getFillColor: [255, 255, 255],
        getLineColor: [0, 0, 0],
        stroked: true,
        lineWidthMinPixels: 2,
      }),
    ].filter(Boolean);
  }, [isochroneB, competitorsB, magnetsB, lat2, lon2]);

  const handleExportComparison = () => {
    if (!siteA || !siteB) return;

    const reportData = {
      type: "Site Comparison Report",
      generated_at: new Date().toISOString(),
      winner: winner,
      site_a: {
        coordinates: { lat: lat1, lon: lon1 },
        score: siteA.site_score,
        traffic: siteA.summary.traffic_potential,
        competitors: siteA.summary.competitors_count,
        magnets: siteA.summary.magnets_count,
        warning: siteA.location_warning || "None",
      },
      site_b: {
        coordinates: { lat: lat2, lon: lon2 },
        score: siteB.site_score,
        traffic: siteB.summary.traffic_potential,
        competitors: siteB.summary.competitors_count,
        magnets: siteB.summary.magnets_count,
        warning: siteB.location_warning || "None",
      },
    };

    const blob = new Blob([JSON.stringify(reportData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `comparison-report-${new Date().toISOString().split("T")[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (isLoading || !siteA || !siteB)
    return <div className="text-white p-8">Loading Battle Room...</div>;

  const winner = siteA.site_score > siteB.site_score ? "A" : "B";

  return (
    <Shell>
      <div className="h-full w-full flex flex-col bg-black">
        {/* Header */}
        <header className="h-16 border-b border-white/10 flex items-center justify-between px-6 bg-black/50 backdrop-blur-sm z-10">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-bold text-white tracking-tight">
              Battle Room
            </h1>
            <div className="h-4 w-px bg-white/20" />
            <div className="text-sm text-white/60">
              Comparing 2 Potential Sites
            </div>
          </div>
          <button
            onClick={handleExportComparison}
            className="bg-white text-black px-4 py-1.5 rounded text-sm font-bold flex items-center gap-2 hover:bg-gray-200 transition-colors"
          >
            <Download size={16} /> Export Report
          </button>
        </header>

        {/* Split View */}
        <div className="flex-1 flex relative">
          {/* Left Map (Site A) */}
          <div
            className={cn(
              "flex-1 relative border-r border-white/10 group",
              pickingMode === "A" && "ring-2 ring-emerald-500 z-30"
            )}
          >
            <MapContainer
              viewState={viewStateA}
              onViewStateChange={(e) => setViewStateA(e.viewState)}
              layers={layersA}
              getTooltip={getTooltip}
              onClick={(info) => handleMapClick("A", info)}
            />
            <div className="absolute top-4 left-4 flex items-center gap-2">
              <div className="bg-black/80 backdrop-blur px-3 py-1 rounded text-sm font-bold text-white border border-white/10">
                Site A
              </div>
              <button
                onClick={() => setPickingMode(pickingMode === "A" ? null : "A")}
                className={cn(
                  "p-1.5 rounded bg-black/80 border border-white/10 hover:bg-white/20 transition-colors",
                  pickingMode === "A"
                    ? "bg-emerald-500 text-white border-emerald-500"
                    : "text-white/60"
                )}
                title="Pick Location"
              >
                {pickingMode === "A" ? (
                  <X size={14} />
                ) : (
                  <MousePointerClick size={14} />
                )}
              </button>
            </div>
            {pickingMode === "A" && (
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none text-emerald-500 font-bold text-shadow-lg animate-pulse bg-black/50 px-4 py-2 rounded-full backdrop-blur">
                Click Map to Set Location
              </div>
            )}
            {winner === "A" && (
              <div className="absolute inset-0 border-4 border-yellow-500/50 pointer-events-none z-10" />
            )}
          </div>

          {/* Right Map (Site B) */}
          <div
            className={cn(
              "flex-1 relative group",
              pickingMode === "B" && "ring-2 ring-emerald-500 z-30"
            )}
          >
            <MapContainer
              viewState={viewStateB}
              onViewStateChange={(e) => setViewStateB(e.viewState)}
              layers={layersB}
              getTooltip={getTooltip}
              onClick={(info) => handleMapClick("B", info)}
            />
            <div className="absolute top-4 left-4 flex items-center gap-2">
              <div className="bg-black/80 backdrop-blur px-3 py-1 rounded text-sm font-bold text-white border border-white/10">
                Site B
              </div>
              <button
                onClick={() => setPickingMode(pickingMode === "B" ? null : "B")}
                className={cn(
                  "p-1.5 rounded bg-black/80 border border-white/10 hover:bg-white/20 transition-colors",
                  pickingMode === "B"
                    ? "bg-emerald-500 text-white border-emerald-500"
                    : "text-white/60"
                )}
                title="Pick Location"
              >
                {pickingMode === "B" ? (
                  <X size={14} />
                ) : (
                  <MousePointerClick size={14} />
                )}
              </button>
            </div>
            {pickingMode === "B" && (
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none text-emerald-500 font-bold text-shadow-lg animate-pulse bg-black/50 px-4 py-2 rounded-full backdrop-blur">
                Click Map to Set Location
              </div>
            )}
            <div className="absolute top-4 left-4 bg-black/80 backdrop-blur px-3 py-1 rounded text-sm font-bold text-white border border-white/10">
              Site B
            </div>
            {winner === "B" && (
              <div className="absolute inset-0 border-4 border-yellow-500/50 pointer-events-none z-10" />
            )}
          </div>

          {/* Floating Comparison Widget (Center) */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] bg-black/90 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl overflow-hidden z-20">
            <div className="grid grid-cols-3 text-center border-b border-white/10 bg-white/5">
              <div className="p-4 font-bold text-white">Site A</div>
              <div className="p-4 text-xs font-bold text-white/40 uppercase tracking-widest flex items-center justify-center">
                VS
              </div>
              <div className="p-4 font-bold text-white">Site B</div>
            </div>

            <div className="divide-y divide-white/10">
              {/* Score Row */}
              <div className="grid grid-cols-3 items-center p-4">
                <div
                  className={cn(
                    "text-3xl font-bold text-center flex items-center justify-center gap-2",
                    winner === "A" ? "text-yellow-400" : "text-white/60"
                  )}
                >
                  {siteA.site_score}
                  {siteA.location_warning && (
                    <div className="group relative">
                      <AlertTriangle className="w-5 h-5 text-red-500" />
                      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-red-900/90 text-white text-xs rounded shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
                        {siteA.location_warning}
                      </div>
                    </div>
                  )}
                </div>
                <div className="text-xs text-center text-white/40">
                  POTENTIAL SCORE
                </div>
                <div
                  className={cn(
                    "text-3xl font-bold text-center flex items-center justify-center gap-2",
                    winner === "B" ? "text-yellow-400" : "text-white/60"
                  )}
                >
                  {siteB.site_score}
                  {siteB.location_warning && (
                    <div className="group relative">
                      <AlertTriangle className="w-5 h-5 text-red-500" />
                      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-red-900/90 text-white text-xs rounded shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
                        {siteB.location_warning}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Competitors Row */}
              <div className="grid grid-cols-3 items-center p-4">
                <div className="text-center text-white">
                  {siteA.summary.competitors_count}
                </div>
                <div className="text-xs text-center text-white/40">
                  COMPETITORS
                </div>
                <div className="text-center text-white">
                  {siteB.summary.competitors_count}
                </div>
              </div>

              {/* Magnets Row */}
              <div className="grid grid-cols-3 items-center p-4">
                <div className="text-center text-white">
                  {siteA.summary.magnets_count}
                </div>
                <div className="text-xs text-center text-white/40">MAGNETS</div>
                <div className="text-center text-white">
                  {siteB.summary.magnets_count}
                </div>
              </div>

              {/* Traffic Row */}
              <div className="grid grid-cols-3 items-center p-4">
                <div className="text-center text-emerald-400 font-bold">
                  {siteA.summary.traffic_potential}
                </div>
                <div className="text-xs text-center text-white/40">TRAFFIC</div>
                <div className="text-center text-yellow-400 font-bold">
                  {siteB.summary.traffic_potential}
                </div>
              </div>
            </div>

            {/* Winner Banner */}
            <div className="bg-yellow-500/20 p-3 text-center border-t border-yellow-500/30">
              <div className="text-yellow-400 font-bold flex items-center justify-center gap-2">
                <Trophy size={16} />
                Site {winner} is the Winner
              </div>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}

export default BattleRoom;
