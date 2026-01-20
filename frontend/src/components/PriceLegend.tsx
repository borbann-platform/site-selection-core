interface PriceLegendProps {
  minPrice: number;
  maxPrice: number;
}

const formatPrice = (value: number): string => {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }
  return `${(value / 1_000).toFixed(0)}K`;
};

export function PriceLegend({ minPrice, maxPrice }: PriceLegendProps) {
  return (
    <div className="absolute bottom-6 right-6 z-40 bg-card/90 backdrop-blur-md border border-border rounded-lg p-3 min-w-40">
      <div className="text-[10px] text-muted-foreground mb-2 font-medium">
        Price (THB)
      </div>
      <div
        className="h-3 rounded-full mb-1"
        style={{
          background:
            "linear-gradient(to right, rgb(50, 200, 50), rgb(255, 200, 50), rgb(255, 50, 50))",
        }}
      />
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>{formatPrice(minPrice)}</span>
        <span>{formatPrice(maxPrice)}</span>
      </div>
    </div>
  );
}
