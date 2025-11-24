#!/usr/bin/env python
"""
Demo script to show unified JSON system for multiple asset file uploads.
This demonstrates how all uploaded assets are consolidated into a single JSON structure.
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CRAproject.settings')
django.setup()

from climate_hazards_analysis_v2.json_console_simple import simple_json_console

def demo_unified_json_multiple_files():
    """
    Demonstrate unified JSON system for multiple file uploads.
    """

    print("UNIFIED JSON SYSTEM FOR MULTIPLE FILE UPLOADS")
    print("="*80)
    print("This demonstrates how all uploaded asset data is consolidated")
    print("into a single JSON structure for the entire session.")
    print("="*80)

    # Simulate File 1: CSV Upload (Point Assets)
    print("\nSTEP 1: Upload first file - CSV with point assets")
    print("-" * 50)

    csv_facilities = [
        {'Facility': 'Manila Factory', 'Lat': 14.5, 'Long': 121.0, 'Archetype': 'Manufacturing'},
        {'Facility': 'Makati Office', 'Lat': 14.55, 'Long': 121.02, 'Archetype': 'Commercial'}
    ]

    csv_file_metadata = {
        'name': 'philippine_facilities.csv',
        'size': 1536,
        'type': 'text/csv',
        'upload_time': '2024-01-15T14:30:00.123456'
    }

    # Unified assets after first upload
    unified_assets_after_first = {
        'metadata': {
            'total_assets': 2,
            'upload_session_id': 'abc123def456789',
            'files_uploaded': [
                {'filename': 'philippine_facilities.csv', 'file_type': 'text/csv', 'asset_count': 2}
            ],
            'asset_types': {'point_assets': 2, 'polygon_assets': 0}
        }
    }

    print("Uploading CSV file...")
    simple_json_console.log_upload_step(csv_facilities, csv_file_metadata, [], unified_assets_after_first)

    # Simulate File 2: Excel Upload (More Point Assets)
    print("\nSTEP 2: Upload second file - Excel with more point assets")
    print("-" * 50)

    excel_facilities = [
        {'Facility': 'Luzon Plant', 'Lat': 15.2, 'Long': 120.8, 'Archetype': 'Industrial'},
        {'Facility': 'Visayas Facility', 'Lat': 10.3, 'Long': 123.9, 'Archetype': 'Processing'}
    ]

    excel_file_metadata = {
        'name': 'regional_assets.xlsx',
        'size': 5120,
        'type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'upload_time': '2024-01-15T14:35:00.123456'
    }

    # Unified assets after second upload
    unified_assets_after_second = {
        'metadata': {
            'total_assets': 4,
            'upload_session_id': 'abc123def456789',
            'files_uploaded': [
                {'filename': 'philippine_facilities.csv', 'file_type': 'text/csv', 'asset_count': 2},
                {'filename': 'regional_assets.xlsx', 'file_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'asset_count': 2}
            ],
            'asset_types': {'point_assets': 4, 'polygon_assets': 0}
        }
    }

    print("Uploading Excel file...")
    simple_json_console.log_upload_step(excel_facilities, excel_file_metadata, [], unified_assets_after_second)

    # Simulate File 3: Shapefile Upload (Polygon Assets)
    print("\nSTEP 3: Upload third file - Shapefile with polygon assets")
    print("-" * 50)

    shapefile_facilities = [
        {
            'Facility': 'Mining Site A',
            'Lat': 13.8,
            'Long': 121.2,
            'Archetype': 'Mining',
            'AssetType': 'polygon',
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[[121.2, 13.8], [121.3, 13.8], [121.3, 13.9], [121.2, 13.9], [121.2, 13.8]]]
            }
        }
    ]

    shapefile_metadata = {
        'name': 'land_management.shp',
        'size': 8192,
        'type': 'application/octet-stream',
        'upload_time': '2024-01-15T14:40:00.123456'
    }

    # Unified assets after third upload (final consolidated data)
    unified_assets_final = {
        'metadata': {
            'total_assets': 5,
            'upload_session_id': 'abc123def456789',
            'files_uploaded': [
                {'filename': 'philippine_facilities.csv', 'file_type': 'text/csv', 'asset_count': 2},
                {'filename': 'regional_assets.xlsx', 'file_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'asset_count': 2},
                {'filename': 'land_management.shp', 'file_type': 'application/octet-stream', 'asset_count': 1}
            ],
            'asset_types': {'point_assets': 4, 'polygon_assets': 1}
        }
    }

    print("Uploading shapefile...")
    simple_json_console.log_upload_step(shapefile_facilities, shapefile_metadata, [], unified_assets_final)

    # Show the final unified JSON structure
    print("\nFINAL UNIFIED JSON STRUCTURE")
    print("=" * 80)
    print("The complete unified JSON contains all assets from all files:")
    print(f"- Total Assets: {unified_assets_final['metadata']['total_assets']}")
    print(f"- Total Files: {len(unified_assets_final['metadata']['files_uploaded'])}")
    print("- Asset Types: Point assets, Polygon assets")
    print("- Session ID: abc123def456789")
    print("\nFiles included:")
    for file_info in unified_assets_final['metadata']['files_uploaded']:
        print(f"  • {file_info['filename']} ({file_info['asset_count']} assets)")

    print("\n" + "="*80)
    print("KEY BENEFITS OF UNIFIED JSON SYSTEM:")
    print("="*80)
    print("• Single JSON structure contains ALL uploaded asset data")
    print("• Each asset maintains link to its source file")
    print("• Automatic consolidation of point and polygon assets")
    print("• Session-based tracking with unique IDs")
    print("• Real-time console logging shows total progress")
    print("• Easy to export or analyze all assets together")
    print("• Database-stored JSON with immediate access")
    print("\nREADY FOR PRODUCTION USE!")
    print("Run: python manage.py runserver")
    print("Upload multiple files and watch the unified JSON system work!")
    print("="*80)

if __name__ == '__main__':
    demo_unified_json_multiple_files()