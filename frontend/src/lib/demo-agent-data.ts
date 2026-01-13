/**
 * Demo data for agentic chat UI - simulates multi-step agent interactions
 * with tool calls, thinking, waiting for user, and streaming responses.
 */

export type AgentStepType = "tool_call" | "thinking" | "waiting_user";
export type AgentStepStatus =
  | "pending"
  | "running"
  | "complete"
  | "error"
  | "waiting";

export interface DemoAgentStep {
  id: string;
  type: AgentStepType;
  name: string;
  description?: string;
  status: AgentStepStatus;
  input?: Record<string, unknown>;
  output?: string;
  startTime: number;
  endTime?: number;
  // For waiting_user step - defines what input is expected
  waitingFor?: {
    type: "location" | "bbox" | "property" | "confirmation" | "text";
    prompt: string;
  };
}

export interface DemoAgentMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  steps?: DemoAgentStep[];
  isStreaming?: boolean;
  isThinking?: boolean;
  isWaitingForUser?: boolean;
  attachments?: DemoAttachment[];
}

export interface DemoAttachment {
  id: string;
  type: "location" | "bbox" | "property";
  label: string;
  data: Record<string, unknown>;
}

// Demo tool definitions
export const DEMO_TOOLS = {
  search_properties: {
    name: "search_properties",
    description: "Search for properties in a given area",
    icon: "search",
  },
  get_market_analysis: {
    name: "get_market_analysis",
    description: "Analyze market trends for an area",
    icon: "chart",
  },
  calculate_distance: {
    name: "calculate_distance",
    description: "Calculate distance between two points",
    icon: "ruler",
  },
  get_poi_nearby: {
    name: "get_poi_nearby",
    description: "Find points of interest near a location",
    icon: "map-pin",
  },
  compare_properties: {
    name: "compare_properties",
    description: "Compare multiple properties side by side",
    icon: "columns",
  },
  request_user_selection: {
    name: "request_user_selection",
    description: "Request user to select an area or property",
    icon: "hand",
  },
} as const;

// Demo conversation scenarios
export const DEMO_CONVERSATIONS: DemoAgentMessage[][] = [
  // Scenario 1: Area analysis with bbox selection
  [
    {
      id: "demo-1-user",
      role: "user",
      content: "I want to analyze property prices in a specific area",
    },
    {
      id: "demo-1-assistant-1",
      role: "assistant",
      content: "",
      isThinking: true,
      steps: [
        {
          id: "step-1",
          type: "thinking",
          name: "Analyzing request",
          status: "complete",
          startTime: Date.now() - 2000,
          endTime: Date.now() - 1500,
        },
        {
          id: "step-2",
          type: "waiting_user",
          name: "Waiting for area selection",
          description:
            "Please draw a rectangle on the map to select the area you want to analyze",
          status: "waiting",
          startTime: Date.now() - 1500,
          waitingFor: {
            type: "bbox",
            prompt:
              "Draw a rectangle on the map to select your area of interest",
          },
        },
      ],
      isWaitingForUser: true,
    },
  ],

  // Scenario 2: Full analysis flow
  [
    {
      id: "demo-2-user",
      role: "user",
      content: "Analyze this area for investment potential",
      attachments: [
        {
          id: "att-1",
          type: "bbox",
          label: "Selected Area (Sukhumvit)",
          data: {
            bounds: [
              [100.55, 13.72],
              [100.58, 13.75],
            ],
          },
        },
      ],
    },
    {
      id: "demo-2-assistant",
      role: "assistant",
      steps: [
        {
          id: "step-1",
          type: "thinking",
          name: "Understanding request",
          status: "complete",
          startTime: Date.now() - 5000,
          endTime: Date.now() - 4500,
        },
        {
          id: "step-2",
          type: "tool_call",
          name: "search_properties",
          status: "complete",
          input: {
            bounds: [
              [100.55, 13.72],
              [100.58, 13.75],
            ],
            limit: 100,
          },
          output: "Found 47 properties in the selected area",
          startTime: Date.now() - 4500,
          endTime: Date.now() - 3000,
        },
        {
          id: "step-3",
          type: "tool_call",
          name: "get_market_analysis",
          status: "complete",
          input: { area_id: "sukhumvit-core", timeframe: "6m" },
          output: JSON.stringify({
            avg_price: 8500000,
            price_trend: "+5.2%",
            inventory: 47,
            days_on_market: 45,
          }),
          startTime: Date.now() - 3000,
          endTime: Date.now() - 2000,
        },
        {
          id: "step-4",
          type: "tool_call",
          name: "get_poi_nearby",
          status: "complete",
          input: { center: [100.565, 13.735], radius: 1000 },
          output:
            "Found 23 POIs: 5 schools, 3 hospitals, 8 transit stops, 7 malls",
          startTime: Date.now() - 2000,
          endTime: Date.now() - 1000,
        },
      ],
      content: `## Investment Analysis: Sukhumvit Area

Based on my analysis of **47 properties** in your selected area:

### Market Overview
- **Average Price:** ฿8,500,000
- **Price Trend:** +5.2% (6 months)
- **Avg. Days on Market:** 45 days

### Accessibility Score: 9.2/10
- 8 BTS/MRT stations within 1km
- 5 schools including international schools
- 3 major hospitals nearby

### Investment Recommendation
This area shows **strong growth potential** with good transit connectivity and amenities. The +5.2% price trend indicates healthy demand.

Would you like me to compare specific properties or analyze a different area?`,
      isStreaming: false,
    },
  ],

  // Scenario 3: Property comparison with drag-drop
  [
    {
      id: "demo-3-user",
      role: "user",
      content: "Compare these properties for me",
      attachments: [
        {
          id: "prop-1",
          type: "property",
          label: "Condo Sukhumvit 24",
          data: { id: "123", price: 7500000, area: 45 },
        },
        {
          id: "prop-2",
          type: "property",
          label: "House Ekkamai",
          data: { id: "456", price: 12000000, area: 120 },
        },
      ],
    },
    {
      id: "demo-3-assistant",
      role: "assistant",
      content: "",
      steps: [
        {
          id: "step-1",
          type: "tool_call",
          name: "compare_properties",
          status: "running",
          input: { property_ids: ["123", "456"] },
          startTime: Date.now() - 1000,
        },
      ],
      isThinking: false,
      isStreaming: true,
    },
  ],
];

// Helper to simulate step progression
export function simulateAgentSteps(
  onStep: (step: DemoAgentStep) => void,
  onToken: (token: string) => void,
  onComplete: () => void
): () => void {
  const steps: DemoAgentStep[] = [
    {
      id: `sim-step-${Date.now()}-1`,
      type: "thinking",
      name: "Analyzing your request...",
      status: "running",
      startTime: Date.now(),
    },
    {
      id: `sim-step-${Date.now()}-2`,
      type: "tool_call",
      name: "search_properties",
      status: "pending",
      input: { query: "nearby properties" },
      startTime: 0,
    },
    {
      id: `sim-step-${Date.now()}-3`,
      type: "tool_call",
      name: "get_market_analysis",
      status: "pending",
      input: { area: "selected" },
      startTime: 0,
    },
  ];

  const response =
    "Based on my analysis, I found several interesting properties in your area. The market shows positive trends with an average price increase of 3.5% over the last quarter.";

  let stepIndex = 0;
  let tokenIndex = 0;
  let cancelled = false;

  const runStep = () => {
    if (cancelled) return;

    if (stepIndex < steps.length) {
      const step = { ...steps[stepIndex] };
      step.status = "running";
      step.startTime = Date.now();
      onStep(step);

      setTimeout(
        () => {
          if (cancelled) return;
          step.status = "complete";
          step.endTime = Date.now();
          step.output = `Completed ${step.name}`;
          onStep(step);
          stepIndex++;
          setTimeout(runStep, 300);
        },
        800 + Math.random() * 500
      );
    } else {
      // Stream tokens
      const streamToken = () => {
        if (cancelled) return;
        if (tokenIndex < response.length) {
          onToken(response[tokenIndex]);
          tokenIndex++;
          setTimeout(streamToken, 20 + Math.random() * 30);
        } else {
          onComplete();
        }
      };
      streamToken();
    }
  };

  setTimeout(runStep, 500);

  return () => {
    cancelled = true;
  };
}

// Demo property data for drag-drop testing
export const DEMO_PROPERTIES = [
  {
    id: "demo-prop-1",
    name: "Modern Condo Sukhumvit",
    price: 7500000,
    area: 45,
    district: "Watthana",
    lat: 13.7321,
    lon: 100.5678,
  },
  {
    id: "demo-prop-2",
    name: "Townhouse Ekkamai",
    price: 12000000,
    area: 120,
    district: "Watthana",
    lat: 13.7245,
    lon: 100.5812,
  },
  {
    id: "demo-prop-3",
    name: "Single House Phra Khanong",
    price: 18500000,
    area: 200,
    district: "Phra Khanong",
    lat: 13.7089,
    lon: 100.5934,
  },
];
