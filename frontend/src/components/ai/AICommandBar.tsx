import { useRef, useEffect } from "react";
import { MapPin, Square, Send, ChevronUp, ChevronDown, X } from "lucide-react";
import { cn } from "@/lib/utils";

// Local type definitions for command bar interaction.
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
  const inputRef = useRef<HTMLTextAreaElement>(null);

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

  useEffect(() => {
    if (!inputRef.current) return;
    inputRef.current.style.height = "0px";
    inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 144)}px`;
  }, [input]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isRunning && selectionMode === "none") {
      onSubmit();
    }
  };

  const showExamples = !input && attachments.length === 0 && !isExpanded;

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-full max-w-3xl px-3 sm:px-4">
      <form
        onSubmit={handleSubmit}
        className={cn(
          "glass-panel rounded-2xl shadow-2xl overflow-hidden transition-all duration-200",
          "focus-within:ring-1 focus-within:ring-ai-accent/30 focus-within:border-ai-border",
          isRunning && "animate-ai-pulse"
        )}
      >
        {/* Selection Mode Indicator */}
        {selectionMode !== "none" && (
          <div className="px-4 py-2 bg-brand-surface border-b border-brand-border/50 flex items-center justify-between">
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
          <div className="px-4 py-2 border-b border-white/[0.06] flex flex-wrap gap-2">
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
        <div className="flex items-end gap-2 px-3 py-3 sm:px-4">
          {/* Selection Toolbar */}
          <div className="flex gap-1">
            <button
              type="button"
              onClick={onPickLocation}
              disabled={selectionMode !== "none"}
              className={cn(
                "p-2 rounded-lg transition-all duration-150 active:scale-95",
                selectionMode === "location"
                  ? "bg-brand/15 text-brand border border-brand/30"
                  : "bg-white/[0.04] hover:bg-white/[0.08] text-muted-foreground hover:text-foreground disabled:opacity-30"
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
                  ? "bg-brand/15 text-brand border border-brand/30"
                  : "bg-white/[0.04] hover:bg-white/[0.08] text-muted-foreground hover:text-foreground disabled:opacity-30"
              )}
              title="Draw area on map"
            >
              <Square size={18} />
            </button>
          </div>

          {/* Input Field */}
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (input.trim() && !isRunning && selectionMode === "none") {
                  onSubmit();
                }
              }
            }}
            placeholder={
              selectionMode !== "none"
                ? "Complete selection on map..."
                : "Ask AI for analysis, planning, or market insights... (press / to focus)"
            }
            disabled={isRunning || selectionMode !== "none"}
            rows={1}
            className="flex-1 resize-none overflow-y-auto max-h-36 min-h-10 bg-white/[0.05] border border-white/[0.08] rounded-xl px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-ai-accent/40 focus:bg-white/[0.08] disabled:opacity-40 transition-all duration-150"
          />

          {/* Send Button */}
          <button
            type="submit"
            disabled={!input.trim() || isRunning || selectionMode !== "none"}
            className={cn(
              "p-2 rounded-lg transition-all duration-150 active:scale-95 disabled:cursor-not-allowed",
              input.trim() && !isRunning && selectionMode === "none"
                ? "bg-ai-accent text-ai-accent-foreground glow-ai-sm"
                : "bg-white/[0.05] text-muted-foreground/40 opacity-50"
            )}
            title="Send message"
          >
            <Send size={18} />
          </button>

          {/* Expand/Collapse Toggle */}
          <button
            type="button"
            onClick={onToggleExpanded}
            className="p-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-muted-foreground/60 hover:text-foreground transition-colors"
            title={isExpanded ? "Collapse panel" : "Expand panel"}
          >
            {isExpanded ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
          </button>
        </div>

        {selectionMode === "none" && (
          <div className="px-4 pb-2 -mt-1 text-[10px] text-muted-foreground">
            Enter to send, Shift+Enter for newline
          </div>
        )}

        {/* Example Prompts */}
        {showExamples && (
          <div className="px-4 pb-3 border-t border-white/[0.05]">
            <div className="text-[10px] text-muted-foreground/50 mb-2 mt-2">
              Try asking:
            </div>
            <div className="flex flex-wrap gap-2">
              {EXAMPLE_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => onInputChange(prompt)}
                  className="px-2.5 py-1 text-[11px] bg-white/[0.04] hover:bg-white/[0.08] text-muted-foreground/70 hover:text-foreground border border-white/[0.08] hover:border-ai-accent/30 rounded-full transition-all duration-150"
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
