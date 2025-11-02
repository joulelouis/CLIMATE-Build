"""
Test fixtures package for Climate Hazards Analysis V2.

This package contains test data factories, mock objects, and sample files
for comprehensive testing of the upload asset data functionality.

Key Components:
- TestDataFactory: Factory for creating test files and mock data
- Sample CSV, Excel, and geospatial files
- Invalid and malformed files for error testing
- Database fixtures for consistent test data

Usage:
    from tests.fixtures.test_data_factory import TestDataFactory

    # Create test files
    csv_file = TestDataFactory.create_valid_csv_file()
    excel_file = TestDataFactory.create_excel_file()

    # Create mock data
    mock_assets = TestDataFactory.create_mock_asset_objects()
"""

from .test_data_factory import TestDataFactory

__all__ = ['TestDataFactory']