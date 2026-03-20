import { useEffect, useRef } from "react";
import {
  ArrowUp,
  ChevronDown,
  ChevronUp,
  Crosshair,
  MapPin,
  Square,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

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
  "Find livable homes near BTS with better resale liquidity.",
  "Compare Ari and Saphan Khwai for low-rise condos under 6M.",
  "Summarize this selected property like an acquisition memo.",
] as const;

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

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "/" && document.activeElement !== inputRef.current) {
        event.preventDefault();
        inputRef.current?.focus();
      }

      if (event.key === "Escape" && document.activeElement === inputRef.current) {
        inputRef.current?.blur();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    const textarea = inputRef.current;
    if (!textarea) {
      return;
    }

    textarea.style.height = "0px";
    const nextHeight = input.length === 0 ? 48 : Math.min(textarea.scrollHeight, 180);
    textarea.style.height = `${nextHeight}px`;
  }, [input]);

  const isBlocked = isRunning || selectionMode !== "none";
  const canSend = input.trim().length > 0 && !isBlocked;
  const showExamples = input.trim().length === 0 && attachments.length === 0 && !isExpanded;

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-50 px-3 pb-3 sm:px-4 sm:pb-4">
      <div className="mx-auto w-full max-w-4xl">
        {selectionMode !== "none" && (
          <div className="pointer-events-auto mb-3 animate-slide-up rounded-full border border-brand/20 bg-[color:rgba(245,250,247,0.96)] px-4 py-2 text-xs text-foreground shadow-[0_14px_30px_rgba(15,23,42,0.08)] dark:bg-[color:rgba(16,20,18,0.94)] dark:text-foreground">
            <div className="flex items-center gap-2 font-medium">
              <Crosshair className="h-3.5 w-3.5 text-brand" />
              {selectionMode === "location"
                ? "Click once on the map to anchor this prompt."
                : "Click four corners to define the analysis area."}
            </div>
          </div>
        )}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (canSend) {
              onSubmit();
            }
          }}
          className="pointer-events-auto overflow-hidden rounded-[1.6rem] border border-black/8 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(249,246,239,0.98))] shadow-[0_20px_56px_rgba(23,27,33,0.12)] backdrop-blur-xl transition-all duration-200 focus-within:-translate-y-0.5 focus-within:shadow-[0_26px_72px_rgba(23,27,33,0.16)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(26,30,34,0.96),rgba(15,18,20,0.98))]"
        >
          <div className="border-b border-black/6 px-4 pb-2.5 pt-3 dark:border-white/8 sm:px-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.28em] text-foreground/42">
                  Property Reasoning Workspace
                </div>
                <div className="mt-0.5 text-[13px] text-foreground/68">
                  Ask for valuation logic, market comparison, legal checks, or place-based recommendations.
                </div>
              </div>

              <button
                type="button"
                onClick={onToggleExpanded}
                className="inline-flex items-center gap-1 rounded-full border border-black/8 bg-black/[0.03] px-3 py-1.5 text-[11px] font-medium text-foreground/58 transition-colors hover:bg-black/[0.05] dark:border-white/10 dark:bg-white/[0.05] dark:hover:bg-white/[0.09]"
              >
                {isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
                {isExpanded ? "Collapse trace" : "Open trace"}
              </button>
            </div>
          </div>

          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 border-b border-black/6 px-4 py-2.5 dark:border-white/8 sm:px-5">
              {attachments.map((attachment) => (
                <AttachmentChip
                  key={attachment.id}
                  attachment={attachment}
                  onRemove={() => onRemoveAttachment?.(attachment.id)}
                />
              ))}
            </div>
          )}

          <div className="flex gap-3 px-4 py-3 sm:px-5">
            <div className="flex shrink-0 flex-col gap-2 pt-0.5">
              <ToolbarButton
                label="Pin"
                title="Pick location"
                onClick={onPickLocation}
                disabled={selectionMode !== "none"}
                active={selectionMode === "location"}
                icon={<MapPin className="h-4 w-4" />}
              />
              <ToolbarButton
                label="Area"
                title="Draw area"
                onClick={onPickBbox}
                disabled={selectionMode !== "none"}
                active={selectionMode === "bbox"}
                icon={<Square className="h-4 w-4" />}
              />
            </div>

            <div className="min-w-0 flex-1">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(event) => onInputChange(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    if (canSend) {
                      onSubmit();
                    }
                  }
                }}
                placeholder={
                  selectionMode !== "none"
                    ? "Finish the map selection to continue..."
                    : "Ask anything about this market, this property, or the area you are exploring..."
                }
                disabled={isBlocked}
                rows={1}
                className="min-h-11 max-h-[148px] w-full resize-none bg-transparent text-[14px] leading-6 text-foreground outline-none placeholder:text-foreground/38 disabled:cursor-not-allowed disabled:opacity-45"
              />

              <div className="mt-2.5 flex flex-wrap items-center justify-between gap-3 text-[11px] text-foreground/45">
                <div className="flex flex-wrap gap-2">
                  {showExamples
                    ? EXAMPLE_PROMPTS.map((prompt) => (
                        <button
                          key={prompt}
                          type="button"
                          onClick={() => onInputChange(prompt)}
                          className="rounded-full border border-black/8 bg-black/[0.03] px-2.5 py-1 text-left transition-colors hover:bg-black/[0.05] dark:border-white/10 dark:bg-white/[0.04] dark:hover:bg-white/[0.08]"
                        >
                          {prompt}
                        </button>
                      ))
                    : [
                        <span key="hint">Enter to send</span>,
                        <span key="divider">/</span>,
                        <span key="newline">Shift + Enter for new line</span>,
                      ]}
                </div>

                <div className="flex items-center gap-2">
                  <span>{attachments.length > 0 ? `${attachments.length} map refs attached` : "No map refs attached"}</span>
                  <button
                    type="submit"
                    disabled={!canSend}
                    className={cn(
                      "inline-flex h-9 w-9 items-center justify-center rounded-full transition-all",
                      canSend
                        ? "bg-foreground text-background shadow-[0_12px_24px_rgba(15,23,42,0.18)] hover:-translate-y-0.5"
                        : "bg-black/[0.08] text-foreground/28 dark:bg-white/[0.08]"
                    )}
                    title="Send message"
                  >
                    <ArrowUp className="h-4.5 w-4.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

function ToolbarButton({
  label,
  title,
  onClick,
  disabled,
  active,
  icon,
}: {
  label: string;
  title: string;
  onClick?: () => void;
  disabled: boolean;
  active: boolean;
  icon: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-2.5 py-2 text-xs font-medium transition-all",
        active
          ? "border-brand/28 bg-brand/12 text-brand"
          : "border-black/8 bg-black/[0.03] text-foreground/65 hover:bg-black/[0.05] dark:border-white/10 dark:bg-white/[0.04] dark:hover:bg-white/[0.08]",
        disabled && !active && "cursor-not-allowed opacity-40"
      )}
    >
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}

function AttachmentChip({
  attachment,
  onRemove,
}: {
  attachment: Attachment;
  onRemove: () => void;
}) {
  const tone =
    attachment.type === "property"
      ? "border-amber-600/18 bg-amber-500/10 text-amber-900 dark:text-amber-200"
      : attachment.type === "bbox"
        ? "border-sky-600/18 bg-sky-500/10 text-sky-900 dark:text-sky-200"
        : "border-emerald-600/18 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200";

  return (
    <div className={cn("inline-flex max-w-full items-center gap-2 rounded-full border px-2.5 py-1 text-[11px]", tone)}>
      <span className="truncate">{attachment.label}</span>
      <button
        type="button"
        onClick={onRemove}
        className="rounded-full p-0.5 transition-colors hover:bg-black/8 dark:hover:bg-white/10"
        title="Remove attachment"
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  );
}
