import type { Attachment } from "./api";

export interface ViewportMetrics {
  width: number;
  height: number;
  pixelRatio: number;
}

export interface ClickMetrics {
  x: number;
  y: number;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function buildViewportMetrics(
  width: unknown,
  height: unknown,
  pixelRatio?: unknown
): ViewportMetrics | null {
  if (!isFiniteNumber(width) || !isFiniteNumber(height)) {
    return null;
  }

  if (width <= 0 || height <= 0) {
    return null;
  }

  return {
    width,
    height,
    pixelRatio:
      isFiniteNumber(pixelRatio) && pixelRatio > 0
        ? pixelRatio
        : typeof window !== "undefined"
          ? window.devicePixelRatio || 1
          : 1,
  };
}

export function buildClickGrounding(
  click: ClickMetrics,
  viewport: ViewportMetrics | null
): Record<string, number> | undefined {
  if (!viewport || !isFiniteNumber(click.x) || !isFiniteNumber(click.y)) {
    return undefined;
  }

  return {
    screen_x: click.x,
    screen_y: click.y,
    normalized_x: clamp(click.x / viewport.width, 0, 1),
    normalized_y: clamp(click.y / viewport.height, 0, 1),
    viewport_width: viewport.width,
    viewport_height: viewport.height,
    pixel_ratio: viewport.pixelRatio,
  };
}

export function resolveHouseReference(
  id: string | number | undefined,
  lat?: number,
  lon?: number
): string | undefined {
  if (typeof id === "string" || typeof id === "number") {
    return `house:${id}`;
  }
  if (isFiniteNumber(lat) && isFiniteNumber(lon)) {
    return `house@${lat.toFixed(6)},${lon.toFixed(6)}`;
  }
  return undefined;
}

export function verifyHouseReferencePresence(
  houseRef: string | undefined,
  properties: Array<{ id?: number | string; lat?: number; lon?: number }>
): boolean {
  if (!houseRef) {
    return false;
  }

  if (houseRef.startsWith("house:")) {
    const target = houseRef.replace("house:", "");
    return properties.some((item) => String(item.id) === target);
  }

  if (houseRef.startsWith("house@")) {
    const coord = houseRef.replace("house@", "");
    const [latText, lonText] = coord.split(",");
    const targetLat = Number(latText);
    const targetLon = Number(lonText);
    if (!isFiniteNumber(targetLat) || !isFiniteNumber(targetLon)) {
      return false;
    }

    return properties.some((item) => {
      if (!isFiniteNumber(item.lat) || !isFiniteNumber(item.lon)) {
        return false;
      }
      const dLat = Math.abs(item.lat - targetLat);
      const dLon = Math.abs(item.lon - targetLon);
      return dLat < 0.001 && dLon < 0.001;
    });
  }

  return false;
}

export function buildLocationAttachment(
  lat: number,
  lon: number,
  clickGrounding?: Record<string, number>
): Attachment | null {
  if (!isFiniteNumber(lat) || !isFiniteNumber(lon)) {
    return null;
  }

  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
    return null;
  }

  return {
    id: `loc-${Date.now()}`,
    type: "location",
    data: {
      lat,
      lon,
      locator: "map.pin",
      ui_grounding: clickGrounding,
    },
    label: `Location (${lat.toFixed(4)}, ${lon.toFixed(4)})`,
  };
}

export function buildBBoxAttachment(
  corners: [number, number][],
  clickGrounding?: Record<string, number>
): Attachment | null {
  if (corners.length < 4) {
    return null;
  }

  const lons = corners.map((c) => c[0]).filter(isFiniteNumber);
  const lats = corners.map((c) => c[1]).filter(isFiniteNumber);
  if (lons.length !== corners.length || lats.length !== corners.length) {
    return null;
  }

  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  if (!(minLon < maxLon && minLat < maxLat)) {
    return null;
  }

  const avgLat = (minLat + maxLat) / 2;
  const widthKm =
    (maxLon - minLon) * 111 * Math.cos((avgLat * Math.PI) / 180);
  const heightKm = (maxLat - minLat) * 111;

  return {
    id: `bbox-${Date.now()}`,
    type: "bbox",
    data: {
      corners,
      minLon,
      maxLon,
      minLat,
      maxLat,
      locator: "map.bbox",
      ui_grounding: clickGrounding,
    },
    label: `Area (${Math.abs(widthKm).toFixed(1)}km x ${Math.abs(heightKm).toFixed(1)}km)`,
  };
}
