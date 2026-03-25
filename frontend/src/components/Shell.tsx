import { useState } from "react";
import { Link, useLocation } from "@tanstack/react-router";
import {
  Map as MapIcon,
  BarChart2,
  Settings,
  ChevronLeft,
  Menu,
  Sparkles,
  Sun,
  Moon,
  Monitor,
  MessageSquare,
} from "lucide-react";
import { cn } from "../lib/utils";
import { useTheme } from "../contexts/ThemeContext";

interface ShellProps {
  children: React.ReactNode;
  panelContent?: React.ReactNode;
}

export function Shell({ children, panelContent }: ShellProps) {
  const [isPanelOpen, setIsPanelOpen] = useState(true);
  const { theme, toggleTheme } = useTheme();

  const ThemeIcon = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;
  const themeLabel = theme === "light" ? "Light" : theme === "dark" ? "Dark" : "System";

  return (
    <div className="flex h-screen w-screen bg-background overflow-hidden">
      {/* Navigation Rail */}
      <nav className="w-16 flex flex-col items-center py-6 bg-card border-r border-border z-50">
        <div className="mb-8">
          <div className="w-8 h-8 bg-emerald-500 rounded-lg flex items-center justify-center font-bold text-black shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/30 transition-shadow duration-200">
            K
          </div>
        </div>

        <div className="flex flex-col gap-6 w-full flex-1">
          <NavItem to="/" icon={MapIcon} label="Map" />
          <NavItem to="/districts" icon={BarChart2} label="Districts" />
          <NavItem to="/valuation" icon={Sparkles} label="Valuation" highlight />
          <NavItem to="/chat" icon={MessageSquare} label="Chat" />
          <NavItem to="/settings" icon={Settings} label="Settings" />
        </div>

        {/* Theme Toggle at bottom */}
        <div className="mt-auto pt-6 border-t border-border w-full">
          <button
            type="button"
            onClick={toggleTheme}
            className="w-full flex flex-col items-center gap-1 py-2 mx-auto rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted transition-all duration-200"
            title={`Theme: ${themeLabel}`}
          >
            <ThemeIcon size={20} />
            <span className="text-[10px] font-medium">{themeLabel}</span>
          </button>
        </div>
      </nav>

      {/* Main Content Area */}
      <div className="flex-1 relative">
        {children}

        {/* Collapsible Control Panel Overlay */}
        {panelContent && (
          <div
            className={cn(
              "absolute top-4 left-4 bottom-4 w-80 bg-card/85 backdrop-blur-xl border border-border rounded-2xl z-40 flex flex-col overflow-hidden transition-all duration-300 ease-in-out",
              !isPanelOpen && "-translate-x-[calc(100%+2rem)] opacity-0 pointer-events-none"
            )}
          >
            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
              {panelContent}
            </div>
          </div>
        )}

        {/* Panel Toggle Button */}
        {panelContent && (
          <button
            type="button"
            onClick={() => setIsPanelOpen(!isPanelOpen)}
            className={cn(
              "absolute top-8 z-50 p-2 bg-card/80 border border-border rounded-r-lg text-muted-foreground hover:text-foreground",
              isPanelOpen
                ? "left-80 rounded-l-none border-l-0"
                : "left-4 rounded-lg"
            )}
            aria-label={isPanelOpen ? "Close control panel" : "Open control panel"}
          >
            {isPanelOpen ? <ChevronLeft size={16} /> : <Menu size={16} />}
          </button>
        )}
      </div>
    </div>
  );
}

function NavItem({
  to,
  icon: Icon,
  label,
  highlight,
}: {
  to: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  highlight?: boolean;
}) {
  const location = useLocation();
  const isActive = location.pathname === to;

  return (
    <Link
      to={to}
      className={cn(
        "w-full flex flex-col items-center gap-1 py-2 transition-all duration-200 relative group",
        isActive
          ? "text-emerald-400"
          : highlight
            ? "text-emerald-400/70 hover:text-emerald-400"
            : "text-muted-foreground hover:text-foreground"
      )}
    >
      <Icon size={20} className="transition-transform duration-200 group-hover:scale-110" />
      <span className="text-[10px] font-medium">{label}</span>
      {isActive && (
        <>
          <div className="absolute left-0 top-1/4 bottom-1/4 w-0.5 bg-emerald-400 rounded-full" />
          <div className="absolute inset-x-1.5 inset-y-0.5 bg-emerald-500/10 rounded-xl -z-10" />
        </>
      )}
    </Link>
  );
}
