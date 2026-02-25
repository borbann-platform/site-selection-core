/**
 * MobileTabBar — Fixed bottom navigation for mobile devices.
 * Shows 5 primary nav items with electric-blue active indicator.
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
  { to: "/", icon: MapIcon, label: "Explorer", exact: true },
  { to: "/districts", icon: BarChart2, label: "Districts", exact: false },
  { to: "/valuation", icon: Sparkles, label: "Valuation", exact: false },
  { to: "/chat", icon: MessageSquare, label: "Chat", exact: false },
  { to: "/settings", icon: Settings, label: "Settings", exact: false },
] as const;

export function MobileTabBar() {
  const location = useLocation();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-border glass-strong md:hidden pb-[env(safe-area-inset-bottom)]">
      <div className="flex items-center justify-around h-16 px-2">
        {TAB_ITEMS.map((item) => {
          const active = item.exact
            ? location.pathname === item.to
            : location.pathname.startsWith(item.to);

          return (
            <Link
              key={item.to}
              to={item.to}
              {...(item.to === "/" ? { search: { district: undefined } } : {})}
              className={cn(
                "flex flex-col items-center justify-center gap-1 flex-1 min-h-[44px] min-w-[44px] py-2 transition-colors relative",
                active ? "text-primary" : "text-muted-foreground"
              )}
            >
              {active && (
                <div className="absolute -top-[1px] left-1/2 -translate-x-1/2 w-8 h-0.5 bg-primary rounded-full" />
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
