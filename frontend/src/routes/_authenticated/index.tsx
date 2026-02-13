import { createFileRoute } from "@tanstack/react-router";
import { Target } from "lucide-react";
import { cn } from "@/lib/utils";
import { MapContainer } from "@/components/MapContainer";
import { AICommandBar, AIExpandedPanel } from "@/components/ai";
import { PriceLegend } from "@/components/PriceLegend";
import { PropertyPopup } from "@/components/PropertyPopup";
import { MapLegend } from "@/components/MapLegend";
import { usePropertyExplorer } from "@/hooks/usePropertyExplorer";
import { useMapLayers } from "@/hooks/useMapLayers";
import { ExplorerPanel } from "@/components/explorer/ExplorerPanel";
import { OverlayControls } from "@/components/explorer/OverlayControls";
import { PropertyCount } from "@/components/explorer/PropertyCount";

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

  return (
    <>
      <div className="w-full h-full bg-background relative overflow-hidden">
        {/* Full-screen Map */}
        <MapContainer
          viewState={explorer.viewState}
          onViewStateChange={(e) => explorer.setViewState(e.viewState)}
          layers={layers}
          getTooltip={getTooltip}
          onClick={explorer.handleMapClick}
          selectionMode={explorer.selectionMode}
        />

        {/* Floating Panel -- desktop only */}
        <div className="absolute left-4 top-4 bottom-4 w-80 z-40 bg-card/95 backdrop-blur-xl border border-border rounded-2xl shadow-xl overflow-auto hidden md:block p-4">
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
        </div>

        {/* Floating Overlay Controls -- top-right */}
        <OverlayControls
          overlays={explorer.overlays}
          setOverlays={explorer.setOverlays}
        />

        {/* Property Count Badge */}
        <PropertyCount
          totalCount={explorer.housePrices?.count || 0}
          shownCount={explorer.housePrices?.items?.length || 0}
        />

        {/* Price Legend */}
        <PriceLegend
          minPrice={explorer.propertyFilters.minPrice}
          maxPrice={explorer.propertyFilters.maxPrice}
        />

        {/* Map Legend */}
        <MapLegend showHouses={true} showPOIs={explorer.overlays.pois} />

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
                  ? "bg-brand border-brand/70 text-brand-foreground shadow-brand/30"
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

      {/* AI Expanded Panel -- conversation history + filters */}
      <AIExpandedPanel
        isExpanded={explorer.isAIExpanded}
        messages={explorer.aiMessages}
        filterValues={explorer.aiFilters}
        onFilterChange={explorer.setAiFilters}
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
