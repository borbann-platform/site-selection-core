// @ts-nocheck
// TypeScript checks disabled due to complex DeckGL generic types
import type * as React from "react";
import MapView, { NavigationControl } from "react-map-gl/maplibre";
import DeckGL from "@deck.gl/react";
import { useTheme } from "../contexts/ThemeContext";

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

const MAP_STYLE_DARK =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const MAP_STYLE_LIGHT =
  "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

export function MapContainer({
  viewState,
  onViewStateChange,
  layers,
  children,
  onClick,
  getTooltip,
  selectionMode = "none",
}: MapContainerProps) {
  const { resolvedTheme } = useTheme();
  const mapStyle = resolvedTheme === "dark" ? MAP_STYLE_DARK : MAP_STYLE_LIGHT;

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
        <MapView
          {...viewState}
          mapStyle={mapStyle}
          reuseMaps
          attributionControl={false}
        >
          <NavigationControl position="bottom-right" />
        </MapView>
      </DeckGL>
      {children}
    </div>
  );
}
