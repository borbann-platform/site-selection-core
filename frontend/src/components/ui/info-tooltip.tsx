import { CircleHelp } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface InfoTooltipProps {
  title: string;
  description: string;
}

export function InfoTooltip({ title, description }: InfoTooltipProps) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={`How ${title} is calculated`}
            className="inline-flex h-4 w-4 items-center justify-center rounded-full text-muted-foreground hover:text-foreground transition-colors"
          >
            <CircleHelp size={12} />
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-72 p-2 text-xs leading-relaxed">
          <div className="font-semibold mb-1">{title}</div>
          <div className="text-primary-foreground/90">{description}</div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
