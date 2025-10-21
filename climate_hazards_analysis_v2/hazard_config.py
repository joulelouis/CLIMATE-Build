"""
Hazard Raster Configuration
============================
Centralized configuration for hazard raster file paths.
Makes it easy to switch between scenarios and time periods.
"""

import os
from django.conf import settings

# Base directory for hazard rasters
HAZARD_RASTER_DIR = os.path.join(
    settings.BASE_DIR,
    'climate_hazards_analysis/static/input_files'
)


# Hazard raster file mappings
HAZARD_RASTERS = {
    # Flood Hazards
    'flood_baseline': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'PH_Flood_100year_UTM_ProjectNOAH_Unmasked.tif'),
        'name': 'Flood (100-year return period)',
        'unit': 'meters',
        'thresholds': {
            'low': 0.5,
            'medium': 1.5,
            'high': 2.5
        }
    },

    # Heat Hazards
    'heat_baseline': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'PH_DaysOver35degC_ANN_2021-2025.tif'),
        'name': 'Heat Stress (Days >35°C)',
        'unit': 'days',
        'thresholds': {
            'low': 10,
            'medium': 45,
            'high': 90
        }
    },
    'heat_ssp245_2030': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'PH_DaysOver35degC_ANN_SSP245_2026-2030.tif'),
        'name': 'Heat Stress SSP2-4.5 (2026-2030)',
        'unit': 'days',
        'thresholds': {
            'low': 10,
            'medium': 45,
            'high': 90
        }
    },
    'heat_ssp585_2050': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'PH_DaysOver35degC_ANN_SSP585_2041-2050.tif'),
        'name': 'Heat Stress SSP5-8.5 (2041-2050)',
        'unit': 'days',
        'thresholds': {
            'low': 10,
            'medium': 45,
            'high': 90
        }
    },

    # Storm Surge
    'storm_surge_baseline': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'PH_StormSurge_Advisory4_UTM_ProjectNOAH_Unmasked.tif'),
        'name': 'Storm Surge (Advisory 4)',
        'unit': 'meters',
        'thresholds': {
            'low': 0.5,
            'medium': 1.5,
            'high': 2.5
        }
    },
    'storm_surge_future': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'PH_StormSurge_Advisory4_Future_UTM_ProjectNOAH-GIRI_Unmasked.tif'),
        'name': 'Storm Surge Future Scenario',
        'unit': 'meters',
        'thresholds': {
            'low': 0.5,
            'medium': 1.5,
            'high': 2.5
        }
    },

    # Landslide
    'landslide_baseline': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'PH_LandslideHazards_UTM_ProjectNOAH_Unmasked.tif'),
        'name': 'Landslide Hazard (Baseline)',
        'unit': 'factor of safety',
        'thresholds': {
            'low': 1.5,   # Reversed: lower values = higher risk
            'medium': 1.0,
            'high': 0.5
        },
        'reversed': True  # Lower values mean higher risk
    },
    'landslide_rcp26': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'PH_LandslideHazards_RCP26_UTM_ProjectNOAH-GIRI_Unmasked.tif'),
        'name': 'Landslide Hazard RCP2.6',
        'unit': 'factor of safety',
        'thresholds': {
            'low': 1.5,
            'medium': 1.0,
            'high': 0.5
        },
        'reversed': True
    },
    'landslide_rcp85': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'PH_LandslideHazards_RCP85_UTM_ProjectNOAH-GIRI_Unmasked.tif'),
        'name': 'Landslide Hazard RCP8.5',
        'unit': 'factor of safety',
        'thresholds': {
            'low': 1.5,
            'medium': 1.0,
            'high': 0.5
        },
        'reversed': True
    },

    # Sea Level Rise (elevation-based)
    'sea_level_rise': {
        'path': os.path.join(HAZARD_RASTER_DIR, 'merit_lecz_ph.tif'),
        'name': 'Low Elevation Coastal Zone',
        'unit': 'meters above sea level',
        'thresholds': {
            'low': 10,   # >10m above sea level = low risk
            'medium': 5,  # 5-10m = medium risk
            'high': 2     # <2m = high risk
        },
        'reversed': True  # Lower elevation = higher risk
    },
}


def get_hazard_raster(hazard_key):
    """
    Get hazard raster configuration by key.

    Args:
        hazard_key: Key from HAZARD_RASTERS dict

    Returns:
        dict with path, name, unit, thresholds

    Example:
        >>> config = get_hazard_raster('flood_baseline')
        >>> config['path']
        '/path/to/PH_Flood_100year_UTM_ProjectNOAH_Unmasked.tif'
    """
    return HAZARD_RASTERS.get(hazard_key)


def get_available_hazards():
    """
    Get list of available hazard rasters (files that actually exist).

    Returns:
        List of tuples: (key, name, exists)

    Example:
        >>> get_available_hazards()
        [('flood_baseline', 'Flood (100-year)', True), ...]
    """
    available = []

    for key, config in HAZARD_RASTERS.items():
        exists = os.path.exists(config['path'])
        available.append((key, config['name'], exists))

    return available


def get_default_hazard_for_granular():
    """
    Get the default hazard raster to use for granular analysis.
    Prioritizes flood as it's most commonly used.

    Returns:
        dict with hazard configuration or None if no raster found
    """
    # Priority order for default hazard
    priority_order = [
        'flood_baseline',
        'heat_baseline',
        'storm_surge_baseline',
        'landslide_baseline'
    ]

    for hazard_key in priority_order:
        config = HAZARD_RASTERS.get(hazard_key)
        if config and os.path.exists(config['path']):
            return {
                'key': hazard_key,
                **config
            }

    return None


def classify_risk_value(value, hazard_key):
    """
    Classify a raster value into risk category based on hazard thresholds.

    Args:
        value: Raw raster value
        hazard_key: Which hazard to use thresholds from

    Returns:
        str: 'Low', 'Medium', 'High', or 'Very High'

    Example:
        >>> classify_risk_value(0.3, 'flood_baseline')
        'Low'
        >>> classify_risk_value(2.0, 'flood_baseline')
        'High'
    """
    config = HAZARD_RASTERS.get(hazard_key)
    if not config:
        return 'Unknown'

    thresholds = config['thresholds']
    reversed_scale = config.get('reversed', False)

    if reversed_scale:
        # For reversed scales (like landslide, sea level): lower value = higher risk
        if value < thresholds['high']:
            return 'Very High'
        elif value < thresholds['medium']:
            return 'High'
        elif value < thresholds['low']:
            return 'Medium'
        else:
            return 'Low'
    else:
        # For normal scales: higher value = higher risk
        if value > thresholds['high']:
            return 'Very High'
        elif value > thresholds['medium']:
            return 'High'
        elif value > thresholds['low']:
            return 'Medium'
        else:
            return 'Low'
