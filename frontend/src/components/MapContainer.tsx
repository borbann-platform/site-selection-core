import React from "react";
import Map, { NavigationControl, useControl } from "react-map-gl/maplibre";
import DeckGL from "@deck.gl/react";
import { type MapViewState } from "@deck.gl/core";

interface MapContainerProps {
  viewState: MapViewState;
  onViewStateChange: (params: { viewState: MapViewState }) => void;
  layers: any[];
  children?: React.ReactNode;
  onClick?: (info: any) => void;
  getTooltip?: (info: any) => any;
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
}: MapContainerProps) {
  return (
    <div className="relative w-full h-full">
      <DeckGL
        viewState={viewState}
        onViewStateChange={onViewStateChange}
        controller={true}
        layers={layers}
        onClick={onClick}
        getTooltip={getTooltip}
      >
        <Map mapStyle={MAP_STYLE} reuseMaps attributionControl={false}>
          <NavigationControl position="bottom-right" />
        </Map>
      </DeckGL>
      {children}
    </div>
  );
}
