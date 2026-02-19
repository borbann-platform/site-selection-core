/**
 * Property Valuation Page - Upload property details and get AI valuation.
 * Multi-step wizard with location picker and comprehensive report.
 */

import { createFileRoute, Link } from "@tanstack/react-router";
import { cn } from "@/lib/utils";
import { useState, useCallback, lazy, Suspense } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { PropertyUploadForm } from "@/components/PropertyUploadForm";
import { LocationPicker } from "@/components/LocationPicker";
import { api, type PropertyUploadRequest, type ValuationResponse } from "@/lib/api";
import { Sparkles, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { PageHeader } from "@/components/layout/PageHeader";
import { ContentLoader } from "@/components/ui/loading";

const ValuationReport = lazy(() =>
  import("@/components/ValuationReport").then((m) => ({
    default: m.ValuationReport,
  }))
);

export const Route = createFileRoute("/_authenticated/valuation")({
  component: ValuationPage,
});

type PageState = "form" | "report";

function ValuationPage() {
  const [pageState, setPageState] = useState<PageState>("form");
  const [showLocationPicker, setShowLocationPicker] = useState(false);
  const [selectedLocation, setSelectedLocation] = useState<{
    lat: number;
    lon: number;
  } | null>(null);
  const [submittedData, setSubmittedData] =
    useState<PropertyUploadRequest | null>(null);
  const [valuationResult, setValuationResult] =
    useState<ValuationResponse | null>(null);

  // Valuation mutation
  const valuationMutation = useMutation({
    mutationFn: (data: PropertyUploadRequest) => api.getPropertyValuation(data),
    onSuccess: (result, data) => {
      setValuationResult(result);
      setSubmittedData(data);
      setPageState("report");
    },
  });

  // Fetch location intelligence when we have a location
  const { data: locationIntelligence } = useQuery({
    queryKey: [
      "locationIntelligence",
      submittedData?.latitude,
      submittedData?.longitude,
    ],
    queryFn: () => {
      if (!submittedData) throw new Error("No location");
      return api.getLocationIntelligence({
        latitude: submittedData.latitude,
        longitude: submittedData.longitude,
        radius_meters: 1000,
      });
    },
    enabled: !!submittedData && pageState === "report",
    staleTime: 1000 * 60 * 10,
  });

  const handleLocationConfirm = useCallback(
    (location: { lat: number; lon: number }) => {
      setSelectedLocation(location);
      setShowLocationPicker(false);
    },
    []
  );

  const handleFormSubmit = useCallback(
    (data: PropertyUploadRequest) => {
      valuationMutation.mutate(data);
    },
    [valuationMutation]
  );

  const handleNewValuation = useCallback(() => {
    setPageState("form");
    setValuationResult(null);
    setSubmittedData(null);
    setSelectedLocation(null);
  }, []);

  const handleBackToForm = useCallback(() => {
    setPageState("form");
  }, []);

  return (
    <>
      <div className="flex h-full bg-background text-foreground overflow-auto">
        <div className="flex-1 p-6 md:p-8">
          {/* Header */}
          <div className="max-w-3xl mx-auto mb-8">
            <div className="flex items-center gap-4 mb-6">
              <Link to="/" search={{ district: undefined }}>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground hover:text-foreground hover:bg-white/[0.06]"
                >
                  <ArrowLeft size={16} className="mr-2" />
                  Back to Explorer
                </Button>
              </Link>
            </div>

            <PageHeader
              icon={Sparkles}
              title="AI Property Valuation"
              subtitle="Get an instant estimate of your property's value using our AI model"
            />
          </div>

          {/* Step Progress Indicator */}
          <div className="max-w-3xl mx-auto flex items-center gap-3 mb-6 -mt-2">
            <div className="flex items-center gap-2">
              <div className={cn(
                "w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold",
                pageState === "form"
                  ? "bg-brand text-brand-foreground glow-brand-sm"
                  : "bg-surface-2 border border-white/[0.12] text-muted-foreground"
              )}>1</div>
              <span className={cn("text-xs font-medium", pageState !== "form" && "text-muted-foreground")}>
                Property Details
              </span>
            </div>
            <div className="flex-1 h-px bg-border/40" />
            <div className={cn("flex items-center gap-2", pageState === "form" && "opacity-40")}>
              <div className={cn(
                "w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold",
                pageState === "report"
                  ? "bg-brand text-brand-foreground glow-brand-sm"
                  : "bg-surface-2 border border-border text-muted-foreground"
              )}>2</div>
              <span className={cn("text-xs font-medium", pageState === "form" && "text-muted-foreground")}>
                Valuation Report
              </span>
            </div>
          </div>

          {/* Content */}
          {pageState === "form" && (
            <PropertyUploadForm
              onSubmit={handleFormSubmit}
              onLocationPick={() => setShowLocationPicker(true)}
              selectedLocation={selectedLocation}
              isSubmitting={valuationMutation.isPending}
            />
          )}

          {pageState === "report" && valuationResult && submittedData && (
            <Suspense fallback={<ContentLoader lines={15} />}>
              <ValuationReport
                valuation={valuationResult}
                propertyData={submittedData}
                locationIntelligence={locationIntelligence}
                onBack={handleBackToForm}
                onNewValuation={handleNewValuation}
              />
            </Suspense>
          )}

          {/* Error State */}
          {valuationMutation.isError && (
            <div className="max-w-2xl mx-auto mt-6">
              <ErrorState
                compact
                message={`Failed to get valuation. ${(valuationMutation.error as Error)?.message || "Please try again."}`}
                onRetry={() => {
                  if (submittedData) valuationMutation.mutate(submittedData);
                }}
              />
            </div>
          )}
        </div>
      </div>

      {/* Location Picker Modal */}
      <LocationPicker
        isOpen={showLocationPicker}
        onClose={() => setShowLocationPicker(false)}
        onConfirm={handleLocationConfirm}
        initialLocation={selectedLocation}
      />
    </>
  );
}
