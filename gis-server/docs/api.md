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

### Get Location Intelligence
`POST /location-intelligence`

**Request:**
```json
{
  "latitude": 13.7563,
  "longitude": 100.5018,
  "radius_meters": 1000
}
```

**Response:**
```json
{
  "composite_score": 78,
  "transit": {
    "score": 85,
    "nearest_rail": { "name": "Phrom Phong BTS", "distance_m": 350 },
    "bus_stops_500m": 8,
    "description": "Excellent transit access"
  },
  "walkability": {
    "score": 72,
    "total_amenities": 45,
    "categories": [...]
  },
  "schools": { ... },
  "flood_risk": { "level": "low", "risk_group": 1 },
  "noise": { "level": "moderate" }
}
```

---

## 3. Catchment Analysis
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

## 4. AI Property Valuation
**Get AI-powered property price predictions.**

### Submit Property for Valuation
`POST /valuation`

**Request:**
```json
{
  "latitude": 13.7563,
  "longitude": 100.5018,
  "building_area": 150,
  "land_area": 50,
  "building_age": 5,
  "no_of_floor": 2,
  "building_style": "บ้านเดี่ยว",
  "amphur": "วัฒนา",
  "tumbon": "คลองเตยเหนือ",
  "asking_price": 8000000
}
```

**Response:**
```json
{
  "estimated_price": 7500000,
  "price_range": {
    "min": 6900000,
    "max": 8100000
  },
  "price_per_sqm": 50000,
  "confidence": "high",
  "model_type": "baseline",
  "factors": [
    {
      "name": "building_area",
      "display_name": "Building Area",
      "impact": 1200000,
      "direction": "positive",
      "description": "Larger building area increases value"
    }
  ],
  "comparable_properties": [...],
  "market_insights": {
    "district_avg_price": 7200000,
    "district_price_trend": 3.5,
    "days_on_market_avg": 45
  }
}
```

### List Available Models
`GET /valuation/models`

**Response:**
```json
{
  "models": [
    { "model_type": "baseline", "available": true },
    { "model_type": "baseline_hex2vec", "available": true },
    { "model_type": "hgt", "available": false }
  ],
  "default": "baseline"
}
```

### List User Properties
`GET /valuation/user-properties`

**Query Parameters:**
- `user_id` - Filter by user
- `limit`, `offset` - Pagination

**Response:**
```json
{
  "count": 5,
  "properties": [
    {
      "id": 1,
      "building_style": "บ้านเดี่ยว",
      "building_area": 150,
      "estimated_price": 7500000,
      "created_at": "2026-01-20T10:30:00Z"
    }
  ]
}
```

---

## 5. AI Chat Agent
**Interactive AI assistant for property queries.**

### Send Chat Message
`POST /chat`

**Request:**
```json
{
  "message": "What properties are available in Sukhumvit under 10 million?",
  "conversation_id": "optional-uuid"
}
```

**Response:** Server-Sent Events stream with:
- `thinking` - Agent is processing
- `step` - Tool call in progress
- `token` - Response text token
- `done` - Stream complete

### Send Agent Chat (with Attachments)
`POST /chat/agent`

**Request:**
```json
{
  "messages": [
    { "role": "user", "content": "Analyze this location" }
  ],
  "attachments": [
    {
      "type": "location",
      "data": { "lat": 13.7563, "lon": 100.5018 }
    }
  ]
}
```

**Response:** Server-Sent Events stream.

### Check Agent Status
`GET /chat/status`

**Response:**
```json
{
  "agent_available": true,
  "model": "gemini-2.0-flash",
  "tools_count": 8
}
```

---

## 6. Authentication
**User registration and authentication.**

### Register User
`POST /auth/register`

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "name": "John Doe"
}
```

**Response:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "John Doe",
  "created_at": "2026-01-20T10:30:00Z"
}
```

### Login
`POST /auth/login`

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

---

## 7. Projects & Persistence
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
