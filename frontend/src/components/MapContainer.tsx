// @ts-nocheck
// TypeScript checks disabled due to complex DeckGL generic types
import React from "react";
import Map, { NavigationControl } from "react-map-gl/maplibre";
import DeckGL from "@deck.gl/react";

interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch?: number;
  bearing?: number;
}

type SelectionMode = "none" | "location" | "bbox";

interface MapContainerProps {
  viewState: ViewState;
  // biome-ignore lint: DeckGL types are complex
  onViewStateChange: (params: any) => void;
  // biome-ignore lint: DeckGL layer types vary
  layers: any[];
  children?: React.ReactNode;
  // biome-ignore lint: DeckGL info types vary
  onClick?: (info: any) => void;
  // biome-ignore lint: DeckGL tooltip types vary
  getTooltip?: (info: any) => any;
  selectionMode?: SelectionMode;
}

const MAP_STYLE =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

export function MapContainer({
  viewState,
  onViewStateChange,
  layers,
  children,
  onClick,
  getTooltip,
  selectionMode = "none",
}: MapContainerProps) {
  // Disable drag/pan in selection modes to allow click-based selection
  const controllerOptions =
    selectionMode !== "none"
      ? { dragPan: false, dragRotate: false, doubleClickZoom: false }
      : true;

  return (
    <div className="relative w-full h-full">
      <DeckGL
        viewState={viewState}
        onViewStateChange={onViewStateChange}
        controller={controllerOptions}
        layers={layers}
        onClick={onClick}
        getTooltip={getTooltip}
      >
        <Map
          {...viewState}
          mapStyle={MAP_STYLE}
          reuseMaps
          attributionControl={false}
        >
          <NavigationControl position="bottom-right" />
        </Map>
      </DeckGL>
      {children}
    </div>
  );
}
