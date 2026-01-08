/**
 * Price Explanation component - displays SHAP-based price breakdown.
 * Shows predicted price with feature contributions as a horizontal bar chart.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface PriceExplanationProps {
  propertyId: number;
  actualPrice?: number | null;
}

function formatPrice(price: number): string {
  if (price >= 1_000_000) {
    return `฿${(price / 1_000_000).toFixed(2)}M`;
  }
  return `฿${price.toLocaleString()}`;
}

function formatContribution(contribution: number): string {
  const sign = contribution >= 0 ? "+" : "";
  if (Math.abs(contribution) >= 1_000_000) {
    return `${sign}฿${(contribution / 1_000_000).toFixed(2)}M`;
  }
  if (Math.abs(contribution) >= 1_000) {
    return `${sign}฿${(contribution / 1_000).toFixed(0)}K`;
  }
  return `${sign}฿${contribution.toFixed(0)}`;
}

function formatFeatureValue(feature: string, value: number): string {
  // Format value based on feature type
  if (feature.includes("area")) {
    return `${value.toFixed(0)} sqm`;
  }
  if (feature.includes("age")) {
    return `${value.toFixed(0)} years`;
  }
  if (feature.includes("floor")) {
    return `${value.toFixed(0)} floors`;
  }
  if (feature.includes("score")) {
    return `${value.toFixed(0)}/100`;
  }
  if (feature.includes("density") || feature.includes("stops")) {
    return `${value.toFixed(0)} nearby`;
  }
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
  if (feature === "district_avg_price_sqm") {
    return `฿${value.toLocaleString()}/sqm`;
  }
  return value.toFixed(2);
}

function ContributionBar({
  feature_display,
  feature,
  value,
  contribution,
  direction,
  maxContribution,
}: {
  feature_display: string;
  feature: string;
  value: number;
  contribution: number;
  direction: "positive" | "negative";
  maxContribution: number;
}) {
  // Calculate bar width as percentage of max contribution
  const widthPercent = Math.min(
    (Math.abs(contribution) / maxContribution) * 100,
    100
  );

  return (
    <div className="mb-3">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-white/80">{feature_display}</span>
        <span className="text-white/60">
          {formatFeatureValue(feature, value)}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex-1 h-6 bg-white/5 rounded relative overflow-hidden">
          <div
            className={`absolute h-full rounded transition-all ${
              direction === "positive" ? "bg-emerald-500/80" : "bg-rose-500/80"
            }`}
            style={{ width: `${widthPercent}%` }}
          />
        </div>
        <span
          className={`text-sm font-mono min-w-20 text-right ${
            direction === "positive" ? "text-emerald-400" : "text-rose-400"
          }`}
        >
          {formatContribution(contribution)}
        </span>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="bg-black/40 border border-white/10 rounded-lg p-4">
      <div className="animate-pulse space-y-3">
        <div className="h-6 bg-white/10 rounded w-1/3" />
        <div className="h-10 bg-white/10 rounded w-2/3" />
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-8 bg-white/10 rounded" />
          ))}
        </div>
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="bg-black/40 border border-white/10 rounded-lg p-4">
      <div className="text-center py-4">
        <div className="text-rose-400 text-sm mb-2">
          ⚠️ Price Analysis Unavailable
        </div>
        <p className="text-white/50 text-xs">{message}</p>
      </div>
    </div>
  );
}

export function PriceExplanation({
  propertyId,
  actualPrice,
}: PriceExplanationProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["priceExplanation", propertyId],
    queryFn: () => api.getPriceExplanation(propertyId),
    staleTime: 1000 * 60 * 10, // Cache for 10 minutes
    retry: false,
  });

  if (isLoading) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={(error as Error).message} />;
  }

  if (!data) {
    return null;
  }

  // Find max contribution for scaling bars
  const maxContribution = Math.max(
    ...data.feature_contributions.map((c) => Math.abs(c.contribution))
  );

  // Calculate difference from actual if available
  const showActualComparison = actualPrice && actualPrice > 0;
  const priceDifference = showActualComparison
    ? data.predicted_price - actualPrice
    : null;
  const priceDifferencePercent =
    priceDifference && actualPrice
      ? (priceDifference / actualPrice) * 100
      : null;

  return (
    <div className="bg-black/40 border border-white/10 rounded-lg p-4">
      <h3 className="text-white font-semibold mb-4">Price Analysis</h3>

      {/* Price Summary */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div>
          <div className="text-white/50 text-xs uppercase tracking-wide mb-1">
            Predicted Value
          </div>
          <div className="text-2xl font-bold text-emerald-400">
            {formatPrice(data.predicted_price)}
          </div>
        </div>

        {showActualComparison && (
          <div>
            <div className="text-white/50 text-xs uppercase tracking-wide mb-1">
              Appraised Value
            </div>
            <div className="text-2xl font-bold text-white">
              {formatPrice(actualPrice)}
            </div>
            {priceDifferencePercent !== null && (
              <div
                className={`text-xs ${
                  priceDifferencePercent >= 0
                    ? "text-emerald-400"
                    : "text-rose-400"
                }`}
              >
                {priceDifferencePercent >= 0 ? "+" : ""}
                {priceDifferencePercent.toFixed(1)}% from model
              </div>
            )}
          </div>
        )}
      </div>

      {/* District Comparison */}
      {data.district_avg_price > 0 && (
        <div className="bg-white/5 rounded-lg p-3 mb-4">
          <div className="flex justify-between items-center">
            <span className="text-white/60 text-sm">vs. District Average</span>
            <span
              className={`font-semibold ${
                data.price_vs_district >= 0
                  ? "text-emerald-400"
                  : "text-rose-400"
              }`}
            >
              {data.price_vs_district >= 0 ? "+" : ""}
              {data.price_vs_district.toFixed(1)}%
            </span>
          </div>
        </div>
      )}

      {/* Feature Contributions */}
      <div className="mb-2">
        <div className="text-white/50 text-xs uppercase tracking-wide mb-3">
          Top Price Factors
        </div>
        {data.feature_contributions.map((contrib) => (
          <ContributionBar
            key={contrib.feature}
            feature_display={contrib.feature_display}
            feature={contrib.feature}
            value={contrib.value}
            contribution={contrib.contribution}
            direction={contrib.direction}
            maxContribution={maxContribution}
          />
        ))}
      </div>

      {/* Legend */}
      <div className="flex gap-4 text-xs text-white/40 mt-4 pt-3 border-t border-white/10">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-emerald-500/80" />
          <span>Increases value</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-rose-500/80" />
          <span>Decreases value</span>
        </div>
      </div>
    </div>
  );
}

export default PriceExplanation;
