#!/usr/bin/env python
"""
Test script to verify the polygon asset workflow implementation.
This script tests the backend components for the draw polygon workflow.
"""

import os
import sys
import json
import django

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CRAproject.settings')
django.setup()

from climate_hazards_analysis_v2.models import Asset
from climate_hazards_analysis_v2.forms import AssetForm
from decimal import Decimal


def test_asset_form():
    """Test the AssetForm validation and functionality."""
    print("Testing AssetForm...")

    # Test valid form data
    form_data = {
        'name': 'Test Building',
        'archetype': 'default archetype'
    }
    form = AssetForm(data=form_data)
    assert form.is_valid(), f"Form should be valid, but errors: {form.errors}"
    print("✓ Valid form data test passed")

    # Test invalid form data (empty name)
    form_data = {
        'name': '',
        'archetype': 'default archetype'
    }
    form = AssetForm(data=form_data)
    assert not form.is_valid(), "Form with empty name should be invalid"
    print("✓ Invalid form data test passed")

    # Test empty archetype
    form_data = {
        'name': 'Test Building',
        'archetype': ''
    }
    form = AssetForm(data=form_data)
    assert not form.is_valid(), "Form with empty archetype should be invalid"
    print("✓ Empty archetype validation test passed")

    print("AssetForm tests completed successfully!\n")


def test_polygon_asset_creation():
    """Test polygon asset creation and functionality."""
    print("Testing polygon asset creation...")

    # Create a test polygon geometry
    polygon_geometry = {
        "type": "Polygon",
        "coordinates": [[
            [-122.4194, 37.7749],  # San Francisco coordinates (example)
            [-122.4184, 37.7759],
            [-122.4174, 37.7749],
            [-122.4184, 37.7739],
            [-122.4194, 37.7749]  # Closing point
        ]]
    }

    # Create a polygon asset
    asset = Asset.objects.create(
        name='Test Polygon Asset',
        archetype='building',
        latitude=Decimal('37.7749'),
        longitude=Decimal('-122.4194'),
        polygon_geometry=polygon_geometry,
        asset_type='polygon',
        session_key='test_session_123'
    )

    # Verify asset creation
    assert asset.id is not None, "Asset should have been created with an ID"
    assert asset.asset_type == 'polygon', "Asset type should be polygon"
    assert asset.polygon_geometry is not None, "Polygon geometry should be stored"

    # Test centroid calculation
    centroid = asset.calculate_polygon_centroid()
    assert centroid is not None, "Centroid should be calculated"
    assert len(centroid) == 2, "Centroid should have 2 coordinates"
    print(f"✓ Calculated centroid: {centroid}")

    # Test GeoJSON output
    geojson = asset.geojson
    assert geojson['type'] == 'Feature', "GeoJSON should be a Feature"
    assert geojson['geometry']['type'] == 'Polygon', "GeoJSON geometry should be Polygon"
    assert geojson['properties']['name'] == 'Test Polygon Asset', "GeoJSON should contain asset name"
    print("✓ GeoJSON output test passed")

    # Test polygon area calculation
    area = asset.get_polygon_area()
    assert area is not None, "Polygon area should be calculated"
    assert area > 0, "Polygon area should be positive"
    print(f"✓ Calculated polygon area: {area}")

    # Clean up
    asset.delete()
    print("Test asset cleaned up")
    print("Polygon asset creation tests completed successfully!\n")


def test_polygon_workflow_data():
    """Test the specific data structure expected by the workflow."""
    print("Testing polygon workflow data structure...")

    # Simulate the data that would come from the frontend drawing workflow
    workflow_data = {
        'name': 'Test Facility',
        'archetype': 'commercial building',
        'geometry': {
            "type": "Polygon",
            "coordinates": [[
                [-122.4194, 37.7749],
                [-122.4184, 37.7759],
                [-122.4174, 37.7749],
                [-122.4184, 37.7739],
                [-122.4194, 37.7749]
            ]]
        }
    }

    # Validate the workflow data
    assert 'name' in workflow_data, "Workflow data should contain name"
    assert 'archetype' in workflow_data, "Workflow data should contain archetype"
    assert 'geometry' in workflow_data, "Workflow data should contain geometry"
    assert workflow_data['geometry']['type'] == 'Polygon', "Geometry should be Polygon type"
    assert len(workflow_data['geometry']['coordinates'][0]) >= 4, "Polygon should have at least 4 points"

    # Test that we can create an asset from this data
    coords = workflow_data['geometry']['coordinates'][0]
    sum_lng = sum(point[0] for point in coords[:-1])
    sum_lat = sum(point[1] for point in coords[:-1])
    n = len(coords) - 1
    centroid_lng = sum_lng / n
    centroid_lat = sum_lat / n

    asset = Asset.objects.create(
        name=workflow_data['name'],
        archetype=workflow_data['archetype'],
        latitude=Decimal(str(centroid_lat)),
        longitude=Decimal(str(centroid_lng)),
        polygon_geometry=workflow_data['geometry'],
        asset_type='polygon',
        session_key='test_workflow_session'
    )

    # Verify the asset matches the workflow expectations
    assert asset.name == workflow_data['name'], "Asset name should match workflow data"
    assert asset.archetype == workflow_data['archetype'], "Asset archetype should match workflow data"
    assert asset.asset_type == 'polygon', "Asset should be polygon type"

    # Clean up
    asset.delete()
    print("Workflow test asset cleaned up")
    print("Polygon workflow data structure tests completed successfully!\n")


def main():
    """Run all tests."""
    print("=" * 60)
    print("TESTING POLYGON ASSET WORKFLOW IMPLEMENTATION")
    print("=" * 60)

    try:
        test_asset_form()
        test_polygon_asset_creation()
        test_polygon_workflow_data()

        print("=" * 60)
        print("✅ ALL TESTS PASSED SUCCESSFULLY!")
        print("The polygon asset workflow backend is ready.")
        print("=" * 60)

    except Exception as e:
        print(f"❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()