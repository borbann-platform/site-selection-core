import { useState } from 'react';
import { useNavigate } from 'react-router';
import {
  Search, SlidersHorizontal, X, School, Train, Grid3x3,
  MapPin, Square, MousePointer, MessageSquare, ChevronLeft, ChevronRight
} from 'lucide-react';
import { Card } from '../components/Card';
import { Input } from '../components/Input';
import { Select } from '../components/Select';
import { Slider } from '../components/Slider';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { MockMap } from '../components/MockMap';
import { motion, AnimatePresence } from 'motion/react';

const mockProperties = [
  { id: '1', lat: 25, lng: 30, price: 85000000, district: 'Sukhumvit', sqm: 120, style: 'Condo', address: '123 Sukhumvit Rd', floors: 25, age: 5, image: 'modern-condo' },
  { id: '2', lat: 40, lng: 60, price: 45000000, district: 'Sathorn', sqm: 95, style: 'Apartment', address: '456 Sathorn Rd', floors: 15, age: 8, image: 'apartment-building' },
  { id: '3', lat: 60, lng: 25, price: 120000000, district: 'Silom', sqm: 150, style: 'Penthouse', address: '789 Silom Rd', floors: 35, age: 3, image: 'luxury-penthouse' },
  { id: '4', lat: 35, lng: 80, price: 35000000, district: 'Phrom Phong', sqm: 80, style: 'Condo', address: '321 Phrom Phong', floors: 20, age: 10, image: 'urban-condo' },
  { id: '5', lat: 70, lng: 50, price: 95000000, district: 'Thonglor', sqm: 135, style: 'Duplex', address: '654 Thonglor Rd', floors: 30, age: 4, image: 'modern-duplex' },
  { id: '6', lat: 50, lng: 40, price: 62000000, district: 'Asoke', sqm: 110, style: 'Condo', address: '987 Asoke Rd', floors: 22, age: 6, image: 'city-condo' },
];

export function PropertyExplorer() {
  const navigate = useNavigate();
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDistrict, setSelectedDistrict] = useState('all');
  const [selectedStyle, setSelectedStyle] = useState<string[]>([]);
  const [priceRange, setPriceRange] = useState([0, 150000000]);
  const [areaRange, setAreaRange] = useState([0, 200]);
  const [overlays, setOverlays] = useState({ schools: false, transit: false, h3Grid: false });
  const [selectedProperty, setSelectedProperty] = useState<any>(null);
  const [mapMode, setMapMode] = useState<'pin' | 'box' | 'select'>('select');
  
  const districtOptions = [
    { value: 'all', label: 'All Districts' },
    { value: 'sukhumvit', label: 'Sukhumvit' },
    { value: 'sathorn', label: 'Sathorn' },
    { value: 'silom', label: 'Silom' },
    { value: 'phrom-phong', label: 'Phrom Phong' },
    { value: 'thonglor', label: 'Thonglor' },
    { value: 'asoke', label: 'Asoke' },
  ];
  
  const styles = ['Condo', 'Apartment', 'Penthouse', 'Duplex', 'Villa'];
  
  const toggleStyle = (style: string) => {
    setSelectedStyle(prev =>
      prev.includes(style) ? prev.filter(s => s !== style) : [...prev, style]
    );
  };
  
  const toggleOverlay = (overlay: 'schools' | 'transit' | 'h3Grid') => {
    setOverlays(prev => ({ ...prev, [overlay]: !prev[overlay] }));
  };
  
  return (
    <div className="h-[calc(100vh-4rem)] md:h-[calc(100vh-4rem)] relative overflow-hidden">
      {/* Map Background */}
      <div className="absolute inset-0">
        <MockMap properties={mockProperties} onPropertyClick={setSelectedProperty} />
      </div>
      
      {/* Left Panel - Explorer */}
      <AnimatePresence>
        {!panelCollapsed && (
          <motion.div
            initial={{ x: -400 }}
            animate={{ x: 0 }}
            exit={{ x: -400 }}
            transition={{ type: 'spring', damping: 25 }}
            className="absolute left-0 top-0 bottom-0 w-[400px] max-w-[90vw] p-4 z-10"
          >
            <div className="glass-strong rounded-2xl h-full flex flex-col overflow-hidden">
              {/* Header */}
              <div className="p-4 border-b border-border flex items-center justify-between">
                <h2 className="font-semibold">Explorer</h2>
                <button
                  onClick={() => setPanelCollapsed(true)}
                  className="p-1 hover:bg-accent rounded-lg transition-colors"
                >
                  <ChevronLeft className="h-5 w-5" />
                </button>
              </div>
              
              {/* Search */}
              <div className="p-4 border-b border-border">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    type="text"
                    placeholder="Search properties..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 bg-input-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
              </div>
              
              {/* Filters */}
              <div className="p-4 space-y-4 border-b border-border">
                <Select
                  label="District"
                  options={districtOptions}
                  value={selectedDistrict}
                  onChange={(e) => setSelectedDistrict(e.target.value)}
                />
                
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-foreground">Building Style</label>
                  <div className="flex flex-wrap gap-2">
                    {styles.map((style) => (
                      <button
                        key={style}
                        onClick={() => toggleStyle(style)}
                        className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                          selectedStyle.includes(style)
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
                        }`}
                      >
                        {style}
                      </button>
                    ))}
                  </div>
                </div>
                
                <Slider
                  label="Price Range"
                  min={0}
                  max={150000000}
                  step={1000000}
                  value={priceRange}
                  onValueChange={setPriceRange}
                  formatValue={(v) => `฿${(v / 1000000).toFixed(0)}M`}
                />
                
                <Slider
                  label="Area (sqm)"
                  min={0}
                  max={200}
                  step={5}
                  value={areaRange}
                  onValueChange={setAreaRange}
                  formatValue={(v) => `${v} sqm`}
                />
              </div>
              
              {/* Property List */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-muted-foreground">{mockProperties.length} properties</span>
                </div>
                
                {mockProperties.map((property) => (
                  <div
                    key={property.id}
                    onClick={() => navigate(`/property/${property.id}`)}
                    className="glass rounded-lg p-3 cursor-pointer hover:ring-2 hover:ring-primary transition-all group"
                  >
                    <div className="flex gap-3">
                      <div className="w-20 h-20 rounded-lg bg-secondary flex items-center justify-center flex-shrink-0">
                        <MapPin className="h-8 w-8 text-primary" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-primary">฿{(property.price / 1000000).toFixed(1)}M</div>
                        <div className="text-sm text-muted-foreground truncate">{property.address}</div>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge variant="info">{property.district}</Badge>
                          <span className="text-xs text-muted-foreground">{property.sqm} sqm</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      
      {/* Collapse Button */}
      {panelCollapsed && (
        <button
          onClick={() => setPanelCollapsed(false)}
          className="absolute left-4 top-4 glass-strong p-3 rounded-xl z-10 hover:bg-accent transition-colors"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      )}
      
      {/* Map Controls - Top Right */}
      <div className="absolute top-4 right-4 flex flex-col gap-2 z-10">
        <div className="glass-strong rounded-xl p-2 flex gap-2">
          <button
            onClick={() => toggleOverlay('schools')}
            className={`p-2 rounded-lg transition-colors ${overlays.schools ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'}`}
            title="Schools"
          >
            <School className="h-5 w-5" />
          </button>
          <button
            onClick={() => toggleOverlay('transit')}
            className={`p-2 rounded-lg transition-colors ${overlays.transit ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'}`}
            title="Transit Lines"
          >
            <Train className="h-5 w-5" />
          </button>
          <button
            onClick={() => toggleOverlay('h3Grid')}
            className={`p-2 rounded-lg transition-colors ${overlays.h3Grid ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'}`}
            title="H3 Grid"
          >
            <Grid3x3 className="h-5 w-5" />
          </button>
        </div>
        
        {/* Map Mode Selection */}
        <div className="glass-strong rounded-xl p-2 flex gap-2">
          <button
            onClick={() => setMapMode('pin')}
            className={`p-2 rounded-lg transition-colors ${mapMode === 'pin' ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'}`}
            title="Pin Mode"
          >
            <MapPin className="h-5 w-5" />
          </button>
          <button
            onClick={() => setMapMode('box')}
            className={`p-2 rounded-lg transition-colors ${mapMode === 'box' ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'}`}
            title="Bounding Box"
          >
            <Square className="h-5 w-5" />
          </button>
          <button
            onClick={() => setMapMode('select')}
            className={`p-2 rounded-lg transition-colors ${mapMode === 'select' ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'}`}
            title="Property Select"
          >
            <MousePointer className="h-5 w-5" />
          </button>
        </div>
      </div>
      
      {/* Map Legend - Bottom Right */}
      <div className="absolute bottom-20 md:bottom-4 right-4 glass-strong rounded-xl p-4 z-10 max-w-xs">
        <h3 className="text-sm font-semibold mb-3">Price Range</h3>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-[#10B981]" />
            <span className="text-xs text-muted-foreground">Low ({"<"}฿50M)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-[#F59E0B]" />
            <span className="text-xs text-muted-foreground">Medium (฿50M-100M)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-[#EF4444]" />
            <span className="text-xs text-muted-foreground">High ({">"}฿100M)</span>
          </div>
        </div>
      </div>
      
      {/* Property Popup */}
      <AnimatePresence>
        {selectedProperty && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-20 w-[400px] max-w-[90vw]"
          >
            <div className="glass-strong rounded-2xl p-6 relative">
              <button
                onClick={() => setSelectedProperty(null)}
                className="absolute top-4 right-4 p-1 hover:bg-accent rounded-lg transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
              
              <div className="w-full h-48 rounded-lg bg-secondary flex items-center justify-center mb-4">
                <MapPin className="h-16 w-16 text-primary" />
              </div>
              
              <div className="space-y-3">
                <div>
                  <div className="text-2xl font-bold text-primary">
                    ฿{(selectedProperty.price / 1000000).toFixed(1)}M
                  </div>
                  <div className="text-sm text-muted-foreground">{selectedProperty.address}</div>
                </div>
                
                <div className="flex items-center gap-2">
                  <Badge variant="info">{selectedProperty.district}</Badge>
                  <Badge variant="neutral">{selectedProperty.style}</Badge>
                </div>
                
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <div>
                    <div className="text-muted-foreground">Area</div>
                    <div className="font-semibold">{selectedProperty.sqm} sqm</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Floors</div>
                    <div className="font-semibold">{selectedProperty.floors}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Age</div>
                    <div className="font-semibold">{selectedProperty.age} years</div>
                  </div>
                </div>
                
                <Button
                  className="w-full"
                  onClick={() => navigate(`/property/${selectedProperty.id}`)}
                >
                  View Details
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      
      {/* Floating Chat Button */}
      <button
        onClick={() => navigate('/chat')}
        className="absolute bottom-24 md:bottom-8 right-4 h-14 w-14 bg-primary hover:bg-primary-hover rounded-full flex items-center justify-center shadow-lg hover:shadow-xl transition-all z-10"
      >
        <MessageSquare className="h-6 w-6 text-primary-foreground" />
      </button>
    </div>
  );
}
