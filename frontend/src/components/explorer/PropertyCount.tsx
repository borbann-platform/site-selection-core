import { Home } from "lucide-react";

export interface PropertyCountProps {
  totalCount: number;
  shownCount: number;
}

export function PropertyCount({ totalCount, shownCount }: PropertyCountProps) {
  return (
    <div className="absolute top-6 left-1/2 -translate-x-1/2 z-40 bg-card/90 backdrop-blur-md border border-border rounded-full px-4 py-2 shadow-lg">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Home className="w-3 h-3" />
        <span>
          {totalCount} properties | {shownCount} shown
        </span>
      </div>
    </div>
  );
}
