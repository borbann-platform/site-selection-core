import { useState } from 'react';
import { MapPin } from 'lucide-react';
import { motion } from 'motion/react';

interface Property {
  id: string;
  lat: number;
  lng: number;
  price: number;
  district: string;
  sqm: number;
  style: string;
  address: string;
}

interface MockMapProps {
  properties: Property[];
  onPropertyClick: (property: Property) => void;
}

export function MockMap({ properties, onPropertyClick }: MockMapProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  
  return (
    <div className="relative w-full h-full bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 overflow-hidden">
      {/* Mock map grid pattern */}
      <div className="absolute inset-0 opacity-20">
        <svg width="100%" height="100%">
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(148, 163, 184, 0.3)" strokeWidth="0.5"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
      </div>
      
      {/* Mock streets and landmarks */}
      <div className="absolute inset-0">
        {/* River representation */}
        <div className="absolute top-1/3 left-0 right-0 h-20 bg-blue-900/30 blur-sm" />
        
        {/* Main roads */}
        <div className="absolute top-1/4 left-0 right-0 h-1 bg-yellow-600/20" />
        <div className="absolute top-2/3 left-0 right-0 h-1 bg-yellow-600/20" />
        <div className="absolute left-1/3 top-0 bottom-0 w-1 bg-yellow-600/20" />
        <div className="absolute left-2/3 top-0 bottom-0 w-1 bg-yellow-600/20" />
      </div>
      
      {/* Property markers */}
      {properties.map((property) => {
        const priceLevel = property.price > 100000000 ? 'high' : property.price > 50000000 ? 'medium' : 'low';
        const colors = {
          high: '#EF4444',
          medium: '#F59E0B',
          low: '#10B981',
        };
        
        return (
          <motion.button
            key={property.id}
            className="absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer group"
            style={{
              left: `${property.lng}%`,
              top: `${property.lat}%`,
            }}
            onClick={() => onPropertyClick(property)}
            onMouseEnter={() => setHoveredId(property.id)}
            onMouseLeave={() => setHoveredId(null)}
            whileHover={{ scale: 1.2 }}
            whileTap={{ scale: 0.9 }}
          >
            <div className="relative">
              <MapPin
                className="h-8 w-8 drop-shadow-lg transition-all"
                style={{ color: colors[priceLevel], fill: colors[priceLevel] }}
              />
              {hoveredId === property.id && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 whitespace-nowrap"
                >
                  <div className="glass-strong px-3 py-2 rounded-lg text-xs">
                    <div className="font-semibold">฿{(property.price / 1000000).toFixed(1)}M</div>
                    <div className="text-muted-foreground">{property.district}</div>
                  </div>
                </motion.div>
              )}
            </div>
          </motion.button>
        );
      })}
    </div>
  );
}
