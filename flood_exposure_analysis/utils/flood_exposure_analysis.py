import os
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import matplotlib.pyplot as plt
from pyproj import CRS
from rasterstats import zonal_stats
from django.conf import settings

def generate_flood_exposure_analysis(facility_csv_path, scenarios=None):
    """
    Performs flood exposure analysis for facility locations across multiple scenarios.

    Args:
        facility_csv_path (str): Path to the facility CSV file with locations
        scenarios (list): List of scenarios to analyze ['current', 'moderate', 'worst']
                         Default: ['current'] for backward compatibility

    Returns:
        dict: Dictionary containing file paths to generated outputs and scenarios processed
    """
    try:
        # Default to current scenario for backward compatibility
        if scenarios is None:
            scenarios = ['current']

        # Scenario configuration
        FLOOD_SCENARIOS = {
            'current': {
                'file': 'PH_Flood_100year_UTM_ProjectNOAH_Unmasked_COG.tif',
                'column_name': 'Flood Depth (meters)',
                'description': 'Current flood exposure'
            },
            'moderate': {
                'file': 'PH_Flood_100year_UTM_ProjectNOAH_Unmasked_COG_SSP245.tif',
                'column_name': 'Flood Depth (meters) - Moderate Case',
                'description': 'Future flood exposure - Moderate Case (SSP2-4.5)'
            },
            'worst': {
                'file': 'PH_Flood_100year_UTM_ProjectNOAH_Unmasked_COG_SSP585.tif',
                'column_name': 'Flood Depth (meters) - Worst Case',
                'description': 'Future flood exposure - Worst Case (SSP5-8.5)'
            }
        }

        # Validate scenarios
        for scenario in scenarios:
            if scenario not in FLOOD_SCENARIOS:
                raise ValueError(f"Invalid scenario: {scenario}. Valid scenarios: {list(FLOOD_SCENARIOS.keys())}")

        # Lists to track generated files
        output_csv_files = []
        output_png_files = []

        # Define path for climate_hazards_analysis input_files directory
        output_dir = os.path.join(settings.BASE_DIR, 'climate_hazards_analysis', 'static', 'input_files')
        os.makedirs(output_dir, exist_ok=True)
        
        # Helper function to get raster path with fallback
        def get_raster_path(filename):
            # Try flood_exposure_analysis directory first
            raster_path = os.path.join(
                settings.BASE_DIR, 'flood_exposure_analysis', 'static',
                'input_files', filename
            )

            if not os.path.exists(raster_path):
                print(f"Warning: Flood raster file not found: {raster_path}")
                # Fallback to climate_hazards_analysis directory
                raster_path = os.path.join(
                    settings.BASE_DIR, 'climate_hazards_analysis', 'static',
                    'input_files', filename
                )
                if not os.path.exists(raster_path):
                    raise FileNotFoundError(f"Flood raster file '{filename}' not found in either flood_exposure_analysis or climate_hazards_analysis directories")

            return raster_path
        
        # Load facility locations
        df_fac = pd.read_csv(facility_csv_path)
        
        # Ensure Facility, Lat, Long columns exist
        rename_map = {}
        for col in df_fac.columns:
            low = col.strip().lower()
            if low in ['facility', 'site', 'site name', 'facility name', 'facilty name']:
                rename_map[col] = 'Facility'
        if rename_map:
            df_fac.rename(columns=rename_map, inplace=True)
            
        # Ensure coordinates are present
        for coord in ['Long', 'Lat']:
            if coord not in df_fac.columns:
                raise ValueError(f"Missing '{coord}' column in facility CSV.")
        
        # Convert to numeric and drop invalid coordinates
        df_fac['Long'] = pd.to_numeric(df_fac['Long'], errors='coerce')
        df_fac['Lat'] = pd.to_numeric(df_fac['Lat'], errors='coerce')
        df_fac.dropna(subset=['Long', 'Lat'], inplace=True)
        
        if 'Facility' not in df_fac.columns:
            raise ValueError("Your facility CSV must include a 'Facility' column or equivalent header.")
        
        # Set buffer size for analysis (~250 meters)
        buffer = 0.0045
        
        # Create polygons with buffer for flood analysis
        flood_polys = [
            Point(x, y).buffer(buffer, cap_style=3) 
            for x, y in zip(df_fac['Long'], df_fac['Lat'])
        ]
        
        # Create GeoDataFrame with proper projection
        flood_gdf = gpd.GeoDataFrame(df_fac.copy(), geometry=flood_polys, crs=CRS('epsg:32651'))

        # Helper function to classify flood exposure
        def determine_exposure(percentile):
            if pd.isna(percentile):
                return 'Unknown'
            if percentile == 1:
                return '0.1 to 0.5'
            elif percentile == 2:
                return '0.5 to 1.5'
            else:
                return 'Greater than 1.5'

        # Process each scenario
        result_columns = ['Facility', 'Lat', 'Long']
        combined_gdf = df_fac.copy()

        print(f"\n{'='*60}")
        print(f"FLOOD EXPOSURE ANALYSIS - MULTI-SCENARIO PROCESSING")
        print(f"{'='*60}")
        print(f"Total scenarios to process: {len(scenarios)}")
        print(f"Scenarios: {', '.join(scenarios)}")
        print(f"Number of facilities: {len(df_fac)}")
        print(f"{'='*60}\n")

        for i, scenario in enumerate(scenarios, 1):
            scenario_config = FLOOD_SCENARIOS[scenario]
            raster_filename = scenario_config['file']
            column_name = scenario_config['column_name']

            print(f"[{i}/{len(scenarios)}] PROCESSING SCENARIO: {scenario.upper()}")
            print(f"  Description: {scenario_config['description']}")
            print(f"  Raster File: {raster_filename}")
            print(f"  Output Column: {column_name}")

            # Get raster path for this scenario
            raster_path = get_raster_path(raster_filename)
            print(f"  Raster Path: {raster_path}")
            print(f"  Raster Exists: {os.path.exists(raster_path)}")

            # Extract 75th percentile flood depth from raster
            print(f"  Extracting flood depths using zonal statistics...")
            stats = zonal_stats(flood_gdf.geometry, raster_path, stats='percentile_75')
            print(f"  Zonal stats completed: {len(stats)} results")

            # Process the results for this scenario
            percentile_values = [
                stat['percentile_75'] if stat['percentile_75'] is not None else 1
                for stat in stats
            ]

            # Classify exposure based on flood depth
            exposure_values = [determine_exposure(p) for p in percentile_values]

            # Log exposure distribution for this scenario
            exposure_counts = {}
            for exp in exposure_values:
                exposure_counts[exp] = exposure_counts.get(exp, 0) + 1

            print(f"  Exposure Classification Results:")
            for exp_level, count in exposure_counts.items():
                print(f"    {exp_level}: {count} facilities")

            # Add scenario data to combined results
            combined_gdf[column_name] = exposure_values
            result_columns.append(column_name)

            print(f"  > Scenario '{scenario}' completed successfully")
            print(f"  > Column '{column_name}' added to results")
            print(f"  {'-'*50}")

        print(f"\n{'='*60}")
        print(f"MULTI-SCENARIO FLOOD ANALYSIS SUMMARY")
        print(f"{'='*60}")
        print(f"Total scenarios processed: {len(scenarios)}")
        print(f"Result columns: {result_columns}")
        print(f"Combined dataset shape: {combined_gdf.shape}")
        print(f"{'='*60}\n")
        
        # Create a visualization of the flood exposure
        fig, ax = plt.subplots(figsize=(12, 8))

        # Create a colormap for different exposure categories
        cmap = {
            '0.1 to 0.5': 'green',
            '0.5 to 1.5': 'orange',
            'Greater than 1.5': 'red',
            'Unknown': 'gray'
        }

        # Create a point-based GeoDataFrame for visualization
        # Use the first scenario's column for visualization
        first_scenario_column = result_columns[3] if len(result_columns) > 3 else result_columns[-1]
        viz_columns = ['Facility', 'Lat', 'Long', first_scenario_column]

        points_gdf = gpd.GeoDataFrame(
            combined_gdf[viz_columns],
            geometry=gpd.points_from_xy(combined_gdf['Long'], combined_gdf['Lat']),
            crs='EPSG:4326'
        )

        # Simple plot with facility locations
        points_gdf.plot(ax=ax, color='blue', markersize=100)

        # Update title to reflect scenarios processed
        title = f'Flood Exposure for Facility Locations'
        if len(scenarios) > 1:
            title += f' ({", ".join(scenarios).title()} scenarios)'
        else:
            title += f' ({scenarios[0].title()} scenario)'

        ax.set_title(title)
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')

        # Save the plot to the climate_hazards_analysis input_files directory
        plot_filename = 'flood_exposure_plot.png'
        if len(scenarios) > 1:
            plot_filename = f'flood_exposure_plot_{"_".join(scenarios)}.png'

        plot_path = os.path.join(output_dir, plot_filename)
        plt.savefig(plot_path, format='png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        output_png_files.append(plot_path)

        # Save the results to CSV in the climate_hazards_analysis input_files directory
        output_csv = os.path.join(output_dir, 'flood_exposure_analysis_output.csv')

        # Save combined results with all scenario columns
        combined_gdf[result_columns].to_csv(output_csv, index=False)
        output_csv_files.append(output_csv)

        print(f"Multi-scenario flood analysis output saved to: {output_csv}")
        print(f"Scenarios processed: {scenarios}")
        print(f"Result columns: {result_columns}")

        # Return paths to the generated files with scenario information
        return {
            "combined_csv_paths": output_csv_files,
            "png_paths": output_png_files,
            "scenarios_processed": scenarios,
            "result_columns": result_columns
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "scenarios_processed": [],
            "result_columns": []
        }