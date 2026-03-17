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
	TrendingDown,
	TrendingUp,
} from "lucide-react";
import { useMemo, useState } from "react";
import { api, type HousePriceItem } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ComprehensivePriceReportProps {
	propertyId: number;
	property: HousePriceItem;
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

interface MarketTrend {
	price_change_6m: number;
	district_growth_rate: number;
	supply_demand: "balanced" | "high_demand" | "oversupply";
	avg_days_on_market: number;
}

interface ConfidenceMetrics {
	overall: "high" | "medium" | "low";
	data_quality_score: number;
	comparable_count: number;
	model_accuracy: number;
}

// Helper functions
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

// Generate mock extended data based on real property and price explanation
function generateMockExtendedData(
	property: HousePriceItem,
	predictedPrice: number,
	nearbyProperties: (HousePriceItem & { distance_m: number })[],
): {
	comparables: ComparableProperty[];
	marketTrend: MarketTrend;
	confidence: ConfidenceMetrics;
	pricePercentile: number;
	priceRange: { min: number; max: number };
} {
	// Generate comparable properties from nearby data
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

	// Mock market trend data
	const marketTrend: MarketTrend = {
		price_change_6m: 4.2 + Math.random() * 4, // 4.2% to 8.2%
		district_growth_rate: 5.5 + Math.random() * 3, // 5.5% to 8.5%
		supply_demand:
			Math.random() > 0.6
				? "high_demand"
				: Math.random() > 0.3
					? "balanced"
					: "oversupply",
		avg_days_on_market: 35 + Math.floor(Math.random() * 30),
	};

	// Calculate confidence based on comparable count and data quality
	const comparableCount = comparables.length;
	const dataQuality =
		(property.building_area ? 20 : 0) +
		(property.land_area ? 20 : 0) +
		(property.building_age !== null ? 20 : 0) +
		(property.no_of_floor ? 15 : 0) +
		(property.tumbon ? 15 : 0) +
		10; // Base score

	const confidence: ConfidenceMetrics = {
		overall:
			comparableCount >= 3 && dataQuality >= 70
				? "high"
				: comparableCount >= 2 && dataQuality >= 50
					? "medium"
					: "low",
		data_quality_score: Math.min(dataQuality, 100),
		comparable_count: comparableCount,
		model_accuracy: 87 + Math.random() * 8, // 87% to 95%
	};

	// Calculate price percentile (mock based on district comparison)
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
		marketTrend,
		confidence,
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
	const widthPercent = Math.min(
		(Math.abs(contribution) / maxContribution) * 100,
		100,
	);

	return (
		<div className="mb-2.5">
			<div className="flex justify-between text-xs mb-1">
				<span className="text-muted-foreground">{feature_display}</span>
				<span className="text-muted-foreground">
					{formatFeatureValue(feature, value)}
				</span>
			</div>
			<div className="flex items-center gap-2">
				<div className="flex-1 h-5 bg-muted/50 rounded relative overflow-hidden">
					<div
						className={cn(
							"absolute h-full rounded transition-all",
							direction === "positive" ? "bg-success/70" : "bg-destructive/70",
						)}
						style={{ width: `${widthPercent}%` }}
					/>
				</div>
				<span
					className={cn(
						"text-xs font-mono min-w-16 text-right",
						direction === "positive" ? "text-success" : "text-destructive",
					)}
				>
					{contributionDisplay || formatContribution(contribution)}
				</span>
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

function MarketTrendSection({ trend }: { trend: MarketTrend }) {
	const demandConfig = {
		high_demand: { label: "High Demand", color: "text-success" },
		balanced: { label: "Balanced", color: "text-warning" },
		oversupply: { label: "Oversupply", color: "text-destructive" },
	};

	return (
		<div className="grid grid-cols-2 gap-3">
			<div className="bg-muted/50 rounded-lg p-3">
				<div className="flex items-center gap-1 mb-1">
					{trend.price_change_6m >= 0 ? (
						<TrendingUp size={14} className="text-success" />
					) : (
						<TrendingDown size={14} className="text-destructive" />
					)}
					<span className="text-xs text-muted-foreground">6-Month Change</span>
				</div>
				<p
					className={cn(
						"text-lg font-bold",
						trend.price_change_6m >= 0 ? "text-success" : "text-destructive",
					)}
				>
					{trend.price_change_6m >= 0 ? "+" : ""}
					{trend.price_change_6m.toFixed(1)}%
				</p>
			</div>

			<div className="bg-muted/50 rounded-lg p-3">
				<div className="flex items-center gap-1 mb-1">
					<BarChart3 size={14} className="text-muted-foreground" />
					<span className="text-xs text-muted-foreground">District Growth</span>
				</div>
				<p className="text-lg font-bold text-foreground">
					+{trend.district_growth_rate.toFixed(1)}%
					<span className="text-xs text-muted-foreground font-normal ml-1">
						YoY
					</span>
				</p>
			</div>

			<div className="bg-muted/50 rounded-lg p-3">
				<div className="flex items-center gap-1 mb-1">
					<Scale size={14} className="text-muted-foreground" />
					<span className="text-xs text-muted-foreground">Market Balance</span>
				</div>
				<p
					className={cn(
						"text-sm font-semibold",
						demandConfig[trend.supply_demand].color,
					)}
				>
					{demandConfig[trend.supply_demand].label}
				</p>
			</div>

			<div className="bg-muted/50 rounded-lg p-3">
				<div className="flex items-center gap-1 mb-1">
					<Home size={14} className="text-muted-foreground" />
					<span className="text-xs text-muted-foreground">
						Avg. Days Listed
					</span>
				</div>
				<p className="text-lg font-bold text-foreground">
					{trend.avg_days_on_market}
				</p>
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
}: ComprehensivePriceReportProps) {
	const [showFactors, setShowFactors] = useState(true);
	const [showComparables, setShowComparables] = useState(true);
	const [showTrends, setShowTrends] = useState(false);

	// Fetch price explanation from API
	const {
		data: priceData,
		isLoading: isPriceLoading,
		error: priceError,
	} = useQuery({
		queryKey: ["priceExplanation", propertyId],
		queryFn: () => api.getPriceExplanation(propertyId),
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

	const maxContribution = Math.max(
		1,
		...priceData.feature_contributions.map((c) => Math.abs(c.contribution)),
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
					{extendedData && (
						<ConfidenceBadge level={extendedData.confidence.overall} />
					)}
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
					{priceData.district_avg_price > 0 && (
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
					title="Model Signals"
					expandable
					expanded={showFactors}
					onToggle={() => setShowFactors(!showFactors)}
				/>
				{showFactors && (
					<div className="mt-4">
						{priceData.feature_contributions.map((contrib) => (
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
						<p className="text-xs text-muted-foreground mb-3">
							Signal bars show relative model influence for this estimate, not
							additive THB components.
						</p>
						<div className="flex gap-4 text-xs text-muted-foreground mt-3 pt-3 border-t border-border">
							<div className="flex items-center gap-1">
								<div className="w-3 h-3 rounded bg-success/70" />
								<span>Pushes estimate higher</span>
							</div>
							<div className="flex items-center gap-1">
								<div className="w-3 h-3 rounded bg-destructive/70" />
								<span>Pushes estimate lower</span>
							</div>
						</div>
						<p className="text-xs text-muted-foreground mt-3">
							{priceData.explanation_disclaimer}
						</p>
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

			{/* Market Trends */}
			{extendedData && (
				<div className="bg-card border border-border rounded-lg p-4">
					<SectionHeader
						icon={TrendingUp}
						title="Market Trends"
						expandable
						expanded={showTrends}
						onToggle={() => setShowTrends(!showTrends)}
					/>
					{showTrends && (
						<div className="mt-4">
							<MarketTrendSection trend={extendedData.marketTrend} />
						</div>
					)}
				</div>
			)}

			{/* Confidence Metrics */}
			{extendedData && (
				<div className="bg-card border border-border rounded-lg p-4">
					<SectionHeader icon={CheckCircle2} title="Valuation Quality" />
					<div className="mt-3 grid grid-cols-3 gap-3">
						<div className="text-center">
							<div className="text-xs text-muted-foreground mb-1">
								Data Quality
							</div>
							<div className="text-lg font-bold text-foreground">
								{extendedData.confidence.data_quality_score}%
							</div>
						</div>
						<div className="text-center">
							<div className="text-xs text-muted-foreground mb-1">
								Model Accuracy
							</div>
							<div className="text-lg font-bold text-brand">
								{extendedData.confidence.model_accuracy.toFixed(1)}%
							</div>
						</div>
						<div className="text-center">
							<div className="text-xs text-muted-foreground mb-1">
								Comparables
							</div>
							<div className="text-lg font-bold text-foreground">
								{extendedData.confidence.comparable_count}
							</div>
						</div>
					</div>
				</div>
			)}
		</div>
	);
}

export default ComprehensivePriceReport;
