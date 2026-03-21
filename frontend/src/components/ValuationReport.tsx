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
  Share2,
  ArrowLeft,
  Sparkles,
  Calendar,
  DollarSign,
  Loader2,
  Check,
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
  maxImpact,
}: {
  factor: ValuationResponse["factors"][0];
  maxImpact: number;
}) {
  const widthPercent = Math.min(
    (Math.abs(factor.impact) / maxImpact) * 100,
    100
  );
  const isPositive = factor.direction === "positive";

  return (
    <div className="mb-3">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-muted-foreground">{factor.display_name}</span>
        <span
          className={cn(
            "font-mono",
            isPositive ? "text-success" : "text-destructive"
          )}
        >
          {isPositive ? "+" : ""}
          {formatPrice(factor.impact)}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex-1 h-5 bg-muted/50 rounded relative overflow-hidden">
          <div
            className={cn(
              "absolute h-full rounded transition-all",
              isPositive ? "bg-success/70" : "bg-destructive/70"
            )}
            style={{ width: `${widthPercent}%` }}
          />
        </div>
      </div>
      <p className="text-xs text-muted-foreground mt-1">{factor.description}</p>
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
  const [shareState, setShareState] = useState<"idle" | "copied">("idle");
  const reportRef = useRef<HTMLDivElement>(null);

  const maxImpact = Math.max(
    ...valuation.factors.map((f) => Math.abs(f.impact))
  );

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
      
      // Ensure element is scrolled into view and visible
      element.scrollIntoView({ behavior: "instant", block: "start" });
      
      // Small delay to ensure rendering is complete
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // Capture the report element with settings optimized for dark backgrounds
      const canvas = await html2canvas(element, {
        scale: 2,
        useCORS: true,
        logging: false,
        backgroundColor: "#18181b", // zinc-900
        allowTaint: true,
        windowWidth: element.scrollWidth,
        windowHeight: element.scrollHeight,
        // Ignore problematic elements (buttons, spinners)
        ignoreElements: (el) => {
          if (!(el instanceof HTMLElement)) return false;
          return el.classList?.contains('animate-spin') || 
                 el.tagName === 'BUTTON' ||
                 el.classList?.contains('backdrop-blur') ||
                 el.classList?.contains('backdrop-blur-md');
        },
        onclone: (clonedDoc) => {
          // Ensure cloned element has solid background
          const clonedElement = clonedDoc.body.querySelector('[class*="max-w-3xl"]');
          if (clonedElement instanceof HTMLElement) {
            clonedElement.style.backgroundColor = '#18181b';
          }
        }
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
      
      // Calculate dimensions to fit content
      const ratio = Math.min(
        (pdfWidth - 20) / imgWidth,  // 10mm margin on each side
        (pdfHeight - 20) / imgHeight
      );
      const imgX = (pdfWidth - imgWidth * ratio) / 2;
      const imgY = 10;

      // Handle multi-page if content is too long
      const scaledHeight = imgHeight * ratio;
      if (scaledHeight > pdfHeight - 20) {
        // Content is longer than one page, scale to fit width and add pages
        const pageHeight = pdfHeight - 20;
        const contentHeight = (imgHeight * (pdfWidth - 20)) / imgWidth;
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
            pdfWidth - 20,
            contentHeight
          );
          position += pageHeight;
          page++;
        }
      } else {
        pdf.addImage(
          imgData,
          "PNG",
          imgX,
          imgY,
          imgWidth * ratio,
          imgHeight * ratio
        );
      }

      // Generate filename with property info
      const district = propertyData.amphur || "Bangkok";
      const date = new Date().toISOString().split("T")[0];
      pdf.save(`Borban-Valuation-${district}-${date}.pdf`);
    } catch (error) {
      console.error("PDF generation failed:", error);
      // More helpful error message
      const errorMsg = error instanceof Error ? error.message : "Unknown error";
      toast.error(`Failed to generate PDF: ${errorMsg}. Try refreshing the page.`);
    } finally {
      setIsDownloading(false);
    }
  }, [isDownloading, propertyData.amphur]);

  // Share functionality
  const handleShare = useCallback(async () => {
    const shareData = {
      title: "Borban Property Valuation",
      text: `Property Valuation: ${formatPrice(valuation.estimated_price)}\n` +
        `Type: ${propertyData.building_style}\n` +
        `Area: ${propertyData.building_area} sqm\n` +
        `District: ${propertyData.amphur}\n` +
        `Confidence: ${valuation.confidence.charAt(0).toUpperCase() + valuation.confidence.slice(1)}\n\n` +
        "Powered by Borban AI",
      url: window.location.href,
    };

    // Try native share first (mobile/modern browsers)
    if (navigator.share && navigator.canShare?.(shareData)) {
      try {
        await navigator.share(shareData);
        return;
      } catch (error) {
        // User cancelled or share failed, fall back to clipboard
        if ((error as Error).name !== "AbortError") {
          console.error("Share failed:", error);
        }
      }
    }

    // Fallback: copy to clipboard
    try {
      await navigator.clipboard.writeText(
        `${shareData.text}\n\n${shareData.url}`
      );
      setShareState("copied");
      setTimeout(() => setShareState("idle"), 2000);
    } catch (error) {
      console.error("Clipboard copy failed:", error);
      toast.error("Failed to copy to clipboard.");
    }
  }, [valuation, propertyData]);

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
            {isDownloading ? "Generating..." : "Download"}
          </Button>
          <Button
            variant="outline"
            className="border-border bg-muted/50 text-foreground hover:bg-muted"
            onClick={handleShare}
          >
            {shareState === "copied" ? (
              <>
                <Check size={14} className="mr-2 text-brand" />
                Copied!
              </>
            ) : (
              <>
                <Share2 size={14} className="mr-2" />
                Share
              </>
            )}
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

      {/* Price Factors */}
      <div className="bg-card border border-border rounded-lg p-6">
        <SectionHeader
          icon={Scale}
          title="How We Calculated This"
          expandable
          expanded={showFactors}
          onToggle={() => setShowFactors(!showFactors)}
        />
        {showFactors && (
          <div className="mt-4">
            {valuation.factors.map((factor) => (
              <FactorBar key={factor.name} factor={factor} maxImpact={maxImpact} />
            ))}
            <div className="flex gap-4 text-xs text-muted-foreground mt-3 pt-3 border-t border-border">
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded bg-success/70" />
                <span>Increases value</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded bg-destructive/70" />
                <span>Decreases value</span>
              </div>
            </div>
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
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-card rounded-lg p-4 border border-border">
            <h4 className="font-medium text-foreground mb-2">
              Get Professional Appraisal
            </h4>
            <p className="text-sm text-muted-foreground mb-3">
              Connect with certified appraisers for an official valuation
              report.
            </p>
            <Button
              variant="outline"
              className="w-full border-border bg-muted/50 text-foreground hover:bg-muted"
              onClick={() => toast.info("Coming soon!")}
            >
              Request Appraisal
            </Button>
          </div>
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
