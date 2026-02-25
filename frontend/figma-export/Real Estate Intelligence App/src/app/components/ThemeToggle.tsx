import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
import { motion } from 'motion/react';

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className="relative h-9 w-16 rounded-full bg-muted/30 border border-border transition-colors hover:bg-muted/50 overflow-hidden"
      aria-label="Toggle theme"
    >
      <motion.div
        className="absolute inset-0.5 w-7 h-7 rounded-full bg-primary flex items-center justify-center"
        initial={false}
        animate={{
          x: theme === 'dark' ? 0 : 28,
        }}
        transition={{
          type: 'spring',
          stiffness: 500,
          damping: 30,
        }}
      >
        {theme === 'dark' ? (
          <Moon className="h-4 w-4 text-primary-foreground" />
        ) : (
          <Sun className="h-4 w-4 text-primary-foreground" />
        )}
      </motion.div>
      
      {/* Background icons */}
      <div className="absolute inset-0 flex items-center justify-between px-2 pointer-events-none">
        <Moon className={`h-3.5 w-3.5 transition-opacity ${theme === 'dark' ? 'opacity-0' : 'opacity-40'}`} />
        <Sun className={`h-3.5 w-3.5 transition-opacity ${theme === 'light' ? 'opacity-0' : 'opacity-40'}`} />
      </div>
    </button>
  );
}
