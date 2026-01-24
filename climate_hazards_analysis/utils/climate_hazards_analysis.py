"""
Integrated Climate Hazards Analysis Module

This module provides functionality to generate a combined analysis of multiple climate hazards
for facility locations, integrating data from specialized modules for each hazard type.

Dependencies:
- pandas, numpy, matplotlib, geopandas
- Specialized hazard analysis modules
"""

import os
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import rasterstats as rstat
from shapely.geometry import shape
from django.conf import settings

# Import specialized hazard analysis modules
from sea_level_rise_analysis.utils.sea_level_rise_analysis import generate_sea_level_rise_analysis
from tropical_cyclone_analysis.utils.tropical_cyclone_analysis import generate_tropical_cyclone_analysis
from water_stress.utils.water_stress_analysis import generate_water_stress_analysis
from water_stress.utils.water_stress_future_analysis import generate_future_water_stress_from_baseline
from heat_exposure_analysis.utils.heat_exposure_analysis import generate_heat_exposure_analysis
from heat_exposure_analysis.utils.heat_future_analysis import generate_heat_future_analysis
from climate_hazards_analysis.utils.storm_surge_updated import generate_storm_surge_analysis
from climate_hazards_analysis.utils.rainfall_induced_landslide_updated import (
    generate_rainfall_induced_landslide_analysis,
)
from flood_exposure_analysis.utils.flood_exposure_analysis import generate_flood_exposure_analysis
from climate_hazards_analysis.utils.common_utils import (
    standardize_facility_dataframe as _standardize_facility_dataframe,
    process_nan_values_in_dataframe,
    merge_dataframes_safely
)


# Set up logging
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
    return _standardize_facility_dataframe(df, strict_mode=True)


def process_flood_exposure_analysis(facility_csv_path, selected_fields, scenarios=None, facility_geofile_path=None, facility_geojson_records=None):
    """
    Process flood exposure analysis if selected.
    Enhanced version that supports multiple flood scenarios.

    Args:
        facility_csv_path (str): Path to facility CSV file
        selected_fields (list): List of selected fields for analysis
        scenarios (list): List of flood scenarios ['current', 'moderate', 'worst']
                         Default: ['current'] for backward compatibility
    """
    if 'Flood' not in selected_fields:
        logger.info("Flood analysis not selected, skipping")
        return None, []

    # Default to current scenario for backward compatibility
    if scenarios is None:
        scenarios = ['current']

    logger.info(f"Starting Flood Exposure Analysis with scenarios: {scenarios}")
    logger.info(f"{'='*60}")
    logger.info(f"CLIMATE HAZARDS ANALYSIS - FLOOD PROCESSING")
    logger.info(f"{'='*60}")
    logger.info(f"Facility CSV: {facility_csv_path}")
    logger.info(f"Selected scenarios: {scenarios}")
    logger.info(f"Number of scenarios: {len(scenarios)}")

    plot_paths = []

    try:
        # Import the enhanced flood analysis function
        from flood_exposure_analysis.utils.flood_exposure_analysis import generate_flood_exposure_analysis

        logger.info("Calling multi-scenario flood exposure analysis function...")
        # Call with scenarios parameter
        flood_res = generate_flood_exposure_analysis(
            facility_csv_path,
            scenarios=scenarios,
            facility_geofile_path=facility_geofile_path,
            facility_geojson_records=facility_geojson_records
        )
        logger.info("Multi-scenario flood exposure analysis completed")
        
        if 'error' in flood_res:
            logger.warning(f"Warning in Flood Exposure Analysis: {flood_res['error']}")
            # Create placeholder flood data instead of returning None
            df_fac = pd.read_csv(facility_csv_path)
            df_fac = standardize_facility_dataframe(df_fac)
            df_fac['Flood Depth (meters)'] = '0.1 to 0.5'  # Default to lowest risk category
            return df_fac[['Facility', 'Lat', 'Long', 'Flood Depth (meters)']], []
            
        if not flood_res.get('combined_csv_paths'):
            logger.warning("No flood CSV paths returned")
            # Create placeholder flood data
            df_fac = pd.read_csv(facility_csv_path)
            df_fac = standardize_facility_dataframe(df_fac)
            df_fac['Flood Depth (meters)'] = '0.1 to 0.5'
            return df_fac[['Facility', 'Lat', 'Long', 'Flood Depth (meters)']], plot_paths
            
        # Read the flood analysis CSV with proper encoding handling
        flood_csv_path = flood_res['combined_csv_paths'][0]
        logger.info(f"Reading flood CSV from: {flood_csv_path}")
        
        try:
            df_flood = pd.read_csv(flood_csv_path, encoding='utf-8')
        except UnicodeDecodeError:
            try:
                df_flood = pd.read_csv(flood_csv_path, encoding='latin-1')
                logger.warning("Flood CSV read with latin-1 encoding")
            except UnicodeDecodeError:
                df_flood = pd.read_csv(flood_csv_path, encoding='cp1252')
                logger.warning("Flood CSV read with cp1252 encoding")
        
        logger.info(f"Flood CSV columns: {df_flood.columns.tolist()}")
        logger.info(f"Flood CSV shape: {df_flood.shape}")
        
        # Standardize column names
        rename_map = {'Site': 'Facility', 'latitude': 'Lat', 'longitude': 'Long'}
        for old, new in rename_map.items():
            if old in df_flood.columns and new not in df_flood.columns:
                df_flood.rename(columns={old: new}, inplace=True)
        
        # Get the expected flood columns based on scenarios processed
        result_columns = flood_res.get('result_columns', ['Facility', 'Lat', 'Long', 'Flood Depth (meters)'])
        flood_columns = [col for col in result_columns if 'Flood Depth' in col]
        scenarios_processed = flood_res.get('scenarios_processed', [])

        logger.info(f"FLOOD ANALYSIS RESULTS:")
        logger.info(f"  Scenarios processed: {scenarios_processed}")
        logger.info(f"  Expected flood columns: {flood_columns}")
        logger.info(f"  Available columns in CSV: {df_flood.columns.tolist()}")
        logger.info(f"  Total columns expected: {len(flood_columns)}")
        logger.info(f"  CSV file path: {flood_csv_path}")

        # Check if we have all expected flood columns
        missing_columns = [col for col in flood_columns if col not in df_flood.columns]
        if missing_columns:
            logger.warning(f"Missing flood columns: {missing_columns}")
        else:
            logger.info(f"SUCCESS: All expected flood columns found in CSV!")

        # Log flood column mapping
        for i, scenario in enumerate(scenarios_processed):
            expected_col = flood_columns[i] if i < len(flood_columns) else f"Unknown column {i}"
            exists = expected_col in df_flood.columns
            logger.info(f"  Scenario '{scenario}' -> Column '{expected_col}' -> Present: {exists}")

        # Find available flood columns (including legacy column names)
        available_flood_columns = []
        for col in df_flood.columns:
            if any(flood_col in col for flood_col in ['Flood Depth', 'Exposure', 'flood_depth', 'Flood_Depth']):
                available_flood_columns.append(col)

        if not available_flood_columns:
            logger.warning(f"No flood depth columns found in output. Available columns: {df_flood.columns.tolist()}")
            # Create placeholder data with the expected columns
            df_fac = pd.read_csv(facility_csv_path)
            df_fac = standardize_facility_dataframe(df_fac)
            for col in flood_columns:
                df_fac[col] = '0.1 to 0.5'  # Default to lowest risk category
            return df_fac[['Facility', 'Lat', 'Long'] + flood_columns], []

        # Select the columns we want to return
        output_columns = ['Facility', 'Lat', 'Long'] + available_flood_columns
        df_flood_values = df_flood[output_columns]

        logger.info(f"Successfully found flood columns: {available_flood_columns}")
            
        # Clean any NaN values in all flood columns
        valid_categories = {
            '0.1 to 0.5', '0.5 to 1.5', 'Greater than 1.5', 'Unknown',
            '<0.1', '0.1-0.5', '0.5-1.5', '>1.5'
        }

        for flood_col in available_flood_columns:
            # Handle NaN values
            flood_nan_count = df_flood_values[flood_col].isna().sum()
            if flood_nan_count > 0:
                logger.warning(f"Found {flood_nan_count} NaN values in {flood_col}, replacing with '0.1 to 0.5'")
                df_flood_values[flood_col].fillna('0.1 to 0.5', inplace=True)

            # Ensure all values are valid categories
            invalid_mask = ~df_flood_values[flood_col].isin(valid_categories)
            invalid_count = invalid_mask.sum()
            if invalid_count > 0:
                logger.warning(f"Found {invalid_count} invalid flood category values in {flood_col}, replacing with '0.1 to 0.5'")
                invalid_values = df_flood_values.loc[invalid_mask, flood_col].unique()
                logger.warning(f"Invalid values were: {invalid_values}")
                df_flood_values.loc[invalid_mask, flood_col] = '0.1 to 0.5'

            # Final verification for this column
            final_nan_count = df_flood_values[flood_col].isna().sum()
            if final_nan_count > 0:
                logger.error(f"ERROR: Still have {final_nan_count} NaN values in {flood_col} after cleaning!")
                df_flood_values[flood_col].fillna('0.1 to 0.5', inplace=True)

            logger.info(f"{flood_col} value counts:")
            logger.info(df_flood_values[flood_col].value_counts())
        
        # Collect plot paths
        if flood_res.get('png_paths'):
            plot_paths.extend(flood_res['png_paths'])
        
        logger.info(f"Successfully processed flood data with {len(df_flood_values)} rows")
        logger.info(f"Sample flood data:\n{df_flood_values.head()}")
            
        return df_flood_values, plot_paths
        
    except Exception as e:
        logger.exception(f"Error in Flood Exposure Analysis: {e}")
        # Create placeholder flood data even on error
        try:
            df_fac = pd.read_csv(facility_csv_path)
            df_fac = standardize_facility_dataframe(df_fac)
            df_fac['Flood Depth (meters)'] = '0.1 to 0.5'  # Default to lowest risk category
            return df_fac[['Facility', 'Lat', 'Long', 'Flood Depth (meters)']], []
        except Exception as e2:
            logger.exception(f"Error creating placeholder flood data: {e2}")
            return None, []


def process_water_stress_analysis(facility_csv_path, selected_fields, buffer_size=0.0009):
    """
    Process water stress analysis if selected.
    Args:
    facility_csv_path (str): Path to facility CSV
    selected_fields (list): List of selected hazard types
    buffer_size (float): Buffer size for analysis
    
    Returns:
        tuple: (DataFrame with water stress values, list of plot paths)
    """
    if 'Water Stress' not in selected_fields:
        return None, []
        
    logger.info(f"Integrating Water Stress Analysis with buffer size: {buffer_size}")
    plot_paths = []

    try:
        ws_res = generate_water_stress_analysis(facility_csv_path, buffer_size)
        
        if 'error' in ws_res:
            logger.warning(f"Warning in Water Stress Analysis: {ws_res['error']}")
            return None, []
            
        if not ws_res.get('combined_csv_paths'):
            return None, plot_paths
            
        # Read the water stress analysis CSV with proper encoding handling
        try:
            df_ws = pd.read_csv(ws_res['combined_csv_paths'][0], encoding='utf-8')
        except UnicodeDecodeError:
            df_ws = pd.read_csv(ws_res['combined_csv_paths'][0], encoding='latin-1')

        # Generate future water stress projections using pfaf_id
        future_res = generate_future_water_stress_from_baseline(ws_res['combined_csv_paths'][0])
        if future_res.get('output_csv'):
            try:
                df_ws = pd.read_csv(future_res['output_csv'])
            except Exception as e:
                logger.warning(f"Failed to load future water stress output: {e}")
        
        # Standardize column names
        rename_map = {'Site': 'Facility', 'latitude': 'Lat', 'longitude': 'Long'}
        for old, new in rename_map.items():
            if old in df_ws.columns and new not in df_ws.columns:
                df_ws.rename(columns={old: new}, inplace=True)
        
        if 'bws_raw' in df_ws.columns:
            df_ws.rename(columns={'bws_raw': 'Water Stress Exposure (%)'}, inplace=True)

        if 'pfaf_id' in df_ws.columns:
            df_ws.drop(columns=['pfaf_id'], inplace=True)

        water_cols = [
            'Water Stress Exposure (%)',
            'Water Stress Exposure 2030 (%) - Moderate Case',
            'Water Stress Exposure 2050 (%) - Moderate Case',
            'Water Stress Exposure 2030 (%) - Worst Case',
            'Water Stress Exposure 2050 (%) - Worst Case',
        ]
        existing_water_cols = [c for c in water_cols if c in df_ws.columns]
        if not existing_water_cols:
            logger.warning("Water stress columns not found in analysis output")
            return None, plot_paths
        df_ws_values = df_ws[['Facility', 'Lat', 'Long'] + existing_water_cols]
            
        # Collect plot paths
        if ws_res.get('png_paths'):
            plot_paths.extend(ws_res['png_paths'])
            
        return df_ws_values, plot_paths
        
    except Exception as e:
        logger.exception(f"Error in Water Stress Analysis: {e}")
        return None, []


def _load_facility_geometries_for_slr(facility_geofile_path, facility_geojson_records, df_fallback):
    gdf = None
    if facility_geofile_path:
        try:
            gdf = gpd.read_file(facility_geofile_path)
        except Exception:
            gdf = None

    if gdf is None and facility_geojson_records:
        geo_rows = []
        geometries = []
        for record in facility_geojson_records:
            geom = record.get("geometry")
            if not geom:
                continue
            try:
                geometries.append(shape(geom))
            except Exception:
                continue
            geo_rows.append(
                {
                    "Facility": record.get("Facility")
                    or record.get("Name")
                    or record.get("Site"),
                    "Lat": record.get("Lat"),
                    "Long": record.get("Long"),
                }
            )
        if geo_rows and geometries:
            gdf = gpd.GeoDataFrame(geo_rows, geometry=geometries, crs="EPSG:4326")

    if gdf is None:
        df_points = df_fallback[['Facility', 'Lat', 'Long']].copy()
        geometry = gpd.points_from_xy(df_points['Long'], df_points['Lat'], crs='EPSG:4326')
        gdf = gpd.GeoDataFrame(df_points, geometry=geometry, crs='EPSG:4326')

    gdf = gdf.to_crs("EPSG:4326")
    if "Facility" not in gdf.columns:
        for name_col in ["Name", "name", "NAME", "Site", "Asset", "asset", "facility"]:
            if name_col in gdf.columns:
                gdf["Facility"] = gdf[name_col].astype(str)
                break
    if "Facility" not in gdf.columns:
        gdf["Facility"] = [f"Facility {i + 1}" for i in range(len(gdf))]

    return gdf[['Facility', 'geometry']].copy()


def _apply_ssa1_exposure_mask(slr_values, facility_geofile_path, facility_geojson_records):
    ssa1_path = Path(settings.BASE_DIR) / 'climate_hazards_analysis' / 'static' / 'input_files' / 'PH_SSA1.shp'
    if not ssa1_path.exists():
        logger.warning(f"SSA1 file not found: {ssa1_path}")
        return slr_values

    try:
        ssa1_gdf = gpd.read_file(ssa1_path).to_crs("EPSG:4326")
    except Exception as e:
        logger.warning(f"Failed to load SSA1 file: {e}")
        return slr_values

    fac_gdf = _load_facility_geometries_for_slr(
        facility_geofile_path,
        facility_geojson_records,
        slr_values[['Facility', 'Lat', 'Long']]
    )
    if fac_gdf.empty:
        return slr_values

    fac_gdf['Facility_key'] = fac_gdf['Facility'].astype(str).str.strip().str.lower()
    slr_values = slr_values.copy()
    slr_values['Facility_key'] = slr_values['Facility'].astype(str).str.strip().str.lower()

    try:
        coastal = gpd.sjoin(fac_gdf, ssa1_gdf, how='inner', predicate='intersects')
        coastal_keys = set(coastal['Facility_key'].unique())
    except Exception as e:
        logger.warning(f"SSA1 spatial join failed: {e}")
        return slr_values.drop(columns=['Facility_key'], errors='ignore')

    slr_cols = [c for c in slr_values.columns if 'Sea Level Rise (meters)' in c]
    if slr_cols:
        mask = ~slr_values['Facility_key'].isin(coastal_keys)
        for col in slr_cols:
            slr_values.loc[mask, col] = 'Not Exposed'

    return slr_values.drop(columns=['Facility_key'], errors='ignore')


def process_sea_level_rise_analysis(facility_csv_path, selected_fields, facility_geofile_path=None, facility_geojson_records=None):
    """
    Process sea level rise analysis if selected.

    Args:
        facility_csv_path (str): Path to facility CSV
        selected_fields (list): List of selected hazard types

    Returns:
        tuple: (DataFrame with SLR values, list of plot paths)
    """
    if 'Sea Level Rise' not in selected_fields:
        logger.info("Sea Level Rise not in selected fields, skipping")
        return None, []

    logger.info("=== STARTING SEA LEVEL RISE ANALYSIS ===")
    logger.info(f"Facility CSV path: {facility_csv_path}")
    plot_paths = []

    try:
        logger.info("Calling generate_sea_level_rise_analysis...")
        slr_res = generate_sea_level_rise_analysis(facility_csv_path)
        logger.info(f"SLR analysis result keys: {slr_res.keys() if slr_res else 'None'}")

        if 'error' in slr_res:
            logger.error(f"ERROR in Sea Level Rise Analysis: {slr_res['error']}")
            return None, []

        if not slr_res.get('combined_csv_paths'):
            logger.warning("No combined_csv_paths in SLR result")
            return None, plot_paths
            
        # Read the SLR analysis CSV with proper encoding handling
        slr_csv_path = slr_res['combined_csv_paths'][0]
        logger.info(f"Reading SLR CSV from: {slr_csv_path}")
        logger.info(f"SLR CSV exists: {os.path.exists(slr_csv_path)}")

        try:
            df_slr = pd.read_csv(slr_csv_path, encoding='utf-8')
        except UnicodeDecodeError:
            df_slr = pd.read_csv(slr_csv_path, encoding='latin-1')

        logger.info(f"SLR DataFrame shape: {df_slr.shape}")
        logger.info(f"SLR DataFrame columns: {df_slr.columns.tolist()}")

        # Standardize column names
        rename_map = {
            'Site': 'Facility',
            'LAT': 'Lat',
            'latitude': 'Lat',
            'Lon': 'Long',
            'LON': 'Long',
            'LONG': 'Long',
            'longitude': 'Long'
        }
        logger.info(f"Applying rename map: {rename_map}")
        for old, new in rename_map.items():
            if old in df_slr.columns and new not in df_slr.columns:
                df_slr.rename(columns={old: new}, inplace=True)

        logger.info(f"SLR DataFrame columns after renaming: {df_slr.columns.tolist()}")
        
        # Standardize sea level rise column names
        rename_fields = {
            # Old median CI columns -> new Moderate case naming
            '2030 Sea Level Rise CI 0.5': '2030 Sea Level Rise (meters) - Moderate Case',
            '2040 Sea Level Rise CI 0.5': '2040 Sea Level Rise (meters) - Moderate Case',
            '2050 Sea Level Rise CI 0.5': '2050 Sea Level Rise (meters) - Moderate Case',
            '2060 Sea Level Rise CI 0.5': '2060 Sea Level Rise (meters) - Moderate Case',
            # Older generic naming -> new Moderate case
            '2030 Sea Level Rise (in meters)': '2030 Sea Level Rise (meters) - Moderate Case',
            '2040 Sea Level Rise (in meters)': '2040 Sea Level Rise (meters) - Moderate Case',
            '2050 Sea Level Rise (in meters)': '2050 Sea Level Rise (meters) - Moderate Case',
            '2060 Sea Level Rise (in meters)': '2060 Sea Level Rise (meters) - Moderate Case',
        }
        df_slr.rename(columns=rename_fields, inplace=True)
        
        # Rename elevation column if present
        if 'SRTM elevation' in df_slr.columns:
            df_slr.rename(columns={'SRTM elevation': 'Elevation (meter above sea level)'}, inplace=True)
        
        # Get available SLR columns (both Moderate and Worst Case)
        slr_cols = [c for c in df_slr.columns if 'Sea Level Rise (meters)' in c]
        if 'Elevation (meter above sea level)' in df_slr.columns:
            slr_cols.insert(0, 'Elevation (meter above sea level)')
        available_slr_cols = slr_cols

        logger.info(f"Available SLR columns found: {available_slr_cols}")

        if not available_slr_cols:
            logger.warning("No SLR columns found in analysis output")
            return None, plot_paths

        # Create SLR values dataframe
        required_cols = ['Facility', 'Lat', 'Long']
        logger.info(f"Required columns for merge: {required_cols}")
        logger.info(f"Checking if required columns exist in df_slr: {[col in df_slr.columns for col in required_cols]}")

        slr_values = df_slr[required_cols + available_slr_cols].copy()
        logger.info(f"Created SLR values dataframe with shape: {slr_values.shape}")
        logger.info(f"SLR values columns: {slr_values.columns.tolist()}")

        slr_values = _apply_ssa1_exposure_mask(
            slr_values,
            facility_geofile_path,
            facility_geojson_records,
        )

        # Collect plot paths
        if slr_res.get('png_paths'):
            plot_paths.extend(slr_res['png_paths'])

        logger.info("=== SEA LEVEL RISE ANALYSIS COMPLETED SUCCESSFULLY ===")
        return slr_values, plot_paths
        
    except Exception as e:
        logger.exception(f"Error in Sea Level Rise Analysis: {e}")
        return None, []


def process_tropical_cyclone_analysis(facility_csv_path, selected_fields):
    """
    Process tropical cyclone analysis if selected.
    Modified to exclude 200 and 500-year return period columns.
    
    Args:
        facility_csv_path (str): Path to facility CSV
        selected_fields (list): List of selected hazard types
        
    Returns:
        tuple: (DataFrame with TC values, list of plot paths)
    """
    if 'Tropical Cyclones' not in selected_fields:
        return None, []
        
    logger.info("Integrating Tropical Cyclones Analysis")
    plot_paths = []
    
    try:
        tc_res = generate_tropical_cyclone_analysis(facility_csv_path)
        
        if 'error' in tc_res:
            logger.warning(f"Warning in Tropical Cyclones Analysis: {tc_res['error']}")
            return None, []
            
        if not tc_res.get('combined_csv_paths'):
            return None, plot_paths
            
        # Read the TC analysis CSV with proper encoding handling
        try:
            df_tc = pd.read_csv(tc_res['combined_csv_paths'][0], encoding='utf-8')
        except UnicodeDecodeError:
            df_tc = pd.read_csv(tc_res['combined_csv_paths'][0], encoding='latin-1')
        
        # Standardize column names
        rename_map = {
            'Facility Name': 'Facility',
            'Latitude': 'Lat',
            'Longitude': 'Long'
        }
        for old, new in rename_map.items():
            if old in df_tc.columns and new not in df_tc.columns:
                df_tc.rename(columns={old: new}, inplace=True)
        
        # Standardize TC column names - focus on 100-year RP current + future horizons
        tc_rename = {
            '1-min MSW 100 yr RP': 'Extreme Windspeed 100 year Return Period (km/h)',
        }
        df_tc.rename(columns=tc_rename, inplace=True)
        
        tc_cols = [
            'Extreme Windspeed 100 year Return Period (km/h)',
            '2030 - Extreme Windspeed 100 year Return Period (km/h)',
            '2040 - Extreme Windspeed 100 year Return Period (km/h)',
            '2050 - Extreme Windspeed 100 year Return Period (km/h)',
            '2030 - Extreme Windspeed 100 year Return Period (km/h) - RCP8.5',
            '2040 - Extreme Windspeed 100 year Return Period (km/h) - RCP8.5',
            '2050 - Extreme Windspeed 100 year Return Period (km/h) - RCP8.5',
        ]
        
        # Filter columns that exist in the DataFrame
        available_tc_cols = [col for col in tc_cols if col in df_tc.columns]
        
        if not available_tc_cols:
            logger.warning("No TC columns found in analysis output")
            return None, plot_paths
            
        # Create TC values dataframe
        tc_values = df_tc[['Facility', 'Lat', 'Long'] + available_tc_cols].copy()
        
        return tc_values, plot_paths
        
    except Exception as e:
        logger.exception(f"Error in Tropical Cyclones Analysis: {e}")
        return None, []


def process_heat_exposure_analysis(
    facility_csv_path,
    selected_fields,
    facility_geofile_path=None,
    facility_geojson_records=None,
):
    """
    Process heat exposure analysis if selected.
    
    Args:
        facility_csv_path (str): Path to facility CSV
        selected_fields (list): List of selected hazard types
        
    Returns:
        tuple: (DataFrame with heat values, list of plot paths)
    """
    if 'Heat' not in selected_fields:
        return None, []
        
    logger.info("Integrating Heat Exposure Analysis")
    plot_paths = []
    
    try:
        heat_res = generate_heat_exposure_analysis(
            facility_csv_path,
            facility_geofile_path=facility_geofile_path,
            facility_geojson_records=facility_geojson_records,
        )
        
        if 'error' in heat_res:
            logger.warning(f"Warning in Heat Exposure Analysis: {heat_res['error']}")
            return None, []
            
        if not heat_res.get('combined_csv_paths'):
            return None, plot_paths
            
        # Read the heat analysis CSV with proper encoding handling
        try:
            df_heat = pd.read_csv(heat_res['combined_csv_paths'][0], encoding='utf-8')
        except UnicodeDecodeError:
            df_heat = pd.read_csv(heat_res['combined_csv_paths'][0], encoding='latin-1')
        logger.info(f"Heat exposure columns: {df_heat.columns.tolist()}")
        
        # Standardize column names
        rename_map = {'Site': 'Facility', 'latitude': 'Lat', 'longitude': 'Long'}
        for old, new in rename_map.items():
            if old in df_heat.columns and new not in df_heat.columns:
                df_heat.rename(columns={old: new}, inplace=True)
        
        # Standardize heat column names
        heat_cols = []
        
        # Handle original format from heat_exposure_analysis.py
        temp_mapping = {
            'n>35degC_2125': 'Days over 35° Celsius',
            'Days over 35 Celsius': 'Days over 35° Celsius',
        }
        
        for old, new in temp_mapping.items():
            if old in df_heat.columns:
                df_heat.rename(columns={old: new}, inplace=True)
                heat_cols.append(new)
            elif new in df_heat.columns:
                heat_cols.append(new)
        
        if not heat_cols:
            logger.warning("No heat columns found in analysis output")
            return None, plot_paths
            
        # Create heat values dataframe
        heat_values = df_heat[['Facility', 'Lat', 'Long'] + heat_cols].copy()
        try:
            df_fac = pd.read_csv(facility_csv_path)
            df_fac = standardize_facility_dataframe(df_fac)
            if 'Facility' in df_fac.columns and 'Lat' in df_fac.columns and 'Long' in df_fac.columns:
                df_fac_unique = df_fac.drop_duplicates(subset=['Facility']).copy()
                df_fac_unique['Facility_key'] = df_fac_unique['Facility'].astype(str).str.strip().str.lower()
                lat_map = df_fac_unique.set_index('Facility_key')['Lat'].to_dict()
                long_map = df_fac_unique.set_index('Facility_key')['Long'].to_dict()
                heat_keys = heat_values['Facility'].astype(str).str.strip().str.lower()
                heat_values['Lat'] = heat_keys.map(lat_map).fillna(heat_values['Lat'])
                heat_values['Long'] = heat_keys.map(long_map).fillna(heat_values['Long'])
        except Exception:
            logger.info("Heat exposure coordinate alignment skipped")
        
        # Collect plot paths
        if heat_res.get('png_paths'):
            plot_paths.extend(heat_res['png_paths'])
            
        return heat_values, plot_paths
        
    except Exception as e:
        logger.exception(f"Error in Heat Exposure Analysis: {e}")
        return None, []


def _build_point_buffer_geometries(df_fac):
    df_a = df_fac[['Facility', 'Lat', 'Long']].copy()
    df_a.rename(columns={'Lat': 'latitude', 'Long': 'longitude'}, inplace=True)
    df_a[['latitude', 'longitude']] = df_a[['latitude', 'longitude']].astype(float)
    df_a['lot_area'] = 250
    gs_a = gpd.points_from_xy(df_a['longitude'], df_a['latitude'], crs='EPSG:4326').to_crs('EPSG:32651')
    gdf_a = gpd.GeoDataFrame(df_a, geometry=gs_a, crs='EPSG:32651')
    gdf_a['geometry'] = gdf_a.geometry.buffer(np.sqrt(gdf_a['lot_area'])/2, cap_style='square', join_style='mitre')
    return gdf_a


def _get_polygon_facility_keys(facility_geofile_path, facility_geojson_records):
    gdf = None
    if facility_geofile_path:
        try:
            gdf = gpd.read_file(facility_geofile_path)
        except Exception:
            gdf = None

    if gdf is None and facility_geojson_records:
        geo_rows = []
        geometries = []
        for record in facility_geojson_records:
            geom = record.get("geometry")
            if not geom:
                continue
            try:
                shapely_geom = shape(geom)
            except Exception:
                continue
            geometries.append(shapely_geom)
            geo_rows.append(
                {
                    "Facility": record.get("Facility")
                    or record.get("Name")
                    or record.get("Site"),
                }
            )
        if geo_rows and geometries:
            gdf = gpd.GeoDataFrame(geo_rows, geometry=geometries, crs="EPSG:4326")

    if gdf is None:
        return set()

    gdf = gdf.to_crs("EPSG:4326")
    if "Facility" not in gdf.columns:
        for name_col in ["Name", "name", "NAME", "Site", "Asset", "asset", "facility"]:
            if name_col in gdf.columns:
                gdf["Facility"] = gdf[name_col].astype(str)
                break
    if "Facility" not in gdf.columns:
        return set()

    poly_mask = gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
    gdf = gdf[poly_mask]
    return set(gdf["Facility"].astype(str).str.strip().str.lower())


def process_storm_surge_analysis(
    df_fac,
    selected_fields,
    facility_geofile_path=None,
    facility_geojson_records=None,
):
    """
    Process storm surge analysis if selected.
    """
    if 'Storm Surge' not in selected_fields:
        return None

    try:
        idir = Path(settings.BASE_DIR) / 'climate_hazards_analysis' / 'static' / 'input_files'
        fp_ss = idir / 'PH_StormSurge_Advisory4_UTM_ProjectNOAH_Unmasked.tif'
        fp_ss_future = idir / 'PH_StormSurge_Advisory4_Future_UTM_ProjectNOAH-GIRI_Unmasked.tif'

        missing = []
        if not os.path.exists(fp_ss):
            missing.append(str(fp_ss))
        if not os.path.exists(fp_ss_future):
            missing.append(str(fp_ss_future))

        if missing:
            logger.warning(f"Missing raster files for Storm Surge analysis: {', '.join(missing)}")
            return None

        df_values = generate_storm_surge_analysis(
            df_fac,
            fp_ss,
            fp_ss_future,
            facility_geofile_path=facility_geofile_path,
            facility_geojson_records=facility_geojson_records,
        )
        return df_values[['Facility', 'Lat', 'Long',
                          'Storm Surge Flood Depth (meters)',
                          'Storm Surge Flood Depth (meters) - Worst Case']].copy()

    except Exception as e:
        logger.exception(f"Error in Storm Surge analysis: {e}")
        return None


def process_landslide_analysis(
    df_fac,
    selected_fields,
    facility_geofile_path=None,
    facility_geojson_records=None,
):
    """
    Process rainfall-induced landslide analysis if selected.
    """
    if 'Rainfall Induced Landslide' not in selected_fields:
        return None

    try:
        idir = Path(settings.BASE_DIR) / 'climate_hazards_analysis' / 'static' / 'input_files'
        fp_ls = idir / 'PH_LandslideHazards_UTM_ProjectNOAH_Unmasked.tif'
        fp_ls_mod = idir / 'PH_LandslideHazards_RCP26_UTM_ProjectNOAH-GIRI_Unmasked.tif'
        fp_ls_worst = idir / 'PH_LandslideHazards_RCP85_UTM_ProjectNOAH-GIRI_Unmasked.tif'

        missing = []
        if not os.path.exists(fp_ls):
            missing.append(str(fp_ls))
        if not os.path.exists(fp_ls_mod):
            missing.append(str(fp_ls_mod))
        if not os.path.exists(fp_ls_worst):
            missing.append(str(fp_ls_worst))

        if missing:
            logger.warning(f"Missing raster files for Rainfall Induced Landslide analysis: {', '.join(missing)}")
            return None

        df_values = generate_rainfall_induced_landslide_analysis(
            df_fac,
            fp_ls,
            fp_ls_mod,
            fp_ls_worst,
            facility_geofile_path=facility_geofile_path,
            facility_geojson_records=facility_geojson_records,
        )
        return df_values[['Facility', 'Lat', 'Long',
                          'Rainfall-Induced Landslide (factor of safety)',
                          'Rainfall-Induced Landslide (factor of safety) - Moderate Case',
                          'Rainfall-Induced Landslide (factor of safety) - Worst Case']].copy()

    except Exception as e:
        logger.exception(f"Error in Rainfall Induced Landslide analysis: {e}")
        return None




def process_nan_values(df):
    """
    Replace NaN values with appropriate text based on column type.

    This function now uses the consolidated implementation from common_utils.

    Args:
        df (DataFrame): Combined dataframe with all hazard data

    Returns:
        DataFrame: Processed dataframe with NaN values replaced
    """
    # Define column mappings for NaN replacement
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

    return process_nan_values_in_dataframe(df, column_mappings)


def generate_climate_hazards_analysis(facility_csv_path=None, selected_fields=None, buffer_size=0.0009, sensitivity_params=None, flood_scenarios=None, facility_geofile_path=None, facility_geojson_records=None):
    """
    Integrates multiple climate hazard analyses into a single output.
    Enhanced version with multi-scenario flood analysis support.

    Args:
    facility_csv_path: Path to facility locations CSV (required)
    selected_fields: List of selected hazard types to include
    buffer_size: Buffer size for spatial analysis (default 0.0009)
    sensitivity_params: Dictionary of sensitivity parameters (flood thresholds removed)
    flood_scenarios: List of flood scenarios ['current', 'moderate', 'worst'] (default: ['current'])
    
    Returns:
        dict: Results dictionary with paths to combined output and plots
    """
    try:
        # Validate inputs
        if not facility_csv_path or not os.path.exists(facility_csv_path):
            raise ValueError("Facility CSV path is required and must exist.")
            
        if selected_fields is None:
            selected_fields = []
            
        logger.info(f"Starting climate hazards analysis with buffer size: {buffer_size}")
        logger.info(f"Selected fields: {selected_fields}")
        if sensitivity_params:
            logger.info(f"Using sensitivity parameters: {list(sensitivity_params.keys())}")
        
        # Define path for final combined output
        input_dir = os.path.join(settings.BASE_DIR, 'climate_hazards_analysis', 'static', 'input_files')
        os.makedirs(input_dir, exist_ok=True)
        
        # Load and standardize facility dataframe with proper encoding
        try:
            df_fac = pd.read_csv(facility_csv_path, encoding='utf-8')
        except UnicodeDecodeError:
            try:
                df_fac = pd.read_csv(facility_csv_path, encoding='latin-1')
                logger.warning(f"Facility CSV read with latin-1 encoding")
            except UnicodeDecodeError:
                df_fac = pd.read_csv(facility_csv_path, encoding='cp1252')
                logger.warning(f"Facility CSV read with cp1252 encoding")
        
        # Enhanced logging before standardization
        logger.info(f"[CLIMATE_ANALYSIS_DEBUG] Before standardization:")
        logger.info(f"[CLIMATE_ANALYSIS_DEBUG] Facility CSV path: {facility_csv_path}")
        logger.info(f"[CLIMATE_ANALYSIS_DEBUG] Original DataFrame shape: {df_fac.shape}")
        logger.info(f"[CLIMATE_ANALYSIS_DEBUG] Original columns: {df_fac.columns.tolist()}")
        if 'Lat' in df_fac.columns:
            logger.info(f"[CLIMATE_ANALYSIS_DEBUG] Lat column sample: {df_fac['Lat'].head().tolist()}")
            logger.info(f"[CLIMATE_ANALYSIS_DEBUG] Lat NaN count: {df_fac['Lat'].isna().sum()}")
        if 'Long' in df_fac.columns:
            logger.info(f"[CLIMATE_ANALYSIS_DEBUG] Long column sample: {df_fac['Long'].head().tolist()}")
            logger.info(f"[CLIMATE_ANALYSIS_DEBUG] Long NaN count: {df_fac['Long'].isna().sum()}")

        df_fac = standardize_facility_dataframe(df_fac)
        logger.info(f"Loaded facility data with {len(df_fac)} facilities")
        logger.info(f"Facility DataFrame columns: {df_fac.columns.tolist()}")

        # Initialize combined DataFrame with base columns, including Asset Archetype if available
        base_columns = ['Facility', 'Lat', 'Long']
        if 'Asset_ID' in df_fac.columns:
            base_columns.append('Asset_ID')

        # Look for Asset Archetype column with various naming conventions
        archetype_column = None
        possible_names = [
            'Asset Archetype', 'asset archetype', 'AssetArchetype', 'assetarchetype',
            'Archetype', 'archetype', 'Asset Type', 'asset type', 'AssetType', 'assettype',
            'Type', 'type', 'Category', 'category', 'Asset Category', 'asset category'
        ]

        for col_name in possible_names:
            if col_name in df_fac.columns:
                archetype_column = col_name
                break

        if archetype_column:
            # Standardize the column name to 'Asset Archetype'
            if archetype_column != 'Asset Archetype':
                df_fac.rename(columns={archetype_column: 'Asset Archetype'}, inplace=True)
            base_columns.append('Asset Archetype')
            logger.info(f"Found and included Asset Archetype column: '{archetype_column}' -> 'Asset Archetype'")
        else:
            logger.info("No Asset Archetype column found in facility data, will add default later")

        combined_df = df_fac[base_columns].copy()
        logger.info(f"Initialized combined DataFrame with columns: {combined_df.columns.tolist()}")
        
        # Track plots for visualization
        all_plot_paths = []
        
        # Process each hazard type (simplified without flood thresholds)
        
        # 1. Flood Exposure Analysis - Enhanced version with multi-scenario support
        logger.info("=== PROCESSING FLOOD EXPOSURE ANALYSIS ===")
        flood_values, flood_plots = process_flood_exposure_analysis(
            facility_csv_path,
            selected_fields,
            scenarios=flood_scenarios,
            facility_geofile_path=facility_geofile_path,
            facility_geojson_records=facility_geojson_records
        )
        all_plot_paths.extend(flood_plots)
        
        if flood_values is not None:
            logger.info(f"Flood values shape: {flood_values.shape}")
            logger.info(f"Flood values columns: {flood_values.columns.tolist()}")
            logger.info("Merging flood values...")
            flood_merge_df = flood_values.copy()
            if 'Facility' in flood_merge_df.columns:
                if flood_merge_df['Facility'].duplicated().any():
                    dupes = flood_merge_df[flood_merge_df['Facility'].duplicated()]['Facility'].unique()
                    logger.warning(f"Duplicate Facility values in flood results: {dupes}")
                    flood_merge_df = flood_merge_df.drop_duplicates(subset=['Facility'], keep='first')

            # Avoid float precision mismatches by merging on Facility only.
            for coord_col in ['Lat', 'Long']:
                if coord_col in flood_merge_df.columns:
                    flood_merge_df.drop(columns=[coord_col], inplace=True)

            combined_df = combined_df.merge(
                flood_merge_df, on=['Facility'], how='left'
            )
            logger.info(f"Combined DF after flood merge - shape: {combined_df.shape}, columns: {combined_df.columns.tolist()}")
        else:
            logger.warning("No flood values to merge")
        
        # 2. Water Stress Analysis
        logger.info("=== PROCESSING WATER STRESS ANALYSIS ===")
        water_stress_values, ws_plots = process_water_stress_analysis(
            facility_csv_path, selected_fields, buffer_size
        )
        all_plot_paths.extend(ws_plots)
        
        if water_stress_values is not None:
            logger.info("Merging water stress values...")
            combined_df = combined_df.merge(
                water_stress_values, on=['Facility', 'Lat', 'Long'], how='left'
            )
            logger.info(f"Combined DF after water stress merge - shape: {combined_df.shape}")
        
        # 3. Other analyses (no buffer size needed for these)
        logger.info("=== PROCESSING OTHER ANALYSES ===")
        slr_values, slr_plots = process_sea_level_rise_analysis(
            facility_csv_path,
            selected_fields,
            facility_geofile_path=facility_geofile_path,
            facility_geojson_records=facility_geojson_records,
        )
        all_plot_paths.extend(slr_plots)
        
        tc_values, tc_plots = process_tropical_cyclone_analysis(
            facility_csv_path, selected_fields
        )
        all_plot_paths.extend(tc_plots)
        
        heat_values, heat_plots = process_heat_exposure_analysis(
            facility_csv_path,
            selected_fields,
            facility_geofile_path=facility_geofile_path,
            facility_geojson_records=facility_geojson_records,
        )
        all_plot_paths.extend(heat_plots)
        
        storm_surge_values = process_storm_surge_analysis(
            df_fac,
            selected_fields,
            facility_geofile_path=facility_geofile_path,
            facility_geojson_records=facility_geojson_records,
        )
        landslide_values = process_landslide_analysis(
            df_fac,
            selected_fields,
            facility_geofile_path=facility_geofile_path,
            facility_geojson_records=facility_geojson_records,
        )

        # Merge remaining hazard data to combined DataFrame
        if storm_surge_values is not None:
            storm_merge = storm_surge_values.copy()
            for coord_col in ['Lat', 'Long']:
                if coord_col in storm_merge.columns:
                    storm_merge[coord_col] = pd.to_numeric(storm_merge[coord_col], errors='coerce')
            combined_df['Lat'] = pd.to_numeric(combined_df['Lat'], errors='coerce')
            combined_df['Long'] = pd.to_numeric(combined_df['Long'], errors='coerce')
            if 'Asset_ID' in storm_merge.columns:
                storm_merge['asset_id_key'] = storm_merge['Asset_ID'].astype(str).str.strip()
            storm_merge['facility_key'] = storm_merge['Facility'].astype(str).str.strip().str.lower()
            storm_merge['merge_key'] = (
                storm_merge['Facility'].astype(str).str.strip().str.lower() + '|' +
                storm_merge['Lat'].round(6).astype(str) + '|' +
                storm_merge['Long'].round(6).astype(str)
            )
            combined_df['merge_key'] = (
                combined_df['Facility'].astype(str).str.strip().str.lower() + '|' +
                combined_df['Lat'].round(6).astype(str) + '|' +
                combined_df['Long'].round(6).astype(str)
            )
            if 'Asset_ID' in combined_df.columns:
                combined_df['asset_id_key'] = combined_df['Asset_ID'].astype(str).str.strip()
            combined_df['facility_key'] = combined_df['Facility'].astype(str).str.strip().str.lower()

            logger.info("=== MERGING STORM SURGE ===")
            logger.info(f"  storm surge dataframe shape: {storm_merge.shape}")
            logger.info(f"  storm surge columns: {storm_merge.columns.tolist()}")
            if 'asset_id_key' in combined_df.columns and 'asset_id_key' in storm_merge.columns:
                combined_df = combined_df.merge(
                    storm_merge,
                    on=['asset_id_key'],
                    how='left',
                    suffixes=('', '_storm')
                )
            else:
                combined_df = combined_df.merge(storm_merge, on=['merge_key'], how='left', suffixes=('', '_storm'))
            if 'Facility_storm' in combined_df.columns:
                combined_df.drop(columns=['Facility_storm'], inplace=True)
            ss_cols = [
                'Storm Surge Flood Depth (meters)',
                'Storm Surge Flood Depth (meters) - Worst Case'
            ]
            for col in ss_cols:
                if col in combined_df.columns and col in storm_merge.columns:
                    val_map = storm_merge.set_index(
                        'asset_id_key' if 'asset_id_key' in storm_merge.columns else 'facility_key'
                    )[col].to_dict()
                    missing = combined_df[col].isna()
                    if missing.any():
                        key_col = 'asset_id_key' if 'asset_id_key' in combined_df.columns else 'facility_key'
                        combined_df.loc[missing, col] = combined_df.loc[missing, key_col].map(val_map)
            logger.info(f"  Combined DF after storm surge merge - shape: {combined_df.shape}")

            try:
                polygon_keys = _get_polygon_facility_keys(
                    facility_geofile_path,
                    facility_geojson_records,
                )
                if polygon_keys:
                    combined_df['Facility_key'] = combined_df['Facility'].astype(str).str.strip().str.lower()
                    point_mask = ~combined_df['Facility_key'].isin(polygon_keys)
                else:
                    combined_df['Facility_key'] = combined_df['Facility'].astype(str).str.strip().str.lower()
                    point_mask = combined_df['Facility_key'].notna()

                ss_cols = [
                    'Storm Surge Flood Depth (meters)',
                    'Storm Surge Flood Depth (meters) - Worst Case'
                ]
                if any(col in combined_df.columns for col in ss_cols):
                    df_points = combined_df.loc[point_mask, ['Facility', 'Lat', 'Long']].copy()
                    df_points['Lat'] = pd.to_numeric(df_points['Lat'], errors='coerce')
                    df_points['Long'] = pd.to_numeric(df_points['Long'], errors='coerce')
                    df_points = df_points.dropna(subset=['Lat', 'Long'])
                    if not df_points.empty:
                        ss_dir = Path(settings.BASE_DIR) / 'climate_hazards_analysis' / 'static' / 'input_files'
                        fp_ss = ss_dir / 'PH_StormSurge_Advisory4_UTM_ProjectNOAH_Unmasked.tif'
                        fp_ss_future = ss_dir / 'PH_StormSurge_Advisory4_Future_UTM_ProjectNOAH-GIRI_Unmasked.tif'
                        ss_recalc = generate_storm_surge_analysis(
                            df_points,
                            fp_ss,
                            fp_ss_future,
                            facility_geofile_path=None,
                            facility_geojson_records=None,
                        )
                        if ss_recalc is not None:
                            ss_recalc['Facility_key'] = ss_recalc['Facility'].astype(str).str.strip().str.lower()
                            for col in ss_cols:
                                if col in ss_recalc.columns and col in combined_df.columns:
                                    val_map = ss_recalc.set_index('Facility_key')[col].to_dict()
                                    mapped = combined_df.loc[point_mask, 'Facility_key'].map(val_map)
                                    combined_df.loc[point_mask, col] = mapped.where(
                                        mapped.notna(),
                                        combined_df.loc[point_mask, col],
                                    )
            except Exception as e:
                logger.warning(f"Storm surge point backfill failed: {e}")

            if 'Facility_key' in combined_df.columns:
                combined_df.drop(columns=['Facility_key'], inplace=True)
            if 'merge_key' in combined_df.columns:
                combined_df.drop(columns=['merge_key'], inplace=True)
            if 'facility_key' in combined_df.columns:
                combined_df.drop(columns=['facility_key'], inplace=True)
            if 'asset_id_key' in combined_df.columns:
                combined_df.drop(columns=['asset_id_key'], inplace=True)

        if landslide_values is not None:
            landslide_merge = landslide_values.copy()
            landslide_cols = [col for col in landslide_merge.columns if col.startswith('Rainfall-Induced Landslide')]
            for coord_col in ['Lat', 'Long']:
                if coord_col in landslide_merge.columns:
                    landslide_merge[coord_col] = pd.to_numeric(landslide_merge[coord_col], errors='coerce')
            combined_df['Lat'] = pd.to_numeric(combined_df['Lat'], errors='coerce')
            combined_df['Long'] = pd.to_numeric(combined_df['Long'], errors='coerce')
            if 'Asset_ID' in landslide_merge.columns:
                landslide_merge['asset_id_key'] = landslide_merge['Asset_ID'].astype(str).str.strip()
            landslide_merge['facility_key'] = landslide_merge['Facility'].astype(str).str.strip().str.lower()
            landslide_merge['merge_key'] = (
                landslide_merge['Facility'].astype(str).str.strip().str.lower() + '|' +
                landslide_merge['Lat'].round(6).astype(str) + '|' +
                landslide_merge['Long'].round(6).astype(str)
            )
            combined_df['merge_key'] = (
                combined_df['Facility'].astype(str).str.strip().str.lower() + '|' +
                combined_df['Lat'].round(6).astype(str) + '|' +
                combined_df['Long'].round(6).astype(str)
            )
            if 'Asset_ID' in combined_df.columns:
                combined_df['asset_id_key'] = combined_df['Asset_ID'].astype(str).str.strip()
            combined_df['facility_key'] = combined_df['Facility'].astype(str).str.strip().str.lower()

            logger.info("=== MERGING LANDSLIDE ===")
            logger.info(f"  landslide dataframe shape: {landslide_merge.shape}")
            logger.info(f"  landslide columns: {landslide_merge.columns.tolist()}")
            if 'asset_id_key' in combined_df.columns and 'asset_id_key' in landslide_merge.columns:
                combined_df = combined_df.merge(
                    landslide_merge,
                    on=['asset_id_key'],
                    how='left',
                    suffixes=('', '_landslide')
                )
            else:
                combined_df = combined_df.merge(
                    landslide_merge,
                    on=['merge_key'],
                    how='left',
                    suffixes=('', '_landslide')
                )
            if 'Facility_landslide' in combined_df.columns:
                combined_df.drop(columns=['Facility_landslide'], inplace=True)
            for col in landslide_cols:
                if col in combined_df.columns and col in landslide_merge.columns:
                    val_map = landslide_merge.set_index(
                        'asset_id_key' if 'asset_id_key' in landslide_merge.columns else 'facility_key'
                    )[col].to_dict()
                    missing = combined_df[col].isna()
                    if missing.any():
                        key_col = 'asset_id_key' if 'asset_id_key' in combined_df.columns else 'facility_key'
                        combined_df.loc[missing, col] = combined_df.loc[missing, key_col].map(val_map)
            if 'merge_key' in combined_df.columns:
                combined_df.drop(columns=['merge_key'], inplace=True)
            if 'facility_key' in combined_df.columns:
                combined_df.drop(columns=['facility_key'], inplace=True)
            if 'asset_id_key' in combined_df.columns:
                combined_df.drop(columns=['asset_id_key'], inplace=True)
            logger.info(f"  Combined DF after landslide merge - shape: {combined_df.shape}")
        # Backfill missing landslide values for point assets using coordinates.
        if 'Rainfall-Induced Landslide (factor of safety)' in combined_df.columns:
            landslide_cols = [
                'Rainfall-Induced Landslide (factor of safety)',
                'Rainfall-Induced Landslide (factor of safety) - Moderate Case',
                'Rainfall-Induced Landslide (factor of safety) - Worst Case'
            ]
            missing_mask = False
            for col in landslide_cols:
                if col in combined_df.columns:
                    col_missing = combined_df[col].isna() | (combined_df[col].astype(str).str.strip().str.upper() == 'N/A')
                    missing_mask = col_missing if isinstance(missing_mask, bool) else (missing_mask | col_missing)
            if not isinstance(missing_mask, bool):
                df_missing = combined_df.loc[missing_mask, ['Facility', 'Lat', 'Long']].copy()
                df_missing['Lat'] = pd.to_numeric(df_missing['Lat'], errors='coerce')
                df_missing['Long'] = pd.to_numeric(df_missing['Long'], errors='coerce')
                df_missing = df_missing.dropna(subset=['Lat', 'Long'])
                if not df_missing.empty:
                    try:
                        fp_ls = os.path.join(input_dir, 'PH_LandslideHazards_UTM_ProjectNOAH_Unmasked.tif')
                        fp_ls_mod = os.path.join(input_dir, 'PH_LandslideHazards_RCP26_UTM_ProjectNOAH-GIRI_Unmasked.tif')
                        fp_ls_worst = os.path.join(input_dir, 'PH_LandslideHazards_RCP85_UTM_ProjectNOAH-GIRI_Unmasked.tif')
                        fallback_vals = generate_rainfall_induced_landslide_analysis(
                            df_missing,
                            fp_ls,
                            fp_ls_mod,
                            fp_ls_worst,
                            facility_geofile_path=None,
                            facility_geojson_records=None,
                        )
                        if fallback_vals is not None:
                            fallback_vals['Facility_merge_key'] = fallback_vals['Facility'].astype(str).str.strip().str.lower()
                            combined_df['Facility_merge_key'] = combined_df['Facility'].astype(str).str.strip().str.lower()
                            combined_df = combined_df.merge(
                                fallback_vals[['Facility_merge_key'] + landslide_cols],
                                on='Facility_merge_key',
                                how='left',
                                suffixes=('', '_landslide_fallback')
                            )
                            for col in landslide_cols:
                                fallback_col = f"{col}_landslide_fallback"
                                if fallback_col in combined_df.columns:
                                    combined_df[col] = combined_df[col].fillna(combined_df[fallback_col])
                                    combined_df.drop(columns=[fallback_col], inplace=True)
                            combined_df.drop(columns=['Facility_merge_key'], inplace=True)
                            logger.info("Applied landslide fallback values for missing facilities")
                    except Exception as e:
                        logger.exception(f"Error applying landslide fallback values: {e}")

        # Recompute landslide values for point assets if polygon inputs are present.
        if 'Rainfall-Induced Landslide (factor of safety)' in combined_df.columns:
            try:
                polygon_keys = _get_polygon_facility_keys(
                    facility_geofile_path,
                    facility_geojson_records,
                )
                combined_df['Facility_key'] = combined_df['Facility'].astype(str).str.strip().str.lower()
                if polygon_keys:
                    point_mask = ~combined_df['Facility_key'].isin(polygon_keys)
                else:
                    point_mask = combined_df['Facility_key'].notna()

                df_points = combined_df.loc[point_mask, ['Facility', 'Lat', 'Long']].copy()
                df_points['Lat'] = pd.to_numeric(df_points['Lat'], errors='coerce')
                df_points['Long'] = pd.to_numeric(df_points['Long'], errors='coerce')
                df_points = df_points.dropna(subset=['Lat', 'Long'])
                if not df_points.empty:
                    fp_ls = os.path.join(input_dir, 'PH_LandslideHazards_UTM_ProjectNOAH_Unmasked.tif')
                    fp_ls_mod = os.path.join(input_dir, 'PH_LandslideHazards_RCP26_UTM_ProjectNOAH-GIRI_Unmasked.tif')
                    fp_ls_worst = os.path.join(input_dir, 'PH_LandslideHazards_RCP85_UTM_ProjectNOAH-GIRI_Unmasked.tif')
                    recalc = generate_rainfall_induced_landslide_analysis(
                        df_points,
                        fp_ls,
                        fp_ls_mod,
                        fp_ls_worst,
                        facility_geofile_path=None,
                        facility_geojson_records=None,
                    )
                    if recalc is not None:
                        recalc['Facility_key'] = recalc['Facility'].astype(str).str.strip().str.lower()
                        for col in landslide_cols:
                            if col in recalc.columns and col in combined_df.columns:
                                val_map = recalc.set_index('Facility_key')[col].to_dict()
                                mapped = combined_df.loc[point_mask, 'Facility_key'].map(val_map)
                                combined_df.loc[point_mask, col] = mapped.where(
                                    mapped.notna(),
                                    combined_df.loc[point_mask, col],
                                )
            except Exception as e:
                logger.warning(f"Landslide point backfill failed: {e}")
            finally:
                if 'Facility_key' in combined_df.columns:
                    combined_df.drop(columns=['Facility_key'], inplace=True)

        data_frames = [
            (slr_values, "sea level rise"),
            (tc_values, "tropical cyclones"),
            (heat_values, "heat exposure"),
        ]
        
        for df_values, name in data_frames:
            if df_values is not None:
                logger.info(f"=== MERGING {name.upper()} ===")
                logger.info(f"  {name} dataframe shape: {df_values.shape}")
                logger.info(f"  {name} columns: {df_values.columns.tolist()}")
                logger.info(f"  Combined DF before merge - shape: {combined_df.shape}")
                logger.info(f"  Combined DF columns before merge: {combined_df.columns.tolist()}")

                combined_df = combined_df.merge(
                    df_values, on=['Facility', 'Lat', 'Long'], how='left'
                )

                logger.info(f"  Combined DF after {name} merge - shape: {combined_df.shape}")
                logger.info(f"  Combined DF columns after merge: {combined_df.columns.tolist()}")
                logger.info(f"=== END {name.upper()} MERGE ===")
            else:
                logger.info(f"Skipping {name} - dataframe is None")

        # Add future heat exposure values if heat analysis was performed.
        if 'Heat' in selected_fields:
            try:
                tiff_dir = Path(settings.BASE_DIR) / 'climate_hazards_analysis' / 'static' / 'input_files'
                combined_df = generate_heat_future_analysis(
                    combined_df,
                    tiff_dir,
                    facility_geofile_path=facility_geofile_path,
                    facility_geojson_records=facility_geojson_records,
                )
                logger.info('Future heat exposure columns added')
            except Exception as e:
                logger.warning(f'Failed to add future heat exposure values: {e}')

            combined_df = _collapse_duplicate_columns(combined_df)

            base_col = 'DaysOver35C_base_2125'
            baseline_col = 'Days over 35° Celsius'
            if base_col in combined_df.columns:
                if baseline_col not in combined_df.columns:
                    combined_df[baseline_col] = np.nan
                baseline_series = combined_df[baseline_col]
                if isinstance(baseline_series, pd.DataFrame):
                    baseline_series = baseline_series.iloc[:, 0]
                base_series = combined_df[base_col]
                if isinstance(base_series, pd.DataFrame):
                    base_series = base_series.iloc[:, 0]
                combined_df[baseline_col] = baseline_series.where(
                    baseline_series.notna(),
                    base_series,
                )

            rename_map = {
                'DaysOver35C_ssp245_2630': 'Days over 35° Celsius (2026 - 2030) - Moderate Case',
                'DaysOver35C_ssp245_3140': 'Days over 35° Celsius (2031 - 2040) - Moderate Case',
                'DaysOver35C_ssp245_4150': 'Days over 35° Celsius (2041 - 2050) - Moderate Case',
                'DaysOver35C_ssp585_2630': 'Days over 35° Celsius (2026 - 2030) - Worst Case',
                'DaysOver35C_ssp585_3140': 'Days over 35° Celsius (2031 - 2040) - Worst Case',
                'DaysOver35C_ssp585_4150': 'Days over 35° Celsius (2041 - 2050) - Worst Case'
            }
            combined_df.rename(columns=rename_map, inplace=True)
            # Ensure expected future heat columns exist even if zonal stats returned nothing
            for col in rename_map.values():
                if col not in combined_df.columns:
                    combined_df[col] = np.nan

            heat_order = [
                'Days over 35° Celsius',
                'Days over 35° Celsius (2026 - 2030) - Moderate Case',
                'Days over 35° Celsius (2031 - 2040) - Moderate Case',
                'Days over 35° Celsius (2041 - 2050) - Moderate Case',
                'Days over 35° Celsius (2026 - 2030) - Worst Case',
                'Days over 35° Celsius (2031 - 2040) - Worst Case',
                'Days over 35° Celsius (2041 - 2050) - Worst Case',
            ]
            existing_heat = [c for c in heat_order if c in combined_df.columns]
            if existing_heat:
                cols = combined_df.columns.tolist()
                first_idx = min(cols.index(c) for c in existing_heat)
                for c in existing_heat:
                    cols.remove(c)
                cols[first_idx:first_idx] = existing_heat
                combined_df = combined_df[cols]

        # Future storm surge values now computed in process_storm_surge_analysis.

        # Future rainfall-induced landslide values now computed in process_landslide_analysis.


        # Remove duplicate rows that can arise from merges on repeated keys.
        dedupe_cols = ['Facility', 'Lat', 'Long']
        if 'Asset Archetype' in combined_df.columns:
            dedupe_cols.append('Asset Archetype')
        if combined_df.duplicated(subset=dedupe_cols).any():
            dupes = combined_df[combined_df.duplicated(subset=dedupe_cols)]['Facility'].unique()
            logger.warning(f"Duplicate facilities detected in combined output: {dupes}")
            combined_df = combined_df.drop_duplicates(subset=dedupe_cols, keep='first')

        # VERIFICATION: Check if flood column exists
        logger.info("=== FINAL VERIFICATION ===")
        logger.info(f"Final combined DataFrame shape: {combined_df.shape}")
        logger.info(f"Final combined DataFrame columns: {combined_df.columns.tolist()}")
        
        if 'Flood Depth (meters)' in combined_df.columns:
            logger.info("Flood Depth (meters) column successfully included!")
            logger.info(f"Flood column sample values: {combined_df['Flood Depth (meters)'].value_counts()}")
        else:
            logger.error("Flood Depth (meters) column is MISSING!")
            # Add placeholder flood column if missing
            if 'Flood' in selected_fields:
                combined_df['Flood Depth (meters)'] = '0.1 to 0.5'
                logger.info("Added placeholder Flood Depth (meters) column")

        # Normalize duplicate columns before NaN processing
        combined_df = _collapse_duplicate_columns(combined_df)

        # Process NaN values
        combined_df = process_nan_values(combined_df)

        # Final override: ensure point assets keep their own storm surge/landslide values.
        try:
            polygon_keys = _get_polygon_facility_keys(
                facility_geofile_path,
                facility_geojson_records,
            )
            df_points = df_fac.copy()
            df_points['Facility'] = df_points['Facility'].astype(str)
            df_points['Facility_key'] = df_points['Facility'].str.strip().str.lower()
            if polygon_keys:
                df_points = df_points[~df_points['Facility_key'].isin(polygon_keys)]

            df_points['Lat'] = pd.to_numeric(df_points['Lat'], errors='coerce')
            df_points['Long'] = pd.to_numeric(df_points['Long'], errors='coerce')
            df_points = df_points.dropna(subset=['Lat', 'Long'])

            if not df_points.empty:
                combined_df['Facility_key'] = combined_df['Facility'].astype(str).str.strip().str.lower()

                ss_cols = [
                    'Storm Surge Flood Depth (meters)',
                    'Storm Surge Flood Depth (meters) - Worst Case'
                ]
                if any(col in combined_df.columns for col in ss_cols):
                    ss_dir = Path(settings.BASE_DIR) / 'climate_hazards_analysis' / 'static' / 'input_files'
                    fp_ss = ss_dir / 'PH_StormSurge_Advisory4_UTM_ProjectNOAH_Unmasked.tif'
                    fp_ss_future = ss_dir / 'PH_StormSurge_Advisory4_Future_UTM_ProjectNOAH-GIRI_Unmasked.tif'
                    ss_recalc = generate_storm_surge_analysis(
                        df_points[['Facility', 'Lat', 'Long']],
                        fp_ss,
                        fp_ss_future,
                        facility_geofile_path=None,
                        facility_geojson_records=None,
                    )
                    if ss_recalc is not None:
                        ss_recalc['Facility_key'] = ss_recalc['Facility'].astype(str).str.strip().str.lower()
                        for col in ss_cols:
                            if col in ss_recalc.columns and col in combined_df.columns:
                                val_map = ss_recalc.set_index('Facility_key')[col].to_dict()
                                combined_df[col] = combined_df['Facility_key'].map(val_map).fillna(combined_df[col])

                landslide_cols = [
                    'Rainfall-Induced Landslide (factor of safety)',
                    'Rainfall-Induced Landslide (factor of safety) - Moderate Case',
                    'Rainfall-Induced Landslide (factor of safety) - Worst Case'
                ]
                if any(col in combined_df.columns for col in landslide_cols):
                    fp_ls = os.path.join(input_dir, 'PH_LandslideHazards_UTM_ProjectNOAH_Unmasked.tif')
                    fp_ls_mod = os.path.join(input_dir, 'PH_LandslideHazards_RCP26_UTM_ProjectNOAH-GIRI_Unmasked.tif')
                    fp_ls_worst = os.path.join(input_dir, 'PH_LandslideHazards_RCP85_UTM_ProjectNOAH-GIRI_Unmasked.tif')
                    ls_recalc = generate_rainfall_induced_landslide_analysis(
                        df_points[['Facility', 'Lat', 'Long']],
                        fp_ls,
                        fp_ls_mod,
                        fp_ls_worst,
                        facility_geofile_path=None,
                        facility_geojson_records=None,
                    )
                    if ls_recalc is not None:
                        ls_recalc['Facility_key'] = ls_recalc['Facility'].astype(str).str.strip().str.lower()
                        for col in landslide_cols:
                            if col in ls_recalc.columns and col in combined_df.columns:
                                val_map = ls_recalc.set_index('Facility_key')[col].to_dict()
                                combined_df[col] = combined_df['Facility_key'].map(val_map).fillna(combined_df[col])
        except Exception as e:
            logger.warning(f"Point hazard override failed: {e}")
        finally:
            if 'Facility_key' in combined_df.columns:
                combined_df.drop(columns=['Facility_key'], inplace=True)

        if 'DaysOver35C_base_2125' in combined_df.columns:
            combined_df.drop(columns=['DaysOver35C_base_2125'], inplace=True)

        # Rename future heat exposure columns for readability
        rename_map = {
            'DaysOver35C_ssp245_2630': 'Days over 35° Celsius (2026 - 2030) - Moderate Case',
            'DaysOver35C_ssp245_3140': 'Days over 35° Celsius (2031 - 2040) - Moderate Case',
            'DaysOver35C_ssp245_4150': 'Days over 35° Celsius (2041 - 2050) - Moderate Case',
            'DaysOver35C_ssp585_2630': 'Days over 35° Celsius (2026 - 2030) - Worst Case',
            'DaysOver35C_ssp585_3140': 'Days over 35° Celsius (2031 - 2040) - Worst Case',
            'DaysOver35C_ssp585_4150': 'Days over 35° Celsius (2041 - 2050) - Worst Case'
        }
        combined_df.rename(columns=rename_map, inplace=True)

        # Final desired column order for output CSV
        final_order = [
            'Facility',
            'Asset Archetype',  # Added Asset Archetype as 2nd column
            'Lat',
            'Long',
            'Flood Depth (meters)',
            'Flood Depth (meters) - Moderate Case',
            'Flood Depth (meters) - Worst Case',
            'Water Stress Exposure (%)',
            'Water Stress Exposure 2030 (%) - Moderate Case',
            'Water Stress Exposure 2050 (%) - Moderate Case',
            'Water Stress Exposure 2030 (%) - Worst Case',
            'Water Stress Exposure 2050 (%) - Worst Case',
            'Elevation (meter above sea level)',
            '2030 Sea Level Rise (meters) - Moderate Case',
            '2040 Sea Level Rise (meters) - Moderate Case',
            '2050 Sea Level Rise (meters) - Moderate Case',
            '2030 Sea Level Rise (meters) - Worst Case',
            '2040 Sea Level Rise (meters) - Worst Case',
            '2050 Sea Level Rise (meters) - Worst Case',
            'Extreme Windspeed 10 year Return Period (km/h)',
            'Extreme Windspeed 20 year Return Period (km/h)',
            'Extreme Windspeed 50 year Return Period (km/h)',
            'Extreme Windspeed 100 year Return Period (km/h)',
            'Extreme Windspeed 10 year Return Period (km/h) - Moderate Case',
            'Extreme Windspeed 20 year Return Period (km/h) - Moderate Case',
            'Extreme Windspeed 50 year Return Period (km/h) - Moderate Case',
            'Extreme Windspeed 100 year Return Period (km/h) - Moderate Case',
            'Extreme Windspeed 10 year Return Period (km/h) - Worst Case',
            'Extreme Windspeed 20 year Return Period (km/h) - Worst Case',
            'Extreme Windspeed 50 year Return Period (km/h) - Worst Case',
            'Extreme Windspeed 100 year Return Period (km/h) - Worst Case',
            'Days over 35° Celsius',
            'Days over 35° Celsius (2026 - 2030) - Moderate Case',
            'Days over 35° Celsius (2031 - 2040) - Moderate Case',
            'Days over 35° Celsius (2041 - 2050) - Moderate Case',
            'Days over 35° Celsius (2026 - 2030) - Worst Case',
            'Days over 35° Celsius (2031 - 2040) - Worst Case',
            'Days over 35° Celsius (2041 - 2050) - Worst Case',
            'Storm Surge Flood Depth (meters)',
            'Storm Surge Flood Depth (meters) - Worst Case',
            'Rainfall-Induced Landslide (factor of safety)',
            'Rainfall-Induced Landslide (factor of safety) - Moderate Case',
            'Rainfall-Induced Landslide (factor of safety) - Worst Case',
        ]
        existing_cols = [c for c in final_order if c in combined_df.columns]
        remaining_cols = [c for c in combined_df.columns if c not in final_order]
        combined_df = combined_df[existing_cols + remaining_cols]

        # Write combined output CSV with parameters in filename if sensitivity analysis
        if sensitivity_params and buffer_size != 0.0009:
            out_csv = os.path.join(input_dir, f'combined_output_sensitivity_buffer_{buffer_size:.4f}.csv')
        elif buffer_size != 0.0009:
            out_csv = os.path.join(input_dir, f'combined_output_buffer_{buffer_size:.4f}.csv')
        else:
            out_csv = os.path.join(input_dir, 'combined_output.csv')
            
        # Add metadata to CSV if sensitivity parameters were used
        metadata_lines = []
        if sensitivity_params:
            metadata_lines.append(f"# Sensitivity Analysis Results")
            metadata_lines.append(f"# Buffer Size: {buffer_size} degrees (~{int(buffer_size * 111000)}m)")
        
        # === JSON-ONLY GENERATION (Migrated from CSV/JSON Parallel) ===
        # Generate JSON output for improved performance and data integrity
        import json

        # Determine JSON filename based on analysis type
        if sensitivity_params and buffer_size != 0.0009:
            out_json = os.path.join(input_dir, f'combined_output_sensitivity_buffer_{buffer_size:.4f}.json')
        elif buffer_size != 0.0009:
            out_json = os.path.join(input_dir, f'combined_output_buffer_{buffer_size:.4f}.json')
        else:
            out_json = os.path.join(input_dir, 'combined_output.json')

        # Create JSON data structure
        json_data = {
            'metadata': {
                'generated_at': str(datetime.now()),
                'analysis_type': 'sensitivity' if sensitivity_params else 'standard',
                'buffer_size_degrees': buffer_size,
                'buffer_size_meters': int(buffer_size * 111000) if buffer_size != 0.0009 else 100,
                'sensitivity_parameters': sensitivity_params or {},
                'total_facilities': len(combined_df),
                'hazards_analyzed': selected_fields or []
            },
            'data': combined_df.to_dict(orient='records')
        }

        # Write JSON file with UTF-8 encoding
        with open(out_json, 'w', encoding='utf-8') as f_json:
            json.dump(json_data, f_json, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Saved JSON output: {out_json}")

        # === END JSON-ONLY GENERATION ===
        
        # Select the main plot for display (prioritizing flood exposure if available)
        main_plot = None
        if all_plot_paths:
            # Prioritize flood exposure plot if available
            flood_plots = [p for p in all_plot_paths if 'flood_exposure' in p.lower()]
            if flood_plots:
                main_plot = flood_plots[0]
            else:
                main_plot = all_plot_paths[0]
        
        logger.info("=== ANALYSIS COMPLETE ===")
        return {
            'combined_json_path': out_json,
            'plot_path': main_plot,
            'all_plots': all_plot_paths,
            'buffer_size': buffer_size,
            'sensitivity_params': sensitivity_params
        }
        
    except Exception as e:
        logger.exception(f"Error in generate_climate_hazards_analysis: {e}")
        return {'error': str(e), 'combined_json_path': None, 'plot_path': None}
    
def validate_and_clean_dataframe(df, analysis_name=""):
    """
    Validate and clean a dataframe to ensure no NaN values and proper data types.
    
    Args:
        df (DataFrame): Dataframe to validate and clean
        analysis_name (str): Name of the analysis for logging
        
    Returns:
        DataFrame: Cleaned dataframe
    """
    if df is None or df.empty:
        logger.warning(f"{analysis_name} dataframe is None or empty")
        return df
    
    logger.info(f"Validating {analysis_name} dataframe with shape {df.shape}")
    
    # Check for any completely empty rows
    empty_rows = df.isnull().all(axis=1).sum()
    if empty_rows > 0:
        logger.warning(f"Found {empty_rows} completely empty rows in {analysis_name}, removing them")
        df = df.dropna(how='all')
    
    # Check for NaN in critical columns
    for col in ['Facility', 'Lat', 'Long']:
        if col in df.columns:
            nan_count = df[col].isna().sum()
            if nan_count > 0:
                logger.warning(f"Found {nan_count} NaN values in critical column {col} for {analysis_name}")
                if col in ['Lat', 'Long']:
                    # For coordinates, drop rows with NaN
                    df = df.dropna(subset=[col])
                else:
                    # For facility names, fill with placeholder
                    df[col].fillna(f"Unknown_{analysis_name}", inplace=True)
    
    # Clean all other columns
    for col in df.columns:
        if col not in ['Facility', 'Lat', 'Long']:
            nan_count = df[col].isna().sum()
            if nan_count > 0:
                logger.info(f"Cleaning {nan_count} NaN values in {col} for {analysis_name}")
                # Apply appropriate default based on column type
                if 'Flood' in col:
                    df[col].fillna('0.1 to 0.5', inplace=True)  # Use simplified category
                elif 'Water Stress' in col:
                    df[col].fillna('N/A', inplace=True)
                elif 'Sea Level Rise' in col:
                    df[col].fillna('Little to none', inplace=True)
                elif 'Elevation' in col:
                    df[col].fillna('Little to no effect', inplace=True)
                elif 'Windspeed' in col or 'Tropical' in col:
                    df[col].fillna('Data not available', inplace=True)
                else:
                    df[col].fillna('N/A', inplace=True)
    
    logger.info(f"{analysis_name} dataframe validation complete")
    return df


def _collapse_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    dupes = df.columns[df.columns.duplicated()].unique().tolist()
    if not dupes:
        return df

    df = df.copy()
    for col in dupes:
        dup_df = df.loc[:, df.columns == col]
        if dup_df.shape[1] <= 1:
            continue
        merged = dup_df.bfill(axis=1).iloc[:, 0]
        df = df.drop(columns=[col])
        df[col] = merged
    return df
