import { Sun, Moon } from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const toggle = () => setTheme(isDark ? "light" : "dark");

  return (
    <button
      type="button"
      onClick={toggle}
      className="relative h-9 w-16 rounded-full bg-muted/30 border border-border hover:bg-muted/50 overflow-hidden transition-colors"
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {/* Sliding pill */}
      <div
        className="absolute inset-0.5 w-7 h-7 rounded-full bg-primary flex items-center justify-center transition-transform duration-300 ease-in-out"
        style={{ transform: isDark ? "translateX(0)" : "translateX(28px)" }}
      >
        {isDark ? (
          <Moon className="h-4 w-4 text-primary-foreground" />
        ) : (
          <Sun className="h-4 w-4 text-primary-foreground" />
        )}
      </div>

      {/* Background icons */}
      <div className="absolute inset-0 flex items-center justify-between px-2 pointer-events-none">
        <Moon
          className={`h-3.5 w-3.5 transition-opacity duration-200 ${isDark ? "opacity-0" : "opacity-40"}`}
        />
        <Sun
          className={`h-3.5 w-3.5 transition-opacity duration-200 ${!isDark ? "opacity-0" : "opacity-40"}`}
        />
      </div>
    </button>
  );
}
