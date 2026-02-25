import { useLocation, useNavigate } from 'react-router';
import { Map, MessageSquare, Calculator, LayoutGrid, User } from 'lucide-react';
import { motion } from 'motion/react';

export function MobileTabBar() {
  const location = useLocation();
  const navigate = useNavigate();
  
  const tabs = [
    { path: '/', icon: Map, label: 'Map' },
    { path: '/chat', icon: MessageSquare, label: 'Chat' },
    { path: '/valuation', icon: Calculator, label: 'Valuation' },
    { path: '/districts', icon: LayoutGrid, label: 'Districts' },
    { path: '/settings', icon: User, label: 'Profile' },
  ];
  
  return (
    <div className="md:hidden fixed bottom-0 left-0 right-0 glass-strong border-t border-border z-50">
      <div className="flex items-center justify-around px-2 py-2 safe-area-inset-bottom">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = location.pathname === tab.path;
          
          return (
            <button
              key={tab.path}
              onClick={() => navigate(tab.path)}
              className="flex flex-col items-center gap-1 px-4 py-2 relative"
            >
              {isActive && (
                <motion.div
                  layoutId="mobile-tab-indicator"
                  className="absolute inset-0 bg-accent rounded-lg"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
              <Icon
                className={`h-5 w-5 relative z-10 transition-colors ${
                  isActive ? 'text-accent-foreground' : 'text-muted-foreground'
                }`}
              />
              <span
                className={`text-xs relative z-10 transition-colors ${
                  isActive ? 'text-accent-foreground font-medium' : 'text-muted-foreground'
                }`}
              >
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
