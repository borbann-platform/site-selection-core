import logging

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AnalyticsService:
    def calculate_cannibalization(
        self,
        db: Session,
        new_site: dict,
        existing_sites: list[dict],
        beta: float = 2.0,
    ) -> dict:
        """
        Calculates the cannibalization impact using the Huff Gravity Model.

        Args:
            db: Database session
            new_site: Dict with 'lat', 'lon'
            existing_sites: List of dicts with 'id', 'lat', 'lon'
            beta: Distance decay parameter (default 2.0)

        Returns:
            Dict containing total expected visits and breakdown per site.

        """
        try:
            # 1. Fetch Demand Points (Demographic Grid Centroids)
            # We need the centroid (lat/lon) and the population count
            query = text(
                """
                SELECT 
                    grid_id, 
                    ST_Y(ST_Centroid(geometry::geometry)) as lat, 
                    ST_X(ST_Centroid(geometry::geometry)) as lon,
                    (COALESCE(population_density, 0) * (ST_Area(geometry::geography) / 1000000.0)) as population
                FROM demographics
                LIMIT 5000 -- Limit for performance in MVP
            """
            )
            results = db.execute(query).fetchall()

            if not results:
                return {"error": "No demographic data found"}

            # Convert to numpy arrays for vectorized calculation
            demand_points = np.array([(r.lat, r.lon) for r in results])
            population = np.array([r.population for r in results])

            # 2. Prepare Supply Points (Sites)
            # Index 0 is the NEW site
            all_sites = [new_site, *existing_sites]
            site_coords = np.array([(s["lat"], s["lon"]) for s in all_sites])

            # 3. Calculate Distance Matrix (Demand x Supply)
            # Using Haversine approximation or simple Euclidean for small areas
            # For speed/simplicity in numpy, we'll use Euclidean on lat/lon (approximate)
            # For better accuracy, we should use Haversine. Let's implement a quick vectorized Haversine.

            def haversine_vectorized(lat1, lon1, lat2, lon2):
                r_earth = 6371  # Earth radius in km
                phi1, phi2 = np.radians(lat1), np.radians(lat2)
                dphi = np.radians(lat2 - lat1)
                dlambda = np.radians(lon2 - lon1)
                a = (
                    np.sin(dphi / 2) ** 2
                    + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
                )
                c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
                return r_earth * c

            # Expand dimensions for broadcasting
            # demand_points: (N, 2) -> lat: (N, 1), lon: (N, 1)
            d_lat = demand_points[:, 0][:, np.newaxis]
            d_lon = demand_points[:, 1][:, np.newaxis]

            # site_coords: (M, 2) -> lat: (1, M), lon: (1, M)
            s_lat = site_coords[:, 0][np.newaxis, :]
            s_lon = site_coords[:, 1][np.newaxis, :]

            distances = haversine_vectorized(d_lat, d_lon, s_lat, s_lon)

            # Avoid division by zero (if site is exactly on a grid center)
            distances = np.maximum(distances, 0.01)

            # 4. Calculate Attractiveness (A_j)
            # Assuming equal attractiveness (1.0) for all sites for now
            attractiveness = np.ones(len(all_sites))

            # 5. Calculate Probabilities (Huff Model)
            # P_ij = (A_j / D_ij^beta) / Sum(A_k / D_ik^beta)

            numerator = attractiveness / (distances**beta)
            denominator = numerator.sum(axis=1)[:, np.newaxis]

            probabilities = numerator / denominator

            # 6. Calculate Expected Patronage
            # Expected Visits = Sum(P_ij * Population_i)
            expected_visits = (probabilities * population[:, np.newaxis]).sum(axis=0)

            # 7. Format Results
            new_site_visits = float(expected_visits[0])
            cannibalization_impact = []

            for i, site in enumerate(existing_sites):
                # Index in expected_visits is i + 1 because index 0 is the new site
                visits = float(expected_visits[i + 1])
                cannibalization_impact.append(
                    {
                        "site_id": site.get("id", f"site_{i}"),
                        "retained_visits": visits,
                        # To calculate "lost" visits, we'd need to run the model WITHOUT the new site
                        # and compare. For MVP, we just return the new equilibrium.
                    }
                )

            return {
                "new_site_prediction": {
                    "expected_visits": new_site_visits,
                    "market_share": float(new_site_visits / population.sum()),
                },
                "existing_sites_impact": cannibalization_impact,
                "total_market_population": float(population.sum()),
            }

        except Exception as e:
            logger.exception("Error calculating cannibalization")
            return {"error": str(e)}


analytics_service = AnalyticsService()
