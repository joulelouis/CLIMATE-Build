"""
Sea Level Rise Analysis Module for Climate Hazards Analysis

This module processes sea level rise projections for facility locations using NetCDF data
and storm surge advisory shapefiles. It handles user-uploaded facility data (CSV, XLSX, ZIP)
and generates CSV outputs with SLR projections for different SSP scenarios and confidence intervals.

This module is integrated into the climate_hazards_analysis workflow and uses the same
static input files directory structure.

Usage in Django views:
    from .utils.slr_analysis import run_sea_level_rise_analysis
    results = run_sea_level_rise_analysis(uploaded_file, output_dir)
"""

import numpy as np
import pandas as pd
import geopandas as gpd
import xarray as xr
from pathlib import Path
import os
import zipfile
import tempfile
import shutil
from shapely.geometry import Point
from django.conf import settings
from django.core.files.storage import default_storage


class SeaLevelRiseAnalyzer:
    """
    A class to analyze sea level rise projections for facility locations in the climate hazards analysis framework.
    """

    def __init__(self):
        """
        Initialize the Sea Level Rise Analyzer with climate_hazards_analysis app paths.
        """
        # Get the climate_hazards_analysis app path
        self.app_path = Path(__file__).parent.parent
        self.static_input_path = self.app_path / "static" / "input_files"
        self.facility_data = None
        self.ssa1_data = None

    def load_storm_surge_data(self):
        """
        Load Storm Surge Advisory 1 data from static input files.

        Returns:
            gpd.GeoDataFrame: Storm surge advisory data
        """
        try:
            ssa1_file = self.static_input_path / "PH_SSA1.shp"
            if not ssa1_file.exists():
                raise FileNotFoundError(f"PH_SSA1.shp not found at {ssa1_file}")

            self.ssa1_data = gpd.read_file(ssa1_file)
            print(f"Loaded SSA1 data from {ssa1_file}")
            return self.ssa1_data
        except Exception as e:
            print(f"Error loading SSA1 data: {e}")
            return None

    def load_facility_data_from_file(self, uploaded_file):
        """
        Load facility data from uploaded file (CSV, XLSX, or ZIP with shapefile).

        Args:
            uploaded_file: Django UploadedFile object or file path string

        Returns:
            pd.DataFrame: Facility data with Facility Name, LAT, LON columns
        """
        try:
            # Handle both file objects and file paths
            if isinstance(uploaded_file, str):
                # If it's a file path, determine type and load
                file_name = uploaded_file.lower()
                if file_name.endswith('.csv'):
                    return self._load_csv_data_from_path(uploaded_file)
                elif file_name.endswith(('.xlsx', '.xls')):
                    return self._load_excel_data_from_path(uploaded_file)
                elif file_name.endswith('.zip'):
                    return self._load_shapefile_from_zip_path(uploaded_file)
                else:
                    raise ValueError(f"Unsupported file format: {file_name}")
            else:
                # Handle Django UploadedFile object
                file_name = uploaded_file.name.lower()
                if file_name.endswith('.csv'):
                    return self._load_csv_data(uploaded_file)
                elif file_name.endswith(('.xlsx', '.xls')):
                    return self._load_excel_data(uploaded_file)
                elif file_name.endswith('.zip'):
                    return self._load_shapefile_from_zip(uploaded_file)
                else:
                    raise ValueError(f"Unsupported file format: {file_name}")

        except Exception as e:
            print(f"Error loading facility data: {e}")
            return None

    def _load_csv_data(self, uploaded_file):
        """Load facility data from CSV Django UploadedFile."""
        df = pd.read_csv(uploaded_file)
        return self._standardize_facility_columns(df)

    def _load_csv_data_from_path(self, file_path):
        """Load facility data from CSV file path."""
        df = pd.read_csv(file_path)
        return self._standardize_facility_columns(df)

    def _load_excel_data(self, uploaded_file):
        """Load facility data from Excel Django UploadedFile."""
        df = pd.read_excel(uploaded_file)
        return self._standardize_facility_columns(df)

    def _load_excel_data_from_path(self, file_path):
        """Load facility data from Excel file path."""
        df = pd.read_excel(file_path)
        return self._standardize_facility_columns(df)

    def _load_shapefile_from_zip(self, uploaded_file):
        """Load facility data from ZIP file containing shapefile (Django UploadedFile)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract ZIP file
            with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # Find .shp file
            shp_files = list(Path(temp_dir).glob("*.shp"))
            if not shp_files:
                raise ValueError("No .shp file found in ZIP archive")

            # Load shapefile
            gdf = gpd.read_file(shp_files[0])

            # Convert to DataFrame with coordinates
            if gdf.geometry.geom_type.iloc[0] == 'Point':
                gdf['LON'] = gdf.geometry.x
                gdf['LAT'] = gdf.geometry.y
            else:
                # Get centroid for non-point geometries
                centroids = gdf.geometry.centroid
                gdf['LON'] = centroids.x
                gdf['LAT'] = centroids.y

            return self._standardize_facility_columns(gdf)

    def _load_shapefile_from_zip_path(self, file_path):
        """Load facility data from ZIP file path containing shapefile."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract ZIP file
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # Find .shp file
            shp_files = list(Path(temp_dir).glob("*.shp"))
            if not shp_files:
                raise ValueError("No .shp file found in ZIP archive")

            # Load shapefile
            gdf = gpd.read_file(shp_files[0])

            # Convert to DataFrame with coordinates
            if gdf.geometry.geom_type.iloc[0] == 'Point':
                gdf['LON'] = gdf.geometry.x
                gdf['LAT'] = gdf.geometry.y
            else:
                # Get centroid for non-point geometries
                centroids = gdf.geometry.centroid
                gdf['LON'] = centroids.x
                gdf['LAT'] = centroids.y

            return self._standardize_facility_columns(gdf)

    def _standardize_facility_columns(self, df):
        """
        Standardize column names to Facility Name, LAT, LON.

        Args:
            df (pd.DataFrame): Input dataframe with facility data

        Returns:
            pd.DataFrame: Standardized dataframe
        """
        # Create a copy to avoid modifying original
        df = df.copy()

        # Map common column name variations
        column_mapping = {}

        # Find facility name column
        name_candidates = ['facility name', 'facility_name', 'name', 'facility', 'site_name', 'site name']
        for col in df.columns:
            if col.lower() in name_candidates:
                column_mapping[col] = 'Facility Name'
                break

        # Find latitude column
        lat_candidates = ['lat', 'latitude', 'y', 'northing']
        for col in df.columns:
            if col.lower() in lat_candidates:
                column_mapping[col] = 'LAT'
                break

        # Find longitude column
        lon_candidates = ['lon', 'long', 'longitude', 'x', 'easting']
        for col in df.columns:
            if col.lower() in lon_candidates:
                column_mapping[col] = 'LON'
                break

        # Check if all required columns found
        if len(column_mapping) < 3:
            available_cols = df.columns.tolist()
            raise ValueError(f"Could not find required columns (Facility Name, LAT, LON). Available columns: {available_cols}")

        # Rename columns
        df = df.rename(columns=column_mapping)

        # Select only required columns
        df = df[['Facility Name', 'LAT', 'LON']].copy()

        # Validate data types
        df['LAT'] = pd.to_numeric(df['LAT'], errors='coerce')
        df['LON'] = pd.to_numeric(df['LON'], errors='coerce')

        # Remove rows with invalid coordinates
        df = df.dropna(subset=['LAT', 'LON'])

        # Validate coordinate ranges (Philippines bounds)
        df = df[(df['LAT'].between(4, 21)) & (df['LON'].between(116, 127))]

        if df.empty:
            raise ValueError("No valid facility coordinates found within Philippines bounds")

        print(f"Loaded {len(df)} facilities with valid coordinates")
        return df

    def create_facility_geodataframe(self, facility_df):
        """
        Convert facility DataFrame to GeoDataFrame with Point geometries.

        Args:
            facility_df (pd.DataFrame): Facility data with LAT, LON columns

        Returns:
            gpd.GeoDataFrame: GeoDataFrame with Point geometries
        """
        geometry = [Point(row['LON'], row['LAT']) for _, row in facility_df.iterrows()]
        gdf = gpd.GeoDataFrame(facility_df, geometry=geometry, crs='EPSG:4326')
        return gdf

    def filter_facilities_in_coastal_areas(self, facility_gdf):
        """
        Filter facilities that are in coastal areas (intersect with SSA1).

        Args:
            facility_gdf (gpd.GeoDataFrame): Facility GeoDataFrame

        Returns:
            pd.DataFrame: Filtered facility data
        """
        if self.ssa1_data is None:
            # Load SSA1 data if not already loaded
            if self.load_storm_surge_data() is None:
                # If SSA1 data not available, return all facilities
                print("Warning: SSA1 data not available, processing all facilities")
                return facility_gdf[['Facility Name', 'LAT', 'LON']]

        # Ensure both GeoDataFrames have the same CRS
        facility_gdf = facility_gdf.to_crs(self.ssa1_data.crs)

        # Spatial join to find facilities in coastal areas
        coastal_facilities = gpd.sjoin(facility_gdf, self.ssa1_data, how='inner', predicate='intersects')

        # Remove duplicates and keep only required columns
        coastal_facilities = coastal_facilities[['Facility Name', 'LAT', 'LON']].drop_duplicates()

        print(f"Found {len(coastal_facilities)} facilities in coastal areas (out of {len(facility_gdf)})")
        return coastal_facilities

    def analyze_slr_projections(self, facility_df, ssp_scenarios=['245', '585'],
                              years=None, quantiles=None):
        """
        Analyze sea level rise projections for facility locations.

        Args:
            facility_df (pd.DataFrame): Facility data with Facility Name, LAT, LON
            ssp_scenarios (list): SSP scenarios to analyze
            years (list, optional): Years to analyze
            quantiles (list, optional): Confidence intervals to analyze

        Returns:
            dict: Results for each SSP scenario
        """
        if years is None:
            years = list(range(2030, 2051, 10))

        if quantiles is None:
            quantiles = [0.05, 0.5, 0.95]

        if facility_df is None or facility_df.empty:
            print("Error: No facility data provided")
            return None

        results = {}

        for ssp in ssp_scenarios:
            print(f"\nProcessing SSP {ssp}...")

            # Initialize master dataframe with facility info
            df_master = facility_df[['Facility Name', 'LAT', 'LON']].copy()

            for year in years:
                for quant in quantiles:
                    # Construct file path for NetCDF file
                    nc_file = self.static_input_path / f"total_{year}_ssp{ssp}_Medium.nc"

                    try:
                        # Load NetCDF file
                        ds_slr = xr.open_dataset(nc_file)

                        # Filter to Philippines region
                        ds_slr = ds_slr.sel(lon=slice(115.0, 128.0), lat=np.arange(3, 22))

                        # Select quantile and filter no-data values
                        ds_slr = ds_slr.sel(CI=quant)
                        ds_slr = ds_slr.where(ds_slr['sealevel_mm'] > -32768)

                        # Create column name
                        quant_col = f"{year}_SLR_CI_{quant}"
                        slr_values = []

                        # Extract SLR values for each facility
                        for _, row in facility_df.iterrows():
                            try:
                                slr_proj = ds_slr.sel(
                                    lon=row['LON'],
                                    lat=row['LAT'],
                                    method="nearest"
                                ).sealevel_mm.values

                                # Convert mm to meters and round
                                slr_proj_m = round(float(slr_proj) / 1000, 3)
                                slr_values.append(slr_proj_m)

                            except Exception as e:
                                print(f"Error processing facility {row['Facility Name']}: {e}")
                                slr_values.append(np.nan)

                        # Add column to master dataframe
                        df_master[quant_col] = slr_values

                    except FileNotFoundError:
                        print(f"Warning: NetCDF file not found - {nc_file}")
                        # Add column with NaN values
                        df_master[f"{year}_SLR_CI_{quant}"] = np.nan

                    except Exception as e:
                        print(f"Error processing {nc_file}: {e}")
                        df_master[f"{year}_SLR_CI_{quant}"] = np.nan

            results[ssp] = df_master

        return results

    def save_results(self, results, output_dir):
        """
        Save analysis results to CSV files.

        Args:
            results (dict): Analysis results for each SSP scenario
            output_dir (str): Directory to save output files

        Returns:
            list: Paths to saved files
        """
        output_paths = []
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        for ssp, df in results.items():
            output_file = output_dir / f"slr_SSP{ssp}_results.csv"
            df.to_csv(output_file, index=False)
            output_paths.append(str(output_file))
            print(f"Saved results to: {output_file}")

        return output_paths

    def analyze_from_file(self, facility_file, output_dir,
                         ssp_scenarios=['245', '585'],
                         filter_coastal=True):
        """
        Complete workflow: analyze SLR from facility file (for climate hazards analysis integration).

        Args:
            facility_file: File path string or Django UploadedFile object
            output_dir (str): Directory to save results
            ssp_scenarios (list): SSP scenarios to analyze
            filter_coastal (bool): Whether to filter only coastal facilities

        Returns:
            dict: Analysis results and file paths
        """
        try:
            print("Starting Sea Level Rise Analysis...")

            # Load facility data from file
            facility_df = self.load_facility_data_from_file(facility_file)
            if facility_df is None or facility_df.empty:
                return {"error": "Failed to load facility data from file"}

            # Filter coastal facilities if requested
            if filter_coastal:
                facility_gdf = self.create_facility_geodataframe(facility_df)
                facility_df = self.filter_facilities_in_coastal_areas(facility_gdf)

                if facility_df.empty:
                    return {"error": "No facilities found in coastal areas"}

            # Analyze SLR projections
            results = self.analyze_slr_projections(
                facility_df,
                ssp_scenarios=ssp_scenarios
            )

            if not results:
                return {"error": "Failed to analyze SLR projections"}

            # Save results
            output_paths = self.save_results(results, output_dir)

            print("\nSea Level Rise Analysis complete!")

            return {
                "success": True,
                "facilities_processed": len(facility_df),
                "ssp_scenarios": list(results.keys()),
                "output_files": output_paths,
                "results": results
            }

        except Exception as e:
            print(f"Sea Level Rise Analysis failed: {e}")
            return {"error": str(e)}

    def get_slr_columns_for_integration(self, facility_df, ssp_scenarios=['245', '585']):
        """
        Get Sea Level Rise data formatted for integration with other climate hazards.
        Returns data in the format expected by the main climate hazards analysis.

        Args:
            facility_df (pd.DataFrame): Facility data with Facility Name, LAT, LON
            ssp_scenarios (list): SSP scenarios to analyze

        Returns:
            pd.DataFrame: Facility data with SLR columns added
        """
        try:
            # Analyze SLR projections
            results = self.analyze_slr_projections(facility_df, ssp_scenarios=ssp_scenarios)

            if not results:
                print("Warning: No SLR results generated")
                return facility_df

            # Combine results from all SSP scenarios
            combined_df = facility_df[['Facility Name', 'LAT', 'LON']].copy()

            for ssp, df in results.items():
                # Add columns from this SSP scenario
                slr_columns = [col for col in df.columns if col.startswith(('2030', '2040', '2050'))]
                for col in slr_columns:
                    # Rename columns to include SSP scenario for clarity
                    new_col_name = f"{col}_SSP{ssp}"
                    combined_df[new_col_name] = df[col]

            print(f"Added {len(combined_df.columns) - 3} Sea Level Rise columns")
            return combined_df

        except Exception as e:
            print(f"Error in SLR integration: {e}")
            return facility_df


def run_sea_level_rise_analysis(facility_file, output_dir,
                               ssp_scenarios=['245', '585'],
                               filter_coastal=True):
    """
    Convenience function to run SLR analysis from Django views (climate hazards analysis integration).

    Args:
        facility_file: File path string or Django UploadedFile object
        output_dir (str): Directory to save results
        ssp_scenarios (list): SSP scenarios to analyze
        filter_coastal (bool): Whether to filter only coastal facilities

    Returns:
        dict: Analysis results
    """
    analyzer = SeaLevelRiseAnalyzer()
    return analyzer.analyze_from_file(
        facility_file,
        output_dir,
        ssp_scenarios,
        filter_coastal
    )


def integrate_slr_with_facility_data(facility_df, ssp_scenarios=['245', '585']):
    """
    Function to integrate SLR data with existing facility data for climate hazards analysis.

    Args:
        facility_df (pd.DataFrame): Facility data with Facility Name, LAT, LON
        ssp_scenarios (list): SSP scenarios to analyze

    Returns:
        pd.DataFrame: Facility data with SLR columns added
    """
    analyzer = SeaLevelRiseAnalyzer()
    return analyzer.get_slr_columns_for_integration(facility_df, ssp_scenarios)