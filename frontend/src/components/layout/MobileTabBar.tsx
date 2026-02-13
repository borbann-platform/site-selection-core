/**
 * MobileTabBar - Bottom navigation bar for mobile devices.
 * Shows 5 primary nav items with active indicator.
 * Only visible on screens < 768px.
 */

import { Link, useLocation } from "@tanstack/react-router";
import {
  Map as MapIcon,
  BarChart2,
  Sparkles,
  MessageSquare,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

const TAB_ITEMS = [
  { to: "/", icon: MapIcon, label: "Explorer" },
  { to: "/districts", icon: BarChart2, label: "Districts" },
  { to: "/valuation", icon: Sparkles, label: "Valuation" },
  { to: "/chat", icon: MessageSquare, label: "Chat" },
  { to: "/settings", icon: Settings, label: "Settings" },
] as const;

export function MobileTabBar() {
  const location = useLocation();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/95 backdrop-blur-sm md:hidden safe-area-bottom">
      <div className="flex items-center justify-around h-16 px-2">
        {TAB_ITEMS.map((item) => {
          const isActive =
            item.to === "/"
              ? location.pathname === "/"
              : location.pathname.startsWith(item.to);

          return (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                "flex flex-col items-center justify-center gap-1 flex-1 py-2 transition-colors relative",
                isActive
                  ? "text-brand"
                  : "text-muted-foreground"
              )}
            >
              {isActive && (
                <div className="absolute -top-[1px] left-1/2 -translate-x-1/2 w-8 h-0.5 bg-brand rounded-full" />
              )}
              <item.icon className="size-5" />
              <span className="text-[10px] font-medium leading-none">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
