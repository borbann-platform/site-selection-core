import { createFileRoute } from "@tanstack/react-router";
import { useQueries } from "@tanstack/react-query";
import { MapContainer } from "../components/MapContainer";
import { Shell } from "../components/Shell";
import { Trophy, Download } from "lucide-react";

import { cn } from "../lib/utils";
import { useState } from "react";
import { api } from "../lib/api";

export const Route = createFileRoute("/compare")({
  component: BattleRoom,
});

const SITE_A_ID = "A";
const SITE_B_ID = "B";

function BattleRoom() {
  const [viewStateA, setViewStateA] = useState<any>({
    longitude: 100.5349,
    latitude: 13.7444,
    zoom: 13,
    pitch: 0,
    bearing: 0,
  });

  const [viewStateB, setViewStateB] = useState<any>({
    longitude: 100.5449,
    latitude: 13.78,
    zoom: 13,
    pitch: 0,
    bearing: 0,
  });

  // Fetch data for both sites
  const results = useQueries({
    queries: [
      {
        queryKey: ["site", SITE_A_ID],
        queryFn: () => api.getSiteDetails(SITE_A_ID),
      },
      {
        queryKey: ["site", SITE_B_ID],
        queryFn: () => api.getSiteDetails(SITE_B_ID),
      },
    ],
  });

  const siteA = results[0].data;
  const siteB = results[1].data;
  const isLoading = results.some((r) => r.isLoading);

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
          <button className="bg-white text-black px-4 py-1.5 rounded text-sm font-bold flex items-center gap-2 hover:bg-gray-200 transition-colors">
            <Download size={16} /> Export Report
          </button>
        </header>

        {/* Split View */}
        <div className="flex-1 flex relative">
          {/* Left Map (Site A) */}
          <div className="flex-1 relative border-r border-white/10 group">
            <MapContainer
              viewState={viewStateA}
              onViewStateChange={(e) => setViewStateA(e.viewState)}
              layers={[]}
            />
            <div className="absolute top-4 left-4 bg-black/80 backdrop-blur px-3 py-1 rounded text-sm font-bold text-white border border-white/10">
              Site A
            </div>
            {winner === "A" && (
              <div className="absolute inset-0 border-4 border-yellow-500/50 pointer-events-none z-10" />
            )}
          </div>

          {/* Right Map (Site B) */}
          <div className="flex-1 relative group">
            <MapContainer
              viewState={viewStateB}
              onViewStateChange={(e) => setViewStateB(e.viewState)}
              layers={[]}
            />
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
                    "text-3xl font-bold text-center",
                    winner === "A" ? "text-yellow-400" : "text-white/60"
                  )}
                >
                  {siteA.site_score}
                </div>
                <div className="text-xs text-center text-white/40">
                  POTENTIAL SCORE
                </div>
                <div
                  className={cn(
                    "text-3xl font-bold text-center",
                    winner === "B" ? "text-yellow-400" : "text-white/60"
                  )}
                >
                  {siteB.site_score}
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
