import pandas as pd
import numpy as np
import os
from django.conf import settings
import logging

# Import consolidated utilities
from climate_hazards_analysis.utils.common_utils import (
    standardize_facility_dataframe as _standardize_facility_dataframe,
    validate_shapefile as _validate_shapefile,
    load_cached_hazard_data as _load_cached_hazard_data,
    combine_facility_with_hazard_data,
    handle_processing_error
)

logger = logging.getLogger(__name__)


def standardize_facility_dataframe(df):
    """
    Standardize facility dataframe column names for consistency.

    This function now uses the consolidated implementation from common_utils.

    Args:
        df (pandas.DataFrame): The input facility dataframe

    Returns:
        pandas.DataFrame: Standardized dataframe with consistent column names
    """
    return _standardize_facility_dataframe(df, strict_mode=False)

def validate_shapefile(gdf):
    """
    Validate that an uploaded shapefile has the expected structure.

    This function now uses the consolidated implementation from common_utils.

    Args:
        gdf (geopandas.GeoDataFrame): The input geodataframe from the shapefile

    Returns:
        list[str]: Attribute column names

    Raises:
        ValueError: If the shapefile has no features, contains unsupported geometries,
                   or lacks a suitable facility name column.
    """
    return _validate_shapefile(gdf)

def load_cached_hazard_data(hazard_type):
    """
    Load pre-computed hazard data from the static files.

    This function now uses the consolidated implementation from common_utils.

    Args:
        hazard_type (str): Type of hazard data to load (flood, heat, water_stress, etc.)

    Returns:
        dict: Dictionary containing hazard data or None if not found
    """
    return _load_cached_hazard_data(hazard_type)

# combine_facility_with_hazard_data is now imported from common_utils