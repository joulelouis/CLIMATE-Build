#!/usr/bin/env python
"""
Test script to demonstrate JSON console display for each workflow step
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CRAproject.settings')
django.setup()

def test_json_console_display():
    """Test JSON console display for all workflow steps"""

    from climate_hazards_analysis_v2.json_console_logger import json_logger

    print("🧪 TESTING JSON CONSOLE DISPLAY")
    print("=" * 60)
    print("This will show how JSON data appears in console at each step:")
    print("1. Upload Asset Data")
    print("2. Select Hazards and Scenarios")
    print("3. Hazard Exposure Results")
    print("=" * 60)

    # Step 1: Test Upload Asset Data
    test_facilities = [
        {
            'Facility': 'Test Factory A',
            'Lat': 14.5,
            'Long': 121.0,
            'Asset Archetype': 'Manufacturing'
        },
        {
            'Facility': 'Test Warehouse B',
            'Lat': 15.0,
            'Long': 121.5,
            'Asset Archetype': 'Commercial'
        }
    ]

    test_file_metadata = {
        'name': 'test_assets.csv',
        'size': 2048,
        'type': 'text/csv',
        'record_count': 2
    }

    print("\n" + "="*80)
    print("🖥️  CONSOLE OUTPUT - WHAT YOU WILL SEE:")
    print("="*80)

    # Simulate the console output for each step
    json_logger.log_upload_step(test_facilities, test_file_metadata, [])

    # Step 2: Test Hazard Selection
    test_asset_ids = [1, 2]
    test_hazards = ['Flood', 'Heat', 'Water Stress']
    test_parameters = {
        'source': 'web_form',
        'scenarios': ['moderate', 'worst'],
        'buffer_size': 0.0009
    }

    json_logger.log_hazard_selection_step(test_asset_ids, test_hazards, test_parameters)

    # Step 3: Test Analysis Processing
    test_analysis_data = [
        {
            'name': 'Test Factory A',
            'latitude': 14.5,
            'longitude': 121.0,
            'archetype': 'Manufacturing',
            'asset_id': 1
        },
        {
            'name': 'Test Warehouse B',
            'latitude': 15.0,
            'longitude': 121.5,
            'archetype': 'Commercial',
            'asset_id': 2
        }
    ]

    json_logger.log_analysis_step(test_analysis_data, test_hazards, "processing")

    # Step 4: Test Results
    test_results = [
        {
            'Facility': 'Test Factory A',
            'Asset Archetype': 'Manufacturing',
            'Lat': 14.5,
            'Long': 121.0,
            'Flood Depth (meters)': '0.1 to 0.5',
            'Days over 35° Celsius': 25,
            'Water Stress Exposure (%)': 12.5
        },
        {
            'Facility': 'Test Warehouse B',
            'Asset Archetype': 'Commercial',
            'Lat': 15.0,
            'Long': 121.5,
            'Flood Depth (meters)': '0.5 to 1.5',
            'Days over 35° Celsius': 35,
            'Water Stress Exposure (%)': 18.2
        }
    ]

    test_columns = ['Facility', 'Asset Archetype', 'Lat', 'Long', 'Flood Depth (meters)', 'Days over 35° Celsius', 'Water Stress Exposure (%)']
    test_groups = {
        'Facility Information': 4,
        'Flood': 1,
        'Heat': 1,
        'Water Stress': 1
    }

    json_logger.log_results_step(test_results, test_columns, test_groups, 2)

    print("\n" + "="*80)
    print("✅ JSON CONSOLE DISPLAY TEST COMPLETED")
    print("="*80)
    print("Now when you use the actual web application, you will see")
    print("similar JSON output in the Django console for each step!")
    print("="*80)

if __name__ == '__main__':
    test_json_console_display()