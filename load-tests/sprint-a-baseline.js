import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const API_PREFIX = `${BASE_URL}/api/v1`;
const WARMUP_REQUESTS = Number.parseInt(__ENV.WARMUP_REQUESTS || "120", 10);
const WARMUP_ENABLED = __ENV.WARMUP_ENABLED !== "false";
const START_VUS = Number.parseInt(__ENV.START_VUS || "20", 10);
const GRACEFUL_RAMP_DOWN = __ENV.GRACEFUL_RAMP_DOWN || "30s";

function parseStages() {
  const raw = __ENV.STAGES || "2m:100,3m:300,2m:100";
  return raw.split(",").map((entry) => {
    const [duration, target] = entry.trim().split(":");
    return {
      duration,
      target: Number.parseInt(target, 10),
    };
  });
}

const HOT_TILES = [
  { zoom: 16, x: 51120, y: 30220 },
  { zoom: 16, x: 51122, y: 30218 },
  { zoom: 16, x: 51118, y: 30216 },
  { zoom: 15, x: 25560, y: 15110 },
  { zoom: 15, x: 25562, y: 15112 },
];

export const options = {
  scenarios: {
    mixed_read_traffic: {
      executor: "ramping-vus",
      startVUs: START_VUS,
      stages: parseStages(),
      gracefulRampDown: GRACEFUL_RAMP_DOWN,
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1200"],
    checks: ["rate>0.99"],
  },
};

export function setup() {
  if (!WARMUP_ENABLED || WARMUP_REQUESTS <= 0) {
    return;
  }

  for (let i = 0; i < WARMUP_REQUESTS; i += 1) {
    const tile = HOT_TILES[i % HOT_TILES.length];
    const url = `${API_PREFIX}/listings/tile/${tile.zoom}/${tile.x}/${tile.y}`;
    http.get(url, { tags: { endpoint: "listings_tile_warmup", phase: "warmup" } });
  }
}

function randomTile(zoom) {
  // Bangkok-ish tile ranges for stable, realistic traffic.
  const xMin = zoom === 15 ? 25500 : 51000;
  const xMax = zoom === 15 ? 25620 : 51240;
  const yMin = zoom === 15 ? 15080 : 30160;
  const yMax = zoom === 15 ? 15220 : 30440;

  const x = Math.floor(Math.random() * (xMax - xMin + 1)) + xMin;
  const y = Math.floor(Math.random() * (yMax - yMin + 1)) + yMin;
  return { x, y };
}

function requestListingsTile() {
  const zoom = Math.random() < 0.7 ? 16 : 15;
  const { x, y } = randomTile(zoom);
  const url = `${API_PREFIX}/listings/tile/${zoom}/${x}/${y}`;
  const res = http.get(url, {
    tags: { endpoint: "listings_tile" },
    responseCallback: http.expectedStatuses(200),
  });
  check(res, {
    "listings tile status 200": (r) => r.status === 200,
    "listings tile has cache header": (r) => !!r.headers["X-Cache"],
  });
}

function requestDetailFlow() {
  const id = 1000 + Math.floor(Math.random() * 2000);
  const detailUrl = `${API_PREFIX}/house-prices/${id}`;
  const nearbyUrl = `${API_PREFIX}/house-prices/${id}/nearby?radius_m=1000&limit=10`;

  const detailRes = http.get(detailUrl, {
    tags: { endpoint: "house_price_detail" },
    responseCallback: http.expectedStatuses(200, 404),
  });
  check(detailRes, {
    "detail status 2xx/404": (r) => (r.status >= 200 && r.status < 300) || r.status === 404,
  });

  const nearbyRes = http.get(nearbyUrl, {
    tags: { endpoint: "house_price_nearby" },
    responseCallback: http.expectedStatuses(200, 404),
  });
  check(nearbyRes, {
    "nearby status 2xx/404": (r) => (r.status >= 200 && r.status < 300) || r.status === 404,
  });
}

function requestLocationIntelligence() {
  const lat = 13.75 + Math.random() * 0.2;
  const lon = 100.45 + Math.random() * 0.2;
  const url = `${API_PREFIX}/location-intelligence/analyze`;

  const res = http.post(
    url,
    JSON.stringify({
      latitude: lat,
      longitude: lon,
      radius_meters: 1000,
    }),
    {
      headers: { "Content-Type": "application/json" },
      tags: { endpoint: "location_intelligence" },
      responseCallback: http.expectedStatuses(200),
    }
  );

  check(res, {
    "location intelligence status 200": (r) => r.status === 200,
  });
}

export default function () {
  const roll = Math.random();

  // 70% tile/listing reads
  if (roll < 0.7) {
    requestListingsTile();
  }
  // 20% detail reads
  else if (roll < 0.9) {
    requestDetailFlow();
  }
  // 10% location intelligence
  else {
    requestLocationIntelligence();
  }

  sleep(0.5 + Math.random() * 0.5);
}
