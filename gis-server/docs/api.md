# Real Estate Information Platform - API Documentation

Base URL: `http://localhost:8000/api/v1`

## Overview
This API provides real estate information, property data, and price prediction services.

---

## 1. House Prices (Primary Feature)
**Access appraised house prices and price prediction AI.**

### List House Prices
`GET /house-prices`

**Query Parameters:**
- `amphur` - Filter by district
- `tumbon` - Filter by sub-district
- `building_style` - Filter by building type
- `min_price`, `max_price` - Price range filter
- `min_area`, `max_area` - Building area filter
- `limit`, `offset` - Pagination

**Response:**
```json
{
  "count": 100,
  "items": [
    {
      "id": 1,
      "amphur": "บางกะปิ",
      "tumbon": "คลองจั่น",
      "building_style_desc": "บ้านเดี่ยว",
      "total_price": 5500000,
      "building_area": 150,
      "lat": 13.7563,
      "lon": 100.5018
    }
  ]
}
```

### Get Price Statistics
`GET /house-prices/stats`

**Response:**
```json
{
  "total_count": 50000,
  "by_district": [
    {
      "amphur": "บางกะปิ",
      "count": 1200,
      "avg_price": 4500000,
      "avg_price_per_sqm": 30000
    }
  ],
  "by_building_style": [...]
}
```

---

## 2. Location Analysis
**Analyze locations for property context.**

### Analyze Site
`POST /site/analyze`

**Request:**
```json
{
  "latitude": 13.7563,
  "longitude": 100.5018,
  "radius_meters": 1000,
  "target_category": "cafe"
}
```

**Response:**
```json
{
  "site_score": 0.75,
  "summary": {
    "competitors_count": 12,
    "magnets_count": 5,
    "traffic_potential": "High"
  },
  "details": { ... }
}
```

### Get Nearby POIs
`POST /site/nearby`

**Request:**
```json
{
  "latitude": 13.7563,
  "longitude": 100.5018,
  "radius_meters": 500,
  "categories": ["cafe", "school"]
}
```

**Response:** GeoJSON FeatureCollection.

---

## 2. Catchment Analysis
**Analyze travel-time based areas.**

### Get Isochrone (Travel Polygon)
`POST /catchment/isochrone`

**Request:**
```json
{
  "latitude": 13.7563,
  "longitude": 100.5018,
  "minutes": 10,
  "mode": "walk"  // "walk" or "drive"
}
```

**Response:** GeoJSON Polygon geometry.

### Analyze Catchment Population
`POST /catchment/analyze`

**Request:** Same as Isochrone.

**Response:**
```json
{
  "population": 15000,
  "score": 0.85
}
```

---

## 3. Projects & Persistence
**Manage user projects and saved properties.**

### Create Project
`POST /projects`

**Request:**
```json
{
  "name": "My Property Search",
  "description": "Looking for properties in Bangkok"
}
```

### Get Project Dashboard
`GET /projects/{project_id}/dashboard`

**Response:** List of saved properties with their analysis data.

### Save Property to Project
`POST /projects/{project_id}/sites`

**Request:**
```json
{
  "name": "Property A - Sukhumvit",
  "latitude": 13.7563,
  "longitude": 100.5018,
  "score": 0.75,
  "notes": "Good location, near BTS"
}
```

---

## 4. Price Prediction AI (Planned)

### Future Improvements
- **Price Prediction Model:** ML model to predict property prices based on location, area, and amenities.
- **Market Trend Analysis:** Historical price trends and market insights.
- **Comparable Properties:** Find similar properties for price comparison.
