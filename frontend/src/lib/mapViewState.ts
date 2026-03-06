import type { MapViewState } from "@deck.gl/core";

const VIEW_STATE_EPSILON = 1e-9;

function nearlyEqual(a: number | undefined, b: number | undefined): boolean {
  const normalizedA = a ?? 0;
  const normalizedB = b ?? 0;
  return Math.abs(normalizedA - normalizedB) < VIEW_STATE_EPSILON;
}

export function isSameMapViewState(
  previous: MapViewState,
  next: MapViewState
): boolean {
  return (
    nearlyEqual(previous.longitude, next.longitude) &&
    nearlyEqual(previous.latitude, next.latitude) &&
    nearlyEqual(previous.zoom, next.zoom) &&
    nearlyEqual(previous.pitch, next.pitch) &&
    nearlyEqual(previous.bearing, next.bearing)
  );
}

export function keepPreviousViewStateIfSame(
  previous: MapViewState,
  next: MapViewState
): MapViewState {
  return isSameMapViewState(previous, next) ? previous : next;
}
