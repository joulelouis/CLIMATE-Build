"""
Climate Hazards Analysis V2 Test Package

This package contains comprehensive test suites for the Climate Hazards Analysis V2
Django application, with a focus on Upload Asset Data and Granular Analysis workflows.

Test Categories:
- Unit tests for views, models, and utility functions
- Integration tests for complete workflows
- Granular analysis workflow tests
- Performance tests for large file handling
- Security tests for file upload validation
- Error handling and edge case tests

Key Features:
- Comprehensive test coverage (80%+ goal)
- Mock data factory for consistent test data
- Support for multiple file formats (CSV, Excel, Shapefile, GeoPackage)
- Performance benchmarking capabilities
- Security validation testing
- Cross-platform compatibility
- End-to-end granular analysis workflow testing

Usage:
    python manage.py test climate_hazards_analysis_v2.tests

    # With coverage
    coverage run --source='climate_hazards_analysis_v2' manage.py test climate_hazards_analysis_v2.tests
    coverage report

    # Specific test categories
    python manage.py test climate_hazards_analysis_v2.tests.test_upload_asset_data -k "upload"
    python manage.py test climate_hazards_analysis_v2.tests.test_granular_workflow -k "granular"
"""

# Test package configuration
TEST_SETTINGS_MODULE = 'climate_hazards_analysis_v2.tests.settings_test'

# Export test utilities
from .fixtures.test_data_factory import TestDataFactory

__all__ = [
    'TestDataFactory',
    'TEST_SETTINGS_MODULE',
]