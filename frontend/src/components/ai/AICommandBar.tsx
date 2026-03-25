import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import {
  ArrowUp,
  ChevronDown,
  ChevronUp,
  Square,
  X,
} from "lucide-react";
import { BoundingBox, MapPinLine, NavigationArrow } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

export type SelectionMode = "none" | "location" | "bbox";

export type AttachmentType = "location" | "bbox" | "property";

export interface Attachment {
  id: string;
  type: AttachmentType;
  data: Record<string, unknown>;
  label: string;
}

function adjustTextareaHeight(textarea: HTMLTextAreaElement, value: string) {
  textarea.style.height = "0px";
  const nextHeight = value.length === 0 ? 44 : Math.min(textarea.scrollHeight, 132);
  textarea.style.height = `${nextHeight}px`;
}

interface AICommandBarProps {
  input: string;
  onInputChange: (value: string) => void;
  onSubmit: () => void;
  attachments: Attachment[];
  recentSelections?: Attachment[];
  selectionMode: SelectionMode;
  isExpanded: boolean;
  isRunning: boolean;
  onToggleExpanded: () => void;
  onPickLocation?: () => void;
  onPickBbox?: () => void;
  onRemoveAttachment?: (id: string) => void;
  onReuseRecentSelection?: (attachmentId: string) => void;
  onStopStreaming?: () => void;
}

export function AICommandBar({
  input,
  onInputChange,
  onSubmit,
  attachments,
  recentSelections = [],
  selectionMode,
  isExpanded,
  isRunning,
  onToggleExpanded,
  onPickLocation,
  onPickBbox,
  onRemoveAttachment,
  onReuseRecentSelection,
  onStopStreaming,
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

    adjustTextareaHeight(textarea, input);
  }, [input]);

  const isBlocked = isRunning || selectionMode !== "none";
  const canSend = input.trim().length > 0 && !isBlocked;

  return (
    <div className="pointer-events-none fixed bottom-0 left-1/2 z-50 w-[min(calc(100vw-1.5rem),56rem)] -translate-x-1/2 pb-3 sm:w-[min(calc(100vw-2rem),56rem)] sm:pb-4 lg:w-[min(calc(100vw-34rem),56rem)] xl:w-[min(calc(100vw-38rem),58rem)]">
      <div className="w-full">
        {selectionMode !== "none" && (
          <div className="pointer-events-auto mb-3 animate-slide-up rounded-full border border-border/80 bg-card/95 px-4 py-2 text-xs text-foreground shadow-xl backdrop-blur-xl">
            <div className="flex items-center gap-2 font-medium">
              <NavigationArrow className="h-3.5 w-3.5 text-brand" weight="duotone" />
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
          className="pointer-events-auto overflow-hidden rounded-[30px] border border-border/90 bg-card/96 shadow-xl backdrop-blur-xl transition-all duration-200 focus-within:border-brand/20 focus-within:shadow-2xl"
        >
          <div className="border-b border-border/50 px-4 py-2.5 sm:px-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Workspace
                </div>
              </div>

              <button
                type="button"
                onClick={onToggleExpanded}
                className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-muted/40 px-3 py-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-muted"
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

          <div className="px-4 py-3 sm:px-5">
            <div className="space-y-3">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(event) => {
                  onInputChange(event.target.value);
                  adjustTextareaHeight(event.currentTarget, event.currentTarget.value);
                }}
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
                    : "Ask about this market, this property, or the area you are exploring..."
                }
                disabled={isBlocked}
                rows={1}
                className="min-h-[72px] max-h-[144px] w-full resize-none rounded-[24px] border border-border/70 bg-background/50 px-4 py-3.5 text-[15px] leading-7 text-foreground outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-45"
              />

              {recentSelections.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 px-1">
                  <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                    Recent
                  </span>
                  {recentSelections.slice(0, 4).map((attachment) => (
                    <button
                      key={attachment.id}
                      type="button"
                      onClick={() => onReuseRecentSelection?.(attachment.id)}
                      className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-muted/25 px-3 py-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    >
                      {attachment.type === "bbox" ? (
                        <BoundingBox className="h-3.5 w-3.5" weight="duotone" />
                      ) : (
                        <MapPinLine className="h-3.5 w-3.5" weight="duotone" />
                      )}
                      <span className="max-w-48 truncate">{attachment.label}</span>
                    </button>
                  ))}
                </div>
              )}

              <div className="flex flex-wrap items-center justify-between gap-3 px-1">
                <div className="flex flex-wrap items-center gap-2">
                  <ToolbarButton
                    label="Pin"
                    title="Pick location"
                    onClick={onPickLocation}
                    disabled={selectionMode !== "none"}
                    active={selectionMode === "location"}
                    icon={<MapPinLine className="h-4 w-4" weight="duotone" />}
                  />
                  <ToolbarButton
                    label="Area"
                    title="Draw area"
                    onClick={onPickBbox}
                    disabled={selectionMode !== "none"}
                    active={selectionMode === "bbox"}
                    icon={<BoundingBox className="h-4 w-4" weight="duotone" />}
                  />
                </div>

                <div className="flex flex-1 flex-wrap items-center justify-end gap-3 text-[11px] text-muted-foreground sm:justify-between">
                  <div className="flex flex-wrap gap-2 md:gap-3">
                    <span>
                      {attachments.length > 0
                        ? `${attachments.length} map refs attached`
                        : "Enter to send"}
                    </span>
                    <span className="opacity-50">/</span>
                    <span>Shift + Enter for new line</span>
                  </div>

                  {isRunning ? (
                    <button
                      type="button"
                      onClick={onStopStreaming}
                      className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-destructive text-destructive-foreground shadow-lg shadow-destructive/25 transition-all hover:bg-destructive/90"
                      title="Stop generating"
                    >
                      <Square className="h-4.5 w-4.5" />
                    </button>
                  ) : (
                    <button
                      type="submit"
                      disabled={!canSend}
                      className={cn(
                        "inline-flex h-10 w-10 items-center justify-center rounded-full transition-all",
                        canSend
                          ? "bg-brand text-brand-foreground shadow-lg shadow-brand/25 hover:bg-brand/90"
                          : "bg-muted text-muted-foreground",
                      )}
                      title="Send message"
                    >
                      <ArrowUp className="h-4.5 w-4.5" />
                    </button>
                  )}
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
  icon: ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-medium transition-all",
        active
          ? "border-brand/28 bg-brand/10 text-brand"
          : "border-border/70 bg-muted/35 text-muted-foreground hover:bg-muted hover:text-foreground",
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
        : "border-brand/18 bg-brand/10 text-brand";

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
