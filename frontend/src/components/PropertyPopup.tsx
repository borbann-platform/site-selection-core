import { X, Home, MessageSquarePlus, ArrowRight } from "lucide-react";
import { Link } from "@tanstack/react-router";

interface PropertyData {
  id?: string | number;
  house_ref?: string;
  locator?: string;
  total_price?: number;
  building_area?: number;
  amphur?: string;
  tumbon?: string;
  building_style_desc?: string;
  no_of_floor?: number;
  building_age?: number;
  lat?: number;
  lon?: number;
}

interface PropertyPopupProps {
  property: PropertyData | null;
  position: { x: number; y: number } | null;
  onClose: () => void;
  onAddToChat?: (property: PropertyData) => void;
}

export function PropertyPopup({
  property,
  position,
  onClose,
  onAddToChat,
}: PropertyPopupProps) {
  if (!property || !position) return null;

  const formatPrice = (p: number) =>
    new Intl.NumberFormat("th-TH", {
      style: "currency",
      currency: "THB",
      maximumFractionDigits: 0,
    }).format(p);

  const price = property.total_price || 0;
  const pricePerSqm =
    property.building_area && price
      ? formatPrice(price / property.building_area)
      : "N/A";

  const handleAddToChat = () => {
    onAddToChat?.(property);
    onClose();
  };

  return (
    <div
      className="fixed z-100 pointer-events-auto animate-fade-in"
      style={{
        left: position.x,
        top: position.y,
        transform: "translate(-50%, -100%) translateY(-10px)",
      }}
    >
      <div className="glass-panel rounded-xl shadow-2xl shadow-black/30 overflow-hidden min-w-64">
        {/* Header */}
        <div className="flex items-center gap-2 px-3 py-2 bg-amber-500/10 border-b border-border">
          <Home size={14} className="text-amber-500 dark:text-amber-400" />
          <span className="flex-1 font-bold text-sm text-amber-600 dark:text-amber-400 truncate">
            {property.building_style_desc || "Property"}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="p-1 hover:bg-white/[0.08] rounded text-muted-foreground hover:text-foreground transition-colors"
          >
            <X size={14} />
          </button>
        </div>

        {/* Content */}
        <div className="p-3">
          <div className="text-lg font-bold text-gradient-brand mb-2">
            {formatPrice(price)}
          </div>
          <div className="grid grid-cols-2 gap-1 text-[11px] text-muted-foreground">
            <div>District:</div>
            <div className="text-right font-medium text-foreground/80">
              {property.amphur || "N/A"}
            </div>
            <div>Sub-district:</div>
            <div className="text-right font-medium text-foreground/80">
              {property.tumbon || "N/A"}
            </div>
            <div>Area:</div>
            <div className="text-right font-medium text-foreground/80">
              {property.building_area ? `${property.building_area} sqm` : "N/A"}
            </div>
            <div>Price/sqm:</div>
            <div className="text-right font-medium text-brand">
              {pricePerSqm}
            </div>
            <div>Floors:</div>
            <div className="text-right font-medium text-foreground/80">
              {property.no_of_floor || "N/A"}
            </div>
            <div>Age:</div>
            <div className="text-right font-medium text-foreground/80">
              {property.building_age ? `${property.building_age} yrs` : "N/A"}
            </div>
          </div>

          {/* View Details button - only show if property has ID */}
          {property.id && (
            <Link
              to="/property/$propertyId"
              params={{ propertyId: String(property.id) }}
              className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 bg-brand hover:bg-brand/90 text-brand-foreground text-xs font-medium rounded-lg transition-colors"
            >
              <ArrowRight size={14} />
              <span>View Details</span>
            </Link>
          )}

          {/* Add to Chat button */}
          {onAddToChat && (
            <button
              type="button"
              onClick={handleAddToChat}
              className="mt-2 w-full flex items-center justify-center gap-2 px-3 py-2 border border-white/[0.08] hover:bg-white/[0.06] text-muted-foreground hover:text-foreground text-xs font-medium rounded-lg transition-colors"
            >
              <MessageSquarePlus size={14} />
              <span>Add to Chat</span>
            </button>
          )}
        </div>
      </div>

      {/* Pointer arrow */}
      <div className="absolute left-1/2 -translate-x-1/2 bottom-0 translate-y-full">
        <div className="w-0 h-0 border-l-8 border-r-8 border-t-8 border-l-transparent border-r-transparent border-t-border" />
      </div>
    </div>
  );
}

// Mini property card for inline display in chat
export function PropertyMiniCard({
  property,
  onRemove,
}: {
  property: {
    name?: string;
    price?: number;
    area?: number;
    district?: string;
  };
  onRemove?: () => void;
}) {
  return (
    <div className="flex items-center gap-2 bg-amber-500/10 border border-amber-500/30 rounded-lg px-2 py-1.5">
      <Home size={12} className="text-amber-500 dark:text-amber-400" />
      <div className="flex-1 min-w-0">
        <div className="text-xs font-medium text-foreground truncate">
          {property.name || "Property"}
        </div>
        {property.price && (
          <div className="text-[10px] text-amber-600 dark:text-amber-300">
            ฿{(property.price / 1000000).toFixed(1)}M
            {property.area && ` • ${property.area}sqm`}
          </div>
        )}
      </div>
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="p-0.5 hover:bg-muted rounded text-muted-foreground hover:text-foreground"
        >
          <X size={12} />
        </button>
      )}
    </div>
  );
}
