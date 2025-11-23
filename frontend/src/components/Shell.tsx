import React, { useState } from "react";
import { Link, useLocation } from "@tanstack/react-router";
import {
  Map,
  BarChart2,
  Layers,
  Settings,
  ChevronLeft,
  ChevronRight,
  Menu,
} from "lucide-react";
import { cn } from "../lib/utils";

interface ShellProps {
  children: React.ReactNode;
  panelContent?: React.ReactNode;
}

export function Shell({ children, panelContent }: ShellProps) {
  const [isPanelOpen, setIsPanelOpen] = useState(true);

  return (
    <div className="flex h-screen w-screen bg-black overflow-hidden">
      {/* Navigation Rail */}
      <nav className="w-16 flex flex-col items-center py-6 bg-black border-r border-white/10 z-50">
        <div className="mb-8">
          <div className="w-8 h-8 bg-emerald-500 rounded-lg flex items-center justify-center font-bold text-black">
            K
          </div>
        </div>

        <div className="flex flex-col gap-6 w-full">
          <NavItem to="/" icon={Map} label="Map" />
          <NavItem to="/compare" icon={BarChart2} label="Compare" />
          <NavItem to="/settings" icon={Settings} label="Settings" />
        </div>
      </nav>

      {/* Main Content Area (Map) */}
      <div className="flex-1 relative">
        {children}

        {/* Collapsible Control Panel Overlay */}
        {panelContent && (
          <div
            className={cn(
              "absolute top-4 left-4 bottom-4 w-80 bg-black/80 backdrop-blur-md border border-white/10 rounded-2xl transition-all duration-300 ease-in-out z-40 flex flex-col overflow-hidden",
              !isPanelOpen && "w-0 opacity-0 pointer-events-none border-0"
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
            onClick={() => setIsPanelOpen(!isPanelOpen)}
            className={cn(
              "absolute top-8 z-50 p-2 bg-black/80 border border-white/10 rounded-r-lg text-white/70 hover:text-white transition-all duration-300",
              isPanelOpen
                ? "left-80 rounded-l-none border-l-0"
                : "left-4 rounded-lg"
            )}
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
}: {
  to: string;
  icon: any;
  label: string;
}) {
  const location = useLocation();
  const isActive = location.pathname === to;

  return (
    <Link
      to={to}
      className={cn(
        "w-full flex flex-col items-center gap-1 py-2 transition-colors relative",
        isActive ? "text-emerald-400" : "text-white/40 hover:text-white/70"
      )}
    >
      <Icon size={20} />
      <span className="text-[10px] font-medium">{label}</span>
      {isActive && (
        <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-emerald-400" />
      )}
    </Link>
  );
}
