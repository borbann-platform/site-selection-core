import type * as React from "react";
import type { DeckGLProps } from "@deck.gl/react";
import type { MapViewState } from "@deck.gl/core";
import MapView, { NavigationControl } from "react-map-gl/maplibre";
import DeckGL from "@deck.gl/react";
import { useTheme } from "../contexts/ThemeContext";

type ViewState = MapViewState;
type DeckLayers = NonNullable<DeckGLProps["layers"]>;
type DeckViewStateChangeHandler = NonNullable<DeckGLProps["onViewStateChange"]>;
type DeckClickHandler = NonNullable<DeckGLProps["onClick"]>;
type DeckTooltipHandler = NonNullable<DeckGLProps["getTooltip"]>;

type SelectionMode = "none" | "location" | "bbox";

export type MapTileStyle = "auto" | "dark" | "light" | "streets" | "satellite";

const TILE_STYLES: Record<Exclude<MapTileStyle, "auto">, string> = {
  dark: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  light: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  streets: "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
  satellite: "https://api.maptiler.com/maps/hybrid/style.json?key=get_your_own_OpIi9ZULNHzrESv6T2vL",
};

interface MapContainerProps {
  viewState: ViewState;
  onViewStateChange: DeckViewStateChangeHandler;
  layers: DeckLayers;
  children?: React.ReactNode;
  onClick?: DeckClickHandler;
  getTooltip?: DeckTooltipHandler;
  selectionMode?: SelectionMode;
  tileStyle?: MapTileStyle;
}

export function MapContainer({
  viewState,
  onViewStateChange,
  layers,
  children,
  onClick,
  getTooltip,
  selectionMode = "none",
  tileStyle = "auto",
}: MapContainerProps) {
  const { resolvedTheme } = useTheme();

  const resolvedMapStyle =
    tileStyle === "auto"
      ? (resolvedTheme === "dark" ? TILE_STYLES.dark : TILE_STYLES.light)
      : TILE_STYLES[tileStyle];

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
          mapStyle={resolvedMapStyle}
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
