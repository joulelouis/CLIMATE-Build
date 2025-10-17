"""
Constants for Climate Hazards Analysis modules.
Centralized location for hazard types, column names, and thresholds.
"""

# Available climate hazard types
CLIMATE_HAZARD_TYPES = [
    'Flood',
    'Water Stress',
    'Heat',
    'Sea Level Rise',
    'Tropical Cyclones',
    'Storm Surge',
    'Rainfall Induced Landslide'
]

# Tropical Cyclone column names
TC_WIND_COLUMNS = [
    'Extreme Windspeed 10 year Return Period (km/h)',
    'Extreme Windspeed 20 year Return Period (km/h)',
    'Extreme Windspeed 50 year Return Period (km/h)',
    'Extreme Windspeed 100 year Return Period (km/h)'
]

# Asset Archetype column name variations
ASSET_ARCHETYPE_COLUMNS = [
    'Asset Archetype', 'asset archetype', 'AssetArchetype', 'assetarchetype',
    'Archetype', 'archetype', 'Asset Type', 'asset type', 'AssetType', 'assettype',
    'Type', 'type', 'Category', 'category', 'Asset Category', 'asset category'
]

# Facility name column variations
FACILITY_NAME_COLUMNS = [
    'Facility', 'Site', 'Name', 'Asset Name'
]

# Hazard column mappings for analysis
HAZARD_COLUMNS = {
    'Flood': ['Flood Depth (meters)'],
    'Water Stress': [
        'Water Stress Exposure (%)',
        'Water Stress Exposure 2030 (%) - Moderate Case',
        'Water Stress Exposure 2050 (%) - Moderate Case',
        'Water Stress Exposure 2030 (%) - Worst Case',
        'Water Stress Exposure 2050 (%) - Worst Case'
    ],
    'Sea Level Rise': [
        '2030 Sea Level Rise (meters) - Moderate Case',
        '2040 Sea Level Rise (meters) - Moderate Case',
        '2050 Sea Level Rise (meters) - Moderate Case',
        '2030 Sea Level Rise (meters) - Worst Case',
        '2040 Sea Level Rise (meters) - Worst Case',
        '2050 Sea Level Rise (meters) - Worst Case'
    ],
    'Tropical Cyclones': TC_WIND_COLUMNS,
    'Heat': [
        'Days over 30° Celsius',
        'Days over 33° Celsius',
        'Days over 35° Celsius',
        'Days over 35° Celsius (2026 - 2030) - Moderate Case',
        'Days over 35° Celsius (2031 - 2040) - Moderate Case',
        'Days over 35° Celsius (2041 - 2050) - Moderate Case',
        'Days over 35° Celsius (2026 - 2030) - Worst Case',
        'Days over 35° Celsius (2031 - 2040) - Worst Case',
        'Days over 35° Celsius (2041 - 2050) - Worst Case'
    ],
    'Storm Surge': [
        'Storm Surge Flood Depth (meters)',
        'Storm Surge Flood Depth (meters) - Worst Case'
    ],
    'Rainfall Induced Landslide': [
        'Rainfall-Induced Landslide (factor of safety)',
        'Rainfall-Induced Landslide (factor of safety) - Moderate Case',
        'Rainfall-Induced Landslide (factor of safety) - Worst Case'
    ]
}

# NaN value replacements
NAN_REPLACEMENTS = {
    'Elevation (meter above sea level)': "Little to no effect",
    'Sea Level Rise': "Little to none",  # Will be matched with 'in' operator
    'Tropical Cyclones': "Data not available",  # Will be matched against TC columns
    'default': "N/A"
}

# File encoding priorities for CSV reading
CSV_ENCODINGS = ['utf-8', 'latin-1', 'cp1252']

# Flood scenarios for analysis
FLOOD_SCENARIOS = ['current', 'moderate', 'worst']