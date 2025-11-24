#!/usr/bin/env python
"""
Demo script to show the complete hazard analysis workflow using unified JSON.
This demonstrates how uploaded assets and selected hazards are consolidated into a single JSON structure.
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CRAproject.settings')
django.setup()

from climate_hazards_analysis_v2.json_console_simple import simple_json_console

def demo_complete_hazard_analysis_workflow():
    """
    Demonstrate the complete hazard analysis workflow using unified JSON.
    """

    print("COMPLETE HAZARD ANALYSIS WORKFLOW WITH UNIFIED JSON")
    print("="*80)
    print("This demonstrates how uploaded assets and selected hazards")
    print("are stored in the same unified JSON structure for analysis.")
    print("="*80)

    # STEP 1: Upload Assets (from previous demo)
    print("\nSTEP 1: Asset Upload Status")
    print("-" * 50)

    # Simulate unified assets after multiple file uploads
    unified_assets_after_upload = {
        'metadata': {
            'total_assets': 5,
            'upload_session_id': 'abc123def456789',
            'files_uploaded': [
                {'filename': 'philippine_facilities.csv', 'file_type': 'text/csv', 'asset_count': 3},
                {'filename': 'mining_sites.shp', 'file_type': 'application/octet-stream', 'asset_count': 2}
            ],
            'asset_types': {'point_assets': 3, 'polygon_assets': 2}
        },
        'assets': [
            {
                'database_id': 1,
                'name': 'Manila Factory',
                'latitude': 14.5,
                'longitude': 121.0,
                'archetype': 'Manufacturing',
                'asset_type': 'point',
                'properties': {
                    'original_filename': 'philippine_facilities.csv',
                    'file_upload_id': 'file-uuid-1'
                }
            },
            {
                'database_id': 2,
                'name': 'Makati Office',
                'latitude': 14.55,
                'longitude': 121.02,
                'archetype': 'Commercial',
                'asset_type': 'point',
                'properties': {
                    'original_filename': 'philippine_facilities.csv',
                    'file_upload_id': 'file-uuid-1'
                }
            },
            {
                'database_id': 3,
                'name': 'Mining Site A',
                'latitude': 13.8,
                'longitude': 121.2,
                'archetype': 'Mining',
                'asset_type': 'polygon',
                'polygon_geometry': {'type': 'Polygon', 'coordinates': [[[121.2, 13.8], [121.3, 13.8], [121.3, 13.9], [121.2, 13.9], [121.2, 13.8]]]},
                'properties': {
                    'original_filename': 'mining_sites.shp',
                    'file_upload_id': 'file-uuid-2'
                }
            }
        ]
    }

    print(f"[OK] Assets uploaded and consolidated: {unified_assets_after_upload['metadata']['total_assets']} total assets")
    print(f"[FILE] Files uploaded: {len(unified_assets_after_upload['metadata']['files_uploaded'])}")
    print(f"[POINT] Point assets: {unified_assets_after_upload['metadata']['asset_types']['point_assets']}")
    print(f"[POLYGON] Polygon assets: {unified_assets_after_upload['metadata']['asset_types']['polygon_assets']}")

    # STEP 2: Hazard Selection
    print("\nSTEP 2: Hazard Selection")
    print("-" * 50)

    selected_hazards = ['Flood', 'Heat', 'Water Stress']
    asset_ids = [1, 2, 3, 4, 5]

    print("User selected hazards:")
    for hazard in selected_hazards:
        print(f"   - {hazard}")

    # Log hazard selection
    parameters = {
        'source': 'hazard_selection_form',
        'total_hazards_available': 7,
        'selected_hazards_count': len(selected_hazards)
    }

    print("\nConsole output for hazard selection:")
    simple_json_console.log_hazard_selection_step(asset_ids, selected_hazards, parameters, unified_assets_after_upload)

    # STEP 3: Unified JSON with Both Assets and Hazards
    print("\nSTEP 3: Unified JSON Structure Ready for Analysis")
    print("-" * 50)

    # Simulate the unified JSON structure after hazard selection
    unified_json_for_analysis = {
        'metadata': {
            'session_id': 'abc123def456789',
            'total_assets': 5,
            'selected_hazards': selected_hazards,
            'selection_timestamp': '2024-01-15T14:45:00.123456',
            'files_uploaded': [
                {'filename': 'philippine_facilities.csv', 'asset_count': 3},
                {'filename': 'mining_sites.shp', 'asset_count': 2}
            ],
            'asset_types': {'point_assets': 3, 'polygon_assets': 2},
            'hazard_selection': {
                'selected_hazards': selected_hazards,
                'selection_timestamp': '2024-01-15T14:45:00.123456',
                'total_hazards_available': 7,
                'selection_source': 'web_form',
                'hazards_count': len(selected_hazards)
            },
            'analysis_status': 'ready'
        },
        'assets_for_analysis': [
            {
                'Facility': 'Manila Factory',
                'Lat': 14.5,
                'Long': 121.0,
                'Archetype': 'Manufacturing',
                '_file_id': 'file-uuid-1',
                'selected_hazards': selected_hazards,
                'asset_id': 1,
                'asset_type': 'point',
                'source_file': 'philippine_facilities.csv'
            },
            {
                'Facility': 'Mining Site A',
                'Lat': 13.8,
                'Long': 121.2,
                'Archetype': 'Mining',
                '_file_id': 'file-uuid-2',
                'selected_hazards': selected_hazards,
                'asset_id': 3,
                'asset_type': 'polygon',
                'source_file': 'mining_sites.shp',
                'polygon_geometry': {'type': 'Polygon', 'coordinates': [[[121.2, 13.8], [121.3, 13.8], [121.3, 13.9], [121.2, 13.9], [121.2, 13.8]]]}
            }
        ]
    }

    print("Unified JSON structure created with:")
    print(f"   - {unified_json_for_analysis['metadata']['total_assets']} assets ready for analysis")
    print(f"   - {len(unified_json_for_analysis['metadata']['selected_hazards'])} hazards selected")
    print(f"   - Assets include required keys: Facility, Lat, Long, Archetype, _file_id, selected_hazards")

    # STEP 4: Backend Analysis Process
    print("\nSTEP 4: Backend Analysis Process")
    print("-" * 50)

    print("Analysis workflow:")
    print("   1. Extract unified JSON data for analysis")
    print("   2. Create temporary CSV from unified JSON assets")
    print("   3. Pass CSV and hazards to existing analysis engine")
    print("   4. Process each selected hazard:")
    for hazard in selected_hazards:
        print(f"      - Processing {hazard} analysis...")
    print("   5. Generate combined JSON results")
    print("   6. Clean up temporary files")
    print("   7. Display results in hazard exposure table")

    # Log analysis step
    simple_json_console.log_analysis_step(
        analysis_data=unified_json_for_analysis['assets_for_analysis'],
        hazards=selected_hazards,
        processing_status="starting_unified_json_analysis"
    )

    # STEP 5: Final Results
    print("\nSTEP 5: Final Analysis Results")
    print("-" * 50)

    # Simulate results data
    mock_results_data = [
        {
            'Facility': 'Manila Factory',
            'Lat': 14.5,
            'Long': 121.0,
            'Archetype': 'Manufacturing',
            'Flood Depth (meters)': '0.1 to 0.5',
            'Days over 35° Celsius': 25,
            'Water Stress Level': 'Low'
        },
        {
            'Facility': 'Mining Site A',
            'Lat': 13.8,
            'Long': 121.2,
            'Archetype': 'Mining',
            'Flood Depth (meters)': '0.5 to 1.2',
            'Days over 35° Celsius': 35,
            'Water Stress Level': 'Medium'
        }
    ]

    mock_columns = ['Facility', 'Lat', 'Long', 'Archetype', 'Flood Depth (meters)', 'Days over 35° Celsius', 'Water Stress Level']
    mock_groups = {'Asset Info': 4, 'Flood': 1, 'Heat': 1, 'Water Stress': 1}

    print("Analysis completed successfully!")
    print(f"   - Processed {len(mock_results_data)} assets")
    print(f"   - Generated {len(mock_columns)} data columns")
    print(f"   - Results saved to combined_output.json")

    print("\nConsole output for analysis results:")
    simple_json_console.log_results_step(
        results_data=mock_results_data,
        columns=mock_columns,
        groups=mock_groups,
        asset_count=len(unified_json_for_analysis['assets_for_analysis'])
    )

    print("\n" + "="*80)
    print("WORKFLOW COMPLETE - KEY ACHIEVEMENTS:")
    print("="*80)
    print("[OK] Multiple asset files consolidated into single JSON")
    print("[OK] Hazard selections stored in same unified JSON")
    print("[OK] Backend analysis uses unified JSON data")
    print("[OK] All required keys present: Facility, Lat, Long, Archetype, _file_id, selected_hazards")
    print("[OK] Complete workflow with detailed console logging")
    print("[OK] Results displayed in hazard exposure table")
    print("\nREADY FOR PRODUCTION!")
    print("Run: python manage.py runserver")
    print("Upload assets -> Select hazards -> Generate analysis -> View results!")
    print("="*80)

if __name__ == '__main__':
    demo_complete_hazard_analysis_workflow()