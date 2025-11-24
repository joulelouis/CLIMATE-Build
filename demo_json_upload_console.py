#!/usr/bin/env python
"""
Demo script to show enhanced JSON console output for asset file uploads.
This demonstrates the JSON storage and display for all supported file types.
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CRAproject.settings')
django.setup()

from climate_hazards_analysis_v2.json_console_simple import simple_json_console

def demo_json_upload_console():
    """
    Demonstrate enhanced JSON console output for different file upload types.
    """

    print("ENHANCED JSON UPLOAD CONSOLE DEMO")
    print("="*80)
    print("This demonstrates what you will see in the Django console")
    print("when uploading asset files (CSV, XLSX, Shapefile, GeoPackage).")
    print("="*80)

    # Demo 1: CSV Upload
    print("\nDEMO 1: CSV File Upload")
    print("-" * 50)

    csv_facilities = [
        {'Facility': 'Manila Factory', 'Lat': 14.5, 'Long': 121.0, 'Archetype': 'Manufacturing'},
        {'Facility': 'Makati Office', 'Lat': 14.55, 'Long': 121.02, 'Archetype': 'Commercial'},
        {'Facility': 'Quezon Warehouse', 'Lat': 14.6, 'Long': 121.05, 'Archetype': 'Storage'}
    ]

    csv_file_metadata = {
        'name': 'philippine_facilities.csv',
        'size': 1536,
        'type': 'text/csv',
        'upload_time': '2024-01-15T14:30:00.123456',
        'file_path': 'C:/CLIMATE/CLIMATE-Build/climate_hazards_analysis_v2/static/input_files/philippine_facilities.csv'
    }

    print("Uploading CSV file with point assets...")
    simple_json_console.log_upload_step(csv_facilities, csv_file_metadata, [])

    # Demo 2: Excel Upload
    print("\nDEMO 2: Excel File Upload")
    print("-" * 50)

    excel_facilities = [
        {'Facility': 'Luzon Plant', 'Lat': 15.2, 'Long': 120.8, 'Archetype': 'Industrial'},
        {'Facility': 'Visayas Facility', 'Lat': 10.3, 'Long': 123.9, 'Archetype': 'Processing'}
    ]

    excel_file_metadata = {
        'name': 'regional_assets.xlsx',
        'size': 5120,
        'type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'upload_time': '2024-01-15T14:35:00.123456',
        'file_path': 'C:/CLIMATE/CLIMATE-Build/climate_hazards_analysis_v2/static/input_files/regional_assets.xlsx'
    }

    print("Uploading Excel file with regional facilities...")
    simple_json_console.log_upload_step(excel_facilities, excel_file_metadata, [])

    # Demo 3: Shapefile Upload
    print("\nDEMO 3: Shapefile Upload")
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
        },
        {
            'Facility': 'Agricultural Zone B',
            'Lat': 13.7,
            'Long': 121.4,
            'Archetype': 'Agriculture',
            'AssetType': 'polygon',
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[[121.4, 13.7], [121.6, 13.7], [121.6, 13.8], [121.4, 13.8], [121.4, 13.7]]]
            }
        }
    ]

    shapefile_metadata = {
        'name': 'land_management.shp',
        'size': 8192,
        'type': 'application/octet-stream',
        'upload_time': '2024-01-15T14:40:00.123456',
        'file_path': 'C:/CLIMATE/CLIMATE-Build/climate_hazards_analysis_v2/static/input_files/land_management.shp'
    }

    print("Uploading shapefile with polygon assets...")
    simple_json_console.log_upload_step(shapefile_facilities, shapefile_metadata, [])

    # Demo 4: GeoPackage Upload
    print("\nDEMO 4: GeoPackage Upload")
    print("-" * 50)

    geopackage_facilities = [
        {
            'Facility': 'Conservation Area',
            'Lat': 12.5,
            'Long': 122.0,
            'Archetype': 'Environmental',
            'AssetType': 'polygon',
            'geometry': {
                'type': 'MultiPolygon',
                'coordinates': [
                    [[[122.0, 12.5], [122.1, 12.5], [122.1, 12.6], [122.0, 12.6], [122.0, 12.5]]],
                    [[[122.2, 12.7], [122.3, 12.7], [122.3, 12.8], [122.2, 12.8], [122.2, 12.7]]]
                ]
            }
        }
    ]

    geopackage_metadata = {
        'name': 'protected_areas.gpkg',
        'size': 16384,
        'type': 'application/geopackage+sqlite3',
        'upload_time': '2024-01-15T14:45:00.123456',
        'file_path': 'C:/CLIMATE/CLIMATE-Build/climate_hazards_analysis_v2/static/input_files/protected_areas.gpkg'
    }

    print("Uploading GeoPackage with multi-polygon assets...")
    simple_json_console.log_upload_step(geopackage_facilities, geopackage_metadata, [])

    print("\nENHANCED JSON UPLOAD CONSOLE DEMO COMPLETE!")
    print("="*80)
    print("KEY FEATURES:")
    print("- All uploaded asset data is stored as JSON in the database")
    print("- Console shows detailed breakdown of file types and asset types")
    print("- Supports point assets (CSV/Excel) and polygon assets (Shapefile/GeoPackage)")
    print("- Enhanced metadata tracking with file information")
    print("- Real-time console display during upload process")
    print("\nReady for production use!")
    print("Now run: python manage.py runserver")
    print("Upload any asset file and you will see this enhanced JSON console output!")
    print("="*80)

if __name__ == '__main__':
    demo_json_upload_console()