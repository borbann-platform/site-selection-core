# Site Selection - Design System Documentation

## Overview
Premium glassmorphism design system for Bangkok real estate intelligence platform with **Dark and Light Mode** support.

## Theme System

### Theme Toggle
The application supports both Dark and Light modes with a smooth toggle transition.
- **Default**: System preference (fallback to Dark mode)
- **Persistence**: Theme choice saved in localStorage
- **Toggle Component**: Located in navbar (top-right) and login/register pages
- **Access Design System Page**: Navigate to `/design-system` to view all color tokens and components

### Dark Mode Philosophy
- Deep navy background (#0F172A) for reduced eye strain
- Glassmorphism with backdrop blur for depth and premium feel
- Electric blue accent (#0EA5E9) for brand identity
- Semi-transparent overlays with blur effects
- Minimal shadows, focus on blur and transparency

### Light Mode Philosophy
- Clean white/light gray background (#FAFAFA) for clarity
- Solid white cards with soft elevation shadows
- Same electric blue accent for brand consistency
- Elevation through shadow layers, not blur
- Strong text contrast (#0F172A) for readability
- Warm neutral tones for surfaces

## Color Palette

### Dark Mode Colors
- **Background**: `#0F172A` (Deep Navy/Charcoal)
- **Foreground**: `#F1F5F9` (Light Slate)
- **Primary**: `#0EA5E9` (Electric Blue)
- **Primary Hover**: `#0284C7` (Darker Blue)
- **Card**: `rgba(30, 41, 59, 0.6)` (Semi-transparent with glassmorphism)
- **Border**: `rgba(148, 163, 184, 0.2)` (Subtle)
- **Muted**: `#334155` (Darker Slate)
- **Muted Foreground**: `#94A3B8` (Medium Slate)

### Light Mode Colors
- **Background**: `#FAFAFA` (Off White)
- **Foreground**: `#0F172A` (Near Black)
- **Primary**: `#0EA5E9` (Electric Blue - same as dark)
- **Primary Hover**: `#0284C7` (Darker Blue - same as dark)
- **Card**: `#FFFFFF` (Pure White with shadow)
- **Border**: `#E2E8F0` (Light Gray)
- **Muted**: `#F1F5F9` (Very Light Gray)
- **Muted Foreground**: `#64748B` (Medium Gray)

### Functional Colors (Same in both modes)
- **Success**: `#10B981` (Green)
- **Warning**: `#F59E0B` (Orange)
- **Destructive**: `#EF4444` (Red)
- **Info**: `#0EA5E9` (Blue)

## Typography Scale
- **text-xs**: 0.75rem
- **text-sm**: 0.875rem
- **text-base**: 1rem
- **text-lg**: 1.125rem
- **text-xl**: 1.25rem
- **text-2xl**: 1.5rem
- **text-3xl**: 1.875rem
- **text-4xl**: 2.25rem

## Font Weights
- **normal**: 400
- **medium**: 500
- **semibold**: 600
- **bold**: 700

## Spacing Scale
- **spacing-1**: 0.25rem (4px)
- **spacing-2**: 0.5rem (8px)
- **spacing-3**: 0.75rem (12px)
- **spacing-4**: 1rem (16px)
- **spacing-5**: 1.25rem (20px)
- **spacing-6**: 1.5rem (24px)
- **spacing-8**: 2rem (32px)
- **spacing-10**: 2.5rem (40px)
- **spacing-12**: 3rem (48px)
- **spacing-16**: 4rem (64px)

## Border Radius
- **radius-sm**: calc(0.75rem - 4px)
- **radius-md**: calc(0.75rem - 2px)
- **radius-lg**: 0.75rem
- **radius-xl**: calc(0.75rem + 4px)

## Component Library

### Buttons
- **Primary**: Blue background, white text
- **Secondary**: Dark background, light text
- **Ghost**: Transparent, hover effect
- **Destructive**: Red background, white text
- **Sizes**: sm, md, lg

### Badges
- **Success**: Green theme
- **Warning**: Orange theme
- **Danger**: Red theme
- **Info**: Blue theme
- **Neutral**: Gray theme

### Cards
- **Glass**: Semi-transparent with backdrop-filter blur
- **Glass Strong**: More opaque variant
- **Hover**: Optional lift effect

### Inputs
- Label support
- Error state styling
- Focus ring effect
- Glassmorphism background

### Select
- Dropdown with custom styling
- ChevronDown icon
- Label support

### Slider
- Dual-handle range support
- Value formatting
- Custom labels

### Score Gauge
- Circular progress indicator
- Dynamic color based on score
- Multiple sizes (sm, md, lg)
- Animated on mount

### Progress Bar
- Linear progress indicator
- Color variants
- Smooth animations

### Spinner
- Loading indicator
- Multiple sizes
- Primary color theme

### Modal/Dialog
- Backdrop blur
- Centered positioning
- Close button
- Title and description support

### Tooltip
- Radix UI based
- Glassmorphism styling
- Configurable positioning

## Glassmorphism Classes

### .glass (Theme-aware)
**Dark Mode:**
```css
background: rgba(30, 41, 59, 0.6);
backdrop-filter: blur(12px);
border: 1px solid rgba(148, 163, 184, 0.1);
```

**Light Mode:**
```css
background: #FFFFFF;
border: 1px solid #E2E8F0;
box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
```

### .glass-strong (Theme-aware)
**Dark Mode:**
```css
background: rgba(30, 41, 59, 0.8);
backdrop-filter: blur(20px);
border: 1px solid rgba(148, 163, 184, 0.15);
```

**Light Mode:**
```css
background: #FFFFFF;
border: 1px solid #E2E8F0;
box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
```

### Map Component (Always Dark)
The interactive map component maintains a dark theme in both modes for optimal visualization and user experience. Maps with light backgrounds can be visually overwhelming and reduce marker visibility.

## Navigation

### Desktop
- Top navbar with logo and nav links
- Horizontal layout
- Active state highlighting

### Mobile
- Bottom tab bar
- 5 main sections: Map, Chat, Valuation, Districts, Profile
- Icon + label layout
- Active indicator animation

## Pages

1. **Property Explorer** - Interactive map with property markers
2. **AI Chat** - Two-column chat interface with sessions
3. **Property Details** - Single property analysis
4. **Valuation** - Property valuation tool
5. **Districts** - District comparison grid
6. **Site Analysis** - Location intelligence scores
7. **Settings** - User profile, AI config, security
8. **Login/Register** - Authentication pages

## Animation Guidelines
- Use Motion (formerly Framer Motion) for animations
- Smooth transitions (200-300ms duration)
- Hover states: scale 1.02
- Tap states: scale 0.98
- Page transitions: fade + slide
- Score gauges: 1s animation on mount
- Micro-interactions on all interactive elements

## Accessibility
- Focus states on all interactive elements
- Semantic HTML structure
- ARIA labels where needed
- Color contrast ratios meet WCAG AA
- Keyboard navigation support