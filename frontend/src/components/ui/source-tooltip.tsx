import { Info } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { DataSourceSpec } from "@/lib/dataSources";

interface SourceTooltipProps {
  source: DataSourceSpec;
  className?: string;
}

export function SourceTooltip({ source, className }: SourceTooltipProps) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={`Data source: ${source.label}`}
            className={
              className ??
              "inline-flex h-4 w-4 items-center justify-center rounded-full text-muted-foreground hover:text-foreground transition-colors"
            }
          >
            <Info size={12} />
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-64 p-2 text-xs leading-relaxed">
          <div className="font-semibold mb-1">{source.label}</div>
          <div className="text-primary-foreground/90">{source.citation}</div>
          {source.url ? (
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 inline-block underline underline-offset-2"
            >
              View source
            </a>
          ) : (
            <div className="mt-1 text-primary-foreground/80">
              Source URL placeholder - pending confirmation
            </div>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
