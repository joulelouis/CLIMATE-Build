#!/usr/bin/env python
"""
Demo script to show what JSON console output will look like
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CRAproject.settings')
django.setup()

from climate_hazards_analysis_v2.json_console_simple import simple_json_console

def demo_json_console():
    """Demonstrate JSON console output"""

    print("🎯 DEMO: What you will see in the Django console:")
    print("="*80)

    # Demo 1: Upload step
    test_facilities = [
        {'Facility': 'Factory A', 'Lat': 14.5, 'Long': 121.0, 'Asset Archetype': 'Manufacturing'},
        {'Facility': 'Warehouse B', 'Lat': 15.0, 'Long': 121.5, 'Asset Archetype': 'Commercial'}
    ]

    test_file = {'name': 'sample_assets.csv', 'size': 1024, 'type': 'text/csv'}

    simple_json_console.log_upload_step(test_facilities, test_file, [])

    # Demo 2: Hazard selection
    simple_json_console.log_hazard_selection_step([1, 2], ['Flood', 'Heat'], {'source': 'web_form'})

    # Demo 3: Results
    test_results = [
        {'Facility': 'Factory A', 'Flood Depth': '0.5m', 'Heat Days': 25},
        {'Facility': 'Warehouse B', 'Flood Depth': '1.2m', 'Heat Days': 35}
    ]

    simple_json_console.log_results_step(test_results, ['Facility', 'Flood Depth', 'Heat Days'],
                                        {'Info': 1, 'Hazards': 2}, 2)

    print("✅ DEMO COMPLETE!")
    print("Now run: python manage.py runserver")
    print("And you will see this output when you use the web application!")

if __name__ == '__main__':
    demo_json_console()