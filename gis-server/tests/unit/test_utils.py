"""
Unit tests for utility functions and helpers.

Tests general utility functions that don't require external dependencies.
"""

import pytest


class TestH3Integration:
    """Tests for H3 hexagon functionality."""

    def test_h3_import(self):
        """Test that h3 library is available."""
        import h3

        assert hasattr(h3, "latlng_to_cell")
        assert hasattr(h3, "cell_to_latlng")

    def test_h3_latlng_to_cell(self):
        """Test converting lat/lon to H3 cell index."""
        import h3

        # Bangkok coordinates
        lat, lon = 13.75, 100.55
        resolution = 9

        h3_index = h3.latlng_to_cell(lat, lon, resolution)

        # H3 index should be a string
        assert isinstance(h3_index, str)
        # H3 index at resolution 9 has specific format
        assert len(h3_index) == 15  # H3 indexes are 15 chars

    def test_h3_cell_contains_coordinates(self):
        """Test that H3 cell center is near original coordinates."""
        import h3

        lat, lon = 13.75, 100.55
        resolution = 9

        h3_index = h3.latlng_to_cell(lat, lon, resolution)
        center_lat, center_lon = h3.cell_to_latlng(h3_index)

        # Center should be close to original (within ~1km for res 9)
        assert abs(center_lat - lat) < 0.01
        assert abs(center_lon - lon) < 0.01


class TestNumpyOperations:
    """Tests for numpy operations used in the codebase."""

    def test_numpy_available(self):
        """Test that numpy is available."""
        import numpy as np

        assert hasattr(np, "array")
        assert hasattr(np, "mean")

    def test_expm1_inverse_of_log1p(self):
        """Test that expm1 is the inverse of log1p (used in price conversion)."""
        import numpy as np

        original_price = 5_000_000.0
        log_price = np.log1p(original_price)
        recovered_price = np.expm1(log_price)

        assert recovered_price == pytest.approx(original_price, rel=1e-10)
