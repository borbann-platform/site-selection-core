/**
 * Price Explanation component - displays top model signals for a prediction.
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
	if (Math.abs(contribution) >= 1_000_000) {
		return `${(contribution / 1_000_000).toFixed(2)}M`;
	}
	if (Math.abs(contribution) >= 1_000) {
		return `${(contribution / 1_000).toFixed(0)}K`;
	}
	return contribution.toFixed(0);
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
	contributionDisplay,
	direction,
	maxContribution,
}: {
	feature_display: string;
	feature: string;
	value: number;
	contribution: number;
	contributionDisplay?: string | null;
	direction: "positive" | "negative";
	maxContribution: number;
}) {
	// Calculate bar width as percentage of max contribution
	const widthPercent = Math.min(
		(Math.abs(contribution) / maxContribution) * 100,
		100,
	);

	return (
		<div className="mb-3">
			<div className="flex justify-between text-sm mb-1">
				<span className="text-foreground/80">{feature_display}</span>
				<span className="text-muted-foreground">
					{formatFeatureValue(feature, value)}
				</span>
			</div>
			<div className="flex items-center gap-2">
				<div className="flex-1 h-6 bg-muted/50 rounded relative overflow-hidden">
					<div
						className={`absolute h-full rounded transition-all ${
							direction === "positive" ? "bg-success/80" : "bg-destructive/80"
						}`}
						style={{ width: `${widthPercent}%` }}
					/>
				</div>
				<span
					className={`text-sm font-mono min-w-20 text-right ${
						direction === "positive" ? "text-success" : "text-destructive"
					}`}
				>
					{contributionDisplay || formatContribution(contribution)}
				</span>
			</div>
		</div>
	);
}

function LoadingState() {
	return (
		<div className="bg-popover border border-border rounded-lg p-4">
			<div className="animate-pulse space-y-3">
				<div className="h-6 bg-muted/50 rounded w-1/3" />
				<div className="h-10 bg-muted/50 rounded w-2/3" />
				<div className="space-y-2">
					{[1, 2, 3, 4, 5].map((i) => (
						<div key={i} className="h-8 bg-muted/50 rounded" />
					))}
				</div>
			</div>
		</div>
	);
}

function ErrorState({ message }: { message: string }) {
	return (
		<div className="bg-popover border border-border rounded-lg p-4">
			<div className="text-center py-4">
				<div className="text-destructive text-sm mb-2">
					⚠️ Price Analysis Unavailable
				</div>
				<p className="text-muted-foreground text-xs">{message}</p>
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
		1,
		...data.feature_contributions.map((c) => Math.abs(c.contribution)),
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
		<div className="bg-popover border border-border rounded-lg p-4">
			<h3 className="text-foreground font-semibold mb-2">
				{data.explanation_title}
			</h3>
			<p className="text-sm text-muted-foreground mb-4">
				{data.explanation_summary}
			</p>

			{/* Price Summary */}
			<div className="grid grid-cols-2 gap-4 mb-6">
				<div>
					<div className="text-muted-foreground text-xs uppercase tracking-wide mb-1">
						Predicted Value
					</div>
					<div className="text-2xl font-bold text-success">
						{formatPrice(data.predicted_price)}
					</div>
				</div>

				{showActualComparison && (
					<div>
						<div className="text-muted-foreground text-xs uppercase tracking-wide mb-1">
							Appraised Value
						</div>
						<div className="text-2xl font-bold text-foreground">
							{formatPrice(actualPrice)}
						</div>
						{priceDifferencePercent !== null && (
							<div
								className={`text-xs ${
									priceDifferencePercent >= 0
										? "text-success"
										: "text-destructive"
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
				<div className="bg-muted/50 rounded-lg p-3 mb-4">
					<div className="flex justify-between items-center">
						<span className="text-muted-foreground text-sm">
							vs. District Average
						</span>
						<span
							className={`font-semibold ${
								data.price_vs_district >= 0
									? "text-success"
									: "text-destructive"
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
				<div className="text-muted-foreground text-xs uppercase tracking-wide mb-3">
					Top Signals
				</div>
				{data.feature_contributions.map((contrib) => (
					<ContributionBar
						key={contrib.feature}
						feature_display={contrib.feature_display}
						feature={contrib.feature}
						value={contrib.value}
						contribution={contrib.contribution}
						contributionDisplay={contrib.contribution_display}
						direction={contrib.direction}
						maxContribution={maxContribution}
					/>
				))}
			</div>

			{data.explanation_narrative && (
				<div className="mt-4 rounded-lg border border-border bg-muted/40 p-3">
					<div className="text-muted-foreground text-xs uppercase tracking-wide mb-2">
						Natural Language Summary
					</div>
					<p className="text-sm text-foreground/90 leading-6">
						{data.explanation_narrative}
					</p>
				</div>
			)}

			{/* Legend */}
			<div className="flex gap-4 text-xs text-muted-foreground mt-4 pt-3 border-t border-border">
				<div className="flex items-center gap-1">
					<div className="w-3 h-3 rounded bg-success/80" />
					<span>Pushes estimate higher</span>
				</div>
				<div className="flex items-center gap-1">
					<div className="w-3 h-3 rounded bg-destructive/80" />
					<span>Pushes estimate lower</span>
				</div>
			</div>
			<p className="text-xs text-muted-foreground mt-3">
				{data.explanation_disclaimer}
			</p>
		</div>
	);
}

export default PriceExplanation;
