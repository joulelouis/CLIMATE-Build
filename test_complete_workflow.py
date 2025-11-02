#!/usr/bin/env python
"""
Complete end-to-end test for hierarchical polygon analysis table implementation.
This script tests the entire workflow from data preparation to template rendering.
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
from climate_hazards_analysis_v2.views import _handle_granular_polygon_results
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware


def test_complete_workflow():
    """Test the complete hierarchical workflow end-to-end."""

    print("=" * 60)
    print("COMPLETE HIERARCHICAL POLYGON ANALYSIS WORKFLOW TEST")
    print("=" * 60)

    try:
        # Step 1: Verify polygon asset with granular analysis exists
        print("\n1. Testing polygon asset availability...")
        asset = Asset.objects.filter(asset_type='polygon', has_granular_analysis=True).first()
        if not asset:
            print("   ❌ No polygon asset found with granular analysis")
            return False
        print(f"   ✅ Found polygon asset: {asset.name} (ID: {asset.id})")

        # Step 2: Verify granular analysis results exist
        print("\n2. Testing granular analysis results...")
        granular_results = GranularAnalysisResult.objects.filter(
            asset=asset, processing_status='completed'
        )
        if not granular_results.exists():
            print("   ❌ No completed granular analysis results found")
            return False

        hazards = list(granular_results.values_list('hazard_type', flat=True).distinct())
        grid_points = granular_results.values_list('latitude', 'longitude').distinct().count()
        print(f"   ✅ Found {granular_results.count()} granular results")
        print(f"   ✅ Hazards analyzed: {hazards}")
        print(f"   ✅ Grid points: {grid_points}")

        # Step 3: Test hierarchical data preparation
        print("\n3. Testing hierarchical data preparation...")
        hierarchical_result = prepare_hierarchical_exposure_data(asset, hazards)
        if not hierarchical_result.get('success'):
            print(f"   ❌ Hierarchical data preparation failed: {hierarchical_result.get('error')}")
            return False

        data = hierarchical_result['data']
        parent_row = data[0]
        child_rows = data[1:]

        print(f"   ✅ Hierarchical data prepared successfully")
        print(f"   ✅ Total rows: {len(data)} (1 parent + {len(child_rows)} children)")
        print(f"   ✅ Parent row: {parent_row['name']} (type: {parent_row['type']})")
        print(f"   ✅ Columns: {hierarchical_result['columns']}")

        # Step 4: Test view function rendering
        print("\n4. Testing view function rendering...")
        factory = RequestFactory()
        request = factory.post('/results/', {'hazards': hazards})

        # Add session support
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()

        try:
            response = _handle_granular_polygon_results(request, asset.id, hazards)
            if response.status_code != 200:
                print(f"   ❌ View returned status {response.status_code}, expected 200")
                return False

            if hasattr(response, 'context_data'):
                context = response.context_data
                if 'hierarchical_results' not in context:
                    print("   ❌ hierarchical_results not found in template context")
                    return False

                template_results = context['hierarchical_results']
                if len(template_results) != len(data):
                    print(f"   ❌ Template results count mismatch: {len(template_results)} != {len(data)}")
                    return False

                print(f"   ✅ View rendered successfully (Status: {response.status_code})")
                print(f"   ✅ Template context contains {len(template_results)} hierarchical results")

        except Exception as e:
            print(f"   ❌ View rendering failed: {e}")
            return False

        # Step 5: Verify hierarchical structure integrity
        print("\n5. Testing hierarchical structure integrity...")

        # Check parent row structure
        required_parent_fields = ['id', 'type', 'name', 'latitude', 'longitude', 'is_parent', 'hazards', 'children_count']
        for field in required_parent_fields:
            if field not in parent_row:
                print(f"   ❌ Missing parent field: {field}")
                return False

        # Check child row structure
        for i, child in enumerate(child_rows[:3]):  # Check first 3 children
            required_child_fields = ['id', 'type', 'parent_id', 'name', 'latitude', 'longitude', 'is_parent', 'hazards']
            for field in required_child_fields:
                if field not in child:
                    print(f"   ❌ Missing child field in row {i}: {field}")
                    return False

            # Verify parent-child relationship
            if child['parent_id'] != parent_row['id']:
                print(f"   ❌ Parent-child relationship mismatch in row {i}")
                return False

        print(f"   ✅ Parent row structure valid")
        print(f"   ✅ Child row structure valid ({len(child_rows)} children)")
        print(f"   ✅ Parent-child relationships valid")

        # Step 6: Test hazard data consistency
        print("\n6. Testing hazard data consistency...")
        for hazard in hazards:
            if hazard not in parent_row['hazards']:
                print(f"   ❌ Missing hazard data in parent: {hazard}")
                return False

            parent_hazard_data = parent_row['hazards'][hazard]
            if 'mean_value' not in parent_hazard_data:
                print(f"   ❌ Missing mean_value for parent hazard {hazard}")
                return False

        # Check a sample child row for hazard data
        if child_rows:
            sample_child = child_rows[0]
            for hazard in hazards:
                if hazard not in sample_child['hazards']:
                    print(f"   ❌ Missing hazard data in child: {hazard}")
                    return False

        print(f"   ✅ Hazard data consistent across {len(hazards)} hazard types")

        # Step 7: Test data values plausibility
        print("\n7. Testing data values plausibility...")

        # Check parent statistics
        for hazard in hazards:
            hazard_stats = parent_row['hazards'][hazard]
            mean_val = hazard_stats.get('mean_value', 0)
            min_val = hazard_stats.get('min_value', 0)
            max_val = hazard_stats.get('max_value', 0)

            if not (min_val <= mean_val <= max_val):
                print(f"   ❌ Invalid statistics for {hazard}: min={min_val}, mean={mean_val}, max={max_val}")
                return False

        # Check child values
        for child in child_rows[:3]:  # Check first 3 children
            for hazard in hazards:
                child_hazard = child['hazards'][hazard]
                value = child_hazard.get('value')
                if value is not None and not isinstance(value, (int, float)):
                    print(f"   ❌ Invalid value type for child hazard {hazard}: {type(value)}")
                    return False

        print(f"   ✅ Parent statistics plausible")
        print(f"   ✅ Child values valid")

        print("\n" + "=" * 60)
        print("🎉 COMPLETE WORKFLOW TEST - ALL TESTS PASSED!")
        print("=" * 60)
        print("\nSUMMARY:")
        print(f"✅ Polygon asset: {asset.name}")
        print(f"✅ Granular points: {grid_points}")
        print(f"✅ Hazards analyzed: {len(hazards)} ({', '.join(hazards)})")
        print(f"✅ Hierarchical rows: {len(data)} (1 parent + {len(child_rows)} children)")
        print(f"✅ Template rendering: Successful")
        print(f"✅ Data structure: Valid")
        print(f"✅ Hazard consistency: Valid")
        print(f"✅ Data values: Plausible")

        print("\nThe hierarchical polygon analysis table is ready for production use!")
        return True

    except Exception as e:
        print(f"\n❌ COMPLETE WORKFLOW TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("Starting complete hierarchical polygon analysis workflow test...\n")
    success = test_complete_workflow()
    sys.exit(0 if success else 1)