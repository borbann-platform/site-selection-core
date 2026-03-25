/**
 * FloatingPanel - A draggable, collapsible, closable container for map overlays.
 * Provides a consistent wrapper for any floating UI on the map.
 */

import {
  useState,
  useRef,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";
import { DotsSix, Minus, Plus, X } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

interface FloatingPanelProps {
  /** Panel content */
  children: ReactNode;
  /** Title shown in the drag handle bar */
  title?: string;
  /** Icon shown next to the title */
  icon?: ReactNode;
  /** Initial CSS position (top, left, right, bottom) */
  defaultPosition?: {
    top?: number;
    left?: number;
    right?: number;
    bottom?: number;
  };
  /** If true, panel starts collapsed */
  defaultCollapsed?: boolean;
  /** If true, panel starts hidden */
  defaultHidden?: boolean;
  /** Called when the panel is closed */
  onClose?: () => void;
  /** Whether the close button is shown */
  closable?: boolean;
  /** Whether the collapse button is shown */
  collapsible?: boolean;
  /** Whether the panel is draggable */
  draggable?: boolean;
  /** Additional className for the outer wrapper */
  className?: string;
  /** Additional className for the content area */
  contentClassName?: string;
  /** Max height of the panel (CSS value). Needed for scroll to work. */
  maxHeight?: string;
  /** Z-index (default 40) */
  zIndex?: number;
}

export function FloatingPanel({
  children,
  title,
  icon,
  defaultPosition = { top: 16, left: 16 },
  defaultCollapsed = false,
  defaultHidden = false,
  onClose,
  closable = true,
  collapsible = true,
  draggable = true,
  className,
  contentClassName,
  maxHeight,
  zIndex = 40,
}: FloatingPanelProps) {
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);
  const [isHidden, setIsHidden] = useState(defaultHidden);
  const [position, setPosition] = useState<{ x: number; y: number } | null>(
    null,
  );
  const [isDragging, setIsDragging] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const dragOffset = useRef({ x: 0, y: 0 });

  // Convert defaultPosition to initial pixel position on first render
  useEffect(() => {
    if (position !== null || !panelRef.current) return;
    const rect = panelRef.current.getBoundingClientRect();
    setPosition({ x: rect.left, y: rect.top });
  }, [position]);

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (!draggable || !panelRef.current) return;
      e.preventDefault();
      e.stopPropagation();

      const rect = panelRef.current.getBoundingClientRect();
      dragOffset.current = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      };
      setIsDragging(true);
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    },
    [draggable],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!isDragging) return;
      e.preventDefault();

      const newX = e.clientX - dragOffset.current.x;
      const newY = e.clientY - dragOffset.current.y;

      // Clamp to viewport
      const maxX = window.innerWidth - 60;
      const maxY = window.innerHeight - 40;

      setPosition({
        x: Math.max(0, Math.min(newX, maxX)),
        y: Math.max(0, Math.min(newY, maxY)),
      });
    },
    [isDragging],
  );

  const handlePointerUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleClose = useCallback(() => {
    setIsHidden(true);
    onClose?.();
  }, [onClose]);

  if (isHidden) return null;

  // Determine positioning style
  const positionStyle: React.CSSProperties = {
    ...(position
      ? { position: "fixed" as const, left: position.x, top: position.y }
      : {
          position: "absolute" as const,
          ...(defaultPosition.top !== undefined && {
            top: defaultPosition.top,
          }),
          ...(defaultPosition.left !== undefined && {
            left: defaultPosition.left,
          }),
          ...(defaultPosition.right !== undefined && {
            right: defaultPosition.right,
          }),
          ...(defaultPosition.bottom !== undefined && {
            bottom: defaultPosition.bottom,
          }),
        }),
    zIndex,
    ...(maxHeight && { maxHeight }),
  };

  return (
    <div
      ref={panelRef}
      style={positionStyle}
      className={cn(
        "grid grid-rows-[auto_minmax(0,1fr)] overflow-y-scroll bg-card/95 backdrop-blur-xl border border-border rounded-2xl shadow-xl transition-shadow",
        isDragging && "shadow-2xl ring-1 ring-brand/20",
        className,
      )}
    >
      {/* Drag handle + controls */}
      <div
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        className={cn(
          "flex items-center justify-between gap-2 px-3 py-2 border-b border-border/50 rounded-t-2xl select-none shrink-0",
          draggable && "cursor-grab",
          isDragging && "cursor-grabbing",
        )}
      >
        <div className="flex items-center gap-2 min-w-0">
          {draggable && (
            <DotsSix className="h-3.5 w-3.5 text-muted-foreground/50 shrink-0" weight="bold" />
          )}
          {icon && <span className="shrink-0">{icon}</span>}
          {title && (
            <span className="text-xs font-medium text-foreground truncate">
              {title}
            </span>
          )}
        </div>

        <div className="flex items-center gap-0.5 shrink-0">
          {collapsible && (
            <button
              type="button"
              onClick={() => setIsCollapsed(!isCollapsed)}
              className="p-1 rounded-md hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
              title={isCollapsed ? "Expand" : "Collapse"}
              aria-label={isCollapsed ? "Expand panel" : "Collapse panel"}
            >
              {isCollapsed ? (
                <Plus className="h-3 w-3" />
              ) : (
                <Minus className="h-3 w-3" />
              )}
            </button>
          )}
          {closable && (
            <button
              type="button"
              onClick={handleClose}
              className="p-1 rounded-md hover:bg-destructive/10 transition-colors text-muted-foreground hover:text-destructive"
              title="Close"
              aria-label="Close panel"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      {!isCollapsed && (
        <div
          className={cn(
            "min-h-0 overflow-y-auto transition-all duration-200",
            contentClassName,
          )}
        >
          {children}
        </div>
      )}
    </div>
  );
}
