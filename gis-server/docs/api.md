# API Documentation

Base URL: `http://localhost:8000/api/v1`

## 1. Site Analysis
**Analyze a potential location.**

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
**Manage user projects and saved sites.**

### Create Project
`POST /projects`

**Request:**
```json
{
  "name": "My New Branch",
  "description": "Expansion plan Q4"
}
```

### Get Project Dashboard
`GET /projects/{project_id}/dashboard`

**Response:** List of saved sites with their analysis data.

### Save Site to Project
`POST /projects/{project_id}/sites`

**Request:**
```json
{
  "name": "Site A - Siam",
  "latitude": 13.7563,
  "longitude": 100.5018,
  "score": 0.75,
  "notes": "Good foot traffic"
}
```

---

## 4. Scoring Methodology

### Road Tier Filter (Implemented)
We use a "Road Tier Filter" to adjust the site score based on the accessibility of the nearest road.
- **Highways/Expressways:** Score multiplier = 0.0 (Location is inaccessible). Returns a warning.
- **Service Roads:** Score multiplier = 0.6 (Low visibility). Returns a warning.
- **Pedestrian/Footways:** Score multiplier = 1.2 (High foot traffic bonus).
- **Other Roads:** Score multiplier = 1.0.

### Future Improvements (Not Implemented)
- **Snapping Validator:** Reject points that are too far (>50m) or too close (<2m) to a road.
- **Projection Correction:** Automatically snap user clicks to the nearest valid building frontage before analysis.
