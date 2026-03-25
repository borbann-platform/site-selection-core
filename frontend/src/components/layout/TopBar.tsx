/**
 * TopBar — Full horizontal navigation bar for all authenticated pages.
 * Brand name left · nav links center (desktop) · ThemeToggle + user avatar right.
 * Matches the Figma "Root.tsx" navbar design.
 */

import { Gear, SignOut, Sparkle } from "@phosphor-icons/react";
import {
  ChartBar,
  ChatCircleText,
  MapTrifold,
  SlidersHorizontal,
} from "@phosphor-icons/react/dist/ssr";
import { Link, useLocation } from "@tanstack/react-router";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { to: "/", icon: MapTrifold, label: "Explorer", exact: true },
  { to: "/districts", icon: ChartBar, label: "Districts", exact: false },
  { to: "/valuation", icon: Sparkle, label: "Valuation", exact: false },
  { to: "/chat", icon: ChatCircleText, label: "Chat", exact: false },
  { to: "/settings", icon: SlidersHorizontal, label: "Settings", exact: false },
] as const;

export function TopBar() {
  const location = useLocation();
  const { user, logout } = useAuth();

  const userInitials = user
    ? `${user.first_name?.[0] ?? ""}${user.last_name?.[0] ?? ""}`.toUpperCase() ||
      "U"
    : "U";

  return (
    <header className="glass-strong border-b border-border sticky top-0 z-40">
      <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand */}
          <Link
            to="/"
            search={{ district: undefined }}
            className="flex items-center gap-2 shrink-0"
          >
            <span className="hidden text-xl font-semibold tracking-[-0.02em] text-foreground sm:block [font-family:var(--font-serif)]">
              Borban
            </span>
          </Link>

          {/* Desktop nav links */}
          <nav className="hidden md:flex items-center gap-1">
            {NAV_LINKS.map((link) => {
              const isActive = link.exact
                ? location.pathname === link.to
                : location.pathname.startsWith(link.to);

              return (
                <Link
                  key={link.to}
                  to={link.to}
                  {...(link.to === "/"
                    ? { search: { district: undefined } }
                    : {})}
                  className={cn(
                    "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:text-foreground hover:bg-accent/50",
                  )}
                >
                  <link.icon className="h-4 w-4" />
                  {link.label}
                </Link>
              );
            })}
          </nav>

          {/* Right controls */}
          <div className="flex items-center gap-3">
            <ThemeToggle />

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button type="button" className="focus:outline-none" aria-label="Open user menu">
                  <Avatar className="h-9 w-9 cursor-pointer ring-2 ring-transparent transition-all hover:ring-primary/30">
                    <AvatarFallback className="border border-border/70 bg-card text-sm font-semibold text-foreground">
                      {userInitials}
                    </AvatarFallback>
                  </Avatar>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                {user && (
                  <>
                    <div className="px-3 py-2">
                      <p className="text-sm font-medium truncate">
                        {user.first_name} {user.last_name}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">
                        {user.email}
                      </p>
                    </div>
                    <DropdownMenuSeparator />
                  </>
                )}
                <DropdownMenuItem asChild>
                  <Link to="/settings" className="cursor-pointer">
                    <Gear className="mr-2 h-4 w-4" weight="duotone" />
                    Settings
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={logout}
                  className="text-destructive focus:text-destructive cursor-pointer"
                >
                  <SignOut className="mr-2 h-4 w-4" weight="duotone" />
                  Sign Out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>
    </header>
  );
}
