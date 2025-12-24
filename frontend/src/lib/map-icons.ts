// Map icon atlas generator
// Renders SVG paths to a canvas to create a sprite sheet for deck.gl IconLayer

export type IconName =
  | "school"
  | "transit"
  | "bus"
  | "police"
  | "museum"
  | "water"
  | "gas"
  | "traffic"
  | "tourist"
  | "home"
  | "building"
  | "default";

const ICON_PATHS: Record<IconName, string> = {
  // Graduation Cap
  school: "M22 10v6M2 10l10-5 10 5-10 5zM6 12v5c3 3 9 3 12 0v-5",
  // Train Front
  transit:
    "M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2zM4 12h16M12 12v8",
  // Bus Front
  bus: "M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2zM2 22h20",
  // Shield
  police: "M12 2L2 7l10 15 10-15-10-5z",
  // Landmark/Bank
  museum:
    "M4 22h16M4 18h16M12 2l-8 6h16l-8-6zM6 18v-8M10 18v-8M14 18v-8M18 18v-8",
  // Waves
  water:
    "M2 12c2 0 2-2 4-2s2 2 4 2 2-2 4-2 2 2 4 2M2 16c2 0 2-2 4-2s2 2 4 2 2-2 4-2 2 2 4 2M2 20c2 0 2-2 4-2s2 2 4 2 2-2 4-2 2 2 4 2",
  // Fuel Pump
  gas: "M3 22v-8c0-1.1.9-2 2-2h10a2 2 0 0 1 2 2v8M15 12a3 3 0 1 0-6 0",
  // Traffic Cone / Warning
  traffic: "M12 2L2 22h20L12 2zM12 16v2M12 10v4",
  // Camera / Attraction
  tourist:
    "M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2zM12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  // Home
  home: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  // Building
  building: "M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18M6 12h12M6 8h12M6 16h12",
  // Circle (Default)
  default: "M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z",
};

export interface IconMapping {
  x: number;
  y: number;
  width: number;
  height: number;
  mask: boolean;
}

export function generateIconAtlas() {
  const ICON_SIZE = 64;
  const PADDING = 4;
  const ROW_LENGTH = 4; // Icons per row

  const keys = Object.keys(ICON_PATHS) as IconName[];
  const count = keys.length;
  const rows = Math.ceil(count / ROW_LENGTH);

  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");

  const width = ROW_LENGTH * (ICON_SIZE + PADDING);
  const height = rows * (ICON_SIZE + PADDING);

  canvas.width = width;
  canvas.height = height;

  if (!ctx) throw new Error("Could not get canvas context");

  const mapping: Record<string, IconMapping> = {};

  keys.forEach((key, index) => {
    const col = index % ROW_LENGTH;
    const row = Math.floor(index / ROW_LENGTH);

    const x = col * (ICON_SIZE + PADDING);
    const y = row * (ICON_SIZE + PADDING);

    // Draw icon
    const path = new Path2D(ICON_PATHS[key]);

    ctx.save();
    ctx.translate(x + PADDING / 2, y + PADDING / 2);
    // Scale path to fit 64x64 (assuming paths are roughly 24x24 viewbox)
    const scale = ICON_SIZE / 24;
    ctx.scale(scale, scale);

    ctx.fillStyle = "white";
    ctx.fill(path);
    ctx.restore();

    mapping[key] = {
      x: x + PADDING / 2,
      y: y + PADDING / 2,
      width: ICON_SIZE,
      height: ICON_SIZE,
      mask: true,
    };
  });

  return {
    atlas: canvas,
    mapping,
  };
}

export function getIconNameForType(type: string): IconName {
  switch (type) {
    case "school":
      return "school";
    case "transit_stop":
      return "transit";
    case "bus_shelter":
      return "bus";
    case "police_station":
      return "police";
    case "museum":
      return "museum";
    case "water_transport":
      return "water";
    case "gas_station":
      return "gas";
    case "traffic_point":
      return "traffic";
    case "tourist_attraction":
      return "tourist";
    case "condo_project":
      return "building";
    case "house":
      return "home";
    default:
      return "default";
  }
}
