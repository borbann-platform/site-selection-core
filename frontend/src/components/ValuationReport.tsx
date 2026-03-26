/**
 * Valuation Report - Displays comprehensive property valuation results.
 * Shows estimated price, factors, comparables, and investment insights.
 */

import { useState, useRef, useCallback } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  TrendingUp,
  TrendingDown,
  BarChart3,
  Home,
  MapPin,
  Scale,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Info,
  Building2,
  Download,
  ArrowLeft,
  Sparkles,
  Calendar,
  DollarSign,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { SourceTooltip } from "@/components/ui/source-tooltip";
import type {
  ValuationResponse,
  PropertyUploadRequest,
  LocationIntelligenceResponse,
} from "@/lib/api";
import { LocationIntelligencePanel } from "@/components/LocationIntelligence";
import { DATA_SOURCES } from "@/lib/dataSources";
import { SCORE_METHODOLOGY } from "@/lib/scoreMethodology";

interface ValuationReportProps {
  valuation: ValuationResponse;
  propertyData: PropertyUploadRequest;
  locationIntelligence?: LocationIntelligenceResponse | null;
  onBack: () => void;
  onNewValuation: () => void;
}

function formatPrice(price: number): string {
  if (price >= 1_000_000) {
    return `฿${(price / 1_000_000).toFixed(2)}M`;
  }
  return `฿${price.toLocaleString()}`;
}

function ConfidenceBadge({ level }: { level: "high" | "medium" | "low" }) {
  const config = {
    high: {
      bg: "bg-brand/10",
      text: "text-brand",
      border: "border-brand/20",
      icon: CheckCircle2,
      label: "High Confidence",
      description: "Strong data support for this valuation",
    },
    medium: {
      bg: "bg-warning/20",
      text: "text-warning",
      border: "border-warning/30",
      icon: Info,
      label: "Medium Confidence",
      description: "Moderate data support; consider additional verification",
    },
    low: {
      bg: "bg-destructive/10",
      text: "text-destructive",
      border: "border-destructive/30",
      icon: AlertTriangle,
      label: "Low Confidence",
      description: "Limited data; valuation is an estimate only",
    },
  };
  const { bg, text, border, icon: Icon, label, description } = config[level];

  return (
    <div className={cn("p-4 rounded-lg border", bg, border)}>
      <div className="flex items-center gap-2 mb-1">
        <Icon size={18} className={text} />
        <span className={cn("font-semibold", text)}>{label}</span>
      </div>
      <p className="text-xs text-muted-foreground">{description}</p>
    </div>
  );
}

function FactorBar({
  factor,
  estimatedPrice,
  maxPct,
}: {
  factor: ValuationResponse["factors"][0];
  estimatedPrice: number;
  maxPct: number;
}) {
  const contributionPct =
    factor.contribution_pct ?? (estimatedPrice > 0
      ? Math.abs(factor.impact / estimatedPrice) * 100
      : 0);
  const widthPercent = maxPct > 0
    ? Math.max(8, Math.round((contributionPct / maxPct) * 100))
    : 8;
  const isPositive = factor.direction === "positive";

  return (
    <div className="rounded-xl border border-border/70 bg-muted/20 p-3">
      <div className="mb-2 flex items-start justify-between gap-3 text-xs">
        <span className="font-medium text-foreground">{factor.display_name}</span>
        <span className="text-muted-foreground">{factor.description}</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-muted/60">
          <div
            className={cn(
              "absolute h-full rounded-full transition-all",
              isPositive ? "bg-success/70" : "bg-destructive/70"
            )}
            style={{ width: `${widthPercent}%` }}
          />
        </div>
        <span
          className={cn(
            "min-w-14 text-right text-[11px] font-semibold",
            isPositive ? "text-success" : "text-destructive"
          )}
        >
          {contributionPct.toFixed(1)}%
        </span>
      </div>
      <div className="mt-2 text-[11px] text-muted-foreground">
        {isPositive
          ? "Relatively stronger upward pressure"
          : "Relatively stronger downward pressure"}
      </div>
    </div>
  );
}

function ComparableCard({
  comp,
}: {
  comp: ValuationResponse["comparable_properties"][0];
}) {
  return (
    <div className="bg-muted/50 rounded-lg p-3 border border-border">
      <div className="flex items-start justify-between mb-2">
        <div>
          <p className="text-sm font-medium text-foreground">
            {comp.building_style_desc}
          </p>
          <p className="text-xs text-muted-foreground">{Math.round(comp.distance_m)}m away</p>
        </div>
        <p className="text-sm font-semibold text-brand">
          {formatPrice(comp.price)}
        </p>
      </div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{comp.building_area} sqm</span>
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
        expandable && "cursor-pointer hover:text-foreground transition-colors"
      )}
    >
      <Icon size={16} className="text-brand" />
      <span className="font-semibold text-foreground text-sm flex-1">{title}</span>
      {expandable &&
        (expanded ? (
          <ChevronUp size={14} className="text-muted-foreground" />
        ) : (
          <ChevronDown size={14} className="text-muted-foreground" />
        ))}
    </button>
  );
}

export function ValuationReport({
  valuation,
  propertyData,
  locationIntelligence,
  onBack,
  onNewValuation,
}: ValuationReportProps) {
  const [showFactors, setShowFactors] = useState(true);
  const [showComparables, setShowComparables] = useState(true);
  const [showInsights, setShowInsights] = useState(true);
  const [isDownloading, setIsDownloading] = useState(false);
  const reportRef = useRef<HTMLDivElement>(null);

  // Calculate if asking price is good value
  const askingPriceDiff = propertyData.asking_price
    ? ((propertyData.asking_price - valuation.estimated_price) /
        valuation.estimated_price) *
      100
    : null;

  // Download PDF functionality
  const handleDownloadPDF = useCallback(async () => {
    if (!reportRef.current || isDownloading) return;

    setIsDownloading(true);
    try {
      // Dynamic import to avoid SSR issues
      const [{ default: jsPDF }, { default: html2canvas }] = await Promise.all([
        import("jspdf"),
        import("html2canvas"),
      ]);

      const element = reportRef.current;

      // Resolve the page background to a hex color that html2canvas can handle.
      // Modern Tailwind CSS (v4) emits colors in oklch/oklab which html2canvas
      // cannot parse, so we resolve through a temporary canvas pixel.
      function resolveToHex(cssColor: string): string {
        try {
          const ctx = document.createElement("canvas").getContext("2d");
          if (!ctx) return "#18181b";
          ctx.fillStyle = cssColor;
          ctx.fillRect(0, 0, 1, 1);
          const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
          return `#${((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1)}`;
        } catch {
          return "#18181b";
        }
      }

      const rawBg =
        getComputedStyle(document.documentElement)
          .getPropertyValue("--background")
          .trim() ||
        getComputedStyle(document.body).backgroundColor;
      const bgColor = resolveToHex(rawBg || "#18181b");

      // Capture the report element
      const canvas = await html2canvas(element, {
        scale: 2,
        useCORS: true,
        logging: false,
        backgroundColor: bgColor,
        allowTaint: true,
        windowWidth: element.scrollWidth,
        windowHeight: element.scrollHeight,
        // Only ignore interactive/animated elements
        ignoreElements: (el) => {
          if (!(el instanceof HTMLElement)) return false;
          return el.classList?.contains("animate-spin");
        },
        // Convert oklab/oklch colors to rgb in the cloned DOM so html2canvas
        // can parse every inline/computed style without errors.
        onclone: (_doc, clonedEl) => {
          const allElements = clonedEl.querySelectorAll("*");
          const colorProps = [
            "color",
            "backgroundColor",
            "borderColor",
            "borderTopColor",
            "borderRightColor",
            "borderBottomColor",
            "borderLeftColor",
            "outlineColor",
          ] as const;
          for (const el of allElements) {
            if (!(el instanceof HTMLElement)) continue;
            const cs = getComputedStyle(el);
            for (const prop of colorProps) {
              const val = cs[prop];
              if (
                typeof val === "string" &&
                (val.includes("oklab") || val.includes("oklch"))
              ) {
                (el.style as unknown as Record<string, string>)[prop] =
                  resolveToHex(val);
              }
            }
          }
        },
      });

      const imgData = canvas.toDataURL("image/png");
      const pdf = new jsPDF({
        orientation: "portrait",
        unit: "mm",
        format: "a4",
      });

      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = pdf.internal.pageSize.getHeight();
      const imgWidth = canvas.width;
      const imgHeight = canvas.height;

      // Scale to fit page width with margins
      const contentWidth = pdfWidth - 20;
      const contentHeight = (imgHeight * contentWidth) / imgWidth;
      const pageHeight = pdfHeight - 20;

      if (contentHeight <= pageHeight) {
        // Single page
        const imgX = (pdfWidth - contentWidth) / 2;
        const imgY = 10;
        pdf.addImage(imgData, "PNG", imgX, imgY, contentWidth, contentHeight);
      } else {
        // Multi-page: slice the image across pages
        let position = 0;
        let page = 0;

        while (position < contentHeight) {
          if (page > 0) {
            pdf.addPage();
          }
          pdf.addImage(
            imgData,
            "PNG",
            10,
            10 - position,
            contentWidth,
            contentHeight,
          );
          position += pageHeight;
          page++;
        }
      }

      // Generate filename with property info
      const district = propertyData.amphur || "Bangkok";
      const date = new Date().toISOString().split("T")[0];
      pdf.save(`Borban-Valuation-${district}-${date}.pdf`);
      toast.success("PDF downloaded successfully");
    } catch (error) {
      console.error("PDF generation failed:", error);
      const errorMsg =
        error instanceof Error ? error.message : "Unknown error";
      toast.error(`Failed to generate PDF: ${errorMsg}`);
    } finally {
      setIsDownloading(false);
    }
  }, [isDownloading, propertyData.amphur]);

  return (
    <div ref={reportRef} className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Button
          variant="ghost"
          onClick={onBack}
          className="text-muted-foreground hover:text-foreground hover:bg-muted"
        >
          <ArrowLeft size={16} className="mr-2" />
          Back to Form
        </Button>
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="border-border bg-muted/50 text-foreground hover:bg-muted"
            onClick={handleDownloadPDF}
            disabled={isDownloading}
          >
            {isDownloading ? (
              <Loader2 size={14} className="mr-2 animate-spin" />
            ) : (
              <Download size={14} className="mr-2" />
            )}
            {isDownloading ? "Generating..." : "Download PDF"}
          </Button>
        </div>
      </div>

      {/* Main Valuation Card */}
      <div className="bg-gradient-to-br from-brand/20 to-brand/5 border border-brand/30 rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles size={20} className="text-brand" />
          <h2 className="text-lg font-semibold text-foreground">
            AI Property Valuation
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Estimated Price */}
          <div>
            <p className="text-sm text-muted-foreground mb-1">Estimated Value</p>
            <p className="text-4xl font-bold text-brand">
              {formatPrice(valuation.estimated_price)}
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              Range: {formatPrice(valuation.price_range.min)} -{" "}
              {formatPrice(valuation.price_range.max)}
            </p>
          </div>

          {/* Price per sqm */}
          <div className="flex flex-col justify-center">
            <div className="bg-card rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign size={16} className="text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Price per sqm</span>
              </div>
              <p className="text-2xl font-bold text-foreground">
                ฿{valuation.price_per_sqm.toLocaleString()}
              </p>
            </div>
          </div>
        </div>

        {/* Asking Price Comparison */}
        {propertyData.asking_price && askingPriceDiff !== null && (
          <div
            className={cn(
              "mt-4 p-4 rounded-lg border",
              askingPriceDiff <= 0
                ? "bg-success/10 border-success/30"
                : askingPriceDiff <= 10
                  ? "bg-warning/10 border-warning/30"
                  : "bg-destructive/10 border-destructive/30"
            )}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Your Asking Price</p>
                <p className="text-xl font-bold text-foreground">
                  {formatPrice(propertyData.asking_price)}
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground">vs. Our Estimate</p>
                <p
                  className={cn(
                    "text-xl font-bold",
                    askingPriceDiff <= 0
                      ? "text-success"
                      : askingPriceDiff <= 10
                        ? "text-warning"
                        : "text-destructive"
                  )}
                >
                  {askingPriceDiff > 0 ? "+" : ""}
                  {askingPriceDiff.toFixed(1)}%
                </p>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              {askingPriceDiff <= 0
                ? "Your asking price is at or below our estimate - good value for buyers!"
                : askingPriceDiff <= 10
                  ? "Your asking price is slightly above our estimate - within negotiable range."
                  : "Your asking price is significantly above our estimate - may need adjustment."}
            </p>
          </div>
        )}
      </div>

      {/* Confidence Badge */}
      <ConfidenceBadge level={valuation.confidence} />

      {/* Property Summary */}
      <div className="bg-card border border-border rounded-lg p-6">
        <SectionHeader icon={Building2} title="Property Summary" />
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-4">
          <SummaryItem
            icon={Home}
            label="Type"
            value={propertyData.building_style}
          />
          <SummaryItem
            icon={Building2}
            label="Building Area"
            value={`${propertyData.building_area} sqm`}
          />
          {propertyData.land_area && (
            <SummaryItem
              icon={MapPin}
              label="Land Area"
              value={`${propertyData.land_area} sqm`}
            />
          )}
          <SummaryItem
            icon={Building2}
            label="Floors"
            value={`${propertyData.no_of_floor}`}
          />
          <SummaryItem
            icon={Calendar}
            label="Building Age"
            value={`${propertyData.building_age} years`}
          />
          <SummaryItem
            icon={MapPin}
            label="District"
            value={propertyData.amphur}
          />
        </div>
      </div>

      {/* Contributing Factors */}
      <div className="bg-card border border-border rounded-lg p-6">
        <SectionHeader
          icon={Scale}
          title="Contributing Factors"
          expandable
          expanded={showFactors}
          onToggle={() => setShowFactors(!showFactors)}
        />
        {showFactors && (
          <div className="mt-4 space-y-3">
            <p className="text-sm leading-6 text-muted-foreground">
              These factors show which inputs mattered most for this estimate. They are relative weights, not additive baht adjustments.
            </p>
            {(() => {
              const maxPct = Math.max(
                ...valuation.factors.map((f) =>
                  f.contribution_pct ?? (valuation.estimated_price > 0
                    ? Math.abs(f.impact / valuation.estimated_price) * 100
                    : 0)
                )
              );
              return valuation.factors.map((factor) => (
                <FactorBar key={factor.name} factor={factor} estimatedPrice={valuation.estimated_price} maxPct={maxPct} />
              ));
            })()}
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
            {valuation.explanation_narrative ? (
              <div className="mt-4 rounded-lg border border-border bg-muted/40 p-3">
                <div className="text-xs uppercase tracking-wide text-muted-foreground mb-2">
                  AI Summary
                </div>
                <p className="text-sm leading-6 text-foreground/90">
                  {valuation.explanation_narrative}
                </p>
              </div>
            ) : null}
          </div>
        )}
      </div>

      {/* Comparable Properties */}
      {valuation.comparable_properties.length > 0 && (
        <div className="bg-card border border-border rounded-lg p-6">
          <SectionHeader
            icon={Home}
            title={`Similar Properties (${valuation.comparable_properties.length})`}
            expandable
            expanded={showComparables}
            onToggle={() => setShowComparables(!showComparables)}
          />
          {showComparables && (
            <div className="mt-4 space-y-3">
              {valuation.comparable_properties.map((comp) => (
                <ComparableCard key={comp.id} comp={comp} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Market Insights */}
      <div className="bg-card border border-border rounded-lg p-6">
        <SectionHeader
          icon={TrendingUp}
          title="Market Insights"
          expandable
          expanded={showInsights}
          onToggle={() => setShowInsights(!showInsights)}
        />
        {showInsights && (
          <div className="mt-4 space-y-3">
            <div className="rounded-lg border border-border bg-muted/40 p-2">
              <div className="text-[11px] font-medium text-muted-foreground mb-1">
                Trend color legend
              </div>
              <div className="flex items-center gap-4 text-[10px] text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />Uptrend
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-red-500" />Downtrend
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-brand" />District benchmark
                </span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
            <div className="bg-muted/50 rounded-lg p-4 text-center">
              <BarChart3
                size={20}
                className="text-brand mx-auto mb-2"
              />
              <p className="text-xs text-muted-foreground mb-1 inline-flex items-center justify-center gap-1">
                District Avg.
                <SourceTooltip source={DATA_SOURCES.housePrices} />
              </p>
              <p className="text-lg font-bold text-foreground">
                {formatPrice(valuation.market_insights.district_avg_price)}
              </p>
            </div>
            <div className="bg-muted/50 rounded-lg p-4 text-center">
              {valuation.market_insights.district_price_trend >= 0 ? (
                <TrendingUp
                  size={20}
                  className="text-success mx-auto mb-2"
                />
              ) : (
                <TrendingDown
                  size={20}
                  className="text-destructive mx-auto mb-2"
                />
              )}
              <p className="text-xs text-muted-foreground mb-1 inline-flex items-center justify-center gap-1">
                Price Trend
                <SourceTooltip source={DATA_SOURCES.districtTrend} />
                <InfoTooltip
                  title="Price trend method"
                  description={SCORE_METHODOLOGY.districtTrend}
                />
              </p>
              <p
                className={cn(
                  "text-lg font-bold",
                  valuation.market_insights.district_price_trend >= 0
                    ? "text-success"
                    : "text-destructive"
                )}
              >
                +{valuation.market_insights.district_price_trend.toFixed(1)}%
              </p>
            </div>
            <div className="bg-muted/50 rounded-lg p-4 text-center">
              <Calendar size={20} className="text-muted-foreground mx-auto mb-2" />
              <p className="text-xs text-muted-foreground mb-1">Avg. Days Listed</p>
              <p className="text-lg font-bold text-foreground">
                {valuation.market_insights.days_on_market_avg}
              </p>
            </div>
            </div>
          </div>
        )}
      </div>

      {/* Location Intelligence */}
      {locationIntelligence && (
        <div className="bg-card border border-border rounded-lg p-6">
          <LocationIntelligencePanel
            data={locationIntelligence}
            isLoading={false}
          />
        </div>
      )}

      {/* Call to Actions */}
      <div className="bg-gradient-to-r from-brand/10 to-blue-500/10 border border-border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-foreground mb-4">
          What's Next?
        </h3>
        <div className="bg-card rounded-lg p-4 border border-border">
          <h4 className="font-medium text-foreground mb-2">List Your Property</h4>
          <p className="text-sm text-muted-foreground mb-3">
            Ready to sell? List your property on our platform.
          </p>
          <Button
            className="w-full bg-brand hover:bg-brand/90 text-black"
            onClick={() => toast.info("Coming soon!")}
          >
            List Property
          </Button>
        </div>
      </div>

      {/* New Valuation Button */}
      <div className="text-center pb-8">
        <Button
          variant="outline"
          onClick={onNewValuation}
          className="border-border bg-muted/50 text-foreground hover:bg-muted"
        >
          <Sparkles size={14} className="mr-2" />
          Get Another Valuation
        </Button>
      </div>
    </div>
  );
}

function SummaryItem({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string; size?: number }>;
  label: string;
  value: string;
}) {
  return (
    <div className="bg-muted/50 rounded-lg p-3">
      <div className="flex items-center gap-2 mb-1">
        <Icon size={12} className="text-muted-foreground" />
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <p className="text-sm font-medium text-foreground">{value}</p>
    </div>
  );
}

export default ValuationReport;
