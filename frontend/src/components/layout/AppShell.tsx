/**
 * AppShell - Main application layout wrapping all authenticated routes.
 * Combines AppSidebar (desktop) + MobileTabBar (mobile) + TopBar + main content.
 * Uses shadcn SidebarProvider for state management.
 */

import type { ReactNode } from "react";
import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar";
import { AppSidebar } from "./AppSidebar";
import { MobileTabBar } from "./MobileTabBar";
import { TopBar } from "./TopBar";

interface AppShellProps {
  children: ReactNode;
  /** If true, hides the TopBar (useful for full-screen map pages) */
  hideTopBar?: boolean;
}

export function AppShell({ children, hideTopBar = false }: AppShellProps) {
  return (
    <SidebarProvider className="bg-background">
      {/* Desktop sidebar - hidden on mobile via shadcn sidebar internals */}
      <AppSidebar />

      <SidebarInset>
        {/* Top bar with breadcrumb */}
        {!hideTopBar && <TopBar />}

        {/* Main content area - pb-16 accounts for MobileTabBar height on mobile */}
        <main className="flex-1 overflow-auto pb-16 md:pb-0 bg-background bg-noise">
          {children}
        </main>
      </SidebarInset>

      {/* Mobile bottom tab bar */}
      <MobileTabBar />
    </SidebarProvider>
  );
}
