"""
Shared pytest fixtures for the test suite.

This file is automatically loaded by pytest and provides common fixtures
that can be used across all test files.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

# Add the gis-server directory to the path so imports work correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def app():
    """
    Create FastAPI app instance for testing.

    This fixture has session scope to avoid recreating the app for each test.
    Note: The lifespan context manager may attempt to load resources.
    """
    from main import app

    return app


@pytest.fixture(scope="session")
def client(app):
    """
    Create a TestClient for making HTTP requests to the FastAPI app.

    Uses session scope for efficiency. The client doesn't raise server errors
    automatically, allowing tests to check error responses.
    """
    from fastapi.testclient import TestClient

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def mock_db_session():
    """
    Create a mock database session for unit tests.

    This allows testing service methods without a real database connection.
    """
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = None
    session.execute.return_value.fetchall.return_value = []
    return session


@pytest.fixture
def sample_coordinates():
    """
    Sample coordinates for testing (Bangkok area).

    Returns a dict with lat/lon for common test locations.
    """
    return {
        "siam_paragon": {"lat": 13.7466, "lon": 100.5348},
        "asoke": {"lat": 13.7371, "lon": 100.5603},
        "silom": {"lat": 13.7286, "lon": 100.5343},
        "random_bangkok": {"lat": 13.75, "lon": 100.55},
    }


@pytest.fixture
def sample_property_data():
    """
    Sample property data for testing price prediction.
    """
    return {
        "lat": 13.75,
        "lon": 100.55,
        "building_area": 150.0,
        "land_area": 50.0,
        "building_age": 10.0,
        "no_of_floor": 2,
        "building_style": "บ้านเดี่ยว",
    }


# ============ Agent/Chat Test Fixtures ============


@pytest.fixture
def sample_chat_messages():
    """
    Sample chat messages for testing agent endpoints.
    Includes both Thai and English examples.
    """
    return [
        {"role": "user", "content": "หาบ้านในบางกะปิ"},
        {"role": "assistant", "content": "ฉันจะช่วยหาบ้านในบางกะปิ..."},
        {"role": "user", "content": "Find houses under 5 million baht"},
    ]


@pytest.fixture
def sample_location_attachment():
    """
    Sample location attachment (pin on map).
    """
    return {
        "id": "loc-12345",
        "type": "location",
        "data": {"lat": 13.7563, "lon": 100.5018},
        "label": "Location (13.7563, 100.5018)",
    }


@pytest.fixture
def sample_bbox_attachment():
    """
    Sample bounding box attachment (area selection on map).
    """
    return {
        "id": "bbox-12345",
        "type": "bbox",
        "data": {
            "corners": [
                [100.49, 13.74],
                [100.51, 13.74],
                [100.51, 13.76],
                [100.49, 13.76],
            ],
            "minLon": 100.49,
            "maxLon": 100.51,
            "minLat": 13.74,
            "maxLat": 13.76,
        },
        "label": "Area (2.2km x 2.2km)",
    }


@pytest.fixture
def sample_bangkok_bbox():
    """
    Sample Bangkok bounding box coordinates for spatial queries.
    """
    return {
        "min_lat": 13.65,
        "max_lat": 13.85,
        "min_lon": 100.40,
        "max_lon": 100.70,
    }


@pytest.fixture
def mock_agent_settings():
    """
    Mock agent settings for testing without a real API key.
    """
    from unittest.mock import patch

    with patch("src.config.agent_settings.agent_settings") as mock:
        mock.is_configured = False
        mock.AGENT_MODEL = "gemini-2.5-flash-lite"
        mock.AGENT_MAX_ITERATIONS = 5
        mock.AGENT_MAX_TOKENS_PER_TURN = 4096
        yield mock
