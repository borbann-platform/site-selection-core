import { useState } from 'react';
import { TrendingUp, TrendingDown, Building2, BarChart3 } from 'lucide-react';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { Select } from '../components/Select';
import { LineChart, Line, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

interface District {
  id: string;
  name: string;
  avgPrice: number;
  pricePerSqm: number;
  propertyCount: number;
  trend: number;
  trendData: { month: string; price: number }[];
  buildingStyles: { style: string; count: number; color: string }[];
}

const mockDistricts: District[] = [
  {
    id: '1',
    name: 'Sukhumvit',
    avgPrice: 85000000,
    pricePerSqm: 708000,
    propertyCount: 1247,
    trend: 8.5,
    trendData: [
      { month: 'Aug', price: 78 },
      { month: 'Sep', price: 80 },
      { month: 'Oct', price: 82 },
      { month: 'Nov', price: 83 },
      { month: 'Dec', price: 84 },
      { month: 'Jan', price: 85 },
    ],
    buildingStyles: [
      { style: 'Condo', count: 650, color: '#0EA5E9' },
      { style: 'Apartment', count: 350, color: '#8B5CF6' },
      { style: 'Penthouse', count: 150, color: '#10B981' },
      { style: 'Others', count: 97, color: '#F59E0B' },
    ],
  },
  {
    id: '2',
    name: 'Sathorn',
    avgPrice: 95000000,
    pricePerSqm: 792000,
    propertyCount: 892,
    trend: 12.3,
    trendData: [
      { month: 'Aug', price: 85 },
      { month: 'Sep', price: 87 },
      { month: 'Oct', price: 90 },
      { month: 'Nov', price: 92 },
      { month: 'Dec', price: 93 },
      { month: 'Jan', price: 95 },
    ],
    buildingStyles: [
      { style: 'Condo', count: 450, color: '#0EA5E9' },
      { style: 'Penthouse', count: 250, color: '#10B981' },
      { style: 'Apartment', count: 150, color: '#8B5CF6' },
      { style: 'Others', count: 42, color: '#F59E0B' },
    ],
  },
  {
    id: '3',
    name: 'Silom',
    avgPrice: 78000000,
    pricePerSqm: 650000,
    propertyCount: 1056,
    trend: 5.7,
    trendData: [
      { month: 'Aug', price: 74 },
      { month: 'Sep', price: 75 },
      { month: 'Oct', price: 76 },
      { month: 'Nov', price: 77 },
      { month: 'Dec', price: 77.5 },
      { month: 'Jan', price: 78 },
    ],
    buildingStyles: [
      { style: 'Apartment', count: 500, color: '#8B5CF6' },
      { style: 'Condo', count: 400, color: '#0EA5E9' },
      { style: 'Others', count: 156, color: '#F59E0B' },
    ],
  },
  {
    id: '4',
    name: 'Thonglor',
    avgPrice: 105000000,
    pricePerSqm: 875000,
    propertyCount: 634,
    trend: 15.2,
    trendData: [
      { month: 'Aug', price: 91 },
      { month: 'Sep', price: 95 },
      { month: 'Oct', price: 98 },
      { month: 'Nov', price: 101 },
      { month: 'Dec', price: 103 },
      { month: 'Jan', price: 105 },
    ],
    buildingStyles: [
      { style: 'Penthouse', count: 250, color: '#10B981' },
      { style: 'Condo', count: 280, color: '#0EA5E9' },
      { style: 'Villa', count: 80, color: '#EF4444' },
      { style: 'Others', count: 24, color: '#F59E0B' },
    ],
  },
  {
    id: '5',
    name: 'Phrom Phong',
    avgPrice: 72000000,
    pricePerSqm: 600000,
    propertyCount: 845,
    trend: 6.8,
    trendData: [
      { month: 'Aug', price: 68 },
      { month: 'Sep', price: 69 },
      { month: 'Oct', price: 70 },
      { month: 'Nov', price: 71 },
      { month: 'Dec', price: 71.5 },
      { month: 'Jan', price: 72 },
    ],
    buildingStyles: [
      { style: 'Condo', count: 550, color: '#0EA5E9' },
      { style: 'Apartment', count: 250, color: '#8B5CF6' },
      { style: 'Others', count: 45, color: '#F59E0B' },
    ],
  },
  {
    id: '6',
    name: 'Asoke',
    avgPrice: 68000000,
    pricePerSqm: 567000,
    propertyCount: 978,
    trend: -2.3,
    trendData: [
      { month: 'Aug', price: 70 },
      { month: 'Sep', price: 69.5 },
      { month: 'Oct', price: 69 },
      { month: 'Nov', price: 68.5 },
      { month: 'Dec', price: 68.2 },
      { month: 'Jan', price: 68 },
    ],
    buildingStyles: [
      { style: 'Apartment', count: 600, color: '#8B5CF6' },
      { style: 'Condo', count: 300, color: '#0EA5E9' },
      { style: 'Others', count: 78, color: '#F59E0B' },
    ],
  },
];

export function Districts() {
  const [sortBy, setSortBy] = useState('price');
  
  const sortOptions = [
    { value: 'price', label: 'Average Price' },
    { value: 'count', label: 'Property Count' },
    { value: 'trend', label: 'Price Trend' },
    { value: 'name', label: 'Name (A-Z)' },
  ];
  
  const sortedDistricts = [...mockDistricts].sort((a, b) => {
    switch (sortBy) {
      case 'price':
        return b.avgPrice - a.avgPrice;
      case 'count':
        return b.propertyCount - a.propertyCount;
      case 'trend':
        return b.trend - a.trend;
      case 'name':
        return a.name.localeCompare(b.name);
      default:
        return 0;
    }
  });
  
  return (
    <div className="min-h-screen pb-20 md:pb-8">
      <div className="max-w-7xl mx-auto p-4 md:p-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Districts</h1>
          <p className="text-muted-foreground">
            Explore Bangkok real estate by district
          </p>
        </div>
        
        {/* Filter Bar */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">{mockDistricts.length} districts</span>
          </div>
          <div className="w-64">
            <Select
              options={sortOptions}
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            />
          </div>
        </div>
        
        {/* District Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {sortedDistricts.map((district) => (
            <Card key={district.id} hover className="cursor-pointer">
              <div className="space-y-4">
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-xl font-bold mb-1">{district.name}</h3>
                    <Badge variant="neutral">
                      <Building2 className="h-3 w-3 mr-1" />
                      {district.propertyCount} properties
                    </Badge>
                  </div>
                  <div className={`flex items-center gap-1 px-2 py-1 rounded-lg ${
                    district.trend >= 0
                      ? 'bg-success/20 text-success'
                      : 'bg-destructive/20 text-destructive'
                  }`}>
                    {district.trend >= 0 ? (
                      <TrendingUp className="h-4 w-4" />
                    ) : (
                      <TrendingDown className="h-4 w-4" />
                    )}
                    <span className="text-sm font-semibold">
                      {district.trend > 0 ? '+' : ''}{district.trend}%
                    </span>
                  </div>
                </div>
                
                {/* Price Info */}
                <div className="space-y-2">
                  <div>
                    <div className="text-sm text-muted-foreground">Average Price</div>
                    <div className="text-2xl font-bold text-primary">
                      ฿{(district.avgPrice / 1000000).toFixed(1)}M
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground">Price per sqm</div>
                    <div className="text-lg font-semibold">
                      ฿{(district.pricePerSqm / 1000).toFixed(0)}K
                    </div>
                  </div>
                </div>
                
                {/* Trend Chart */}
                <div className="h-16">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={district.trendData}>
                      <Line
                        type="monotone"
                        dataKey="price"
                        stroke="#0EA5E9"
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                
                {/* Building Style Distribution */}
                <div className="pt-4 border-t border-border">
                  <div className="text-sm font-medium mb-3">Building Style Distribution</div>
                  <div className="flex items-center gap-4">
                    <div className="w-20 h-20">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={district.buildingStyles}
                            dataKey="count"
                            cx="50%"
                            cy="50%"
                            innerRadius={20}
                            outerRadius={40}
                          >
                            {district.buildingStyles.map((entry, index) => (
                              <Cell key={index} fill={entry.color} />
                            ))}
                          </Pie>
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="flex-1 space-y-1">
                      {district.buildingStyles.slice(0, 3).map((style) => (
                        <div key={style.style} className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-2">
                            <div
                              className="w-2 h-2 rounded-full"
                              style={{ backgroundColor: style.color }}
                            />
                            <span className="text-muted-foreground">{style.style}</span>
                          </div>
                          <span className="font-medium">{style.count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
