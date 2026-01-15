import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  Bot,
  User,
  Loader2,
  MapPin,
  X,
  ChevronDown,
  ChevronUp,
  Sparkles,
  MessageSquare,
} from "lucide-react";
import { cn } from "../lib/utils";
import type { AgentStep } from "../lib/api";
import { AgentStepCard, AgentStepBadge } from "./AgentStepCard";
import { ThinkingIndicator } from "./ThinkingIndicator";
import { StreamingMarkdown } from "./ui/markdown";

export type AttachmentType = "location" | "property";

export interface Attachment {
  id: string;
  type: AttachmentType;
  data: Record<string, unknown>;
  label: string;
}

// Extended message with agent steps
interface AgentMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  steps?: AgentStep[];
  isStreaming?: boolean;
  isThinking?: boolean;
}

interface AgentChatPanelProps {
  className?: string;
  attachments?: Attachment[];
  onPickLocation?: () => void;
  onRemoveAttachment?: (id: string) => void;
}

let messageIdCounter = 0;
function generateMessageId(): string {
  return `msg-${++messageIdCounter}-${Date.now()}`;
}

function generateStepId(): string {
  return `step-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

// Mock agent execution for demo
function useMockAgentStream() {
  const [isRunning, setIsRunning] = useState(false);

  const runMockStream = useCallback(
    async (
      userMessage: string,
      onUpdate: (update: {
        thinking?: boolean;
        step?: AgentStep;
        token?: string;
        done?: boolean;
      }) => void
    ) => {
      setIsRunning(true);

      // Simulate thinking
      onUpdate({ thinking: true });
      await delay(800);

      // Determine which tools to call based on message
      const tools = selectToolsForMessage(userMessage);

      for (const tool of tools) {
        // Add tool call step
        const step: AgentStep = {
          id: generateStepId(),
          type: "tool_call",
          name: tool.name,
          status: "running",
          input: tool.input,
          startTime: Date.now(),
        };
        onUpdate({ step, thinking: false });

        // Simulate execution
        await delay(tool.duration);

        // Complete the step
        step.status = "complete";
        step.endTime = Date.now();
        step.output = tool.output;
        onUpdate({ step });

        // Think between tools
        if (tools.indexOf(tool) < tools.length - 1) {
          onUpdate({ thinking: true });
          await delay(400);
        }
      }

      // Stream final response
      onUpdate({ thinking: false });
      const response = generateResponse(userMessage, tools);
      for (const char of response) {
        onUpdate({ token: char });
        await delay(15 + Math.random() * 25);
      }

      onUpdate({ done: true });
      setIsRunning(false);
    },
    []
  );

  return { runMockStream, isRunning };
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

interface MockTool {
  name: string;
  input: Record<string, unknown>;
  output: string;
  duration: number;
}

// Suggested questions for initial state
const SUGGESTED_QUESTIONS = [
  {
    id: "soi-comparison",
    text: "Why are Soi 39 houses pricier than Soi 71?",
    icon: "📊",
  },
  {
    id: "undervalued-schools",
    text: "Show me undervalued homes near international schools.",
    icon: "🏫",
  },
];

function selectToolsForMessage(message: string): MockTool[] {
  const lowerMsg = message.toLowerCase();

  // Special case: Soi 39 vs Soi 71 comparison
  if (lowerMsg.includes("soi 39") && lowerMsg.includes("soi 71")) {
    return [
      {
        name: "analyze_district_comparison",
        input: {
          areas: ["Sukhumvit Soi 39", "Sukhumvit Soi 71"],
          metrics: ["price_sqm", "transit", "schools", "expat_density"],
        },
        output: JSON.stringify(
          {
            soi_39: {
              avg_price_sqm: 185000,
              transit_score: 92,
              int_schools_1km: 3,
              expat_density: "very_high",
            },
            soi_71: {
              avg_price_sqm: 95000,
              transit_score: 78,
              int_schools_1km: 1,
              expat_density: "moderate",
            },
          },
          null,
          2
        ),
        duration: 1400,
      },
      {
        name: "get_market_statistics",
        input: { districts: ["Watthana", "Phra Khanong"] },
        output: JSON.stringify(
          {
            watthana: { avg_price: 18500000, yoy_growth: 8.2 },
            phra_khanong: { avg_price: 7200000, yoy_growth: 12.5 },
          },
          null,
          2
        ),
        duration: 900,
      },
    ];
  }

  // Special case: Undervalued homes near international schools
  if (
    lowerMsg.includes("undervalued") &&
    (lowerMsg.includes("school") || lowerMsg.includes("international"))
  ) {
    return [
      {
        name: "search_international_schools",
        input: { city: "Bangkok", type: "international" },
        output: JSON.stringify(
          {
            schools: [
              { name: "NIST", lat: 13.7380, lon: 100.5690, tier: "premium" },
              { name: "Bangkok Patana", lat: 13.6950, lon: 100.6210, tier: "premium" },
              { name: "Shrewsbury", lat: 13.6680, lon: 100.6120, tier: "premium" },
            ],
          },
          null,
          2
        ),
        duration: 800,
      },
      {
        name: "find_undervalued_properties",
        input: {
          near_schools: true,
          max_distance_m: 2000,
          value_threshold: -15,
        },
        output: JSON.stringify(
          {
            properties: [
              { id: 1245, price: 8500000, predicted: 10200000, gap: -16.7 },
              { id: 892, price: 6200000, predicted: 7400000, gap: -16.2 },
              { id: 2103, price: 12800000, predicted: 14900000, gap: -14.1 },
            ],
          },
          null,
          2
        ),
        duration: 1600,
      },
      {
        name: "analyze_investment_potential",
        input: { property_ids: [1245, 892, 2103] },
        output: JSON.stringify(
          {
            avg_appreciation_5y: 42,
            rental_yield_range: [4.2, 5.8],
          },
          null,
          2
        ),
        duration: 700,
      },
    ];
  }

  if (lowerMsg.includes("price") || lowerMsg.includes("ราคา")) {
    return [
      {
        name: "search_properties",
        input: { query: message, limit: 5 },
        output: JSON.stringify(
          {
            count: 5,
            properties: [
              { id: 1, price: 4500000, district: "บางกะปิ" },
              { id: 2, price: 5200000, district: "ลาดพร้าว" },
            ],
          },
          null,
          2
        ),
        duration: 1200,
      },
      {
        name: "get_market_statistics",
        input: { district: "บางกะปิ" },
        output: JSON.stringify(
          {
            avg_price: 4800000,
            median_price: 4500000,
            price_change_yoy: 5.2,
          },
          null,
          2
        ),
        duration: 800,
      },
    ];
  }

  if (
    lowerMsg.includes("location") ||
    lowerMsg.includes("area") ||
    lowerMsg.includes("พื้นที่")
  ) {
    return [
      {
        name: "get_location_intelligence",
        input: { latitude: 13.7563, longitude: 100.5018, radius_meters: 1000 },
        output: JSON.stringify(
          {
            transit_score: 85,
            walkability_score: 72,
            flood_risk: "low",
            schools_nearby: 8,
          },
          null,
          2
        ),
        duration: 1500,
      },
      {
        name: "analyze_catchment",
        input: { latitude: 13.7563, longitude: 100.5018, minutes: 15 },
        output: JSON.stringify(
          {
            population_reached: 125000,
            area_sqkm: 4.2,
          },
          null,
          2
        ),
        duration: 1000,
      },
    ];
  }

  if (
    lowerMsg.includes("business") ||
    lowerMsg.includes("site") ||
    lowerMsg.includes("ร้าน")
  ) {
    return [
      {
        name: "analyze_site",
        input: {
          latitude: 13.7563,
          longitude: 100.5018,
          target_category: "restaurant",
        },
        output: JSON.stringify(
          {
            site_score: 78,
            competitors_count: 12,
            magnets_count: 8,
            traffic_potential: "High",
          },
          null,
          2
        ),
        duration: 1800,
      },
    ];
  }

  // Default: simple knowledge retrieval
  return [
    {
      name: "retrieve_knowledge",
      input: { query: message },
      output: JSON.stringify(
        {
          documents: [
            { title: "Bangkok Real Estate Guide", relevance: 0.92 },
            { title: "Price Prediction Methodology", relevance: 0.85 },
          ],
        },
        null,
        2
      ),
      duration: 600,
    },
  ];
}

function generateResponse(message: string, _tools?: MockTool[]): string {
  const lowerMsg = message.toLowerCase();

  // Special case: Soi 39 vs Soi 71 comparison
  if (lowerMsg.includes("soi 39") && lowerMsg.includes("soi 71")) {
    return `## Why Soi 39 Commands Premium Prices

Based on my analysis of **847 properties** across both areas, here's why Sukhumvit Soi 39 (Phrom Phong) commands nearly **2x the price** of Soi 71 (Phra Khanong):

### Price Comparison

| Metric | Soi 39 (Phrom Phong) | Soi 71 (Phra Khanong) | Difference |
|--------|---------------------|----------------------|------------|
| Avg. Price/sqm | ฿185,000 | ฿95,000 | **+94.7%** |
| Transit Score | 92/100 | 78/100 | +14 pts |
| Int'l Schools (1km) | 3 | 1 | +2 |
| Expat Density | Very High | Moderate | — |

### Key Premium Factors

1. **Prime BTS Access**: Phrom Phong station is a major hub with direct mall connections (EmQuartier, Emporium)

2. **International Community**: Soi 39 is Bangkok's premier expat neighborhood with:
   - 3 international schools within walking distance
   - Japanese-friendly infrastructure
   - Premium retail and dining

3. **Established Infrastructure**: Mature neighborhood with tree-lined streets, embassies, and luxury condos

4. **Lower Supply**: Limited new development keeps prices elevated

### Investment Insight

> While Soi 71 offers better **value for money** with 12.5% YoY growth (vs 8.2% for Soi 39), Soi 39 remains the **safer long-term hold** for capital preservation.

Would you like me to find specific properties in either area?`;
  }

  // Special case: Undervalued homes near international schools
  if (
    lowerMsg.includes("undervalued") &&
    (lowerMsg.includes("school") || lowerMsg.includes("international"))
  ) {
    return `## Undervalued Properties Near International Schools

I analyzed properties within **2km of premium international schools** and found **3 promising opportunities** priced below our model's predicted value:

### Top Picks

| Property | Listed Price | Model Value | Gap | Nearest School |
|----------|-------------|-------------|-----|----------------|
| #1245 - บ้านเดี่ยว, Sukhumvit 49 | ฿8.5M | ฿10.2M | **-16.7%** | NIST (800m) |
| #892 - ทาวน์เฮ้าส์, Bangna | ฿6.2M | ฿7.4M | **-16.2%** | Bangkok Patana (1.2km) |
| #2103 - บ้านเดี่ยว, Rama 9 | ฿12.8M | ฿14.9M | **-14.1%** | Shrewsbury (1.8km) |

### Why These Are Undervalued

1. **Property #1245** - Owner relocating urgently; property needs cosmetic updates but structure is solid. NIST proximity is exceptional.

2. **Property #892** - Newer development area with infrastructure catching up. BTS Bangna extension will boost values.

3. **Property #2103** - Listed 6 months; price reduced twice. Good negotiation opportunity.

### Investment Potential

Based on historical data for school-adjacent properties:

- **5-Year Appreciation**: ~42% average
- **Rental Yield**: 4.2% - 5.8% (expat family demand)
- **Liquidity**: High (avg. 45 days on market)

### Risk Assessment

| Factor | Rating |
|--------|--------|
| Market Timing | Good |
| Location Quality | Excellent |
| Price Upside | High |

---

*Click on any property ID to view full details, or ask me to compare specific options.*`;
  }

  if (lowerMsg.includes("price") || lowerMsg.includes("ราคา")) {
    return `Based on my analysis of the market data, the average property price in the บางกะปิ district is around **฿4.8 million**.

### Market Summary

| Metric | Value |
|--------|-------|
| Average Price | ฿4.8M |
| Median Price | ฿4.5M |
| YoY Growth | +5.2% |
| Properties Analyzed | 5 |

I found several comparable properties in the area ranging from **฿4.5M to ฿5.2M**.

Would you like me to analyze a specific location or property type in more detail?`;
  }

  if (
    lowerMsg.includes("location") ||
    lowerMsg.includes("area") ||
    lowerMsg.includes("พื้นที่")
  ) {
    return `## Location Analysis

Here's my comprehensive analysis of this location:

### Scores Overview

| Category | Score | Rating |
|----------|-------|--------|
| Transit | 85/100 | Excellent |
| Walkability | 72/100 | Good |
| Schools | 8 nearby | Good |
| Flood Risk | Low | Safe |

### Key Highlights

- **Transit**: Excellent public transit access with BTS/MRT nearby
- **Walkability**: Good walkability with essential amenities within walking distance
- **Catchment**: 15-minute area reaches ~125,000 people across 4.2 sq km

> This is a well-connected location suitable for residential or commercial purposes.`;
  }

  if (
    lowerMsg.includes("business") ||
    lowerMsg.includes("site") ||
    lowerMsg.includes("ร้าน")
  ) {
    return `## Site Analysis Results

### Overall Score: **78/100** - Good Potential

| Factor | Value | Assessment |
|--------|-------|------------|
| Competitors | 12 nearby | Moderate |
| Traffic Magnets | 8 nearby | Good |
| Traffic Potential | High | Excellent |

### Insights

This location has a healthy balance of foot traffic drivers while maintaining manageable competition. The proximity to transit and schools creates consistent daily traffic patterns.

Would you like me to compare this with other potential sites?`;
  }

  return `I found some relevant information in our knowledge base. Based on the Bangkok real estate data:

### Market Overview

The Bangkok property market shows varied trends across districts:

- **Prime areas** (Sukhumvit): ฿10-15M+ THB
- **Developing areas** (near new transit): ฿3-6M THB with strong appreciation potential

What specific aspect would you like me to explore further?`;
}

// Suggested questions component
interface SuggestedQuestionsProps {
  onSelect: (question: string) => void;
  disabled?: boolean;
}

function SuggestedQuestions({ onSelect, disabled }: SuggestedQuestionsProps) {
  return (
    <div className="px-3 pb-2">
      <div className="flex items-center gap-1.5 text-[10px] text-white/50 mb-2">
        <MessageSquare size={10} />
        <span>Try asking</span>
      </div>
      <div className="flex flex-col gap-2">
        {SUGGESTED_QUESTIONS.map((q) => (
          <button
            key={q.id}
            type="button"
            onClick={() => onSelect(q.text)}
            disabled={disabled}
            className={cn(
              "text-left px-3 py-2.5 rounded-lg border transition-all text-sm",
              "bg-white/5 border-white/10 text-white/80",
              "hover:bg-emerald-500/10 hover:border-emerald-500/30 hover:text-white",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              "group"
            )}
          >
            <span className="mr-2">{q.icon}</span>
            <span className="group-hover:text-emerald-300 transition-colors">
              {q.text}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

// Assistant message with steps visualization
interface AssistantMessageProps {
  message: AgentMessage;
}

function AssistantMessage({ message }: AssistantMessageProps) {
  const [showSteps, setShowSteps] = useState(true);
  const hasSteps = message.steps && message.steps.length > 0;
  const completedSteps =
    message.steps?.filter((s) => s.status === "complete") || [];
  const runningStep = message.steps?.find((s) => s.status === "running");

  return (
    <div className="flex gap-2">
      <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-emerald-500/20">
        <Bot size={12} className="text-emerald-400" />
      </div>
      <div className="flex-1 space-y-2 min-w-0">
        {/* Steps section */}
        {hasSteps && (
          <div className="space-y-1.5">
            {/* Toggle button */}
            <button
              type="button"
              onClick={() => setShowSteps(!showSteps)}
              className="flex items-center gap-1.5 text-[10px] text-white/50 hover:text-white/70 transition-colors"
            >
              {showSteps ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              <Sparkles size={10} />
              <span>
                {completedSteps.length} tool
                {completedSteps.length !== 1 ? "s" : ""} used
              </span>
            </button>

            {/* Expanded steps view */}
            {showSteps && (
              <div className="space-y-1.5">
                {message.steps?.map((step) => (
                  <AgentStepCard key={step.id} step={step} />
                ))}
              </div>
            )}

            {/* Collapsed badges view */}
            {!showSteps && (
              <div className="flex flex-wrap gap-1">
                {message.steps?.map((step) => (
                  <AgentStepBadge
                    key={step.id}
                    step={step}
                    onClick={() => setShowSteps(true)}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Thinking indicator */}
        {message.isThinking && !runningStep && (
          <ThinkingIndicator startTime={Date.now()} />
        )}

        {/* Message content */}
        {(message.content || message.isStreaming) && (
          <div className="max-w-full rounded-xl px-3 py-2 text-sm bg-white/5 text-white/90">
            {message.content ? (
              <StreamingMarkdown
                content={message.content}
                isStreaming={message.isStreaming}
              />
            ) : (
              <span className="flex items-center gap-1 text-white/50">
                <Loader2 size={12} className="animate-spin" />
                Generating response...
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function AgentChatPanel({
  className,
  attachments = [],
  onPickLocation,
  onRemoveAttachment,
}: AgentChatPanelProps) {
  const [messages, setMessages] = useState<AgentMessage[]>([
    {
      id: generateMessageId(),
      role: "assistant",
      content:
        "Hello! I'm your real estate AI assistant. I can help you with property prices, market insights, and location analysis. What would you like to know?",
    },
  ]);
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { runMockStream, isRunning } = useMockAgentStream();

  // Show suggested questions only when we have just the initial message
  const showSuggestions = messages.length === 1 && messages[0].role === "assistant";

  // Handle suggested question click
  const handleSuggestedQuestion = (question: string) => {
    setInput(question);
    // Auto-submit after a brief delay for better UX
    setTimeout(() => {
      inputRef.current?.focus();
    }, 50);
  };

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((!input.trim() && attachments.length === 0) || isRunning) return;

    let content = input.trim();
    if (attachments.length > 0) {
      const attachmentText = attachments
        .map((a) => `[Attachment: ${a.type} - ${JSON.stringify(a.data)}]`)
        .join("\n");
      content = `${content}\n\n${attachmentText}`.trim();
    }

    const userMessage: AgentMessage = {
      id: generateMessageId(),
      role: "user",
      content,
    };

    const assistantMessageId = generateMessageId();
    const assistantMessage: AgentMessage = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      steps: [],
      isThinking: true,
      isStreaming: false,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput("");

    // Run mock agent stream
    await runMockStream(content, (update) => {
      setMessages((prev) => {
        const updated = [...prev];
        const msgIndex = updated.findIndex((m) => m.id === assistantMessageId);
        if (msgIndex === -1) return prev;

        const msg = { ...updated[msgIndex] };

        if (update.thinking !== undefined) {
          msg.isThinking = update.thinking;
        }

        if (update.step) {
          // Update or add step
          const currentStep = update.step;
          const stepIndex = msg.steps?.findIndex(
            (s) => s.id === currentStep.id
          );
          if (stepIndex !== undefined && stepIndex >= 0) {
            msg.steps = [...(msg.steps || [])];
            msg.steps[stepIndex] = update.step;
          } else {
            msg.steps = [...(msg.steps || []), update.step];
          }
        }

        if (update.token) {
          msg.content += update.token;
          msg.isStreaming = true;
          msg.isThinking = false;
        }

        if (update.done) {
          msg.isStreaming = false;
          msg.isThinking = false;
        }

        updated[msgIndex] = msg;
        return updated;
      });
    });

    // Clear attachments
    attachments.forEach((a) => {
      onRemoveAttachment?.(a.id);
    });

    inputRef.current?.focus();
  };

  return (
    <div className={cn("flex flex-col h-full", className)}>
      {/* Header */}
      <div className="flex items-center gap-2 p-3 border-b border-white/10">
        <div className="w-8 h-8 bg-emerald-500/20 rounded-lg flex items-center justify-center">
          <Bot size={18} className="text-emerald-400" />
        </div>
        <div>
          <h3 className="text-sm font-medium text-white">AI Assistant</h3>
          <p className="text-[10px] text-white/50">
            Real Estate Expert • ReAct Agent
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4 custom-scrollbar">
        {messages.map((message) =>
          message.role === "user" ? (
            <div key={message.id} className="flex gap-2 flex-row-reverse">
              <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-blue-500/20">
                <User size={12} className="text-blue-400" />
              </div>
              <div className="max-w-[85%] rounded-xl px-3 py-2 text-sm bg-blue-500/20 text-white">
                {message.content}
              </div>
            </div>
          ) : (
            <AssistantMessage key={message.id} message={message} />
          )
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Questions - show only at initial state */}
      {showSuggestions && (
        <SuggestedQuestions
          onSelect={handleSuggestedQuestion}
          disabled={isRunning}
        />
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-white/10">
        {/* Attachments */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {attachments.map((att) => (
              <div
                key={att.id}
                className="flex items-center gap-1 bg-white/10 rounded-full px-2 py-1 text-xs text-white/80"
              >
                <span className="truncate max-w-36">{att.label}</span>
                <button
                  type="button"
                  onClick={() => onRemoveAttachment?.(att.id)}
                  className="hover:text-white"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          <button
            type="button"
            onClick={onPickLocation}
            className="p-2 bg-white/5 hover:bg-white/10 rounded-lg text-white/70 transition-colors"
            title="Pick location on map"
          >
            <MapPin size={18} />
          </button>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about prices, locations, site analysis..."
            disabled={isRunning}
            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-emerald-500/50 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={(!input.trim() && attachments.length === 0) || isRunning}
            className="p-2 bg-emerald-500 hover:bg-emerald-600 disabled:bg-white/10 disabled:text-white/30 rounded-lg text-black transition-colors"
          >
            {isRunning ? (
              <Loader2 size={18} className="animate-spin text-white/50" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
