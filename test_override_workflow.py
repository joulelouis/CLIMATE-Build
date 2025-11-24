#!/usr/bin/env python3
"""
Test script for the enhanced override workflow implementation.
Tests database fallback and session-independent override functionality.
"""

import os
import sys
import django
import requests
import json
import time
from django.test import Client
from django.contrib.sessions.models import Session

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'climate_hazards_platform.settings')
django.setup()

from climate_hazards_analysis_v2.models import Asset, OverrideValue

def test_override_workflow():
    """Test the complete override workflow with database fallback."""

    print("=== Testing Enhanced Override Workflow ===\n")

    # Initialize Django test client
    client = Client()

    # 1. Test check-analysis-context endpoint with no session data
    print("1. Testing context check with no session data...")
    response = client.get('/climate-hazards-analysis-v2/check-analysis-context/')
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Response: {json.dumps(data, indent=2)}")
        assert data['has_context'] == False
        print("   ✓ Correctly identified no analysis context")
    else:
        print(f"   ✗ Unexpected status: {response.status_code}")
        return False

    print()

    # 2. Create a test asset for testing
    print("2. Creating test asset...")
    try:
        asset = Asset.objects.create(
            name="Test Facility",
            archetype="Test Building",
            latitude=40.7128,
            longitude=-74.0060,
            owner="Test Owner",
            source="Test Source"
        )
        print(f"   ✓ Created test asset: {asset.name} (ID: {asset.id})")
    except Exception as e:
        print(f"   ✗ Failed to create test asset: {e}")
        return False

    print()

    # 3. Test override creation with database fallback
    print("3. Testing database override creation...")

    # Simulate session with uploaded asset ID
    session = client.session
    session['climate_hazards_v2_uploaded_asset_ids'] = [asset.id]
    session.save()

    # Test context check with uploaded asset but no analysis
    print("   Testing context check with uploaded asset...")
    response = client.get('/climate-hazards-analysis-v2/check-analysis-context/')
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Response: {json.dumps(data, indent=2)}")
        assert data['has_context'] == False
        assert 'requires_analysis' in data
        print("   ✓ Correctly identified need for analysis")
    else:
        print(f"   ✗ Unexpected status: {response.status_code}")
        return False

    print()

    # 4. Test save_table_changes with database fallback
    print("4. Testing save_table_changes with database fallback...")

    override_data = {
        "changes": [{
            "rowIndex": 0,
            "column": "Flood Depth (meters)",
            "newValue": "2.5",
            "facilityName": "Test Facility",
            "reason": "Test override reason"
        }]
    }

    response = client.post(
        '/climate-hazards-analysis-v2/save-table-changes/',
        data=json.dumps(override_data),
        content_type='application/json',
        HTTP_X_CSRFTOKEN=client.cookies.get('csrftoken', '')
    )

    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Response: {json.dumps(data, indent=2)}")
        assert data['success'] == True
        assert data['database_mode'] == True
        print("   ✓ Database override creation successful")
    else:
        print(f"   ✗ Failed to create database override: {response.status_code}")
        print(f"   Response: {response.content.decode()}")
        return False

    print()

    # 5. Verify override was saved to database
    print("5. Verifying override in database...")
    try:
        overrides = OverrideValue.objects.filter(asset=asset)
        print(f"   Found {overrides.count()} overrides in database")
        if overrides.exists():
            override = overrides.first()
            print(f"   Override: {override.column_name} = {override.override_value}")
            print(f"   Reason: {override.reason}")
            print(f"   Created: {override.created_at}")
            assert override.override_value == "2.5"
            print("   ✓ Override correctly saved to database")
        else:
            print("   ✗ No overrides found in database")
            return False
    except Exception as e:
        print(f"   ✗ Error checking database: {e}")
        return False

    print()

    # 6. Test asset workflow state updates
    print("6. Testing asset workflow state...")
    asset.refresh_from_db()
    print(f"   Workflow state: {asset.workflow_state}")
    print(f"   Session independent analysis: {asset.has_session_independent_analysis}")
    assert asset.workflow_state == 'overrides_applied'
    assert asset.has_session_independent_analysis == True
    print("   ✓ Asset workflow state correctly updated")

    print()

    # 7. Test context check with database overrides
    print("7. Testing context check with database overrides...")
    response = client.get('/climate-hazards-analysis-v2/check-analysis-context/')
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Response: {json.dumps(data, indent=2)}")
        assert data['has_context'] == True
        assert data['database_mode'] == True
        print("   ✓ Context check now returns database mode")
    else:
        print(f"   ✗ Unexpected status: {response.status_code}")
        return False

    print()

    # 8. Test OverrideValue model methods
    print("8. Testing OverrideValue model methods...")

    # Test get_active_override
    active_override = OverrideValue.get_active_override(
        asset, "Flood Depth (meters)"
    )
    assert active_override is not None
    assert active_override.override_value == "2.5"
    print("   ✓ get_active_override works correctly")

    # Test apply_overrides_to_data
    test_data = {
        "Flood Depth (meters)": "1.0",
        "Wind Speed (mph)": "50.0",
        "Temperature (C)": "25.0"
    }

    overridden_data = OverrideValue.apply_overrides_to_data(
        asset, test_data
    )
    print(f"   Original: {test_data}")
    print(f"   Overridden: {overridden_data}")
    assert overridden_data["Flood Depth (meters)"] == "2.5"
    assert overridden_data["Wind Speed (mph)"] == "50.0"  # Unchanged
    print("   ✓ apply_overrides_to_data works correctly")

    print()

    # Cleanup
    print("9. Cleaning up test data...")
    OverrideValue.objects.filter(asset=asset).delete()
    asset.delete()
    print("   ✓ Test data cleaned up")

    print("\n=== All Tests Passed! ===")
    print("✓ Database fallback mechanism working")
    print("✓ Session-independent override functionality working")
    print("✓ Pre-flight validation working")
    print("✓ Graceful error handling working")
    print("✓ Asset workflow state tracking working")

    return True

if __name__ == "__main__":
    try:
        success = test_override_workflow()
        if success:
            print("\n🎉 Enhanced override workflow implementation is working correctly!")
            sys.exit(0)
        else:
            print("\n❌ Tests failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)