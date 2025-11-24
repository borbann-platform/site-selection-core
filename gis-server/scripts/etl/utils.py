import ast
import logging

from shapely import wkt
from shapely.geometry import Point


def parse_lat_lon_string(coord_str):
    """
    Parses a string like "[13.744456,100.516447]" into a Shapely Point.
    Returns None if parsing fails.
    """
    try:
        # Use ast.literal_eval for safe evaluation of the list string
        coords = ast.literal_eval(coord_str)
        if isinstance(coords, list) and len(coords) == 2:
            # GeoAlchemy2 expects WKBElement or WKT string, or Shapely geometry
            # Note: Shapely Point is (x, y) -> (lon, lat)
            # The input string seems to be [lat, lon] based on the values (13.x, 100.x)
            lat, lon = coords
            return Point(lon, lat)
    except (ValueError, SyntaxError):
        logging.warning(f"Failed to parse coordinate string: {coord_str}")
    return None


def parse_wkt_geometry(wkt_str):
    """
    Parses a WKT string into a Shapely geometry.
    """
    try:
        return wkt.loads(wkt_str)
    except Exception as e:
        logging.warning(f"Failed to parse WKT: {wkt_str}, error: {e}")
        return None


def clean_float(val):
    """
    Safely converts a value to float.
    """
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def clean_int(val):
    """
    Safely converts a value to int.
    """
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
