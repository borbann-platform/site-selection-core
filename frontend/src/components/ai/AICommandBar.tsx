import { useRef, useEffect } from "react";
import { MapPin, Square, Send, ChevronUp, ChevronDown, X } from "lucide-react";
import { cn } from "@/lib/utils";

// Local type definitions (decoupled from AgentChatPanel)
export type SelectionMode = "none" | "location" | "bbox";

export type AttachmentType = "location" | "bbox" | "property";

export interface Attachment {
  id: string;
  type: AttachmentType;
  data: Record<string, unknown>;
  label: string;
}

interface AICommandBarProps {
  input: string;
  onInputChange: (value: string) => void;
  onSubmit: () => void;
  attachments: Attachment[];
  selectionMode: SelectionMode;
  isExpanded: boolean;
  isRunning: boolean;
  onToggleExpanded: () => void;
  onPickLocation?: () => void;
  onPickBbox?: () => void;
  onRemoveAttachment?: (id: string) => void;
}

const EXAMPLE_PROMPTS = [
  "Why are Soi 39 houses pricier than Soi 71?",
  "Show me undervalued homes near international schools.",
];

export function AICommandBar({
  input,
  onInputChange,
  onSubmit,
  attachments,
  selectionMode,
  isExpanded,
  isRunning,
  onToggleExpanded,
  onPickLocation,
  onPickBbox,
  onRemoveAttachment,
}: AICommandBarProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  // Keyboard shortcut: / to focus input
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Focus input with "/"
      if (e.key === "/" && document.activeElement !== inputRef.current) {
        e.preventDefault();
        inputRef.current?.focus();
      }
      // Blur input with Escape
      if (e.key === "Escape" && document.activeElement === inputRef.current) {
        inputRef.current?.blur();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isRunning && selectionMode === "none") {
      onSubmit();
    }
  };

  const showExamples = !input && attachments.length === 0 && !isExpanded;

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-full max-w-2xl px-4">
      <form
        onSubmit={handleSubmit}
        className="bg-card/95 backdrop-blur-xl border border-border rounded-2xl shadow-2xl shadow-black/10 overflow-hidden focus-within:ring-1 focus-within:ring-emerald-500/20 focus-within:border-emerald-500/30 transition-all duration-200"
      >
        {/* Selection Mode Indicator */}
        {selectionMode !== "none" && (
          <div className="px-4 py-2 bg-brand/10 border-b border-brand/30 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-brand">
              {selectionMode === "location" ? (
                <>
                  <MapPin size={14} className="animate-pulse" />
                  <span>Click on map to select a point</span>
                </>
              ) : (
                <>
                  <Square size={14} className="animate-pulse" />
                  <span>Click 4 corners on map to draw area</span>
                </>
              )}
            </div>
          </div>
        )}

        {/* Attachments */}
        {attachments.length > 0 && (
          <div className="px-4 py-2 border-b border-border flex flex-wrap gap-2">
            {attachments.map((att) => (
              <AttachmentBadge
                key={att.id}
                attachment={att}
                onRemove={() => onRemoveAttachment?.(att.id)}
              />
            ))}
          </div>
        )}

        {/* Main Input Bar */}
        <div className="flex items-center gap-2 px-4 py-3">
          {/* Selection Toolbar */}
          <div className="flex gap-1">
            <button
              type="button"
              onClick={onPickLocation}
              disabled={selectionMode !== "none"}
              className={cn(
                "p-2 rounded-lg transition-all duration-150 active:scale-95",
                selectionMode === "location"
                  ? "bg-brand/20 text-brand border border-brand/30"
                  : "bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground disabled:opacity-30"
              )}
              title="Pick point location"
            >
              <MapPin size={18} />
            </button>
            <button
              type="button"
              onClick={onPickBbox}
              disabled={selectionMode !== "none"}
              className={cn(
                "p-2 rounded-lg transition-all duration-150 active:scale-95",
                selectionMode === "bbox"
                  ? "bg-brand/20 text-brand border border-brand/30"
                  : "bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground disabled:opacity-30"
              )}
              title="Draw area on map"
            >
              <Square size={18} />
            </button>
          </div>

          {/* Input Field */}
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            placeholder={
              selectionMode !== "none"
                ? "Complete selection on map..."
                : "Ask AI: Find houses, analyze locations... (press / to focus)"
            }
            disabled={isRunning || selectionMode !== "none"}
            className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-50"
          />

          {/* Send Button */}
          <button
            type="submit"
            disabled={!input.trim() || isRunning || selectionMode !== "none"}
            className="p-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition-all duration-150 disabled:opacity-30 disabled:cursor-not-allowed active:scale-95 enabled:shadow-md enabled:shadow-emerald-500/20"
            title="Send message"
          >
            <Send size={18} />
          </button>

          {/* Expand/Collapse Toggle */}
          <button
            type="button"
            onClick={onToggleExpanded}
            className="p-2 rounded-lg bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground transition-colors"
            title={isExpanded ? "Collapse panel" : "Expand panel"}
          >
            {isExpanded ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
          </button>
        </div>

        {/* Example Prompts */}
        {showExamples && (
          <div className="px-4 pb-3 border-t border-border">
            <div className="text-[10px] text-muted-foreground mb-2 mt-2">
              Try asking:
            </div>
            <div className="flex flex-wrap gap-2">
              {EXAMPLE_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => onInputChange(prompt)}
                  className="px-2 py-1 text-[11px] bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground hover:border-emerald-500/30 rounded border border-border transition-all duration-150"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}
      </form>
    </div>
  );
}

// Attachment Badge Component
function AttachmentBadge({
  attachment,
  onRemove,
}: {
  attachment: Attachment;
  onRemove: () => void;
}) {
  const colors = {
    location: "bg-magenta-500/10 border-magenta-500/30 text-magenta-300",
    bbox: "bg-cyan-500/10 border-cyan-500/30 text-cyan-300",
    property: "bg-amber-500/10 border-amber-500/30 text-amber-300",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-1 rounded-lg border text-xs",
        colors[attachment.type]
      )}
    >
      <span className="truncate max-w-xs">
        {attachment.label || attachment.type}
      </span>
      <button
        type="button"
        onClick={onRemove}
        className="hover:bg-white/10 rounded p-0.5 transition-colors"
      >
        <X size={12} />
      </button>
    </div>
  );
}
