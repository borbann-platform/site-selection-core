/**
 * Property Valuation Page - Upload property details and get AI valuation.
 * Multi-step wizard with location picker and comprehensive report.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { lazy, Suspense, useCallback, useState } from "react";
import { LocationPicker } from "@/components/LocationPicker";
import { PropertyUploadForm } from "@/components/PropertyUploadForm";
import { ErrorState } from "@/components/ui/error-state";
import { ContentLoader } from "@/components/ui/loading";
import {
  api,
  type PropertyUploadRequest,
  type ValuationResponse,
} from "@/lib/api";

const ValuationReport = lazy(() =>
  import("@/components/ValuationReport").then((m) => ({
    default: m.ValuationReport,
  })),
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
    [],
  );

  const handleFormSubmit = useCallback(
    (data: PropertyUploadRequest) => {
      valuationMutation.mutate(data);
    },
    [valuationMutation],
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
      <div className="flex min-h-[calc(100vh-4rem)] bg-background text-foreground overflow-auto">
        <div className="flex-1 p-6 md:p-8">
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
