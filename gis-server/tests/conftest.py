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
