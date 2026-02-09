/**
 * Property Valuation Page - Upload property details and get AI valuation.
 * Multi-step wizard with location picker and comprehensive report.
 */

import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, useCallback } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Shell } from "@/components/Shell";
import { PropertyUploadForm } from "@/components/PropertyUploadForm";
import { LocationPicker } from "@/components/LocationPicker";
import { ValuationReport } from "@/components/ValuationReport";
import { api, type PropertyUploadRequest, type ValuationResponse } from "@/lib/api";
import { Sparkles, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

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
    <Shell>
      <div className="flex h-full bg-background text-foreground overflow-auto">
        <div className="flex-1 p-6 md:p-8">
          {/* Header */}
          <div className="max-w-3xl mx-auto mb-8">
            <div className="flex items-center gap-4 mb-6">
              <Link to="/" search={{ district: undefined }}>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground hover:text-foreground hover:bg-muted"
                >
                  <ArrowLeft size={16} className="mr-2" />
                  Back to Explorer
                </Button>
              </Link>
            </div>

            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center">
                <Sparkles size={24} className="text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-foreground">
                  AI Property Valuation
                </h1>
                <p className="text-muted-foreground">
                  Get an instant estimate of your property's value using our AI
                  model
                </p>
              </div>
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
            <ValuationReport
              valuation={valuationResult}
              propertyData={submittedData}
              locationIntelligence={locationIntelligence}
              onBack={handleBackToForm}
              onNewValuation={handleNewValuation}
            />
          )}

          {/* Error State */}
          {valuationMutation.isError && (
            <div className="max-w-2xl mx-auto mt-6 p-4 bg-rose-500/10 border border-rose-500/30 rounded-lg">
              <p className="text-rose-400 text-sm">
                Failed to get valuation. Please try again.
              </p>
              <p className="text-muted-foreground text-xs mt-1">
                {(valuationMutation.error as Error)?.message}
              </p>
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
    </Shell>
  );
}
