import { Home } from "lucide-react";

export interface PropertyCountProps {
  totalCount: number;
  shownCount: number;
}

export function PropertyCount({ totalCount, shownCount }: PropertyCountProps) {
  return (
    <div className="absolute bottom-20 left-4 z-40 hidden md:flex items-center gap-1.5 glass-panel rounded-full px-3 py-1.5 shadow-md">
      <Home className="w-3 h-3 text-brand" />
      <span className="text-[11px] font-medium text-foreground/80 tabular-nums">
        {totalCount}
        <span className="text-muted-foreground ml-1">({shownCount} shown)</span>
      </span>
    </div>
  );
}
