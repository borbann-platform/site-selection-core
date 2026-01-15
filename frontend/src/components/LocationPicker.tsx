/**
 * Location Picker Modal - Map-based location selection for property upload.
 * Uses the existing MapContainer with click-to-select functionality.
 */

import { useState, useCallback, useMemo } from "react";
import { MapContainer } from "@/components/MapContainer";
import { ScatterplotLayer } from "@deck.gl/layers";
import { Button } from "@/components/ui/button";
import { X, MapPin, Check, Navigation } from "lucide-react";
import { cn } from "@/lib/utils";

interface LocationPickerProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (location: { lat: number; lon: number }) => void;
  initialLocation?: { lat: number; lon: number } | null;
}

// Bangkok default center
const DEFAULT_CENTER = {
  latitude: 13.7563,
  longitude: 100.5018,
  zoom: 12,
};

export function LocationPicker({
  isOpen,
  onClose,
  onConfirm,
  initialLocation,
}: LocationPickerProps) {
  const [selectedLocation, setSelectedLocation] = useState<{
    lat: number;
    lon: number;
  } | null>(initialLocation || null);

  const [viewState, setViewState] = useState({
    ...DEFAULT_CENTER,
    latitude: initialLocation?.lat || DEFAULT_CENTER.latitude,
    longitude: initialLocation?.lon || DEFAULT_CENTER.longitude,
    zoom: initialLocation ? 15 : DEFAULT_CENTER.zoom,
    pitch: 0,
    bearing: 0,
  });

  const handleMapClick = useCallback(
    (info: { coordinate?: [number, number] }) => {
      if (info.coordinate) {
        setSelectedLocation({
          lon: info.coordinate[0],
          lat: info.coordinate[1],
        });
      }
    },
    []
  );

  const handleConfirm = useCallback(() => {
    if (selectedLocation) {
      onConfirm(selectedLocation);
    }
  }, [selectedLocation, onConfirm]);

  // Create marker layer for selected location
  const layers = useMemo(() => {
    if (!selectedLocation) return [];

    return [
      new ScatterplotLayer({
        id: "selected-location",
        data: [selectedLocation],
        getPosition: (d) => [d.lon, d.lat],
        getFillColor: [16, 185, 129, 255], // Emerald
        getRadius: 50,
        radiusMinPixels: 12,
        radiusMaxPixels: 24,
        pickable: false,
      }),
    ];
  }, [selectedLocation]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <button
        type="button"
        className="absolute inset-0 bg-black/80 backdrop-blur-sm cursor-default"
        onClick={onClose}
        onKeyDown={(e) => e.key === "Escape" && onClose()}
        aria-label="Close location picker"
      />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-4xl h-[80vh] bg-zinc-900 rounded-2xl border border-white/10 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center">
              <MapPin size={16} className="text-emerald-400" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">
                Select Property Location
              </h3>
              <p className="text-xs text-white/50">
                Click on the map to set the location
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
          >
            <X size={18} className="text-white/70" />
          </button>
        </div>

        {/* Map */}
        <div className="flex-1 relative">
          <MapContainer
            viewState={viewState}
            onViewStateChange={({ viewState: vs }) => setViewState(vs)}
            layers={layers}
            onClick={handleMapClick}
            getTooltip={() => null}
          />

          {/* Instructions overlay */}
          {!selectedLocation && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-black/80 backdrop-blur-sm rounded-lg px-4 py-2 border border-white/10">
              <p className="text-sm text-white/80 flex items-center gap-2">
                <Navigation size={14} className="text-emerald-400" />
                Click anywhere on the map to select location
              </p>
            </div>
          )}

          {/* Selected location info */}
          {selectedLocation && (
            <div className="absolute bottom-4 left-4 bg-black/80 backdrop-blur-sm rounded-lg px-4 py-3 border border-emerald-500/30">
              <p className="text-xs text-white/50 mb-1">Selected Location</p>
              <p className="text-sm font-mono text-white">
                {selectedLocation.lat.toFixed(6)}, {selectedLocation.lon.toFixed(6)}
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-white/10 bg-black/40">
          <p className="text-xs text-white/50">
            {selectedLocation
              ? "Location selected. Click Confirm to continue."
              : "No location selected yet."}
          </p>
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={onClose}
              className="border-white/20 bg-white/5 text-white hover:bg-white/10"
            >
              Cancel
            </Button>
            <Button
              onClick={handleConfirm}
              disabled={!selectedLocation}
              className={cn(
                "bg-emerald-500 hover:bg-emerald-600 text-black",
                !selectedLocation && "opacity-50 cursor-not-allowed"
              )}
            >
              <Check size={16} className="mr-1" />
              Confirm Location
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LocationPicker;
