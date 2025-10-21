"""
Common Utilities for Climate Hazards Analysis

This module contains consolidated utility functions shared across both
climate_hazards_analysis and climate_hazards_analysis_v2 modules to avoid
code duplication and ensure consistency.

Functions consolidated from multiple sources:
- Column standardization and data validation
- Float filtering and data processing
- File processing utilities
- Data validation helpers
"""

import pandas as pd
import numpy as np
import os
import logging
from pathlib import Path
from typing import Optional, Union, List, Dict, Any
import geopandas as gpd
from django.conf import settings

logger = logging.getLogger(__name__)


def standardize_facility_dataframe(df: pd.DataFrame,
                                 facility_name_col: str = 'Facility',
                                 lat_col: str = 'Lat',
                                 lon_col: str = 'Long',
                                 strict_mode: bool = False) -> pd.DataFrame:
    """
    Standardize facility dataframe column names for consistency.

    This is a consolidated version combining the best features from both
    climate_hazards_analysis and climate_hazards_analysis_v2 implementations.

    Args:
        df (pd.DataFrame): The input facility dataframe
        facility_name_col (str): Target column name for facility names
        lat_col (str): Target column name for latitude
        lon_col (str): Target column name for longitude
        strict_mode (bool): If True, raise errors for missing columns. If False,
                           attempt to create missing columns with default values.

    Returns:
        pd.DataFrame: Standardized dataframe with consistent column names

    Raises:
        ValueError: If required columns cannot be found/created and strict_mode=True
    """
    df = df.copy()

    # Standardize facility name column - Include comprehensive variations
    facility_name_variations = [
        'facility', 'site', 'site name',
        'facility name', 'facilty name', 'name',
        'asset name', 'facility_name', 'site_name'
    ]

    # Find and rename facility name column
    facility_col_found = False
    for col in df.columns:
        if col.strip().lower() in facility_name_variations:
            df.rename(columns={col: facility_name_col}, inplace=True)
            facility_col_found = True
            break

    # If no facility column found and not in strict mode, try to create it
    if not facility_col_found:
        if strict_mode:
            raise ValueError(f"Could not find facility name column. Looked for: {facility_name_variations}")
        else:
            # Try alternative approaches
            if 'Name' in df.columns:
                df.rename(columns={'Name': facility_name_col}, inplace=True)
                facility_col_found = True
            elif 'Site' in df.columns:
                df.rename(columns={'Site': facility_name_col}, inplace=True)
                facility_col_found = True
            else:
                # Create default facility names from index
                df[facility_name_col] = df.index.map(lambda i: f"Facility {i+1}")
                logger.warning(f"Created default facility names from index (no facility column found)")

    # Standardize lat/long columns - make it case-insensitive and comprehensive
    lat_variations = ['lat', 'latitude', 'y', 'northing', 'Latitude', 'LAT']
    lon_variations = ['lon', 'long', 'longitude', 'x', 'easting', 'Longitude', 'LONG', 'LON']

    lat_col_found = False
    lon_col_found = False

    # Find latitude column
    for col in df.columns:
        if col.lower() in [v.lower() for v in lat_variations] and lat_col not in df.columns:
            df.rename(columns={col: lat_col}, inplace=True)
            lat_col_found = True
            break

    # Find longitude column
    for col in df.columns:
        if col.lower() in [v.lower() for v in lon_variations] and lon_col not in df.columns:
            df.rename(columns={col: lon_col}, inplace=True)
            lon_col_found = True
            break

    # Validate required columns
    required_cols = [facility_name_col, lat_col, lon_col]
    missing = [col for col in required_cols if col not in df.columns]

    if missing:
        if strict_mode:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")
        else:
            logger.warning(f"Missing required columns: {', '.join(missing)}")
            # If coordinates are missing, we cannot continue
            if lat_col in missing or lon_col in missing:
                raise ValueError(f"Missing coordinate columns: {', '.join(missing)}. Cannot continue without Lat/Long.")

    # Convert coordinates to numeric and drop invalid
    df[lat_col] = pd.to_numeric(df[lat_col], errors='coerce')
    df[lon_col] = pd.to_numeric(df[lon_col], errors='coerce')

    # Drop rows with invalid coordinates
    initial_count = len(df)
    df.dropna(subset=[lat_col, lon_col], inplace=True)
    dropped_count = initial_count - len(df)

    if dropped_count > 0:
        logger.warning(f"Dropped {dropped_count} rows with invalid coordinates")

    # Validate coordinate ranges (Philippines bounds - can be overridden if needed)
    # This is optional and can be adjusted for different regions
    if df.empty:
        raise ValueError("No valid facility locations after processing coordinates.")

    # Optional coordinate validation for Philippines
    try:
        if hasattr(settings, 'VALIDATE_PHILIPPINES_BOUNDS') and settings.VALIDATE_PHILIPPINES_BOUNDS:
            bounds_mask = (df[lat_col].between(4, 21)) & (df[lon_col].between(116, 127))
            out_of_bounds = len(df) - bounds_mask.sum()
            if out_of_bounds > 0:
                logger.warning(f"Found {out_of_bounds} facilities outside Philippines bounds")
                if strict_mode:
                    df = df[bounds_mask]
    except Exception:
        # Settings not configured, skip coordinate validation
        pass

    logger.info(f"Standardized facility dataframe: {len(df)} facilities with columns: {df.columns.tolist()}")
    return df


def validate_shapefile(gdf: gpd.GeoDataFrame) -> List[str]:
    """
    Validate that an uploaded shapefile has the expected structure.

    Consolidated from climate_hazards_analysis_v2 with enhanced error handling.

    Args:
        gdf (gpd.GeoDataFrame): The input geodataframe from the shapefile

    Returns:
        list[str]: Attribute column names

    Raises:
        ValueError: If the shapefile has no features, contains unsupported geometries,
                   or lacks a suitable facility name column.
    """
    if gdf.empty:
        raise ValueError("Shapefile contains no features")

    # Ensure geometries are of supported types
    allowed_geom_types = ["Point", "MultiPoint", "Polygon", "MultiPolygon"]
    unsupported_types = gdf.geometry.geom_type[~gdf.geometry.geom_type.isin(allowed_geom_types)].unique()

    if len(unsupported_types) > 0:
        raise ValueError(
            f"Shapefile contains unsupported geometry types: {unsupported_types}. "
            f"Allowed types: {allowed_geom_types}"
        )

    attribute_columns = [c for c in gdf.columns if c.lower() != "geometry"]

    facility_name_variations = [
        "facility", "site", "site name", "facility name", "facilty name",
        "name", "asset name", "facility_name", "site_name"
    ]

    if not any(col.strip().lower() in facility_name_variations for col in attribute_columns):
        raise ValueError(
            f"Shapefile attribute table must include a facility name column. "
            f"Looked for: {facility_name_variations}. "
            f"Available columns: {attribute_columns}"
        )

    logger.info(f"Shapefile validation passed. Found {len(gdf)} features with columns: {attribute_columns}")
    return attribute_columns


def safe_float_conversion(value, default_value: float = 0.0) -> float:
    """
    Safely convert a value to float with comprehensive error handling.

    This is the consolidated version of the float filtering functions.

    Args:
        value: Value to convert to float
        default_value (float): Default value if conversion fails

    Returns:
        float: Converted value or default_value
    """
    if value is None:
        return default_value

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        # Try direct conversion first
        try:
            return float(value)
        except (ValueError, TypeError):
            pass

        # Try to extract numeric value from string using regex
        import re
        match = re.search(r"-?\d+(?:\.\d+)?", str(value))
        if match:
            try:
                return float(match.group(0))
            except (ValueError, TypeError):
                pass

    return default_value


def create_geodataframe_from_facilities(df: pd.DataFrame,
                                     lat_col: str = 'Lat',
                                     lon_col: str = 'Long',
                                     crs: str = 'EPSG:4326') -> gpd.GeoDataFrame:
    """
    Create a GeoDataFrame from facility coordinates.

    Args:
        df (pd.DataFrame): Facility dataframe with coordinate columns
        lat_col (str): Name of latitude column
        lon_col (str): Name of longitude column
        crs (str): Coordinate reference system

    Returns:
        gpd.GeoDataFrame: GeoDataFrame with Point geometries

    Raises:
        ValueError: If coordinate columns are missing or invalid
    """
    if lat_col not in df.columns or lon_col not in df.columns:
        raise ValueError(f"Coordinate columns not found: {lat_col}, {lon_col}")

    # Remove any rows with missing coordinates
    df_clean = df.dropna(subset=[lat_col, lon_col])
    if len(df_clean) < len(df):
        logger.warning(f"Removed {len(df) - len(df_clean)} rows with missing coordinates")

    if df_clean.empty:
        raise ValueError("No valid coordinates found in dataframe")

    # Create Point geometries
    geometry = gpd.points_from_xy(df_clean[lon_col], df_clean[lat_col])
    gdf = gpd.GeoDataFrame(df_clean, geometry=geometry, crs=crs)

    logger.info(f"Created GeoDataFrame with {len(gdf)} facilities")
    return gdf


def validate_file_path(file_path: Union[str, Path],
                      must_exist: bool = True,
                      allowed_extensions: Optional[List[str]] = None) -> Path:
    """
    Validate a file path with comprehensive checks.

    Args:
        file_path (str|Path): File path to validate
        must_exist (bool): Whether file must exist
        allowed_extensions (list): List of allowed file extensions (e.g., ['.csv', '.xlsx'])

    Returns:
        Path: Validated Path object

    Raises:
        ValueError: If path validation fails
    """
    path = Path(file_path)

    # Check file extension
    if allowed_extensions:
        if path.suffix.lower() not in [ext.lower() for ext in allowed_extensions]:
            raise ValueError(f"File extension {path.suffix} not allowed. Allowed: {allowed_extensions}")

    # Check if file exists
    if must_exist and not path.exists():
        raise ValueError(f"File does not exist: {path}")

    # Check if parent directory exists
    if not path.parent.exists():
        raise ValueError(f"Parent directory does not exist: {path.parent}")

    return path


def process_nan_values_in_dataframe(df: pd.DataFrame,
                                  column_mappings: Optional[Dict[str, str]] = None) -> pd.DataFrame:
    """
    Process NaN values in a dataframe with column-specific replacements.

    Consolidated from climate_hazards_analysis.py with enhanced configurability.
    Enhanced to handle different data types appropriately, including pandas Int64 dtype.

    Args:
        df (pd.DataFrame): Input dataframe
        column_mappings (dict): Mapping of column patterns to replacement values
                              e.g., {'Flood': '0.1 to 0.5', 'Sea Level': 'Little to none'}

    Returns:
        pd.DataFrame: Processed dataframe with NaN values replaced
    """
    df = df.copy()

    # Default column mappings if not provided
    if column_mappings is None:
        column_mappings = {
            'Sea Level Rise': 'Little to none',
            'Elevation': 'Little to no effect',
            'Extreme Windspeed': 'Data not available',
            'Tropical Cyclone': 'Data not available',
            'Flood Depth': '0.1 to 0.5',
            'Water Stress': 'N/A',
            'Days over': 'N/A',
            'Heat': 'N/A'
        }

    logger.info(f"Processing NaN values for {len(df)} rows and {len(df.columns)} columns")

    for col in df.columns:
        if col in ['Facility', 'Lat', 'Long']:
            continue

        col_series = df[col]
        initial_nan_count = col_series.isna().sum()

        if initial_nan_count > 0:
            logger.info(f"Processing {initial_nan_count} NaN values in column '{col}' (dtype: {col_series.dtype})")

            # Find appropriate replacement based on column mappings
            replacement = 'N/A'  # Default
            for pattern, value in column_mappings.items():
                if pattern.lower() in col.lower():
                    replacement = value
                    break

            # Handle different data types appropriately
            dtype = col_series.dtype

            # Check for pandas nullable integer types (Int64, Int32, etc.)
            if pd.api.types.is_integer_dtype(dtype) and str(dtype).startswith('Int'):
                # For nullable integer types, use a numeric replacement or keep as NaN
                # Int64 columns in tropical cyclone analysis should stay as integers
                if 'Windspeed' in col or 'Tropical Cyclone' in col:
                    # For windspeed columns, use 0 as replacement (meaning no extreme winds)
                    logger.info(f"Filling NaN values in Int64 column '{col}' with 0")
                    df[col] = col_series.fillna(0)
                else:
                    # For other integer columns, use 0 as default
                    logger.info(f"Filling NaN values in Int64 column '{col}' with 0")
                    df[col] = col_series.fillna(0)

            # Check for float dtypes
            elif pd.api.types.is_float_dtype(dtype):
                # For float columns, use 0.0 as replacement
                logger.info(f"Filling NaN values in float column '{col}' with 0.0")
                df[col] = col_series.fillna(0.0)

            # Check for datetime dtypes
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                # For datetime columns, keep as NaT (Not a Time)
                logger.info(f"Keeping NaN values as NaT in datetime column '{col}'")
                # No replacement needed

            # For object/string dtypes and all others
            else:
                # Apply string replacement and convert to object dtype
                logger.info(f"Filling NaN values in column '{col}' with '{replacement}'")
                df[col] = col_series.fillna(replacement).astype(object)

    logger.info("NaN processing complete")
    return df


def merge_dataframes_safely(*dataframes: pd.DataFrame,
                          on_columns: List[str] = ['Facility', 'Lat', 'Long'],
                          how: str = 'left') -> pd.DataFrame:
    """
    Safely merge multiple dataframes with proper error handling and logging.

    Args:
        *dataframes: DataFrames to merge
        on_columns (list): Column names to merge on
        how (str): Type of merge ('left', 'inner', 'outer', 'right')

    Returns:
        pd.DataFrame: Merged dataframe

    Raises:
        ValueError: If merge fails due to incompatible columns
    """
    if not dataframes:
        raise ValueError("No dataframes provided for merging")

    if len(dataframes) == 1:
        return dataframes[0].copy()

    result = dataframes[0].copy()
    logger.info(f"Starting merge process with {len(dataframes)} dataframes")

    for i, df in enumerate(dataframes[1:], 1):
        # Check if merge columns exist
        missing_on_cols = [col for col in on_columns if col not in df.columns]
        if missing_on_cols:
            raise ValueError(f"Dataframe {i} missing merge columns: {missing_on_cols}")

        missing_result_cols = [col for col in on_columns if col not in result.columns]
        if missing_result_cols:
            raise ValueError(f"Result dataframe missing merge columns: {missing_result_cols}")

        # Perform merge
        before_count = len(result)
        result = result.merge(df, on=on_columns, how=how)
        after_count = len(result)

        logger.info(f"Merged dataframe {i}: {before_count} -> {after_count} rows")
        logger.info(f"Columns after merge {i}: {len(result.columns)}")

    return result


def load_cached_hazard_data(hazard_type: str,
                          base_dir: Optional[Path] = None,
                          cache_subdir: str = 'static/output') -> Optional[List[Dict]]:
    """
    Load pre-computed hazard data from cache files.

    Enhanced version from climate_hazards_analysis_v2 with better error handling.

    Args:
        hazard_type (str): Type of hazard data to load
        base_dir (Path): Base directory path (defaults to Django BASE_DIR)
        cache_subdir (str): Subdirectory containing cached files

    Returns:
        list[dict]: Hazard data as list of dictionaries, or None if not found
    """
    if base_dir is None:
        base_dir = Path(settings.BASE_DIR)

    # Define standard cache file mappings
    file_mappings = {
        'flood': 'flood_exposure_analysis_output.csv',
        'water_stress': 'water_stress_analysis_output.csv',
        'heat': 'heat_exposure_analysis_output.csv',
        'sea_level_rise': 'sea_level_rise_analysis_output.csv',
        'tropical_cyclone': 'tropical_cyclone_analysis_output.csv'
    }

    if hazard_type not in file_mappings:
        logger.warning(f"Unknown hazard type: {hazard_type}")
        return None

    cache_dir = base_dir / 'climate_hazards_analysis' / cache_subdir
    file_path = cache_dir / file_mappings[hazard_type]

    try:
        if not file_path.exists():
            logger.warning(f"Cache file not found: {file_path}")
            return None

        # Load the CSV data
        df = pd.read_csv(file_path)
        logger.info(f"Loaded cached {hazard_type} data: {len(df)} records from {file_path}")

        # Return as list of dictionaries for easier processing
        return df.to_dict(orient='records')

    except Exception as e:
        logger.exception(f"Error loading cached hazard data for {hazard_type}: {e}")
        return None


def get_safe_filename(base_name: str,
                     extension: str = '.csv',
                     max_length: int = 255) -> str:
    """
    Generate a safe filename by removing invalid characters.

    Args:
        base_name (str): Base filename
        extension (str): File extension
        max_length (int): Maximum filename length

    Returns:
        str: Safe filename
    """
    import re

    # Remove invalid characters
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)
    safe_name = re.sub(r'\s+', '_', safe_name.strip())

    # Ensure extension starts with dot
    if not extension.startswith('.'):
        extension = '.' + extension

    # Truncate if too long
    max_base_length = max_length - len(extension)
    if len(safe_name) > max_base_length:
        safe_name = safe_name[:max_base_length]

    return safe_name + extension


# Error handling utilities
class DataValidationError(Exception):
    """Custom exception for data validation errors."""
    pass


class FileProcessingError(Exception):
    """Custom exception for file processing errors."""
    pass


def combine_facility_with_hazard_data(facilities: List[Dict],
                                     hazard_data_list: List[List[Dict]]) -> List[Dict]:
    """
    Enrich facility data with available hazard data based on coordinates.

    This function was moved from climate_hazards_analysis_v2/utils.py to the
    consolidated common utilities module.

    Args:
        facilities (list): List of facility dictionaries with Lat/Long
        hazard_data_list (list): List of hazard data dictionaries

    Returns:
        list: Enriched facility dictionaries with hazard data
    """
    # If no hazard data provided, return original facilities
    if not hazard_data_list:
        return facilities

    enriched_facilities = []

    # Process each facility
    for facility in facilities:
        enriched_facility = facility.copy()

        # Try to match facility with hazard data based on coordinates
        for hazard_data in hazard_data_list:
            if not hazard_data:
                continue

            # Find matching facilities in hazard data by coordinates
            matches = [
                h for h in hazard_data
                if abs(h.get('Lat', 0) - facility.get('Lat', 0)) < 0.0001 and
                   abs(h.get('Long', 0) - facility.get('Long', 0)) < 0.0001
            ]

            # If matches found, add hazard data to facility
            if matches:
                # Add all fields from the first match except Facility, Lat, Long
                for key, value in matches[0].items():
                    if key not in ['Facility', 'Lat', 'Long']:
                        enriched_facility[key] = value

        enriched_facilities.append(enriched_facility)

    return enriched_facilities


def handle_processing_error(error: Exception,
                          context: str = "",
                          default_return: Any = None,
                          reraise: bool = False) -> Any:
    """
    Handle processing errors with consistent logging and error handling.

    Args:
        error (Exception): The error that occurred
        context (str): Context description for the error
        default_return: Default return value if not reraising
        reraise (bool): Whether to reraise the exception

    Returns:
        default_return if not reraising

    Raises:
        The original exception if reraise=True
    """
    error_msg = f"Error {context}: {str(error)}" if context else str(error)

    if isinstance(error, (ValueError, FileNotFoundError)):
        logger.error(error_msg)
    else:
        logger.exception(error_msg)

    if reraise:
        raise error

    return default_return