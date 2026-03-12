import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Building2, ExternalLink, Home, MapPin } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";

export const Route = createFileRoute("/_authenticated/listing/$listingKey")({
  component: ListingDetailPage,
});

function formatPrice(price: number | null): string {
  if (price === null || !Number.isFinite(price)) {
    return "Price unavailable";
  }
  return `฿${price.toLocaleString("th-TH")}`;
}

function ListingDetailPage() {
  const { listingKey } = Route.useParams();

  const {
    data: listing,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["listing-detail", listingKey],
    queryFn: () => api.getListingByKey(listingKey),
    staleTime: 1000 * 60 * 5,
  });

  if (isError) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center bg-background text-foreground">
        <ErrorState
          title="Listing not found"
          message="The listing could not be loaded or no longer exists."
        />
        <Link to="/" search={{ district: undefined }} className="mt-3">
          <Button variant="outline">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Explorer
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-5xl p-4 md:p-8">
      <div className="mb-4">
        <Link to="/" search={{ district: undefined }}>
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Explorer
          </Button>
        </Link>
      </div>

      {isLoading || !listing ? (
        <div className="space-y-4">
          <Skeleton className="h-8 w-1/2" />
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          <div className="space-y-4">
            <div className="rounded-xl border border-border bg-card p-5">
              <div className="mb-2 flex items-center gap-2 text-sm text-muted-foreground">
                <Building2 className="h-4 w-4" />
                <span>{listing.source_type.replace(/_/g, " ")}</span>
              </div>
              <h1 className="text-xl font-semibold">
                {listing.title || listing.building_style_desc || "Listing"}
              </h1>
              <p className="mt-2 text-2xl font-bold text-brand">
                {formatPrice(listing.total_price)}
              </p>
              <div className="mt-4 space-y-2 text-sm">
                <p className="flex items-center gap-2 text-muted-foreground">
                  <MapPin className="h-4 w-4" />
                  {[listing.tumbon, listing.amphur].filter(Boolean).join(", ") ||
                    "Location unavailable"}
                </p>
                {listing.building_area != null && (
                  <p className="flex items-center gap-2 text-muted-foreground">
                    <Home className="h-4 w-4" />
                    {listing.building_area.toLocaleString("th-TH")} sqm
                  </p>
                )}
              </div>
            </div>

            {listing.detail_url && (
              <a
                href={listing.detail_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm hover:bg-muted"
              >
                <ExternalLink className="h-4 w-4" />
                Open Source Listing
              </a>
            )}
          </div>

          <div className="rounded-xl border border-border bg-card p-2">
            {listing.image_url ? (
              <img
                src={listing.image_url}
                alt={listing.title || "Listing"}
                className="h-[360px] w-full rounded-lg object-cover"
              />
            ) : (
              <div className="flex h-[360px] items-center justify-center rounded-lg border border-dashed border-border text-sm text-muted-foreground">
                Image unavailable
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
