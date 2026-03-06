import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Target, SlidersHorizontal, Home, MapPin, Layers } from "lucide-react";
import { cn } from "@/lib/utils";
import { keepPreviousViewStateIfSame } from "@/lib/mapViewState";
import { MapContainer } from "@/components/MapContainer";
import { AICommandBar, AIExpandedPanel } from "@/components/ai";
import { PropertyPopup } from "@/components/PropertyPopup";
import { usePropertyExplorer } from "@/hooks/usePropertyExplorer";
import { useMapLayers } from "@/hooks/useMapLayers";
import { ExplorerPanel } from "@/components/explorer/ExplorerPanel";
import { OverlayControls } from "@/components/explorer/OverlayControls";
import { FloatingPanel } from "@/components/ui/floating-panel";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";

export const Route = createFileRoute("/_authenticated/")({
  component: PropertyExplorer,
  validateSearch: (search: Record<string, unknown>) => {
    return {
      district:
        typeof search.district === "string" ? search.district : undefined,
    };
  },
});

function PropertyExplorer() {
  const { district: districtFromUrl } = Route.useSearch();

  const explorer = usePropertyExplorer(districtFromUrl);

  const { layers, getTooltip } = useMapLayers({
    housePrices: explorer.housePrices,
    schools: explorer.schools,
    transitLines: explorer.transitLines,
    h3Data: explorer.h3Data,
    overlays: explorer.overlays,
    viewState: explorer.viewState,
    propertyFilters: explorer.propertyFilters,
    chatAttachments: explorer.chatAttachments,
    selectionMode: explorer.selectionMode,
    bboxCorners: explorer.bboxCorners,
    h3Metric: explorer.h3Metric,
  });

  // Track which floating panels are visible
  const [panels, setPanels] = useState({
    explorer: true,
    overlays: true,
    legends: true,
  });

  const togglePanel = (key: keyof typeof panels) =>
    setPanels((p) => ({ ...p, [key]: !p[key] }));

  // Count hidden panels for the restore bar
  const hiddenPanels = Object.entries(panels).filter(([, v]) => !v);

  return (
    <>
      <div className="w-full h-[calc(100vh-4rem)] bg-background relative overflow-hidden">
        {/* Full-screen Map */}
        <MapContainer
          viewState={explorer.viewState}
          onViewStateChange={({ viewState: next }) =>
            explorer.setViewState((previous) =>
              keepPreviousViewStateIfSame(previous, next)
            )
          }
          layers={layers}
          getTooltip={getTooltip}
          onClick={explorer.handleMapClick}
          selectionMode={explorer.selectionMode}
        />

        {/* Floating Explorer Panel -- desktop only */}
        {panels.explorer && (
          <FloatingPanel
            title="Property Explorer"
            icon={<Home className="h-3.5 w-3.5 text-primary" />}
            defaultPosition={{ top: 16, left: 16 }}
            className="hidden md:block w-80"
            maxHeight="calc(100vh - 120px)"
            contentClassName="p-4"
            onClose={() => togglePanel("explorer")}
          >
            <ExplorerPanel
              propertyFilters={explorer.propertyFilters}
              setPropertyFilters={explorer.setPropertyFilters}
              openSections={explorer.openSections}
              setOpenSections={explorer.setOpenSections}
              overlays={explorer.overlays}
              setOverlays={explorer.setOverlays}
              h3Metric={explorer.h3Metric}
              setH3Metric={explorer.setH3Metric}
            />
          </FloatingPanel>
        )}

        {/* Mobile filter sheet */}
        <div className="md:hidden absolute bottom-20 left-4 z-40">
          <Sheet>
            <SheetTrigger asChild>
              <button
                type="button"
                className="flex items-center gap-2 bg-card/95 backdrop-blur-xl border border-border rounded-full px-4 py-2.5 shadow-lg text-sm font-medium text-foreground"
              >
                <SlidersHorizontal className="h-4 w-4" />
                Filters
              </button>
            </SheetTrigger>
            <SheetContent
              side="bottom"
              className="h-[80vh] overflow-auto rounded-t-2xl"
            >
              <ExplorerPanel
                propertyFilters={explorer.propertyFilters}
                setPropertyFilters={explorer.setPropertyFilters}
                openSections={explorer.openSections}
                setOpenSections={explorer.setOpenSections}
                overlays={explorer.overlays}
                setOverlays={explorer.setOverlays}
                h3Metric={explorer.h3Metric}
                setH3Metric={explorer.setH3Metric}
              />
            </SheetContent>
          </Sheet>
        </div>

        {/* Floating Overlay Controls */}
        {panels.overlays && (
          <FloatingPanel
            title="Layers"
            icon={<Layers className="h-3.5 w-3.5 text-muted-foreground" />}
            defaultPosition={{ top: 16, right: 16 }}
            collapsible={false}
            className="hidden md:block"
            contentClassName="px-2 py-1"
            onClose={() => togglePanel("overlays")}
          >
            <OverlayControls
              overlays={explorer.overlays}
              setOverlays={explorer.setOverlays}
            />
          </FloatingPanel>
        )}

        {/* Property Count Badge */}
        <div className="absolute top-6 left-1/2 -translate-x-1/2 z-40 bg-card/90 backdrop-blur-md border border-border rounded-full px-4 py-2 shadow-lg">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Home className="w-3 h-3" />
            <span>
              {explorer.housePrices?.count || 0} properties |{" "}
              {explorer.housePrices?.items?.length || 0} shown
            </span>
          </div>
        </div>

        {/* Floating Legends Panel */}
        {panels.legends && (
          <FloatingPanel
            title="Legends"
            icon={<MapPin className="h-3.5 w-3.5 text-muted-foreground" />}
            defaultPosition={{ top: 96, right: 16 }}
            draggable
            collapsible
            closable
            className="min-w-44 hidden md:block"
            contentClassName="p-3"
            onClose={() => togglePanel("legends")}
          >
            <div className="space-y-4">
              <div className="space-y-2">
                <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Price
                </div>
                <PriceLegendContent
                  minPrice={explorer.propertyFilters.minPrice}
                  maxPrice={explorer.propertyFilters.maxPrice}
                />
              </div>
              <div className="h-px bg-border/60" />
              <div className="space-y-2">
                <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Map
                </div>
                <MapLegendContent
                  showHouses={true}
                  showPOIs={explorer.overlays.pois}
                />
              </div>
            </div>
          </FloatingPanel>
        )}

        {/* Restore hidden panels bar */}
        {hiddenPanels.length > 0 && (
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-40 hidden md:flex items-center gap-1 bg-card/95 backdrop-blur-xl border border-border rounded-full px-2 py-1.5 shadow-lg">
            <span className="text-[10px] text-muted-foreground px-1">Show:</span>
            {hiddenPanels.map(([key]) => (
              <button
                key={key}
                type="button"
                onClick={() => togglePanel(key as keyof typeof panels)}
                className="px-2.5 py-1 text-[10px] font-medium text-muted-foreground hover:text-foreground bg-muted/50 hover:bg-muted rounded-full transition-colors capitalize"
              >
                {key === "legends" ? "Legends" : key}
              </button>
            ))}
          </div>
        )}

        {/* Property Popup */}
        <PropertyPopup
          property={explorer.selectedProperty}
          position={explorer.popupPosition}
          onClose={() => {
            explorer.setSelectedProperty(null);
            explorer.setPopupPosition(null);
          }}
          onAddToChat={explorer.handleAddPropertyToChat}
        />

        {/* Selection Mode Overlay */}
        {explorer.selectionMode !== "none" && (
          <div className="pointer-events-none fixed inset-0 z-[100] flex items-center justify-center">
            <div
              className={cn(
                "absolute top-24 left-1/2 -translate-x-1/2 px-6 py-3 rounded-full font-bold shadow-2xl backdrop-blur-md border-2 animate-bounce-slight transition-colors",
                explorer.selectionMode === "location"
                  ? "bg-primary border-primary/70 text-primary-foreground shadow-primary/30"
                  : "bg-ai-accent border-ai-accent/70 text-ai-accent-foreground shadow-ai-accent/30"
              )}
            >
              <div className="flex items-center gap-2">
                <Target
                  size={20}
                  className="animate-ping absolute opacity-50"
                />
                <Target size={20} />
                <span>
                  {explorer.selectionMode === "location"
                    ? "CLICK EXACT LOCATION"
                    : `CLICK CORNER ${explorer.bboxCorners.length + 1} OF 4`}
                </span>
              </div>
              <div className="text-[10px] font-normal opacity-90 text-center mt-1">
                Press ESC to cancel
              </div>
            </div>
          </div>
        )}
      </div>

      {/* AI Command Bar -- always visible at bottom */}
      <AICommandBar
        input={explorer.aiInput}
        onInputChange={explorer.setAiInput}
        onSubmit={explorer.handleAISubmit}
        attachments={explorer.chatAttachments}
        selectionMode={explorer.selectionMode}
        isExpanded={explorer.isAIExpanded}
        isRunning={explorer.isAIRunning}
        onToggleExpanded={() =>
          explorer.setIsAIExpanded(!explorer.isAIExpanded)
        }
        onPickLocation={() => explorer.setSelectionMode("location")}
        onPickBbox={() => explorer.setSelectionMode("bbox")}
        onRemoveAttachment={(id) =>
          explorer.setChatAttachments((prev) =>
            prev.filter((a) => a.id !== id)
          )
        }
      />

      {/* AI Expanded Panel -- conversation history */}
      <AIExpandedPanel
        isExpanded={explorer.isAIExpanded}
        messages={explorer.aiMessages}
        onPropertyClick={(property) => {
          const latitude = property.lat;
          const longitude = property.lon;
          if (latitude != null && longitude != null) {
            explorer.setViewState((prev) => ({
              ...prev,
              latitude,
              longitude,
              zoom: 15,
              transitionDuration: 500,
            }));
          }
        }}
      />
    </>
  );
}

/* ------------------------------------------------
   Inline content components (extracted from wrappers)
   ------------------------------------------------ */

function PriceLegendContent({
  minPrice,
  maxPrice,
}: {
  minPrice: number;
  maxPrice: number;
}) {
  const fmt = (v: number) =>
    v >= 1_000_000
      ? `${(v / 1_000_000).toFixed(1)}M`
      : `${(v / 1_000).toFixed(0)}K`;

  return (
    <div>
      <div className="text-[10px] text-muted-foreground mb-2 font-medium">
        Price (THB)
      </div>
      <div
        className="h-3 rounded-full mb-1"
        style={{
          background:
            "linear-gradient(to right, rgb(50, 200, 50), rgb(255, 200, 50), rgb(255, 50, 50))",
        }}
      />
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>{fmt(minPrice)}</span>
        <span>{fmt(maxPrice)}</span>
      </div>
    </div>
  );
}

function MapLegendContent({
  showHouses,
  showPOIs,
}: {
  showHouses: boolean;
  showPOIs: boolean;
}) {
  if (!showHouses && !showPOIs) return null;

  const POI_TYPES = [
    { color: "#8B5CF6", label: "School" },
    { color: "#EAB308", label: "Transit" },
    { color: "#22C55E", label: "Bus Stop" },
    { color: "#1E3A8A", label: "Police" },
    { color: "#9333EA", label: "Museum" },
    { color: "#06B6D4", label: "Water" },
    { color: "#F97316", label: "Gas" },
    { color: "#EF4444", label: "Traffic" },
    { color: "#EC4899", label: "Tourism" },
  ];

  return (
    <div className="space-y-3">
      {showHouses && (
        <div className="space-y-1.5">
          <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
            Property Prices
          </div>
          <div className="h-2 rounded-full bg-gradient-to-r from-green-500 via-yellow-500 to-red-500" />
          <div className="flex justify-between text-[9px] text-muted-foreground">
            <span>Low</span>
            <span>High</span>
          </div>
        </div>
      )}
      {showPOIs && (
        <div className="space-y-1.5">
          <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
            Points of Interest
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1">
            {POI_TYPES.map(({ color, label }) => (
              <div
                key={label}
                className="flex items-center gap-1.5 text-[10px] text-foreground/80"
              >
                <div
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: color }}
                />
                <span className="truncate">{label}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
