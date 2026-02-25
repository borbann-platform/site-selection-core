/**
 * AppShell — Main layout wrapper for all authenticated routes.
 * Horizontal TopBar (sticky) + main content + MobileTabBar (mobile).
 * Matches the Figma design system: no sidebar, horizontal nav.
 */

import type { ReactNode } from "react";
import { MobileTabBar } from "./MobileTabBar";
import { TopBar } from "./TopBar";

interface AppShellProps {
  children: ReactNode;
  /** When true, hides the TopBar (used for full-screen pages like the map) */
  hideTopBar?: boolean;
}

export function AppShell({ children, hideTopBar = false }: AppShellProps) {
  return (
    <div className="min-h-screen flex flex-col bg-background">
      {!hideTopBar && <TopBar />}

      {/* Main content — pb-16 reserves space for the MobileTabBar on mobile */}
      <main className="flex-1 relative pb-16 md:pb-0">
        {children}
      </main>

      <MobileTabBar />
    </div>
  );
}
