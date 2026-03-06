import { useMemo, useCallback } from "react";
import {
  PathLayer,
  IconLayer,
  ScatterplotLayer,
  PolygonLayer,
} from "@deck.gl/layers";
import { MVTLayer, H3HexagonLayer } from "@deck.gl/geo-layers";
import { generateIconAtlas, getIconNameForType } from "@/lib/map-icons";
import { API_URL } from "@/lib/api";
import type { TransitLineFeature, H3HexagonResponse } from "@/lib/api";
import type { Attachment, SelectionMode } from "@/components/ai";
import type { PropertyFiltersState } from "@/components/PropertyFilters";
import type { DeckGLObject, ViewState, OverlayState } from "@/hooks/usePropertyExplorer";

// Minimal types for query data passed in
interface HousePricesData {
  count: number;
  items: DeckGLObject[];
}

interface SchoolsData {
  // biome-ignore lint/suspicious/noExplicitAny: GeoJSON school features have variable property shapes
  features: any[];
}

interface TransitLinesData {
  type: "FeatureCollection";
  features: TransitLineFeature[];
}

interface UseMapLayersParams {
  housePrices: HousePricesData | undefined;
  schools: SchoolsData | undefined;
  transitLines: TransitLinesData | undefined;
  h3Data: H3HexagonResponse | undefined;
  overlays: OverlayState;
  viewState: ViewState;
  propertyFilters: PropertyFiltersState;
  chatAttachments: Attachment[];
  selectionMode: SelectionMode;
  bboxCorners: [number, number][];
  h3Metric: string;
}

export function useMapLayers({
  housePrices,
  schools,
  transitLines,
  h3Data,
  overlays,
  viewState,
  propertyFilters,
  chatAttachments,
  selectionMode,
  bboxCorners,
  h3Metric,
}: UseMapLayersParams) {
  // Derived zoom tier – only changes when crossing the threshold,
  // so useMemo below won't re-run on every fractional zoom change.
  const zoomTier = viewState.zoom < 13 ? "low" : "high";

  // Generate icon atlas for POIs
  const iconAtlasData = useMemo(() => generateIconAtlas(), []);
  const iconAtlas = useMemo(
    () => ({
      atlas: iconAtlasData.atlas as unknown as string,
      mapping: iconAtlasData.mapping,
    }),
    [iconAtlasData]
  );

  const layers = useMemo(() => {
    const layerList = [];

    // Primary: House Prices Layer (always shown when data available)
    if (housePrices && zoomTier === "low") {
      layerList.push(
        new IconLayer({
          id: "house-prices-icon",
          data: housePrices.items,
          iconAtlas: iconAtlas.atlas,
          iconMapping: iconAtlas.mapping,
          getIcon: () => "home",
          getPosition: (d: DeckGLObject) => [d.lon || 0, d.lat || 0],
          getColor: (d: DeckGLObject) => {
            const price = d.total_price || 0;
            const minPrice = propertyFilters.minPrice;
            const maxPrice = propertyFilters.maxPrice;
            const t = Math.min(
              1,
              Math.max(0, (price - minPrice) / (maxPrice - minPrice))
            );
            if (t < 0.5) {
              const r = Math.round(t * 2 * 255);
              return [r, 200, 50];
            }
            const g = Math.round((1 - (t - 0.5) * 2) * 200);
            return [255, g, 50];
          },
          getSize: 20,
          sizeScale: 1,
          sizeMinPixels: 20,
          sizeMaxPixels: 30,
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 100],
        })
      );
    }

    // MVT tiles for high zoom
    if (zoomTier === "high") {
      const mvtParams = new URLSearchParams();
      if (propertyFilters.district)
        mvtParams.set("amphur", propertyFilters.district);
      if (propertyFilters.buildingStyle)
        mvtParams.set("building_style", propertyFilters.buildingStyle);
      if (propertyFilters.minPrice !== undefined)
        mvtParams.set("min_price", String(propertyFilters.minPrice));
      if (propertyFilters.maxPrice !== undefined)
        mvtParams.set("max_price", String(propertyFilters.maxPrice));
      if (propertyFilters.minArea !== undefined)
        mvtParams.set("min_area", String(propertyFilters.minArea));
      if (propertyFilters.maxArea !== undefined)
        mvtParams.set("max_area", String(propertyFilters.maxArea));
      const mvtQueryString = mvtParams.toString()
        ? `?${mvtParams.toString()}`
        : "";

      layerList.push(
        new MVTLayer({
          id: "house-prices-mvt",
          data: `${API_URL}/house-prices/tile/{z}/{x}/{y}${mvtQueryString}`,
          minZoom: 13,
          maxZoom: 20,
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 100],
          binary: false,
          renderSubLayers: (props) => {
            return new IconLayer(props, {
              id: `${props.id}-icon`,
              iconAtlas: iconAtlas.atlas,
              iconMapping: iconAtlas.mapping,
              getIcon: () => "home",
              getPosition: (d: DeckGLObject) => {
                const coords = d.geometry?.coordinates;
                return [Number(coords?.[0] ?? 0), Number(coords?.[1] ?? 0)] as [
                  number,
                  number,
                ];
              },
              getSize: 32,
              getColor: (d: DeckGLObject) => {
                const price = Number(d.properties?.total_price) || 0;
                const minPrice = propertyFilters.minPrice;
                const maxPrice = propertyFilters.maxPrice;
                const t = Math.min(
                  1,
                  Math.max(0, (price - minPrice) / (maxPrice - minPrice))
                );
                if (t < 0.5) {
                  const r = Math.round(t * 2 * 255);
                  return [r, 200, 50];
                }
                const g = Math.round((1 - (t - 0.5) * 2) * 200);
                return [255, g, 50];
              },
              sizeScale: 1,
              sizeMinPixels: 28,
              sizeMaxPixels: 48,
              pickable: true,
              autoHighlight: true,
              highlightColor: [255, 255, 255, 100],
            });
          },
        })
      );
    }

    // Overlay: POIs with improved styling (Icons)
    if (overlays.pois) {
      layerList.push(
        new MVTLayer({
          id: "all-pois-layer",
          data: `${API_URL}/analytics/all-pois/tile/{z}/{x}/{y}`,
          minZoom: 12,
          maxZoom: 20,
          binary: false,
          renderSubLayers: (props) => {
            return new IconLayer(props, {
              id: `${props.id}-icon`,
              iconAtlas: iconAtlas.atlas,
              iconMapping: iconAtlas.mapping,
              getIcon: (d: DeckGLObject) =>
                getIconNameForType(String(d.properties?.type ?? "")),
              getPosition: (d: DeckGLObject) => {
                const coords = d.geometry?.coordinates;
                return [Number(coords?.[0] ?? 0), Number(coords?.[1] ?? 0)] as [
                  number,
                  number,
                ];
              },
              getSize: (d: DeckGLObject) => {
                const type = d.properties?.type;
                if (type === "transit_stop") return 28;
                if (type === "school") return 24;
                return 20;
              },
              getColor: (d: DeckGLObject) => {
                const type = d.properties?.type;
                if (type === "transit_stop") return [255, 200, 50];
                if (type === "school") return [59, 130, 246];
                if (type === "police_station") return [30, 58, 138];
                if (type === "museum") return [147, 51, 234];
                if (type === "tourist_attraction") return [236, 72, 153];
                if (type === "water_transport") return [6, 182, 212];
                if (type === "bus_shelter") return [34, 197, 94];
                if (type === "gas_station") return [249, 115, 22];
                if (type === "traffic_point") return [239, 68, 68];
                return [148, 163, 184];
              },
              sizeScale: 1,
              sizeMinPixels: 20,
              sizeMaxPixels: 40,
              pickable: true,
              autoHighlight: true,
              highlightColor: [255, 255, 255, 100],
            });
          },
        })
      );
    }

    // Overlay: Schools
    if (overlays.schools && schools) {
      layerList.push(
        new IconLayer({
          id: "schools",
          data: schools.features,
          iconAtlas: iconAtlas.atlas,
          iconMapping: iconAtlas.mapping,
          getIcon: () => "school",
          getPosition: (d: DeckGLObject) => {
            const coords = d.geometry?.coordinates;
            return [Number(coords?.[0] ?? 0), Number(coords?.[1] ?? 0)] as [
              number,
              number,
            ];
          },
          getColor: [59, 130, 246],
          getSize: 32,
          sizeScale: 1,
          sizeMinPixels: 20,
          sizeMaxPixels: 40,
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 100],
        })
      );
    }

    // Overlay: Transit Rail Lines (BTS, MRT, ARL)
    if (overlays.transitRail && transitLines) {
      layerList.push(
        new PathLayer<TransitLineFeature>({
          id: "transit-lines",
          data: transitLines.features,
          getPath: (d) => d.geometry.coordinates,
          getColor: (d) => {
            const color = d.properties.route_color;
            if (color) {
              const hex = color.replace("#", "");
              const r = Number.parseInt(hex.substring(0, 2), 16);
              const g = Number.parseInt(hex.substring(2, 4), 16);
              const b = Number.parseInt(hex.substring(4, 6), 16);
              return [r, g, b, 220];
            }
            const routeType = d.properties.route_type;
            if (routeType === 0) return [101, 183, 36, 220];
            if (routeType === 1) return [25, 100, 183, 220];
            if (routeType === 2) return [227, 32, 32, 220];
            return [150, 150, 150, 180];
          },
          getWidth: 4,
          widthMinPixels: 2,
          widthMaxPixels: 8,
          pickable: true,
          capRounded: true,
          jointRounded: true,
        })
      );
    }

    // Overlay: H3 Hexagon Analytics
    if (overlays.h3Hexagons && h3Data && h3Data.hexagons.length > 0) {
      layerList.push(
        new H3HexagonLayer({
          id: "h3-hexagons",
          data: h3Data.hexagons,
          pickable: true,
          filled: true,
          extruded: false,
          getHexagon: (d: { h3_index: string }) => d.h3_index,
          getFillColor: (d: { value: number }) => {
            const range = h3Data.max_value - h3Data.min_value || 1;
            const t = (d.value - h3Data.min_value) / range;
            if (t < 0.5) {
              const r = Math.round(t * 2 * 255);
              const g = Math.round(t * 2 * 200);
              return [r, g, 255, 200];
            }
            const b = Math.round((1 - (t - 0.5) * 2) * 255);
            const g = Math.round((1 - (t - 0.5) * 2) * 200);
            return [255, g, b, 200];
          },
          getLineColor: [255, 255, 255, 150],
          lineWidthMinPixels: 2,
          opacity: 0.85,
        })
      );
    }

    // Overlay: Chat Selection Markers (Location points)
    const locationAttachments = chatAttachments.filter(
      (a) => a.type === "location"
    );
    if (locationAttachments.length > 0) {
      layerList.push(
        new ScatterplotLayer({
          id: "chat-selection-markers",
          data: locationAttachments,
          getPosition: (d: Attachment) => [
            Number(d.data.lon) || 0,
            Number(d.data.lat) || 0,
          ],
          getFillColor: [255, 0, 255],
          getRadius: 200,
          pickable: false,
          opacity: 0.8,
          stroked: true,
          getLineColor: [255, 255, 255],
          getLineWidth: 2,
          radiusMinPixels: 5,
        })
      );
    }

    // Overlay: Bbox Attachments (persistent polygon visualization)
    const bboxAttachments = chatAttachments.filter((a) => a.type === "bbox");
    if (bboxAttachments.length > 0) {
      layerList.push(
        new PolygonLayer({
          id: "bbox-attachment-polygons",
          data: bboxAttachments,
          getPolygon: (d: Attachment) => {
            const corners = d.data.corners as [number, number][];
            if (!corners || corners.length < 3) return [];
            return [...corners, corners[0]];
          },
          getFillColor: [0, 180, 255, 40],
          getLineColor: [0, 180, 255, 200],
          getLineWidth: 2,
          lineWidthMinPixels: 2,
          pickable: false,
          filled: true,
          stroked: true,
        })
      );
    }

    // Overlay: Bbox Selection Corners (blue dots while selecting)
    if (selectionMode === "bbox" && bboxCorners.length > 0) {
      layerList.push(
        new ScatterplotLayer({
          id: "bbox-selection-corners",
          data: bboxCorners,
          getPosition: (d: [number, number]) => d,
          getFillColor: [0, 180, 255],
          getRadius: 150,
          pickable: false,
          opacity: 1,
          stroked: true,
          getLineColor: [255, 255, 255],
          getLineWidth: 3,
          radiusMinPixels: 8,
          radiusMaxPixels: 12,
        })
      );

      if (bboxCorners.length >= 2) {
        layerList.push(
          new PolygonLayer({
            id: "bbox-selection-polygon-preview",
            data: [{ corners: bboxCorners }],
            getPolygon: (d: { corners: [number, number][] }) => {
              return [...d.corners, d.corners[0]];
            },
            getFillColor: [0, 180, 255, 30],
            getLineColor: [0, 180, 255, 180],
            getLineWidth: 2,
            lineWidthMinPixels: 2,
            pickable: false,
            filled: true,
            stroked: true,
          })
        );
      }
    }

    return layerList;
  }, [
    housePrices,
    schools,
    transitLines,
    h3Data,
    overlays,
    zoomTier,
    propertyFilters,
    iconAtlas,
    chatAttachments,
    selectionMode,
    bboxCorners,
  ]);

  const getTooltip = useCallback(
    ({ object }: { object?: DeckGLObject | null }) => {
      if (!object) return null;

      // POI Tooltip
      if (object.properties?.type) {
        const props = object.properties;
        const name = props.name || "Unnamed Location";
        const type = props.type || "Unknown Type";

        return {
          html: `<div class="p-3 bg-zinc-900/90 border border-zinc-700 text-white rounded-lg shadow-xl backdrop-blur-md min-w-50">
          <div class="font-bold text-sm mb-1">${name}</div>
          <div class="text-xs font-medium text-zinc-400">${type}</div>
        </div>`,
        };
      }

      // H3 Hexagon Tooltip
      if (object.h3_index !== undefined) {
        const metricLabel = h3Metric
          .replace(/_/g, " ")
          .replace(/\b\w/g, (c) => c.toUpperCase());
        const value =
          typeof object.value === "number"
            ? object.value.toLocaleString("th-TH", {
                maximumFractionDigits: 2,
              })
            : object.value;

        return {
          html: `<div class="p-3 bg-zinc-900/90 border border-zinc-700 text-white rounded-lg shadow-xl backdrop-blur-md min-w-50">
          <div class="font-bold text-sm mb-1">${String.fromCodePoint(0x1f4ca)} ${metricLabel}</div>
          <div class="text-xl font-bold text-cyan-400">${value}</div>
          <div class="text-xs text-zinc-500 mt-1">H3: ${object.h3_index.slice(0, 12)}...</div>
        </div>`,
        };
      }

      // Transit Line Tooltip
      if (object.properties?.route_short_name !== undefined) {
        const props = object.properties;
        const routeName = props.route_short_name || "Transit Line";
        const longName = props.route_long_name || "";
        const routeType = props.route_type;
        const typeLabel =
          routeType === 0
            ? `${String.fromCodePoint(0x1f688)} BTS Skytrain`
            : routeType === 1
              ? `${String.fromCodePoint(0x1f687)} MRT Metro`
              : routeType === 2
                ? `${String.fromCodePoint(0x1f686)} Rail/ARL`
                : `${String.fromCodePoint(0x1f68c)} Transit`;
        const color = props.route_color ? `#${props.route_color}` : "#888";

        return {
          html: `<div class="p-3 bg-zinc-900/90 border border-zinc-700 text-white rounded-lg shadow-xl backdrop-blur-md min-w-50">
          <div class="flex items-center gap-2 mb-1">
            <div class="w-3 h-3 rounded-full" style="background-color: ${color}"></div>
            <span class="font-bold text-sm">${routeName}</span>
          </div>
          <div class="text-xs text-zinc-400 mb-1">${typeLabel}</div>
          ${longName ? `<div class="text-xs text-zinc-500">${longName}</div>` : ""}
        </div>`,
        };
      }

      return null;
    },
    [h3Metric]
  );

  return { layers, getTooltip };
}
