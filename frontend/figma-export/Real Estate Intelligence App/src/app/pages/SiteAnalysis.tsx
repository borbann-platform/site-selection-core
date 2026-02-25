import { useState } from 'react';
import { MapPin, Train, Utensils, GraduationCap, Droplet, Volume2, Star } from 'lucide-react';
import { Card } from '../components/Card';
import { ScoreGauge } from '../components/ScoreGauge';
import { Badge } from '../components/Badge';

interface POI {
  id: string;
  name: string;
  type: 'transit' | 'restaurant' | 'school' | 'cafe' | 'shop';
  distance: number;
  icon: any;
}

const mockPOIs: POI[] = [
  { id: '1', name: 'BTS Phrom Phong', type: 'transit', distance: 250, icon: Train },
  { id: '2', name: 'EmQuartier Mall', type: 'shop', distance: 300, icon: Star },
  { id: '3', name: 'Starbucks Coffee', type: 'cafe', distance: 150, icon: Utensils },
  { id: '4', name: 'International School', type: 'school', distance: 800, icon: GraduationCap },
  { id: '5', name: 'BTS Thong Lo', type: 'transit', distance: 1200, icon: Train },
  { id: '6', name: 'Villa Market', type: 'shop', distance: 400, icon: Star },
  { id: '7', name: 'Blue Elephant', type: 'restaurant', distance: 350, icon: Utensils },
  { id: '8', name: 'Benjakitti Park', type: 'cafe', distance: 600, icon: Star },
];

export function SiteAnalysis() {
  const [selectedLocation] = useState({
    address: '123 Sukhumvit Road, Watthana',
    coordinates: { lat: 13.7563, lng: 100.5018 },
  });
  
  const scores = {
    transit: 92,
    walkability: 88,
    schools: 75,
    floodRisk: 15,
    noiseLevel: 35,
    composite: 85,
  };
  
  return (
    <div className="h-[calc(100vh-4rem)] flex overflow-hidden pb-16 md:pb-0">
      {/* Map Side */}
      <div className="hidden md:block md:w-2/5 relative bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        {/* Mock map grid pattern */}
        <div className="absolute inset-0 opacity-20">
          <svg width="100%" height="100%">
            <defs>
              <pattern id="site-grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(148, 163, 184, 0.3)" strokeWidth="0.5"/>
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#site-grid)" />
          </svg>
        </div>
        
        {/* Site Pin */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
          <div className="relative">
            <div className="absolute -inset-8 bg-primary/20 rounded-full animate-ping" />
            <MapPin className="h-12 w-12 text-primary relative z-10" style={{ fill: '#0EA5E9' }} />
          </div>
        </div>
        
        {/* Nearby POI markers */}
        {mockPOIs.slice(0, 5).map((poi, i) => {
          const angle = (i / 5) * Math.PI * 2;
          const radius = 100 + Math.random() * 80;
          const x = Math.cos(angle) * radius;
          const y = Math.sin(angle) * radius;
          const Icon = poi.icon;
          
          return (
            <div
              key={poi.id}
              className="absolute top-1/2 left-1/2"
              style={{
                transform: `translate(calc(-50% + ${x}px), calc(-50% + ${y}px))`,
              }}
            >
              <div className="h-8 w-8 rounded-full bg-secondary flex items-center justify-center border border-border">
                <Icon className="h-4 w-4 text-primary" />
              </div>
            </div>
          );
        })}
      </div>
      
      {/* Analysis Panel */}
      <div className="flex-1 overflow-y-auto p-4 md:p-8">
        <div className="max-w-3xl mx-auto space-y-6">
          {/* Header */}
          <div>
            <h1 className="text-3xl font-bold mb-2">Site Analysis</h1>
            <div className="flex items-center gap-2 text-muted-foreground">
              <MapPin className="h-4 w-4" />
              <span>{selectedLocation.address}</span>
            </div>
            <p className="text-sm text-muted-foreground mt-1">
              {selectedLocation.coordinates.lat.toFixed(4)}, {selectedLocation.coordinates.lng.toFixed(4)}
            </p>
          </div>
          
          {/* Composite Score */}
          <Card>
            <h2 className="text-xl font-semibold mb-6 text-center">Overall Location Score</h2>
            <div className="flex justify-center">
              <ScoreGauge score={scores.composite} label="Composite Score" size="lg" />
            </div>
            <p className="text-center text-muted-foreground mt-4">
              This location scores exceptionally well for urban living and investment potential
            </p>
          </Card>
          
          {/* Individual Scores */}
          <Card>
            <h2 className="text-xl font-semibold mb-6">Location Intelligence</h2>
            
            <div className="grid md:grid-cols-2 gap-6">
              {/* Transit Score */}
              <div className="glass rounded-lg p-4">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-10 w-10 rounded-lg bg-primary/20 flex items-center justify-center">
                    <Train className="h-6 w-6 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold">Transit Score</h3>
                    <p className="text-xs text-muted-foreground">BTS, MRT, Bus Access</p>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <ScoreGauge score={scores.transit} size="sm" />
                  <div className="text-right">
                    <Badge variant="success">Excellent</Badge>
                    <p className="text-xs text-muted-foreground mt-1">250m to BTS</p>
                  </div>
                </div>
              </div>
              
              {/* Walkability Score */}
              <div className="glass rounded-lg p-4">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-10 w-10 rounded-lg bg-primary/20 flex items-center justify-center">
                    <Utensils className="h-6 w-6 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold">Walkability Score</h3>
                    <p className="text-xs text-muted-foreground">Restaurants, Cafes, Shops</p>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <ScoreGauge score={scores.walkability} size="sm" />
                  <div className="text-right">
                    <Badge variant="success">Very Good</Badge>
                    <p className="text-xs text-muted-foreground mt-1">25+ venues nearby</p>
                  </div>
                </div>
              </div>
              
              {/* Schools Score */}
              <div className="glass rounded-lg p-4">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-10 w-10 rounded-lg bg-primary/20 flex items-center justify-center">
                    <GraduationCap className="h-6 w-6 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold">Schools Score</h3>
                    <p className="text-xs text-muted-foreground">Educational Facilities</p>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <ScoreGauge score={scores.schools} size="sm" />
                  <div className="text-right">
                    <Badge variant="info">Good</Badge>
                    <p className="text-xs text-muted-foreground mt-1">3 schools within 2km</p>
                  </div>
                </div>
              </div>
              
              {/* Flood Risk */}
              <div className="glass rounded-lg p-4">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-10 w-10 rounded-lg bg-primary/20 flex items-center justify-center">
                    <Droplet className="h-6 w-6 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold">Flood Risk</h3>
                    <p className="text-xs text-muted-foreground">Historical Data</p>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <ScoreGauge score={100 - scores.floodRisk} size="sm" />
                  <div className="text-right">
                    <Badge variant="success">Low Risk</Badge>
                    <p className="text-xs text-muted-foreground mt-1">No incidents</p>
                  </div>
                </div>
              </div>
              
              {/* Noise Level */}
              <div className="glass rounded-lg p-4">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-10 w-10 rounded-lg bg-primary/20 flex items-center justify-center">
                    <Volume2 className="h-6 w-6 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold">Noise Level</h3>
                    <p className="text-xs text-muted-foreground">Ambient Sound</p>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <ScoreGauge score={100 - scores.noiseLevel} size="sm" />
                  <div className="text-right">
                    <Badge variant="info">Moderate</Badge>
                    <p className="text-xs text-muted-foreground mt-1">Urban area</p>
                  </div>
                </div>
              </div>
            </div>
          </Card>
          
          {/* Nearby POIs */}
          <Card>
            <h2 className="text-xl font-semibold mb-4">Nearby Points of Interest</h2>
            <div className="space-y-2">
              {mockPOIs.map((poi) => {
                const Icon = poi.icon;
                return (
                  <div
                    key={poi.id}
                    className="flex items-center justify-between p-3 glass rounded-lg hover:bg-accent/50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="h-8 w-8 rounded-lg bg-primary/20 flex items-center justify-center">
                        <Icon className="h-4 w-4 text-primary" />
                      </div>
                      <div>
                        <div className="font-medium">{poi.name}</div>
                        <div className="text-xs text-muted-foreground capitalize">{poi.type}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-semibold">{poi.distance}m</div>
                      <div className="text-xs text-muted-foreground">
                        {Math.round(poi.distance / 80)} min walk
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
