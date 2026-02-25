import { Outlet, useLocation, useNavigate } from 'react-router';
import { Building2, Map, MessageSquare, Calculator, LayoutGrid, Settings } from 'lucide-react';
import { MobileTabBar } from '../components/MobileTabBar';
import { ThemeToggle } from '../components/ThemeToggle';

export function Root() {
  const location = useLocation();
  const navigate = useNavigate();
  
  const navLinks = [
    { path: '/', icon: Map, label: 'Map' },
    { path: '/chat', icon: MessageSquare, label: 'Chat' },
    { path: '/valuation', icon: Calculator, label: 'Valuation' },
    { path: '/districts', icon: LayoutGrid, label: 'Districts' },
    { path: '/settings', icon: Settings, label: 'Settings' },
  ];
  
  return (
    <div className="min-h-screen flex flex-col bg-background">
      {/* Top Navbar - Desktop */}
      <nav className="glass-strong border-b border-border sticky top-0 z-40">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center gap-2 cursor-pointer" onClick={() => navigate('/')}>
              <div className="h-10 w-10 rounded-lg bg-primary flex items-center justify-center">
                <Building2 className="h-6 w-6 text-primary-foreground" />
              </div>
              <span className="text-xl font-bold bg-gradient-to-r from-primary to-blue-400 bg-clip-text text-transparent">
                Site Selection
              </span>
            </div>
            
            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center gap-1">
              {navLinks.map((link) => {
                const Icon = link.icon;
                const isActive = location.pathname === link.path;
                
                return (
                  <button
                    key={link.path}
                    onClick={() => navigate(link.path)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all ${
                      isActive
                        ? 'bg-accent text-accent-foreground'
                        : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    <span className="font-medium">{link.label}</span>
                  </button>
                );
              })}
            </div>
            
            {/* User Avatar */}
            <div className="flex items-center gap-3">
              <ThemeToggle />
              <div className="h-9 w-9 rounded-full bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center cursor-pointer">
                <span className="text-sm font-semibold text-white">JD</span>
              </div>
            </div>
          </div>
        </div>
      </nav>
      
      {/* Main Content */}
      <main className="flex-1 relative">
        <Outlet />
      </main>
      
      {/* Mobile Tab Bar */}
      <MobileTabBar />
    </div>
  );
}