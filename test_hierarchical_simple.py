#!/usr/bin/env python
"""
Simple test script to verify the hierarchical polygon exposure data structure.
This script tests the prepare_hierarchical_exposure_data function with sample data.
"""

import os
import sys
import django

# Setup Django environment
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'CRAproject'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from climate_hazards_analysis_v2.models import Asset, GranularAnalysisResult
from climate_hazards_analysis_v2.granular_utils import prepare_hierarchical_exposure_data


def test_hierarchical_data_structure():
    """Test the hierarchical data preparation function."""

    print("Testing hierarchical polygon exposure data structure...")

    try:
        # Find a polygon asset with granular analysis
        assets = Asset.objects.filter(
            asset_type='polygon',
            has_granular_analysis=True
        ).first()

        if not assets:
            print("No polygon assets with granular analysis found.")
            print("Creating a test asset...")

            # Create a test polygon asset
            test_asset = Asset.objects.create(
                name='Test Polygon Asset',
                archetype='test archetype',
                latitude=40.7128,
                longitude=-74.0060,
                asset_type='polygon',
                polygon_geometry={
                    'type': 'Polygon',
                    'coordinates': [[
                        [-74.01, 40.71],
                        [-74.00, 40.71],
                        [-74.00, 40.72],
                        [-74.01, 40.72],
                        [-74.01, 40.71]
                    ]]
                },
                has_granular_analysis=True,
                granular_analysis_status='completed',
                granular_grid_spacing=0.001,
                granular_grid_points_count=4
            )

            # Create some test granular results
            hazards = ['Heat', 'Flood']
            grid_points = [
                (40.710, -74.010, 0, 0),
                (40.710, -74.000, 0, 1),
                (40.720, -74.000, 1, 1),
                (40.720, -74.010, 1, 0)
            ]

            for lat, lng, row, col in grid_points:
                for hazard in hazards:
                    GranularAnalysisResult.objects.create(
                        asset=test_asset,
                        latitude=lat,
                        longitude=lng,
                        grid_row=row,
                        grid_col=col,
                        grid_spacing=0.001,
                        hazard_type=hazard,
                        scenario='current',
                        result_data={
                            'value': 25.5 + row * 5 + col * 2,
                            'risk_level': 'medium' if row == 0 else 'high',
                            'unit': 'celsius' if hazard == 'Heat' else 'meters'
                        },
                        processing_status='completed'
                    )

            asset = test_asset
            selected_hazards = hazards
        else:
            asset = assets
            # Get some sample hazards for this asset
            asset_hazards = GranularAnalysisResult.objects.filter(
                asset=asset,
                processing_status='completed'
            ).values_list('hazard_type', flat=True).distinct()
            selected_hazards = list(asset_hazards[:2])  # Test with first 2 hazards

        print(f"SUCCESS: Found asset: {asset.name}")
        print(f"SUCCESS: Selected hazards: {selected_hazards}")

        # Test the hierarchical data preparation
        result = prepare_hierarchical_exposure_data(asset, selected_hazards)

        if result.get('success'):
            print("SUCCESS: Hierarchical data preparation successful!")
            print(f"SUCCESS: Total rows: {len(result['data'])}")
            print(f"SUCCESS: Columns: {result['columns']}")
            print(f"SUCCESS: Grid points count: {result['grid_points_count']}")

            # Verify structure
            data = result['data']
            if len(data) > 0:
                parent_row = data[0]
                print(f"SUCCESS: Parent row: {parent_row['name']} (type: {parent_row['type']})")
                print(f"SUCCESS: Parent has children: {parent_row.get('children_count', 0)}")

                if len(data) > 1:
                    child_rows = data[1:]
                    print(f"SUCCESS: Number of child rows: {len(child_rows)}")

                    # Check first child row structure
                    first_child = child_rows[0]
                    print(f"SUCCESS: First child: {first_child['name']}")
                    print(f"SUCCESS: Child hazards: {list(first_child['hazards'].keys())}")

                    # Verify hazard data structure
                    for hazard in selected_hazards:
                        if hazard in first_child['hazards']:
                            hazard_data = first_child['hazards'][hazard]
                            print(f"SUCCESS: {hazard} data - Value: {hazard_data.get('value')}, "
                                  f"Risk: {hazard_data.get('risk_level')}")

                print("\nSample hierarchical structure:")
                print("Parent (Centroid):")
                print(f"  - Name: {parent_row['name']}")
                print(f"  - Location: {parent_row['latitude']}, {parent_row['longitude']}")
                print(f"  - Type: {parent_row['asset_type']}")

                for hazard in selected_hazards:
                    if hazard in parent_row['hazards']:
                        hazard_stats = parent_row['hazards'][hazard]
                        print(f"  - {hazard} Stats: Mean={hazard_stats.get('mean_value', 'N/A'):.2f}, "
                              f"Points={hazard_stats.get('point_count', 0)}")

                if len(data) > 1:
                    print("\nChildren (Grid Points):")
                    for i, child in enumerate(child_rows[:3]):  # Show first 3 children
                        print(f"  - {child['name']}: {child['latitude']:.4f}, {child['longitude']:.4f}")
                        for hazard in selected_hazards:
                            if hazard in child['hazards']:
                                hazard_data = child['hazards'][hazard]
                                print(f"    * {hazard}: {hazard_data.get('value', 'N/A')} ({hazard_data.get('risk_level', 'N/A')})")
                        if i >= 2:  # Limit output
                            break

                    if len(child_rows) > 3:
                        print(f"  ... and {len(child_rows) - 3} more grid points")

            print("\nHierarchical data structure test PASSED!")
            return True

        else:
            print(f"ERROR: Hierarchical data preparation failed: {result.get('error')}")
            return False

    except Exception as e:
        print(f"ERROR: Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_data_structure_consistency():
    """Test that the data structure is consistent and well-formed."""

    print("\nTesting data structure consistency...")

    try:
        # Get a polygon asset with granular analysis
        asset = Asset.objects.filter(
            asset_type='polygon',
            has_granular_analysis=True
        ).first()

        if not asset:
            print("WARNING: No assets found for consistency test")
            return True

        # Get hazards for this asset
        hazards = list(GranularAnalysisResult.objects.filter(
            asset=asset,
            processing_status='completed'
        ).values_list('hazard_type', flat=True).distinct()[:2])

        if not hazards:
            print("WARNING: No completed analysis results found")
            return True

        result = prepare_hierarchical_exposure_data(asset, hazards)

        if not result.get('success'):
            print(f"ERROR: Failed to prepare data: {result.get('error')}")
            return False

        data = result['data']
        columns = result['columns']

        # Verify parent row structure
        parent_row = data[0]
        required_parent_fields = ['id', 'type', 'name', 'latitude', 'longitude', 'is_parent', 'hazards']
        for field in required_parent_fields:
            if field not in parent_row:
                print(f"ERROR: Missing required field in parent row: {field}")
                return False

        # Verify child rows structure
        for child in data[1:]:
            required_child_fields = ['id', 'type', 'parent_id', 'name', 'latitude', 'longitude', 'is_parent', 'hazards']
            for field in required_child_fields:
                if field not in child:
                    print(f"ERROR: Missing required field in child row: {field}")
                    return False

            # Verify parent reference
            if child['parent_id'] != parent_row['id']:
                print(f"ERROR: Child parent_id mismatch: {child['parent_id']} != {parent_row['id']}")
                return False

        # Verify hazard data consistency
        for row in data:
            for hazard in hazards:
                if hazard not in row['hazards']:
                    print(f"ERROR: Missing hazard data for {hazard} in row {row['name']}")
                    return False

        print("SUCCESS: Data structure consistency test PASSED!")
        return True

    except Exception as e:
        print(f"ERROR: Consistency test failed: {str(e)}")
        return False


if __name__ == '__main__':
    print("Starting hierarchical polygon exposure table tests...\n")

    success1 = test_hierarchical_data_structure()
    success2 = test_data_structure_consistency()

    if success1 and success2:
        print("\nAll tests PASSED! The hierarchical data structure is ready for use.")
        sys.exit(0)
    else:
        print("\nSome tests FAILED. Please check the implementation.")
        sys.exit(1)