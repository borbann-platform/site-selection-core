/**
 * Property Upload Form - Multi-step wizard for property valuation.
 * Collects property details and location for AI valuation.
 */

import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import { cn } from "@/lib/utils";
import {
  Home,
  MapPin,
  Ruler,
  Calendar,
  Layers,
  Building2,
  ChevronRight,
  ChevronLeft,
  Check,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  api,
  type PropertyUploadRequest,
  type ResolveLocationResponse,
} from "@/lib/api";

interface PropertyUploadFormProps {
  onSubmit: (data: PropertyUploadRequest) => void;
  onLocationPick: () => void;
  selectedLocation: { lat: number; lon: number } | null;
  isSubmitting?: boolean;
}

interface FormData {
  building_style: string;
  building_area: string;
  land_area: string;
  no_of_floor: string;
  building_age: string;
  amphur: string;
  tumbon: string;
  village: string;
  asking_price: string;
}

const BUILDING_STYLES = [
  { value: "บ้านเดี่ยว", label: "บ้านเดี่ยว (Detached House)" },
  { value: "ทาวน์เฮ้าส์", label: "ทาวน์เฮ้าส์ (Townhouse)" },
  { value: "บ้านแฝด", label: "บ้านแฝด (Semi-Detached)" },
  { value: "อาคารพาณิชย์", label: "อาคารพาณิชย์ (Commercial Building)" },
  { value: "ตึกแถว", label: "ตึกแถว (Shophouse)" },
];

const DISTRICTS = [
  "วัฒนา",
  "ปทุมวัน",
  "คลองเตย",
  "พระโขนง",
  "สวนหลวง",
  "บางกะปิ",
  "ลาดพร้าว",
  "จตุจักร",
  "บางนา",
  "ห้วยขวาง",
  "บางรัก",
  "สาทร",
  "ยานนาวา",
  "บางคอแหลม",
  "ราชเทวี",
  "พญาไท",
  "ดินแดง",
  "บึงกุ่ม",
  "วังทองหลาง",
  "คันนายาว",
];

const STEPS = [
  { id: 1, title: "Property Details", icon: Home },
  { id: 2, title: "Location", icon: MapPin },
  { id: 3, title: "Review", icon: Check },
];

function StepIndicator({
  steps,
  currentStep,
}: {
  steps: typeof STEPS;
  currentStep: number;
}) {
  return (
    <div className="flex items-center justify-between mb-8">
      {steps.map((step, index) => {
        const isActive = currentStep === step.id;
        const isCompleted = currentStep > step.id;
        const Icon = step.icon;

        return (
          <div key={step.id} className="flex items-center flex-1">
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  "w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all",
                  isCompleted && "bg-brand border-brand",
                  isActive && "border-brand bg-brand/20",
                  !isActive && !isCompleted && "border-border bg-muted/50"
                )}
              >
                {isCompleted ? (
                  <Check size={18} className="text-foreground" />
                ) : (
                  <Icon
                    size={18}
                    className={cn(
                      isActive ? "text-brand" : "text-muted-foreground"
                    )}
                  />
                )}
              </div>
              <span
                className={cn(
                  "text-xs mt-2 font-medium",
                  isActive ? "text-brand" : "text-muted-foreground"
                )}
              >
                {step.title}
              </span>
            </div>
            {index < steps.length - 1 && (
              <div
                className={cn(
                  "flex-1 h-0.5 mx-3",
                  isCompleted ? "bg-brand" : "bg-muted/50"
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function InputField({
  label,
  icon: Icon,
  error,
  children,
}: {
  label: string;
  icon?: React.ComponentType<{ className?: string; size?: number }>;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label className="text-muted-foreground flex items-center gap-2">
        {Icon && <Icon size={14} className="text-muted-foreground" />}
        {label}
      </Label>
      {children}
      {error && (
        <p className="text-xs text-destructive flex items-center gap-1">
          <AlertCircle size={12} />
          {error}
        </p>
      )}
    </div>
  );
}

export function PropertyUploadForm({
  onSubmit,
  onLocationPick,
  selectedLocation,
  isSubmitting = false,
}: PropertyUploadFormProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const lastAutoFillLocation = useRef<string | null>(null);
  const [locationStatus, setLocationStatus] = useState<
    "idle" | "resolving" | "resolved" | "failed"
  >("idle");
  const [resolvedLocation, setResolvedLocation] =
    useState<ResolveLocationResponse | null>(null);
  const [formData, setFormData] = useState<FormData>({
    building_style: "",
    building_area: "",
    land_area: "",
    no_of_floor: "1",
    building_age: "0",
    amphur: "",
    tumbon: "",
    village: "",
    asking_price: "",
  });
  const [errors, setErrors] = useState<Partial<FormData>>({});

  const districtOptions = useMemo(() => {
    const options = [...DISTRICTS];
    const detected = resolvedLocation?.amphur;
    if (detected && !options.includes(detected)) {
      options.unshift(detected);
    }
    if (formData.amphur && !options.includes(formData.amphur)) {
      options.unshift(formData.amphur);
    }
    return options;
  }, [formData.amphur, resolvedLocation?.amphur]);

  const hasDetectedLocationDiff = useMemo(() => {
    if (!resolvedLocation) return false;
    return (
      (resolvedLocation.amphur && resolvedLocation.amphur !== formData.amphur) ||
      (resolvedLocation.tumbon || "") !== (formData.tumbon || "") ||
      (resolvedLocation.village || "") !== (formData.village || "")
    );
  }, [formData.amphur, formData.tumbon, formData.village, resolvedLocation]);

  useEffect(() => {
    if (!selectedLocation) {
      setLocationStatus("idle");
      setResolvedLocation(null);
      lastAutoFillLocation.current = null;
      return;
    }

    const locationKey = `${selectedLocation.lat}:${selectedLocation.lon}`;
    if (lastAutoFillLocation.current === locationKey) return;
    lastAutoFillLocation.current = locationKey;

    const autoFillLocation = async () => {
      try {
        setLocationStatus("resolving");
        const resolved = await api.resolveLocation({
          lat: selectedLocation.lat,
          lon: selectedLocation.lon,
        });
        setResolvedLocation(resolved);
        setLocationStatus("resolved");

        setFormData((prev) => {
          return {
            ...prev,
            amphur: resolved.amphur,
            tumbon: resolved.tumbon || "",
            village: resolved.village || "",
          };
        });

        setErrors((prev) => ({
          ...prev,
          amphur: resolved.amphur ? undefined : prev.amphur,
          tumbon: resolved.tumbon ? undefined : prev.tumbon,
        }));
      } catch {
        setLocationStatus("failed");
        setResolvedLocation(null);
      }
    };

    void autoFillLocation();
  }, [selectedLocation]);

  const handleApplyDetected = useCallback(() => {
    if (!resolvedLocation) return;
    setFormData((prev) => ({
      ...prev,
      amphur: resolvedLocation.amphur,
      tumbon: resolvedLocation.tumbon || "",
      village: resolvedLocation.village || "",
    }));
    setErrors((prev) => ({
      ...prev,
      amphur: undefined,
      tumbon: undefined,
    }));
  }, [resolvedLocation]);

  const updateField = useCallback(
    (field: keyof FormData, value: string) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      // Clear error when field is updated
      if (errors[field]) {
        setErrors((prev) => ({ ...prev, [field]: undefined }));
      }
    },
    [errors]
  );

  const validateStep1 = (): boolean => {
    const newErrors: Partial<FormData> = {};

    if (!formData.building_style) {
      newErrors.building_style = "Please select a building type";
    }
    if (!formData.building_area || Number(formData.building_area) <= 0) {
      newErrors.building_area = "Building area is required";
    }
    if (Number(formData.no_of_floor) < 1) {
      newErrors.no_of_floor = "At least 1 floor required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateStep2 = (): boolean => {
    const newErrors: Partial<FormData> = {};

    if (!formData.amphur) {
      newErrors.amphur = "Please select a district";
    }
    if (!selectedLocation) {
      // We'll handle this separately since it's not in formData
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0 && selectedLocation !== null;
  };

  const handleNext = () => {
    if (currentStep === 1 && validateStep1()) {
      setCurrentStep(2);
    } else if (currentStep === 2 && validateStep2()) {
      setCurrentStep(3);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSubmit = () => {
    if (!selectedLocation) return;

    const data: PropertyUploadRequest = {
      building_style: formData.building_style,
      building_area: Number(formData.building_area),
      land_area: formData.land_area ? Number(formData.land_area) : undefined,
      no_of_floor: Number(formData.no_of_floor),
      building_age: Number(formData.building_age),
      amphur: formData.amphur,
      tumbon: formData.tumbon || undefined,
      village: formData.village || undefined,
      latitude: selectedLocation.lat,
      longitude: selectedLocation.lon,
      asking_price: formData.asking_price
        ? Number(formData.asking_price)
        : undefined,
    };

    onSubmit(data);
  };

  return (
    <div className="max-w-2xl mx-auto">
      <StepIndicator steps={STEPS} currentStep={currentStep} />

      {/* Step 1: Property Details */}
      {currentStep === 1 && (
        <div className="space-y-6">
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-lg font-semibold text-foreground mb-6 flex items-center gap-2">
              <Home size={20} className="text-brand" />
              Property Details
            </h3>

            <div className="space-y-5">
              {/* Building Style */}
              <InputField
                label="Building Type"
                icon={Building2}
                error={errors.building_style}
              >
                <select
                  value={formData.building_style}
                  onChange={(e) => updateField("building_style", e.target.value)}
                  className="w-full bg-card border border-border rounded-lg px-3 py-2.5 text-foreground focus:outline-none focus:border-brand"
                >
                  <option value="" className="bg-card text-foreground">
                    Select building type...
                  </option>
                  {BUILDING_STYLES.map((style) => (
                    <option
                      key={style.value}
                      value={style.value}
                      className="bg-card text-foreground"
                    >
                      {style.label}
                    </option>
                  ))}
                </select>
              </InputField>

              {/* Building Area */}
              <InputField
                label="Building Area (sqm)"
                icon={Ruler}
                error={errors.building_area}
              >
                <input
                  type="number"
                  min="1"
                  value={formData.building_area}
                  onChange={(e) => updateField("building_area", e.target.value)}
                  placeholder="e.g., 150"
                  className="w-full bg-card border border-border rounded-lg px-3 py-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-brand"
                />
              </InputField>

              {/* Land Area */}
              <InputField label="Land Area (sqm, optional)" icon={Ruler}>
                <input
                  type="number"
                  min="0"
                  value={formData.land_area}
                  onChange={(e) => updateField("land_area", e.target.value)}
                  placeholder="e.g., 200"
                  className="w-full bg-card border border-border rounded-lg px-3 py-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-brand"
                />
              </InputField>

              <div className="grid grid-cols-2 gap-4">
                {/* Floors */}
                <InputField
                  label="Number of Floors"
                  icon={Layers}
                  error={errors.no_of_floor}
                >
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={formData.no_of_floor}
                    onChange={(e) => updateField("no_of_floor", e.target.value)}
                    className="w-full bg-card border border-border rounded-lg px-3 py-2.5 text-foreground focus:outline-none focus:border-brand"
                  />
                </InputField>

                {/* Building Age */}
                <InputField label="Building Age (years)" icon={Calendar}>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={formData.building_age}
                    onChange={(e) => updateField("building_age", e.target.value)}
                    className="w-full bg-card border border-border rounded-lg px-3 py-2.5 text-foreground focus:outline-none focus:border-brand"
                  />
                </InputField>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Step 2: Location */}
      {currentStep === 2 && (
        <div className="space-y-6">
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-lg font-semibold text-foreground mb-6 flex items-center gap-2">
              <MapPin size={20} className="text-brand" />
              Location
            </h3>

            <div className="space-y-5">
              {/* Location Status */}
              <div className="rounded-lg border border-border bg-muted/40 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      Location details
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {selectedLocation
                        ? `Pin set at ${selectedLocation.lat.toFixed(5)}, ${selectedLocation.lon.toFixed(5)}`
                        : "Pick a location to auto-detect district"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    {locationStatus === "resolving" && (
                      <span className="rounded-full bg-brand/20 px-2 py-1 text-brand">
                        Detecting...
                      </span>
                    )}
                    {locationStatus === "resolved" && (
                      <span className="rounded-full bg-emerald-500/20 px-2 py-1 text-emerald-200">
                        Detected
                      </span>
                    )}
                    {locationStatus === "failed" && (
                      <span className="rounded-full bg-rose-500/20 px-2 py-1 text-rose-200">
                        Detect failed
                      </span>
                    )}
                  </div>
                </div>
                {resolvedLocation && (
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span className="rounded-md border border-border bg-card px-2 py-1">
                      District: {resolvedLocation.amphur}
                    </span>
                    {resolvedLocation.tumbon && (
                      <span className="rounded-md border border-border bg-card px-2 py-1">
                        Sub-district: {resolvedLocation.tumbon}
                      </span>
                    )}
                    {resolvedLocation.village && (
                      <span className="rounded-md border border-border bg-card px-2 py-1">
                        Village: {resolvedLocation.village}
                      </span>
                    )}
                    <span className="text-muted-foreground/70">
                      ({resolvedLocation.distance_m.toLocaleString()}m away)
                    </span>
                  </div>
                )}
                {hasDetectedLocationDiff && resolvedLocation && (
                  <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-brand/20 bg-brand/10 px-3 py-2">
                    <p className="text-xs text-foreground">
                      Detected location differs from current fields. Apply the
                      detected values?
                    </p>
                    <Button
                      type="button"
                      size="sm"
                      onClick={handleApplyDetected}
                      className="bg-brand hover:bg-brand/90 text-black"
                    >
                      Apply
                    </Button>
                  </div>
                )}
              </div>

              {/* District */}
              <InputField
                label="District (เขต)"
                icon={MapPin}
                error={errors.amphur}
              >
                <select
                  value={formData.amphur}
                  onChange={(e) => updateField("amphur", e.target.value)}
                  className="w-full bg-card border border-border rounded-lg px-3 py-2.5 text-foreground focus:outline-none focus:border-brand"
                >
                  <option value="" className="bg-card text-foreground">
                    Select district...
                  </option>
                  {districtOptions.map((district) => (
                    <option
                      key={district}
                      value={district}
                      className="bg-card text-foreground"
                    >
                      {district}
                    </option>
                  ))}
                </select>
              </InputField>

              {/* Sub-district */}
              <InputField label="Sub-district (แขวง, optional)">
                <input
                  type="text"
                  value={formData.tumbon}
                  onChange={(e) => updateField("tumbon", e.target.value)}
                  placeholder="e.g., คลองตันเหนือ"
                  className="w-full bg-card border border-border rounded-lg px-3 py-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-brand"
                />
              </InputField>

              {/* Village */}
              <InputField label="Village/Project Name (optional)">
                <input
                  type="text"
                  value={formData.village}
                  onChange={(e) => updateField("village", e.target.value)}
                  placeholder="e.g., บ้านกลางเมือง"
                  className="w-full bg-card border border-border rounded-lg px-3 py-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-brand"
                />
              </InputField>

              {/* Location Picker */}
              <div className="space-y-2">
                <Label className="text-muted-foreground flex items-center gap-2">
                  <MapPin size={14} className="text-muted-foreground" />
                  Property Location
                </Label>
                <div
                  className={cn(
                    "border rounded-lg p-4 transition-all",
                    selectedLocation
                      ? "border-brand/30 bg-brand/10"
                      : "border-border bg-muted/50"
                  )}
                >
                  {selectedLocation ? (
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-foreground font-medium">
                          Location Selected
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {selectedLocation.lat.toFixed(6)},{" "}
                          {selectedLocation.lon.toFixed(6)}
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={onLocationPick}
                        className="border-border bg-muted/50 text-foreground hover:bg-muted"
                      >
                        Change
                      </Button>
                    </div>
                  ) : (
                    <div className="text-center py-4">
                      <MapPin
                        size={32}
                        className="mx-auto text-muted-foreground mb-3"
                      />
                      <p className="text-sm text-muted-foreground mb-3">
                        Click to select property location on map
                      </p>
                      <Button
                        type="button"
                        onClick={onLocationPick}
                        className="bg-brand hover:bg-brand/90 text-black"
                      >
                        <MapPin size={16} className="mr-2" />
                        Pick Location
                      </Button>
                    </div>
                  )}
                </div>
                {!selectedLocation && errors.amphur && (
                  <p className="text-xs text-destructive flex items-center gap-1">
                    <AlertCircle size={12} />
                    Please select a location on the map
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Step 3: Review */}
      {currentStep === 3 && (
        <div className="space-y-6">
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-lg font-semibold text-foreground mb-6 flex items-center gap-2">
              <Check size={20} className="text-brand" />
              Review Your Property
            </h3>

            <div className="space-y-4">
              {/* Property Summary */}
              <div className="grid grid-cols-2 gap-4">
                <ReviewItem
                  label="Building Type"
                  value={formData.building_style}
                />
                <ReviewItem
                  label="Building Area"
                  value={`${formData.building_area} sqm`}
                />
                <ReviewItem
                  label="Land Area"
                  value={
                    formData.land_area ? `${formData.land_area} sqm` : "N/A"
                  }
                />
                <ReviewItem
                  label="Floors"
                  value={`${formData.no_of_floor} floor(s)`}
                />
                <ReviewItem
                  label="Building Age"
                  value={`${formData.building_age} years`}
                />
                <ReviewItem label="District" value={formData.amphur} />
                <ReviewItem
                  label="Sub-district"
                  value={formData.tumbon || "N/A"}
                />
                <ReviewItem
                  label="Village/Project"
                  value={formData.village || "N/A"}
                />
              </div>

              {/* Location */}
              {selectedLocation && (
                <div className="mt-4 p-3 bg-muted/50 rounded-lg">
                  <p className="text-xs text-muted-foreground mb-1">Location</p>
                  <p className="text-sm text-foreground font-mono">
                    {selectedLocation.lat.toFixed(6)},{" "}
                    {selectedLocation.lon.toFixed(6)}
                  </p>
                </div>
              )}

              {/* Optional: Asking Price */}
              <div className="mt-4 pt-4 border-t border-border">
                <InputField label="Your Asking Price (optional, for comparison)">
                  <input
                    type="number"
                    min="0"
                    value={formData.asking_price}
                    onChange={(e) => updateField("asking_price", e.target.value)}
                    placeholder="e.g., 5000000"
                    className="w-full bg-card border border-border rounded-lg px-3 py-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-brand"
                  />
                </InputField>
                <p className="text-xs text-muted-foreground mt-2">
                  If you have an asking price in mind, we'll compare it with our
                  AI valuation.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Navigation Buttons */}
      <div className="flex justify-between mt-8">
        <Button
          type="button"
          variant="outline"
          onClick={handleBack}
          disabled={currentStep === 1}
          className={cn(
            "border-border bg-muted/50 text-foreground hover:bg-muted",
            currentStep === 1 && "opacity-0 pointer-events-none"
          )}
        >
          <ChevronLeft size={16} className="mr-1" />
          Back
        </Button>

        {currentStep < 3 ? (
          <Button
            type="button"
            onClick={handleNext}
            className="bg-brand hover:bg-brand/90 text-black"
          >
            Next
            <ChevronRight size={16} className="ml-1" />
          </Button>
        ) : (
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting || !selectedLocation}
            className="bg-brand hover:bg-brand/90 text-black disabled:opacity-50"
          >
            {isSubmitting ? (
              <>
                <span className="animate-spin mr-2">
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                </span>
                Analyzing...
              </>
            ) : (
              <>
                Get Valuation
                <ChevronRight size={16} className="ml-1" />
              </>
            )}
          </Button>
        )}
      </div>
    </div>
  );
}

function ReviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-muted/50 rounded-lg p-3">
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      <p className="text-sm text-foreground font-medium">{value}</p>
    </div>
  );
}

export default PropertyUploadForm;
