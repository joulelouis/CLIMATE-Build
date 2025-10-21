"""
Hazard Raster Configuration
============================
Maps hazard types to their raster file paths for granular analysis.
"""

import os
from django.conf import settings

# Base directory for hazard rasters
HAZARD_RASTER_DIR = os.path.join(settings.BASE_DIR, 'climate_hazards_analysis', 'static', 'input_files')

# Hazard raster file mappings
HAZARD_RASTERS = {
    'Flood': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'PH_Flood_100year_UTM_ProjectNOAH_Unmasked.tif'),
        'name': 'Flood (100-year return period)',
        'unit': 'meters'
    },
    'Heat': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'PH_DaysOver35degC_ANN_2021-2025.tif'),
        'name': 'Heat Stress (Days >35°C)',
        'unit': 'days'
    },
    'Water Stress': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'PH_WaterStress_Baseline.tif'),
        'name': 'Water Stress (Baseline)',
        'unit': 'percentage'
    },
    'Sea Level Rise': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'PH_LECZ_elevation.tif'),
        'name': 'Sea Level Rise (Elevation)',
        'unit': 'meters'
    },
    'Storm Surge': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'PH_StormSurge_Current.tif'),
        'name': 'Storm Surge (Current)',
        'unit': 'meters'
    },
    'Rainfall Induced Landslide': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'PH_Landslide_Baseline.tif'),
        'name': 'Landslide (Rainfall Induced)',
        'unit': 'factor of safety'
    },
    'Tropical Cyclones': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'PH_TropicalCyclone_100yr.tif'),
        'name': 'Tropical Cyclones (100-year)',
        'unit': 'km/h'
    }
}


def get_hazard_raster_path(hazard_name):
    """
    Get the raster file path for a given hazard name.

    Args:
        hazard_name: Name of the hazard (e.g., 'Flood', 'Heat')

    Returns:
        Path to raster file if it exists, None otherwise
    """
    hazard_config = HAZARD_RASTERS.get(hazard_name)
    if hazard_config:
        path = hazard_config['path']
        if os.path.exists(path):
            return path
        else:
            # Try alternative naming conventions
            alternatives = [
                os.path.join(HAZARD_RASTER_DIR, f'PH_{hazard_name.replace(" ", "")}_Baseline.tif'),
                os.path.join(HAZARD_RASTER_DIR, f'{hazard_name.replace(" ", "_")}.tif'),
                os.path.join(HAZARD_RASTER_DIR, f'PH_{hazard_name.replace(" ", "_")}.tif')
            ]

            for alt_path in alternatives:
                if os.path.exists(alt_path):
                    return alt_path

    return None


def get_available_hazards():
    """
    Get list of hazards that have available raster files.

    Returns:
        List of hazard names with available rasters
    """
    available = []
    for hazard_name in HAZARD_RASTERS.keys():
        if get_hazard_raster_path(hazard_name):
            available.append(hazard_name)
    return available
