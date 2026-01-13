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

export const MARKER_PATH =
  "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z";

export const POI_COLORS: Record<string, string> = {
  school: "#8B5CF6", // Purple (Education)
  transit: "#EAB308", // Yellow/Gold (Transit)
  bus: "#22C55E", // Green (Bus)
  police: "#1E3A8A", // Navy (Safety)
  museum: "#9333EA", // Purple (Culture)
  water: "#06B6D4", // Cyan (Water)
  gas: "#F97316", // Orange (Utilities)
  traffic: "#EF4444", // Red (Traffic)
  tourist: "#EC4899", // Pink (Tourist)
  home: "#000000", // Black (Home - though usually masked)
  building: "#64748B", // Slate (Building)
  default: "#94A3B8", // Gray (Default)
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
  const PADDING = 8;
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

    // Determine if this is a "maskable" icon (like home/building which change color by price)
    // or a "fixed color" icon (POIs)
    const isMaskable = key === "home" || key === "building" || key === "default";

    ctx.save();
    ctx.translate(x + PADDING / 2, y + PADDING / 2);
    
    // Scale factor to fit the 24x24 viewBox into our ICON_SIZE
    const scale = ICON_SIZE / 24;
    ctx.scale(scale, scale);

    // 1. Draw Pin Body
    const pinPath = new Path2D(MARKER_PATH);
    
    if (isMaskable) {
      // For maskable icons, we draw white so DeckGL can tint it
      ctx.fillStyle = "white";
      ctx.fill(pinPath);
      
      // 2. Cut out the inner icon
      // We want the inner icon to be transparent
      ctx.globalCompositeOperation = "destination-out";
      
      // Center and scale the inner icon
      // We scale it down to ~55% to fit nicely in the pin head
      // Pin head center in 24x24 viewbox is approx (12, 9)
      ctx.translate(12, 9);
      ctx.scale(0.55, 0.55);
      ctx.translate(-12, -12); // Center path at origin before drawing
      
      const iconPath = new Path2D(ICON_PATHS[key]);
      ctx.fillStyle = "black"; // Color doesn't matter for destination-out, just opacity
      ctx.fill(iconPath);
    } else {
      // For POIs, we bake the colors in
      ctx.fillStyle = POI_COLORS[key] || POI_COLORS.default;
      
      // Add a subtle drop shadow for depth
      ctx.shadowColor = "rgba(0,0,0,0.3)";
      ctx.shadowBlur = 4;
      ctx.shadowOffsetY = 2;
      
      ctx.fill(pinPath);
      
      // Reset shadow for inner icon
      ctx.shadowColor = "transparent";
      ctx.shadowBlur = 0;
      ctx.shadowOffsetY = 0;

      // 2. Draw the inner icon in white
      // Center and scale
      ctx.translate(12, 9);
      ctx.scale(0.55, 0.55);
      ctx.translate(-12, -12);
      
      const iconPath = new Path2D(ICON_PATHS[key]);
      ctx.fillStyle = "white";
      ctx.fill(iconPath);
    }

    ctx.restore();

    mapping[key] = {
      x: x + PADDING / 2,
      y: y + PADDING / 2,
      width: ICON_SIZE,
      height: ICON_SIZE,
      mask: isMaskable, // true for home (tintable), false for POIs (baked colors)
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
