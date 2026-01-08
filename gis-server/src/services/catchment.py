import json
import logging
import os

import geopandas as gpd
import networkx as nx
import osmnx as ox
from shapely.geometry import Point
from sqlalchemy import text
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CatchmentService:
    def __init__(self):
        self.graph = None
        self.graph_path = "data/bangkok_graph.graphml"

    def load_graph(self):
        """Loads the graph from disk or downloads it if missing."""
        if os.path.exists(self.graph_path):
            logger.info(f"Loading graph from {self.graph_path}...")
            self.graph = ox.load_graphml(self.graph_path)
        else:
            logger.info(
                "Graph file not found. Downloading Bangkok graph (this may take a while)..."
            )
            # Download a smaller area for MVP speed, or the whole city for prod
            # Using a central point and radius for now to keep it manageable
            self.graph = ox.graph_from_point(
                (13.7563, 100.5018), dist=5000, network_type="walk"
            )
            # Save for next time
            ox.save_graphml(self.graph, self.graph_path)

        if self.graph is None:
            logger.error("Failed to load graph.")
            return

        # Pre-calculate travel times for different modes
        # Walk Speed: 5 km/h = 83.33 m/min
        walk_speed = 5 * 1000 / 60
        # Drive Speed: 30 km/h = 500 m/min (Conservative city speed)
        drive_speed = 30 * 1000 / 60

        for _u, _v, _k, data in self.graph.edges(data=True, keys=True):
            length = data.get("length", 0)
            data["time_walk"] = length / walk_speed
            data["time_drive"] = length / drive_speed

        logger.info("Graph loaded successfully.")

    def get_isochrone(
        self, lat: float, lon: float, minutes: int, mode: str = "walk"
    ) -> dict | None:
        try:
            if self.graph is None:
                self.load_graph()

            if self.graph is None:
                logger.error("Failed to load graph.")
                return None

            # Select weight attribute based on mode
            weight_attr = "time_walk"
            if mode == "drive":
                weight_attr = "time_drive"

            # 2. Find center node
            # OSMnx v1.0+ uses ox.nearest_nodes
            center_node = ox.nearest_nodes(self.graph, lon, lat)

            # 3. Calculate isochrone
            subgraph = nx.ego_graph(
                self.graph, center_node, radius=minutes, distance=weight_attr
            )  # 4. Create polygon
            node_points = [
                Point((data["x"], data["y"]))
                for _node, data in subgraph.nodes(data=True)
            ]
            if not node_points:
                return None

            # Use convex hull for simplicity
            isochrone_poly = gpd.GeoSeries(node_points).unary_union.convex_hull

            return json.loads(gpd.GeoSeries([isochrone_poly]).to_json())["features"][0][
                "geometry"
            ]

        except Exception:
            logger.exception("Error calculating isochrone")
            return None

    def calculate_population(self, db: Session, isochrone_geom: dict) -> int:
        """
        Calculates the total population within the isochrone geometry using areal interpolation.
        """
        try:
            # Convert GeoJSON dict to string for PostGIS
            geom_json = json.dumps(isochrone_geom)

            # Use ST_Intersection to calculate the exact overlap area
            # population = sum(density * overlap_area)
            # Assuming population_density is people per square km (based on / 1000000.0 factor)

            query = text(
                """
                SELECT
                    SUM(
                        population_density *
                        (ST_Area(ST_Intersection(geometry::geography, ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)::geography)) / ST_Area(geometry::geography))
                    )
                FROM population_grid
                WHERE ST_Intersects(geometry, ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326))
            """
            )

            result = db.execute(query, {"geom": geom_json}).scalar()
            return int(result) if result else 0
        except Exception:
            logger.exception("Error calculating population")
            return 0

    def get_nearest_road_type(self, lat: float, lon: float) -> str | None:
        """
        Finds the type of the nearest road (highway tag) to the given coordinates.
        """
        try:
            if self.graph is None:
                self.load_graph()

            if self.graph is None:
                return None

            # Find nearest edge
            # X is longitude, Y is latitude
            u, v, key = ox.nearest_edges(self.graph, X=lon, Y=lat)
            edge_data = self.graph.get_edge_data(u, v, key)
            highway = edge_data.get("highway")

            # Handle list of tags (sometimes an edge has multiple types)
            if isinstance(highway, list):
                return highway[0]
            return highway
        except Exception:
            logger.exception("Error finding nearest road type")
            return None


# Singleton instance to be shared across routes
catchment_service = CatchmentService()
