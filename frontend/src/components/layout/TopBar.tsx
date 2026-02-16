/**
 * TopBar - Top navigation bar visible on all screen sizes.
 * Shows breadcrumb/page title and sidebar trigger on mobile.
 */

import { useLocation } from "@tanstack/react-router";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";

const PAGE_TITLES: Record<string, string> = {
  "/": "Explorer",
  "/districts": "Districts",
  "/valuation": "Valuation",
  "/chat": "Chat",
  "/settings": "Settings",
};

function getPageTitle(pathname: string): string {
  // Exact match first
  if (PAGE_TITLES[pathname]) return PAGE_TITLES[pathname];

  // Prefix match
  if (pathname.startsWith("/property/")) return "Property Detail";
  if (pathname.startsWith("/site/")) return "Site Analysis";
  if (pathname.startsWith("/chat/")) return "Chat";

  return "Borbann";
}

export function TopBar() {
  const location = useLocation();
  const title = getPageTitle(location.pathname);

  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b border-border bg-background/95 backdrop-blur-sm px-4">
      <SidebarTrigger className="-ml-1 hidden md:flex" />
      <Separator orientation="vertical" className="mr-2 h-4 hidden md:block" />
      <h1 className="text-sm font-medium truncate">{title}</h1>
    </header>
  );
}
