import { Card } from '../components/Card';
import { Button } from '../components/Button';
import { Badge } from '../components/Badge';
import { Input } from '../components/Input';
import { Select } from '../components/Select';
import { Slider } from '../components/Slider';
import { ScoreGauge } from '../components/ScoreGauge';
import { ProgressBar } from '../components/ProgressBar';
import { ThemeToggle } from '../components/ThemeToggle';
import { useTheme } from '../contexts/ThemeContext';
import { CheckCircle, AlertCircle, Info, XCircle, Sun, Moon } from 'lucide-react';

export function DesignSystem() {
  const { theme } = useTheme();

  const colorTokens = [
    { name: 'Background', light: '#FAFAFA', dark: '#0F172A', var: '--background' },
    { name: 'Foreground', light: '#0F172A', dark: '#F1F5F9', var: '--foreground' },
    { name: 'Primary', light: '#0EA5E9', dark: '#0EA5E9', var: '--primary' },
    { name: 'Primary Hover', light: '#0284C7', dark: '#0284C7', var: '--primary-hover' },
    { name: 'Secondary', light: '#F1F5F9', dark: '#1E293B', var: '--secondary' },
    { name: 'Card', light: '#FFFFFF', dark: 'rgba(30, 41, 59, 0.6)', var: '--card' },
    { name: 'Card Border', light: '#E2E8F0', dark: 'rgba(148, 163, 184, 0.1)', var: '--card-border' },
    { name: 'Muted', light: '#F1F5F9', dark: '#334155', var: '--muted' },
    { name: 'Muted Foreground', light: '#64748B', dark: '#94A3B8', var: '--muted-foreground' },
    { name: 'Accent', light: 'rgba(14, 165, 233, 0.08)', dark: 'rgba(14, 165, 233, 0.1)', var: '--accent' },
    { name: 'Border', light: '#E2E8F0', dark: 'rgba(148, 163, 184, 0.2)', var: '--border' },
  ];

  const statusColors = [
    { name: 'Success', color: '#10B981', var: '--success', icon: CheckCircle },
    { name: 'Warning', color: '#F59E0B', var: '--warning', icon: AlertCircle },
    { name: 'Destructive', color: '#EF4444', var: '--destructive', icon: XCircle },
    { name: 'Info', color: '#0EA5E9', var: '--primary', icon: Info },
  ];

  return (
    <div className="min-h-screen pb-20 md:pb-8">
      <div className="max-w-7xl mx-auto p-4 md:p-8">
        {/* Header */}
        <div className="mb-8 flex items-start justify-between">
          <div>
            <h1 className="text-4xl font-bold mb-2">Design System</h1>
            <p className="text-muted-foreground text-lg">
              Site Selection - Dark & Light Mode Tokens
            </p>
            <div className="mt-4 flex items-center gap-3">
              <Badge variant={theme === 'dark' ? 'primary' : 'secondary'}>
                <Moon className="h-3 w-3 mr-1" />
                Dark Mode
              </Badge>
              <Badge variant={theme === 'light' ? 'primary' : 'secondary'}>
                <Sun className="h-3 w-3 mr-1" />
                Light Mode
              </Badge>
              <span className="text-sm text-muted-foreground">
                Current: {theme === 'dark' ? 'Dark' : 'Light'}
              </span>
            </div>
          </div>
          <ThemeToggle />
        </div>

        {/* Color Tokens Section */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold mb-6">Color Tokens</h2>
          <Card className="p-8">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {colorTokens.map((token) => (
                <div key={token.var} className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">{token.name}</span>
                    <code className="text-xs bg-muted px-2 py-1 rounded">{token.var}</code>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <div
                        className="h-16 rounded-lg border border-border shadow-sm"
                        style={{ backgroundColor: token.light }}
                      />
                      <div className="flex items-center gap-1">
                        <Sun className="h-3 w-3 text-muted-foreground" />
                        <span className="text-xs font-mono text-muted-foreground">{token.light}</span>
                      </div>
                    </div>
                    <div className="space-y-1">
                      <div
                        className="h-16 rounded-lg border border-border shadow-sm"
                        style={{ backgroundColor: token.dark === 'rgba(30, 41, 59, 0.6)' ? '#1E293B' : token.dark }}
                      />
                      <div className="flex items-center gap-1">
                        <Moon className="h-3 w-3 text-muted-foreground" />
                        <span className="text-xs font-mono text-muted-foreground truncate">
                          {token.dark.length > 12 ? token.dark.substring(0, 12) + '...' : token.dark}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </section>

        {/* Status Colors */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold mb-6">Status Colors</h2>
          <Card className="p-8">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {statusColors.map((status) => {
                const Icon = status.icon;
                return (
                  <div key={status.var} className="space-y-3">
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4" style={{ color: status.color }} />
                      <span className="font-medium">{status.name}</span>
                    </div>
                    <div
                      className="h-20 rounded-lg border border-border flex items-center justify-center shadow-sm"
                      style={{ backgroundColor: status.color }}
                    >
                      <span className="text-white font-semibold">{status.color}</span>
                    </div>
                    <code className="text-xs bg-muted px-2 py-1 rounded block text-center">{status.var}</code>
                  </div>
                );
              })}
            </div>
          </Card>
        </section>

        {/* Buttons */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold mb-6">Buttons</h2>
          <Card className="p-8">
            <div className="space-y-6">
              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-3">Variants</h3>
                <div className="flex flex-wrap gap-3">
                  <Button variant="primary">Primary</Button>
                  <Button variant="secondary">Secondary</Button>
                  <Button variant="ghost">Ghost</Button>
                  <Button variant="destructive">Destructive</Button>
                </div>
              </div>
              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-3">Sizes</h3>
                <div className="flex flex-wrap items-center gap-3">
                  <Button size="sm">Small</Button>
                  <Button size="md">Medium</Button>
                  <Button size="lg">Large</Button>
                </div>
              </div>
            </div>
          </Card>
        </section>

        {/* Badges */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold mb-6">Badges</h2>
          <Card className="p-8">
            <div className="flex flex-wrap gap-3">
              <Badge variant="primary">Primary</Badge>
              <Badge variant="secondary">Secondary</Badge>
              <Badge variant="success">Success</Badge>
              <Badge variant="warning">Warning</Badge>
              <Badge variant="danger">Danger</Badge>
              <Badge variant="info">Info</Badge>
            </div>
          </Card>
        </section>

        {/* Cards */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold mb-6">Cards</h2>
          <div className="grid md:grid-cols-2 gap-6">
            <Card glass={true}>
              <h3 className="font-semibold mb-2">Glass Card</h3>
              <p className="text-muted-foreground text-sm">
                In dark mode, this uses glassmorphism with backdrop blur.
                In light mode, it uses a solid white background with shadow.
              </p>
            </Card>
            <Card glass={false}>
              <h3 className="font-semibold mb-2">Solid Card</h3>
              <p className="text-muted-foreground text-sm">
                This card always uses a solid background without glassmorphism.
              </p>
            </Card>
            <Card glass={true} hover={true}>
              <h3 className="font-semibold mb-2">Hover Card</h3>
              <p className="text-muted-foreground text-sm">
                Hover over this card to see the elevation effect.
              </p>
            </Card>
            <div className="glass-strong rounded-xl p-6">
              <h3 className="font-semibold mb-2">Glass Strong</h3>
              <p className="text-muted-foreground text-sm">
                Used for navigation bars and important UI elements.
              </p>
            </div>
          </div>
        </section>

        {/* Form Elements */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold mb-6">Form Elements</h2>
          <Card className="p-8">
            <div className="space-y-6 max-w-md">
              <div>
                <label className="block text-sm font-medium mb-2">Input Field</label>
                <Input placeholder="Enter your email..." />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Select Dropdown</label>
                <Select
                  options={[
                    { value: '1', label: 'Option 1' },
                    { value: '2', label: 'Option 2' },
                    { value: '3', label: 'Option 3' },
                  ]}
                  value="1"
                  onChange={() => {}}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Slider</label>
                <Slider min={0} max={100} value={50} onChange={() => {}} />
              </div>
            </div>
          </Card>
        </section>

        {/* Data Visualization */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold mb-6">Data Visualization</h2>
          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <h3 className="font-semibold mb-4">Score Gauge</h3>
              <div className="grid grid-cols-2 gap-4">
                <ScoreGauge score={85} label="Excellent" />
                <ScoreGauge score={65} label="Good" />
              </div>
            </Card>
            <Card>
              <h3 className="font-semibold mb-4">Progress Bar</h3>
              <div className="space-y-4">
                <ProgressBar progress={75} label="Loading..." />
                <ProgressBar progress={45} label="Processing..." color="warning" />
                <ProgressBar progress={100} label="Complete" color="success" />
              </div>
            </Card>
          </div>
        </section>

        {/* Typography */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold mb-6">Typography</h2>
          <Card className="p-8">
            <div className="space-y-4">
              <div>
                <h1>Heading 1 - Bold, 1.875rem</h1>
                <p className="text-xs text-muted-foreground">var(--text-3xl) / 700 weight</p>
              </div>
              <div>
                <h2>Heading 2 - Semibold, 1.5rem</h2>
                <p className="text-xs text-muted-foreground">var(--text-2xl) / 600 weight</p>
              </div>
              <div>
                <h3>Heading 3 - Semibold, 1.25rem</h3>
                <p className="text-xs text-muted-foreground">var(--text-xl) / 600 weight</p>
              </div>
              <div>
                <h4>Heading 4 - Medium, 1.125rem</h4>
                <p className="text-xs text-muted-foreground">var(--text-lg) / 500 weight</p>
              </div>
              <div>
                <p className="text-foreground">Body text - Regular, 1rem</p>
                <p className="text-xs text-muted-foreground">var(--text-base) / 400 weight</p>
              </div>
              <div>
                <p className="text-muted-foreground">Muted text - Regular, 1rem</p>
                <p className="text-xs text-muted-foreground">Uses var(--muted-foreground)</p>
              </div>
            </div>
          </Card>
        </section>

        {/* Theme Toggle Component */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold mb-6">Theme Toggle</h2>
          <Card className="p-8">
            <div className="flex items-center justify-between max-w-md">
              <div>
                <h3 className="font-semibold mb-1">Dark / Light Mode Toggle</h3>
                <p className="text-sm text-muted-foreground">
                  Click to switch between themes
                </p>
              </div>
              <ThemeToggle />
            </div>
          </Card>
        </section>

        {/* Design Philosophy */}
        <section>
          <h2 className="text-2xl font-semibold mb-6">Design Philosophy</h2>
          <Card className="p-8">
            <div className="grid md:grid-cols-2 gap-8">
              <div>
                <h3 className="font-semibold mb-3 flex items-center gap-2">
                  <Moon className="h-5 w-5 text-primary" />
                  Dark Mode
                </h3>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  <li>• Deep navy background (#0F172A) for reduced eye strain</li>
                  <li>• Glassmorphism with backdrop blur for depth</li>
                  <li>• Electric blue accent (#0EA5E9) for premium feel</li>
                  <li>• Semi-transparent overlays with blur effects</li>
                  <li>• Minimal shadows, focus on blur and transparency</li>
                </ul>
              </div>
              <div>
                <h3 className="font-semibold mb-3 flex items-center gap-2">
                  <Sun className="h-5 w-5 text-primary" />
                  Light Mode
                </h3>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  <li>• Clean white/light gray background (#FAFAFA)</li>
                  <li>• Solid white cards with soft shadows</li>
                  <li>• Same electric blue accent for brand consistency</li>
                  <li>• Elevation through shadow, not blur</li>
                  <li>• Strong text contrast for readability</li>
                </ul>
              </div>
            </div>
          </Card>
        </section>
      </div>
    </div>
  );
}
