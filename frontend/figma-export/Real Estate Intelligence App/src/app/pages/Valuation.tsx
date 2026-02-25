import { useState } from 'react';
import { MapPin, Download, TrendingUp, Building2 } from 'lucide-react';
import { Card } from '../components/Card';
import { Input } from '../components/Input';
import { Select } from '../components/Select';
import { Button } from '../components/Button';
import { Badge } from '../components/Badge';
import { Spinner } from '../components/Spinner';
import { motion, AnimatePresence } from 'motion/react';

const buildingStyles = [
  { value: 'condo', label: 'Condo' },
  { value: 'apartment', label: 'Apartment' },
  { value: 'penthouse', label: 'Penthouse' },
  { value: 'duplex', label: 'Duplex' },
  { value: 'villa', label: 'Villa' },
];

const districts = [
  { value: 'sukhumvit', label: 'Sukhumvit' },
  { value: 'sathorn', label: 'Sathorn' },
  { value: 'silom', label: 'Silom' },
  { value: 'thonglor', label: 'Thonglor' },
  { value: 'phrom-phong', label: 'Phrom Phong' },
];

interface ValuationResult {
  estimatedPrice: number;
  priceRange: { min: number; max: number };
  confidence: 'High' | 'Medium' | 'Low';
  factors: { name: string; impact: number; positive: boolean }[];
  comparables: { address: string; price: number; sqm: number }[];
  marketInsights: { avgPrice: number; trend: string };
}

export function Valuation() {
  const [formData, setFormData] = useState({
    style: 'condo',
    area: '',
    floors: '',
    age: '',
    district: 'sukhumvit',
  });
  
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ValuationResult | null>(null);
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    // Simulate API call
    setTimeout(() => {
      const basePrice = 750000 * parseInt(formData.area);
      const ageFactor = Math.max(0, 1 - parseInt(formData.age) * 0.03);
      const estimatedPrice = basePrice * ageFactor;
      
      setResult({
        estimatedPrice,
        priceRange: {
          min: estimatedPrice * 0.9,
          max: estimatedPrice * 1.1,
        },
        confidence: 'High',
        factors: [
          { name: 'Location (Sukhumvit)', impact: 15, positive: true },
          { name: 'Building Age', impact: -parseInt(formData.age) * 2, positive: false },
          { name: 'Floor Level', impact: 8, positive: true },
          { name: 'Market Trend', impact: 12, positive: true },
          { name: 'Amenities Score', impact: 10, positive: true },
        ],
        comparables: [
          { address: '123 Sukhumvit Rd', price: estimatedPrice * 0.95, sqm: parseInt(formData.area) - 5 },
          { address: '456 Sukhumvit Rd', price: estimatedPrice * 1.05, sqm: parseInt(formData.area) + 5 },
          { address: '789 Sukhumvit Rd', price: estimatedPrice * 0.98, sqm: parseInt(formData.area) },
        ],
        marketInsights: {
          avgPrice: 85000000,
          trend: 'Prices in Sukhumvit increased by 8.5% in the last 12 months',
        },
      });
      
      setLoading(false);
    }, 2000);
  };
  
  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };
  
  return (
    <div className="min-h-screen pb-20 md:pb-8">
      <div className="max-w-7xl mx-auto p-4 md:p-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Property Valuation</h1>
          <p className="text-muted-foreground">
            Get instant AI-powered property valuations for Bangkok real estate
          </p>
        </div>
        
        <div className="grid lg:grid-cols-2 gap-8">
          {/* Left: Input Form */}
          <div>
            <Card>
              <h2 className="text-xl font-semibold mb-6">Property Details</h2>
              
              <form onSubmit={handleSubmit} className="space-y-4">
                <Select
                  label="Building Style"
                  options={buildingStyles}
                  value={formData.style}
                  onChange={(e) => handleInputChange('style', e.target.value)}
                />
                
                <Input
                  type="number"
                  label="Area (sqm)"
                  placeholder="Enter property area"
                  value={formData.area}
                  onChange={(e) => handleInputChange('area', e.target.value)}
                  required
                />
                
                <Input
                  type="number"
                  label="Number of Floors"
                  placeholder="Enter floor number"
                  value={formData.floors}
                  onChange={(e) => handleInputChange('floors', e.target.value)}
                  required
                />
                
                <Input
                  type="number"
                  label="Building Age (years)"
                  placeholder="Enter building age"
                  value={formData.age}
                  onChange={(e) => handleInputChange('age', e.target.value)}
                  required
                />
                
                <Select
                  label="Location / District"
                  options={districts}
                  value={formData.district}
                  onChange={(e) => handleInputChange('district', e.target.value)}
                />
                
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-foreground">
                    Location Pin
                  </label>
                  <button
                    type="button"
                    className="w-full p-4 border-2 border-dashed border-border rounded-lg hover:border-primary transition-colors flex items-center justify-center gap-2 text-muted-foreground hover:text-foreground"
                  >
                    <MapPin className="h-5 w-5" />
                    <span>Click to select location on map</span>
                  </button>
                </div>
                
                <Button
                  type="submit"
                  className="w-full"
                  size="lg"
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <Spinner size="sm" className="mr-2" />
                      Calculating...
                    </>
                  ) : (
                    'Get Valuation'
                  )}
                </Button>
              </form>
            </Card>
          </div>
          
          {/* Right: Valuation Report */}
          <div>
            <AnimatePresence mode="wait">
              {result ? (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="space-y-6"
                >
                  {/* Estimated Price */}
                  <Card>
                    <div className="text-center">
                      <div className="flex items-center justify-center gap-2 mb-2">
                        <h2 className="text-2xl font-semibold">Estimated Value</h2>
                        <Badge variant="success">{result.confidence} Confidence</Badge>
                      </div>
                      <div className="text-5xl font-bold text-primary mb-4">
                        ฿{(result.estimatedPrice / 1000000).toFixed(2)}M
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Range: ฿{(result.priceRange.min / 1000000).toFixed(2)}M - ฿
                        {(result.priceRange.max / 1000000).toFixed(2)}M
                      </div>
                    </div>
                  </Card>
                  
                  {/* Price Factors */}
                  <Card>
                    <h3 className="text-lg font-semibold mb-4">Price Factors</h3>
                    <div className="space-y-3">
                      {result.factors.map((factor, i) => (
                        <div key={i} className="flex items-center justify-between">
                          <span className="text-sm">{factor.name}</span>
                          <div className="flex items-center gap-2">
                            <div className="w-24 h-2 bg-secondary rounded-full overflow-hidden">
                              <div
                                className={`h-full ${factor.positive ? 'bg-success' : 'bg-destructive'}`}
                                style={{ width: `${Math.abs(factor.impact) * 5}%` }}
                              />
                            </div>
                            <span className={`text-sm font-semibold w-12 text-right ${
                              factor.positive ? 'text-success' : 'text-destructive'
                            }`}>
                              {factor.positive ? '+' : ''}{factor.impact}%
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                  
                  {/* Comparable Properties */}
                  <Card>
                    <h3 className="text-lg font-semibold mb-4">Comparable Properties</h3>
                    <div className="space-y-3">
                      {result.comparables.map((comp, i) => (
                        <div key={i} className="glass rounded-lg p-3 flex items-center justify-between">
                          <div>
                            <div className="text-sm font-medium">{comp.address}</div>
                            <div className="text-xs text-muted-foreground">{comp.sqm} sqm</div>
                          </div>
                          <div className="text-sm font-semibold text-primary">
                            ฿{(comp.price / 1000000).toFixed(1)}M
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                  
                  {/* Market Insights */}
                  <Card>
                    <h3 className="text-lg font-semibold mb-4">Market Insights</h3>
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">District Average</span>
                        <span className="font-semibold">
                          ฿{(result.marketInsights.avgPrice / 1000000).toFixed(1)}M
                        </span>
                      </div>
                      <div className="flex items-start gap-2">
                        <TrendingUp className="h-5 w-5 text-success flex-shrink-0 mt-0.5" />
                        <p className="text-sm">{result.marketInsights.trend}</p>
                      </div>
                    </div>
                  </Card>
                  
                  {/* Export Button */}
                  <Button variant="secondary" className="w-full">
                    <Download className="h-4 w-4 mr-2" />
                    Export PDF Report
                  </Button>
                </motion.div>
              ) : (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="h-full flex items-center justify-center"
                >
                  <Card className="text-center p-12">
                    <div className="h-20 w-20 rounded-full bg-primary/20 flex items-center justify-center mx-auto mb-4">
                      <Building2 className="h-10 w-10 text-primary" />
                    </div>
                    <h3 className="text-xl font-semibold mb-2">Ready to Value</h3>
                    <p className="text-muted-foreground">
                      Fill in the property details to get your instant AI valuation
                    </p>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}
