import { useParams, useNavigate } from 'react-router';
import { ArrowLeft, MapPin, Layers, Home, Calendar, TrendingUp, TrendingDown } from 'lucide-react';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const mockProperty = {
  id: '1',
  address: '123 Sukhumvit Road, Watthana',
  district: 'Sukhumvit',
  style: 'Condo',
  price: 85000000,
  sqm: 120,
  pricePerSqm: 708333,
  floors: 25,
  age: 5,
  predictedPrice: 87500000,
  confidence: 'High',
  model: 'XGBoost Ensemble',
};

const priceFactors = [
  { factor: 'Location Score', impact: 12500000, positive: true },
  { factor: 'BTS Proximity', impact: 8500000, positive: true },
  { factor: 'Building Age', impact: -3000000, positive: false },
  { factor: 'Floor Level', impact: 4200000, positive: true },
  { factor: 'View Quality', impact: 5800000, positive: true },
  { factor: 'Maintenance', impact: -1200000, positive: false },
];

const comparableProperties = [
  { id: '2', address: '456 Sukhumvit Rd', price: 82000000, sqm: 115, similarity: 95 },
  { id: '3', address: '789 Sukhumvit Rd', price: 88000000, sqm: 125, similarity: 92 },
  { id: '4', address: '321 Sukhumvit Rd', price: 79000000, sqm: 110, similarity: 89 },
];

const historicalData = [
  { month: 'Aug', price: 78 },
  { month: 'Sep', price: 79.5 },
  { month: 'Oct', price: 81 },
  { month: 'Nov', price: 82 },
  { month: 'Dec', price: 83.5 },
  { month: 'Jan', price: 85 },
];

export function PropertyDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  
  const maxImpact = Math.max(...priceFactors.map(f => Math.abs(f.impact)));
  
  return (
    <div className="min-h-screen pb-20 md:pb-8">
      <div className="max-w-4xl mx-auto p-4 md:p-8 space-y-6">
        {/* Back Button */}
        <Button variant="ghost" onClick={() => navigate('/')}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Map
        </Button>
        
        {/* Hero Section */}
        <Card>
          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-3xl font-bold mb-2">{mockProperty.address}</h1>
                <div className="flex items-center gap-2">
                  <Badge variant="info">{mockProperty.district}</Badge>
                  <Badge variant="neutral">{mockProperty.style}</Badge>
                </div>
              </div>
            </div>
            
            {/* Key Stats */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 pt-4 border-t border-border">
              <div>
                <div className="text-sm text-muted-foreground mb-1">Price</div>
                <div className="text-xl font-bold text-primary">
                  ฿{(mockProperty.price / 1000000).toFixed(1)}M
                </div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground mb-1">Area</div>
                <div className="text-xl font-bold">{mockProperty.sqm} sqm</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground mb-1">Price/sqm</div>
                <div className="text-xl font-bold">
                  ฿{(mockProperty.pricePerSqm / 1000).toFixed(0)}K
                </div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground mb-1">Floors</div>
                <div className="text-xl font-bold">{mockProperty.floors}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground mb-1">Age</div>
                <div className="text-xl font-bold">{mockProperty.age} years</div>
              </div>
            </div>
          </div>
        </Card>
        
        {/* Price Prediction */}
        <Card>
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-xl font-semibold mb-1">AI Price Prediction</h2>
              <p className="text-sm text-muted-foreground">Based on {mockProperty.model}</p>
            </div>
            <Badge variant="success">
              {mockProperty.confidence} Confidence
            </Badge>
          </div>
          
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <div className="text-sm text-muted-foreground mb-2">Predicted Value</div>
              <div className="text-3xl font-bold text-primary">
                ฿{(mockProperty.predictedPrice / 1000000).toFixed(2)}M
              </div>
              <div className="flex items-center gap-2 mt-2">
                <TrendingUp className="h-4 w-4 text-success" />
                <span className="text-sm text-success font-medium">
                  +{((mockProperty.predictedPrice - mockProperty.price) / 1000000).toFixed(2)}M
                  ({(((mockProperty.predictedPrice - mockProperty.price) / mockProperty.price) * 100).toFixed(1)}%)
                </span>
              </div>
            </div>
            
            <div className="flex items-center justify-center">
              <div className="w-full h-32 glass rounded-lg flex items-center justify-center">
                <div className="text-center">
                  <div className="text-4xl font-bold text-primary mb-2">94%</div>
                  <div className="text-sm text-muted-foreground">Prediction Accuracy</div>
                </div>
              </div>
            </div>
          </div>
        </Card>
        
        {/* Price Explanation */}
        <Card>
          <h2 className="text-xl font-semibold mb-4">Price Factors</h2>
          <div className="space-y-3">
            {priceFactors.map((factor, i) => (
              <div key={i}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">{factor.factor}</span>
                  <span className={`text-sm font-semibold ${factor.positive ? 'text-success' : 'text-destructive'}`}>
                    {factor.positive ? '+' : ''}฿{(factor.impact / 1000000).toFixed(1)}M
                  </span>
                </div>
                <div className="h-2 bg-secondary rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${factor.positive ? 'bg-success' : 'bg-destructive'}`}
                    style={{ width: `${(Math.abs(factor.impact) / maxImpact) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
        
        {/* Historical Data */}
        <Card>
          <h2 className="text-xl font-semibold mb-4">Price Trend (Last 6 Months)</h2>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={historicalData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" />
              <XAxis dataKey="month" stroke="#94A3B8" />
              <YAxis stroke="#94A3B8" />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(30, 41, 59, 0.95)',
                  border: '1px solid rgba(148, 163, 184, 0.2)',
                  borderRadius: '8px',
                }}
              />
              <Line type="monotone" dataKey="price" stroke="#0EA5E9" strokeWidth={2} dot={{ fill: '#0EA5E9' }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
        
        {/* Comparable Properties */}
        <Card>
          <h2 className="text-xl font-semibold mb-4">Comparable Properties</h2>
          <div className="grid md:grid-cols-3 gap-4">
            {comparableProperties.map((comp) => (
              <div
                key={comp.id}
                className="glass rounded-lg p-4 cursor-pointer hover:ring-2 hover:ring-primary transition-all"
                onClick={() => navigate(`/property/${comp.id}`)}
              >
                <div className="flex items-start justify-between mb-3">
                  <MapPin className="h-5 w-5 text-primary" />
                  <Badge variant="success">{comp.similarity}% Match</Badge>
                </div>
                <div className="text-sm text-muted-foreground mb-2">{comp.address}</div>
                <div className="font-bold text-primary">฿{(comp.price / 1000000).toFixed(1)}M</div>
                <div className="text-sm text-muted-foreground">{comp.sqm} sqm</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
