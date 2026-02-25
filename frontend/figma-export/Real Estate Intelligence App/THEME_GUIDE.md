# Site Selection - Theme System Guide

## Quick Start

### Switching Themes
1. **Click the theme toggle** in the top-right corner of the navigation bar
2. The sun ☀️ icon indicates Light Mode
3. The moon 🌙 icon indicates Dark Mode
4. Your preference is automatically saved

### Viewing the Design System
Navigate to `/design-system` in your browser to see:
- All color tokens for both themes
- Complete component library
- Interactive examples
- Design philosophy

## For Developers

### Using the Theme Hook

```tsx
import { useTheme } from './contexts/ThemeContext';

function MyComponent() {
  const { theme, toggleTheme, setTheme } = useTheme();
  
  return (
    <div>
      <p>Current theme: {theme}</p>
      <button onClick={toggleTheme}>Toggle</button>
      <button onClick={() => setTheme('dark')}>Dark</button>
      <button onClick={() => setTheme('light')}>Light</button>
    </div>
  );
}
```

### Using Theme Colors

All components automatically adapt to the theme using CSS variables:

```tsx
// ✅ Correct - Uses theme variables
<div className="bg-background text-foreground">
  <Card className="border border-border">
    Content
  </Card>
</div>

// ❌ Avoid - Hard-coded colors
<div className="bg-slate-900 text-white">
  Hard-coded colors don't adapt
</div>
```

### Available CSS Variables

#### Backgrounds
- `bg-background` - Main page background
- `bg-card` - Card backgrounds
- `bg-secondary` - Secondary backgrounds
- `bg-muted` - Muted/disabled backgrounds

#### Text
- `text-foreground` - Primary text
- `text-muted-foreground` - Secondary text
- `text-primary` - Brand color text
- `text-accent-foreground` - Accent text

#### Borders
- `border-border` - Standard borders
- `border-card-border` - Card borders

#### Interactive
- `bg-accent` - Hover/active states
- `bg-primary` - Primary actions
- `hover:bg-primary-hover` - Primary hover

### Glassmorphism Classes

These automatically adapt between themes:

```tsx
// Dark Mode: Glassmorphism with blur
// Light Mode: Solid white with shadow
<div className="glass rounded-xl p-6">
  Content
</div>

// Stronger variant for navigation
<div className="glass-strong rounded-xl p-6">
  Content
</div>
```

### Creating Theme-Aware Components

```tsx
import { useTheme } from '../contexts/ThemeContext';

export function MyComponent() {
  const { theme } = useTheme();
  
  return (
    <div className="p-4 bg-card border border-border">
      {/* This adapts automatically */}
      <p className="text-foreground">
        Content looks great in {theme} mode!
      </p>
      
      {/* Optional: Theme-specific logic */}
      {theme === 'dark' ? (
        <StarBackground />
      ) : (
        <CloudBackground />
      )}
    </div>
  );
}
```

## Color Token Reference

### Dark Mode
```css
--background: #0F172A
--foreground: #F1F5F9
--card: rgba(30, 41, 59, 0.6)
--border: rgba(148, 163, 184, 0.2)
--primary: #0EA5E9
```

### Light Mode
```css
--background: #FAFAFA
--foreground: #0F172A
--card: #FFFFFF
--border: #E2E8F0
--primary: #0EA5E9
```

## Best Practices

### ✅ Do
- Use semantic color variables (`bg-background`, `text-foreground`)
- Test components in both themes
- Use the `.glass` and `.glass-strong` utilities
- Let CSS variables handle theme switching
- Use the design system page for reference

### ❌ Don't
- Hard-code color values in Tailwind classes
- Use `dark:` prefix (we use class-based theming)
- Assume the theme (always use variables)
- Forget to test in both modes
- Override theme colors unnecessarily

## Component Examples

### Button
```tsx
<Button variant="primary">Primary Action</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="ghost">Ghost</Button>
```

### Card
```tsx
<Card glass={true}>Glassmorphism Card</Card>
<Card glass={false}>Solid Card</Card>
<Card hover={true}>Hover Effect</Card>
```

### Badge
```tsx
<Badge variant="success">Success</Badge>
<Badge variant="warning">Warning</Badge>
<Badge variant="primary">Primary</Badge>
```

## Special Cases

### Maps
Maps maintain a dark background in both themes for better visibility:
```tsx
<MockMap properties={properties} />
// Always dark background regardless of theme
```

### Charts
Charts use theme-aware colors but maintain contrast:
```tsx
<LineChart data={data}>
  <Line stroke="var(--chart-1)" />
</LineChart>
```

## Troubleshooting

### Theme not persisting?
- Check localStorage for `site-selection-theme`
- Ensure ThemeProvider wraps your app
- Clear browser cache if needed

### Colors not changing?
- Verify you're using CSS variables, not hard-coded colors
- Check that the component uses theme-aware classes
- Inspect the element to see computed styles

### Glassmorphism not showing?
- Only works in dark mode (by design)
- Ensure `.glass` or `.glass-strong` class is applied
- Check backdrop-filter browser support

## More Information

- **Full Documentation**: See `/DESIGN_SYSTEM.md`
- **Implementation Details**: See `/THEME_IMPLEMENTATION.md`
- **Live Examples**: Navigate to `/design-system` in the app
