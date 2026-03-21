/**
 * Comprehensive Price Analysis Report component.
 * Displays predicted price with model signals, market context,
 * comparable properties analysis, and confidence metrics.
 */

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart3,
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Home,
  Info,
  Scale,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  api,
  type ExplainabilityEvidenceResponse,
  type HousePriceItem,
  type PricePredictRequest,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface ComprehensivePriceReportProps {
  propertyId?: number;
  property: HousePriceItem;
  predictionRequest?: PricePredictRequest;
}

// Types for extended report data
interface ComparableProperty {
  id: number;
  price: number;
  building_style_desc: string | null;
  building_area: number | null;
  distance_m: number;
  similarity_score: number;
  price_diff_percent: number;
}

interface MetricCardProps {
  label: string;
  value: string;
  helper?: string;
}

interface SignalShare {
  feature: string;
  featureDisplay: string;
  value: number;
  direction: "positive" | "negative";
  share: number;
}

// Helper functions
function formatPrice(price: number): string {
  if (price >= 1_000_000) {
    return `฿${(price / 1_000_000).toFixed(2)}M`;
  }
  return `฿${price.toLocaleString()}`;
}

function formatFeatureValue(feature: string, value: number): string {
  if (feature.includes("area")) return `${value.toFixed(0)} sqm`;
  if (feature.includes("age")) return `${value.toFixed(0)} years`;
  if (feature.includes("floor")) return `${value.toFixed(0)} floors`;
  if (feature.includes("score")) return `${value.toFixed(0)}/100`;
  if (feature.includes("density") || feature.includes("stops"))
    return `${value.toFixed(0)} nearby`;
  if (feature === "building_style") {
    const styles: Record<number, string> = {
      0: "Unknown",
      1: "บ้านเดี่ยว",
      2: "ทาวน์เฮ้าส์",
      3: "บ้านแฝด",
      4: "อาคารพาณิชย์",
      5: "ตึกแถว",
    };
    return styles[value] || "Other";
  }
  if (feature === "district_avg_price_sqm")
    return `฿${value.toLocaleString()}/sqm`;
  return value.toFixed(2);
}

function generateMockExtendedData(
  property: HousePriceItem,
  predictedPrice: number,
  nearbyProperties: (HousePriceItem & { distance_m: number })[],
): {
  comparables: ComparableProperty[];
  pricePercentile: number;
  priceRange: { min: number; max: number };
} {
  const comparables: ComparableProperty[] = nearbyProperties
    .filter((p) => p.id !== property.id && p.total_price && p.total_price > 0)
    .slice(0, 4)
    .map((p) => {
      const totalPrice = p.total_price ?? 0;
      const priceDiff = property.total_price
        ? ((totalPrice - property.total_price) / property.total_price) * 100
        : 0;

      // Calculate similarity based on building area and style
      let similarity = 70; // Base similarity
      if (p.building_style_desc === property.building_style_desc) {
        similarity += 15;
      }
      if (
        p.building_area &&
        property.building_area &&
        Math.abs(p.building_area - property.building_area) < 50
      ) {
        similarity += 15;
      }

      return {
        id: p.id,
        price: totalPrice,
        building_style_desc: p.building_style_desc,
        building_area: p.building_area,
        distance_m: p.distance_m,
        similarity_score: Math.min(similarity, 98),
        price_diff_percent: priceDiff,
      };
    });

  const avgComparablePrice =
    comparables.length > 0
      ? comparables.reduce((sum, c) => sum + c.price, 0) / comparables.length
      : predictedPrice;
  const pricePercentile =
    property.total_price && avgComparablePrice
      ? Math.min(
          Math.max(
            50 +
              ((property.total_price - avgComparablePrice) /
                avgComparablePrice) *
                50,
            5,
          ),
          95,
        )
      : 50;

  // Calculate price range with confidence interval
  const priceRange = {
    min: Math.round(predictedPrice * 0.92),
    max: Math.round(predictedPrice * 1.08),
  };

  return {
    comparables,
    pricePercentile,
    priceRange,
  };
}

// Sub-components
function SectionHeader({
  icon: Icon,
  title,
  expandable,
  expanded,
  onToggle,
}: {
  icon: React.ComponentType<{ className?: string; size?: number }>;
  title: string;
  expandable?: boolean;
  expanded?: boolean;
  onToggle?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={!expandable}
      className={cn(
        "flex items-center gap-2 w-full text-left",
        expandable && "cursor-pointer hover:text-foreground transition-colors",
      )}
    >
      <Icon size={16} className="text-brand" />
      <span className="font-semibold text-foreground text-sm flex-1">
        {title}
      </span>
      {expandable &&
        (expanded ? (
          <ChevronUp size={14} className="text-muted-foreground" />
        ) : (
          <ChevronDown size={14} className="text-muted-foreground" />
        ))}
    </button>
  );
}

function ConfidenceBadge({ level }: { level: "high" | "medium" | "low" }) {
  const config = {
    high: {
      bg: "bg-success/10",
      text: "text-success",
      icon: CheckCircle2,
      label: "High Confidence",
    },
    medium: {
      bg: "bg-warning/20",
      text: "text-warning",
      icon: Info,
      label: "Medium Confidence",
    },
    low: {
      bg: "bg-destructive/10",
      text: "text-destructive",
      icon: AlertTriangle,
      label: "Low Confidence",
    },
  };
  const { bg, text, icon: Icon, label } = config[level];

  return (
    <div className={cn("flex items-center gap-1.5 px-2 py-1 rounded-full", bg)}>
      <Icon size={12} className={text} />
      <span className={cn("text-xs font-medium", text)}>{label}</span>
    </div>
  );
}

function valuationConfidenceFromData(
  confidence: number,
): "high" | "medium" | "low" {
  if (confidence >= 0.8) {
    return "high";
  }
  if (confidence >= 0.6) {
    return "medium";
  }
  return "low";
}

function buildSignalShares(
  featureContributions: {
    feature: string;
    feature_display: string;
    value: number;
    direction: "positive" | "negative";
    contribution: number;
  }[],
): SignalShare[] {
  const totalMagnitude = featureContributions.reduce(
    (sum, item) => sum + Math.abs(item.contribution),
    0,
  );

  if (totalMagnitude <= 0) {
    return [];
  }

  return featureContributions.map((item) => ({
    feature: item.feature,
    featureDisplay: item.feature_display,
    value: item.value,
    direction: item.direction,
    share: Math.abs(item.contribution) / totalMagnitude,
  }));
}

function ContributionBar({
  featureDisplay,
  feature,
  value,
  direction,
  share,
}: {
  featureDisplay: string;
  feature: string;
  value: number;
  direction: "positive" | "negative";
  share: number;
}) {
  const widthPercent = Math.max(8, Math.round(share * 100));

  return (
    <div className="rounded-xl border border-border/70 bg-muted/20 p-3">
      <div className="mb-2 flex items-start justify-between gap-3 text-xs">
        <span className="font-medium text-foreground">{featureDisplay}</span>
        <span className="text-muted-foreground">
          {formatFeatureValue(feature, value)}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <div className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-muted/60">
          <div
            className={cn(
              "absolute h-full rounded-full transition-all",
              direction === "positive" ? "bg-success/70" : "bg-destructive/70",
            )}
            style={{ width: `${widthPercent}%` }}
          />
        </div>
        <span
          className={cn(
            "min-w-14 text-right text-[11px] font-semibold",
            direction === "positive" ? "text-success" : "text-destructive",
          )}
        >
          {(share * 100).toFixed(0)}%
        </span>
      </div>
      <div className="mt-2 text-[11px] text-muted-foreground">
        {direction === "positive"
          ? "Relatively stronger upward pressure"
          : "Relatively stronger downward pressure"}
      </div>
    </div>
  );
}

function ComparableCard({ comp }: { comp: ComparableProperty }) {
  const isHigher = comp.price_diff_percent > 0;

  return (
    <div className="bg-muted/50 rounded-lg p-3 border border-border">
      <div className="flex items-start justify-between mb-2">
        <div>
          <p className="text-sm font-medium text-foreground">
            {comp.building_style_desc || "Property"}
          </p>
          <p className="text-xs text-muted-foreground">
            {Math.round(comp.distance_m)}m away
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm font-semibold text-brand">
            {formatPrice(comp.price)}
          </p>
          <p
            className={cn(
              "text-xs",
              isHigher ? "text-destructive" : "text-success",
            )}
          >
            {isHigher ? "+" : ""}
            {comp.price_diff_percent.toFixed(1)}%
          </p>
        </div>
      </div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">
          {comp.building_area ? `${comp.building_area} sqm` : "-"}
        </span>
        <div className="flex items-center gap-1">
          <span className="text-muted-foreground">Similarity:</span>
          <span className="text-brand font-medium">
            {comp.similarity_score}%
          </span>
        </div>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="animate-pulse space-y-4">
        <div className="h-6 bg-muted/50 rounded w-1/3" />
        <div className="grid grid-cols-2 gap-4">
          <div className="h-20 bg-muted/50 rounded" />
          <div className="h-20 bg-muted/50 rounded" />
        </div>
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={`skeleton-${i}`} className="h-8 bg-muted/50 rounded" />
          ))}
        </div>
      </div>
    </div>
  );
}

function formatEvidenceMetric(metric: string, value: number): string {
  if (metric.includes("mae") || metric.includes("rmse")) {
    return `฿${Math.round(value).toLocaleString()}`;
  }
  if (
    metric.includes("mape") ||
    metric.includes("coverage") ||
    metric.includes("overlap")
  ) {
    return `${(value * (value <= 1 ? 100 : 1)).toFixed(1)}${value <= 1 ? "%" : ""}`;
  }
  if (metric === "r2") {
    return value.toFixed(3);
  }
  if (
    metric.includes("delta") ||
    metric.includes("lift") ||
    metric.includes("correlation")
  ) {
    return value.toFixed(3);
  }
  return value.toFixed(2);
}

function formatMetricLabel(metric: string): string {
  return metric
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatEvidenceTimestamp(timestamp: string | null | undefined): string {
  if (!timestamp) {
    return "Unknown";
  }

  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function MetricCard({ label, value, helper }: MetricCardProps) {
  return (
    <div className="rounded-xl border border-border bg-muted/35 p-4">
      <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </div>
      <div className="mt-2 break-words text-lg font-semibold leading-7 text-foreground">
        {value}
      </div>
      {helper ? (
        <div className="mt-2 text-xs leading-5 text-muted-foreground">{helper}</div>
      ) : null}
    </div>
  );
}

function ExplainabilityEvidenceSection({
  evidence,
  isLoading,
  error,
}: {
  evidence: ExplainabilityEvidenceResponse | undefined;
  isLoading: boolean;
  error: Error | null;
}) {
  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="animate-pulse space-y-3">
          <div className="h-5 w-48 rounded bg-muted/50" />
          <div className="h-16 rounded bg-muted/50" />
          <div className="grid grid-cols-2 gap-3">
            <div className="h-20 rounded bg-muted/50" />
            <div className="h-20 rounded bg-muted/50" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4">
        <div className="text-sm text-destructive font-medium mb-1">
          Explainability Evidence Unavailable
        </div>
        <p className="text-xs text-muted-foreground">{error.message}</p>
      </div>
    );
  }

  if (!evidence) {
    return null;
  }

  const primaryMetrics = [
    "faithfulness_lift",
    "shap_rank_correlation",
    "top5_overlap",
    "expected_feature_coverage",
  ];
  const shownPrimaryMetrics = primaryMetrics.filter(
    (metric) => evidence.explanation_metrics[metric] !== undefined,
  );

  return (
    <div className="space-y-5 rounded-xl border border-border bg-muted/15 p-4 sm:p-5">
      <div className="flex flex-col gap-3">
        <div>
          <h4 className="text-sm font-semibold text-foreground">
            Explainability Evidence
          </h4>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
            {evidence.summary}
          </p>
        </div>
        <div className="w-fit rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
          {evidence.evaluation_complete ? "Benchmarked" : "Partial Evidence"}
        </div>
      </div>

      <div className="space-y-3">
        <MetricCard
          label="Runtime Method"
          value={formatMetricLabel(evidence.runtime_explanation_method)}
        />
        <MetricCard
          label="Last Generated"
          value={formatEvidenceTimestamp(evidence.generated_at)}
        />
        {evidence.model_performance.mae !== undefined && (
          <MetricCard
            label="Model MAE"
            value={formatEvidenceMetric("mae", evidence.model_performance.mae)}
            helper="Offline CV performance"
          />
        )}
        {evidence.model_performance.r2 !== undefined && (
          <MetricCard
            label="Model R2"
            value={formatEvidenceMetric("r2", evidence.model_performance.r2)}
          />
        )}
      </div>

      {shownPrimaryMetrics.length > 0 && (
        <div>
          <div className="mb-2 text-xs uppercase tracking-[0.08em] text-muted-foreground">
            Benchmark Metrics
          </div>
          <div className="space-y-3">
            {shownPrimaryMetrics.map((metric) => (
              <MetricCard
                key={metric}
                label={formatMetricLabel(metric)}
                value={formatEvidenceMetric(
                  metric,
                  evidence.explanation_metrics[metric],
                )}
              />
            ))}
          </div>
        </div>
      )}

      {evidence.top_shap_features.length > 0 && (
        <div>
          <div className="mb-2 text-xs uppercase tracking-[0.08em] text-muted-foreground">
            Top Offline SHAP Features
          </div>
          <p className="mb-3 text-xs leading-5 text-muted-foreground">
            These features come from offline benchmark runs. They validate the runtime explanation method, but they are not a direct per-property price breakdown.
          </p>
          <div className="space-y-3">
            {evidence.top_shap_features.map((feature, index) => (
              <div
                key={feature.feature}
                className="rounded-xl border border-border bg-muted/30 px-4 py-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border/70 bg-card/70 text-xs text-muted-foreground">
                      {index + 1}
                    </span>
                    <span className="text-base leading-7 text-foreground">
                      {formatMetricLabel(feature.feature)}
                    </span>
                  </div>
                  <span className="shrink-0 pt-1 text-xs font-mono text-muted-foreground">
                    {feature.importance.toFixed(4)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {evidence.missing_artifacts.length > 0 && (
        <div className="rounded-lg border border-warning/30 bg-warning/10 p-3">
          <div className="mb-2 text-xs uppercase tracking-[0.08em] text-warning">
            Missing Artifacts
          </div>
          <p className="text-sm text-foreground/90">
            {evidence.missing_artifacts.join(", ")}
          </p>
        </div>
      )}

      <div className="space-y-2">
        <div className="text-xs uppercase tracking-[0.08em] text-muted-foreground">
          Notes
        </div>
        {evidence.notes.map((note) => (
          <p key={note} className="text-sm text-muted-foreground leading-6">
            {note}
          </p>
        ))}
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="text-center py-4">
        <AlertTriangle className="h-8 w-8 text-destructive mx-auto mb-2" />
        <div className="text-destructive text-sm mb-2">
          Price Analysis Unavailable
        </div>
        <p className="text-muted-foreground text-xs">{message}</p>
      </div>
    </div>
  );
}

export function ComprehensivePriceReport({
  propertyId,
  property,
  predictionRequest,
}: ComprehensivePriceReportProps) {
  const [showFactors, setShowFactors] = useState(false);
  const [showComparables, setShowComparables] = useState(true);
  const [showEvidence, setShowEvidence] = useState(false);

  // Fetch price explanation from API
  const {
    data: priceData,
    isLoading: isPriceLoading,
    error: priceError,
  } = useQuery({
    queryKey: [
      "priceExplanation",
      propertyId ?? null,
      predictionRequest ?? null,
    ],
    queryFn: () => {
      if (typeof propertyId === "number") {
        return api.getPriceExplanation(propertyId);
      }
      if (predictionRequest) {
        return api.predictPrice(predictionRequest);
      }
      throw new Error("No property context for prediction");
    },
    enabled: typeof propertyId === "number" || !!predictionRequest,
    staleTime: 1000 * 60 * 10,
    retry: false,
  });

  const {
    data: localShapData,
    isLoading: isLocalShapLoading,
    error: localShapError,
  } = useQuery({
    queryKey: ["localShap", propertyId ?? null, predictionRequest ?? null],
    queryFn: () => {
      if (typeof propertyId === "number") {
        return api.getLocalShapExplanation(propertyId);
      }
      if (predictionRequest) {
        return api.predictLocalShap(predictionRequest);
      }
      throw new Error("No property context for local SHAP");
    },
    enabled:
      showFactors && (typeof propertyId === "number" || !!predictionRequest),
    staleTime: 1000 * 60 * 10,
    retry: false,
  });

  // Fetch nearby properties for comparables
  const { data: nearbyData } = useQuery({
    queryKey: ["nearbyProperties", property.lat, property.lon, "comparables"],
    queryFn: () =>
      api.getNearbyProperties({
        lat: property.lat,
        lon: property.lon,
        radius_m: 1500,
        building_style: property.building_style_desc || undefined,
        limit: 10,
      }),
    enabled: !!property,
    staleTime: 1000 * 60 * 5,
  });

  const {
    data: explainabilityEvidence,
    isLoading: isEvidenceLoading,
    error: evidenceError,
  } = useQuery({
    queryKey: ["explainabilityEvidence", priceData?.model_type],
    queryFn: () =>
      api.getExplainabilityEvidence(priceData?.model_type || "baseline"),
    enabled: !!priceData?.model_type,
    staleTime: 1000 * 60 * 10,
    retry: false,
  });

  // Generate extended data based on real data
  const extendedData = useMemo(() => {
    if (!priceData || !nearbyData) return null;
    return generateMockExtendedData(
      property,
      priceData.predicted_price,
      nearbyData.items,
    );
  }, [priceData, nearbyData, property]);

  if (isPriceLoading) {
    return <LoadingState />;
  }

  if (priceError) {
    return <ErrorState message={(priceError as Error).message} />;
  }

  if (!priceData) {
    return null;
  }

  const activeSignalData = localShapData || priceData;
  const signalShares = buildSignalShares(
    activeSignalData.feature_contributions,
  );

  const actualPrice = property.total_price;
  const priceDifference = actualPrice
    ? priceData.predicted_price - actualPrice
    : null;
  const priceDifferencePercent =
    priceDifference && actualPrice
      ? (priceDifference / actualPrice) * 100
      : null;

  return (
    <div className="space-y-4">
      {/* Main Price Card */}
      <div className="bg-card border border-border rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-foreground font-semibold flex items-center gap-2">
            <BarChart3 size={18} className="text-brand" />
            {priceData.explanation_title}
          </h3>
          <ConfidenceBadge
            level={valuationConfidenceFromData(priceData.confidence)}
          />
        </div>
        <p className="text-sm text-muted-foreground mb-4">
          {priceData.explanation_summary}
        </p>

        {/* Price Summary */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="bg-brand/10 border border-brand/20 rounded-lg p-3">
            <div className="text-muted-foreground text-xs uppercase tracking-wide mb-1">
              Predicted Value
            </div>
            <div className="text-2xl font-bold text-brand">
              {formatPrice(priceData.predicted_price)}
            </div>
            {extendedData && (
              <div className="text-xs text-muted-foreground mt-1">
                Range: {formatPrice(extendedData.priceRange.min)} -{" "}
                {formatPrice(extendedData.priceRange.max)}
              </div>
            )}
          </div>

          <div className="bg-muted/50 border border-border rounded-lg p-3">
            <div className="text-muted-foreground text-xs uppercase tracking-wide mb-1">
              Appraised Value
            </div>
            <div className="text-2xl font-bold text-foreground">
              {actualPrice ? formatPrice(actualPrice) : "-"}
            </div>
            {priceDifferencePercent !== null && (
              <div
                className={cn(
                  "text-xs mt-1",
                  priceDifferencePercent >= 0
                    ? "text-success"
                    : "text-destructive",
                )}
              >
                {priceDifferencePercent >= 0 ? "+" : ""}
                {priceDifferencePercent.toFixed(1)}% from model
              </div>
            )}
          </div>
        </div>

        {/* Market Position */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          {/* District Comparison */}
          {priceData.district_avg_price !== null &&
            priceData.price_vs_district !== null &&
            priceData.district_avg_price > 0 && (
              <div className="bg-muted/50 rounded-lg p-3">
                <div className="text-xs text-muted-foreground mb-1">
                  vs. District Avg
                </div>
                <div
                  className={cn(
                    "text-lg font-bold",
                    priceData.price_vs_district >= 0
                      ? "text-success"
                      : "text-destructive",
                  )}
                >
                  {priceData.price_vs_district >= 0 ? "+" : ""}
                  {priceData.price_vs_district.toFixed(1)}%
                </div>
              </div>
            )}

          {/* Price Percentile */}
          {extendedData && (
            <div className="bg-muted/50 rounded-lg p-3">
              <div className="text-xs text-muted-foreground mb-1">
                Price Percentile
              </div>
              <div className="text-lg font-bold text-foreground">
                Top {(100 - extendedData.pricePercentile).toFixed(0)}%
              </div>
            </div>
          )}
        </div>

        {/* Price per sqm */}
        {property.building_area && priceData.predicted_price && (
          <div className="bg-muted/50 rounded-lg p-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Building2 size={14} className="text-muted-foreground" />
              <span className="text-sm text-muted-foreground">
                Predicted Price per sqm
              </span>
            </div>
            <span className="text-sm font-semibold text-foreground">
              ฿
              {Math.round(
                priceData.predicted_price / property.building_area,
              ).toLocaleString()}
            </span>
          </div>
        )}
      </div>

      {/* Model Signals */}
      <div className="bg-card border border-border rounded-lg p-4">
        <SectionHeader
          icon={Scale}
          title={
            activeSignalData.explanation_method === "local_shap"
              ? "Local SHAP Signals"
              : "Model Signals"
          }
          expandable
          expanded={showFactors}
          onToggle={() => setShowFactors(!showFactors)}
        />
        {showFactors && (
          <div className="mt-4">
            <p className="mb-4 text-sm leading-6 text-muted-foreground">
              These signals show which inputs mattered most for this estimate. They are relative weights for this prediction, not additive baht adjustments.
            </p>
            {isLocalShapLoading ? (
              <div className="space-y-3">
                <div className="h-4 w-40 animate-pulse rounded bg-muted" />
                {[1, 2, 3].map((item) => (
                  <div
                    key={`signal-skeleton-${item}`}
                    className="rounded-xl border border-border/70 bg-muted/20 p-3"
                  >
                    <div className="mb-2 h-3 w-28 animate-pulse rounded bg-muted" />
                    <div className="h-2.5 w-full animate-pulse rounded-full bg-muted" />
                  </div>
                ))}
              </div>
            ) : null}
            {localShapError ? (
              <p className="text-xs text-warning mb-3">
                Fell back to baseline model signals because local SHAP could not
                be loaded.
              </p>
            ) : null}
            {signalShares.map((contrib) => (
              <ContributionBar
                key={contrib.feature}
                featureDisplay={contrib.featureDisplay}
                feature={contrib.feature}
                value={contrib.value}
                direction={contrib.direction}
                share={contrib.share}
              />
            ))}
            <p className="text-xs text-muted-foreground mb-3">
              {activeSignalData.explanation_method === "local_shap"
                ? "Local SHAP is available for this property, so the ordering reflects this specific estimate."
                : "Runtime SHAP was unavailable, so these bars fall back to the model explanation response."}
            </p>
            <div className="flex gap-4 text-xs text-muted-foreground mt-3 pt-3 border-t border-border">
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded bg-success/70" />
                <span>Higher relative pressure</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded bg-destructive/70" />
                <span>Lower relative pressure</span>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-3">
              {priceData.explanation_disclaimer}
            </p>
            {priceData.explanation_narrative && (
              <div className="mt-4 rounded-lg border border-border bg-muted/40 p-3">
                <div className="text-xs uppercase tracking-wide text-muted-foreground mb-2">
                  Natural Language Summary
                </div>
                <p className="text-sm leading-6 text-foreground/90">
                  {priceData.explanation_narrative}
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Comparable Properties */}
      {extendedData && extendedData.comparables.length > 0 && (
        <div className="bg-card border border-border rounded-lg p-4">
          <SectionHeader
            icon={Home}
            title={`Comparable Properties (${extendedData.comparables.length})`}
            expandable
            expanded={showComparables}
            onToggle={() => setShowComparables(!showComparables)}
          />
          {showComparables && (
            <div className="mt-4 space-y-3">
              {extendedData.comparables.map((comp) => (
                <ComparableCard key={comp.id} comp={comp} />
              ))}
              {extendedData.comparables.length > 0 && (
                <div className="bg-muted/50 rounded-lg p-3 flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    Avg. Comparable Price
                  </span>
                  <span className="text-sm font-semibold text-brand">
                    {formatPrice(
                      extendedData.comparables.reduce(
                        (sum, c) => sum + c.price,
                        0,
                      ) / extendedData.comparables.length,
                    )}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="bg-card border border-border rounded-lg p-4">
        <SectionHeader
          icon={CheckCircle2}
          title="Explainability Evidence"
          expandable
          expanded={showEvidence}
          onToggle={() => setShowEvidence(!showEvidence)}
        />
        {showEvidence && (
          <div className="mt-4">
            <ExplainabilityEvidenceSection
              evidence={explainabilityEvidence}
              isLoading={isEvidenceLoading}
              error={evidenceError as Error | null}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default ComprehensivePriceReport;
