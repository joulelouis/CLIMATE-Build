import json
import os
import tempfile
import zipfile
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, shape
import matplotlib.pyplot as plt
from pyproj import CRS
from rasterstats import zonal_stats
from django.conf import settings


def generate_flood_exposure_analysis(facility_csv_path, scenarios=None, facility_geofile_path=None, facility_geojson_records=None):
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
        if scenarios is None:
            scenarios = ['current']

        # Scenario configuration (keep column names used in hazard tables)
        FLOOD_SCENARIOS = {
            'current': {
                # Prefer the non-COG raster to mirror flood_updated.py, fallback to COG
                'files': [
                    'PH_Flood_100year_UTM_ProjectNOAH_Unmasked.tif',
                    'PH_Flood_100year_UTM_ProjectNOAH_Unmasked_COG.tif'
                ],
                'column_name': 'Flood Depth (meters)',
                'description': 'Current flood exposure'
            },
            'moderate': {
                'files': ['PH_Flood_100year_UTM_ProjectNOAH_Unmasked_COG_SSP245.tif'],
                'column_name': 'Flood Depth (meters) - Moderate Case',
                'description': 'Future flood exposure - Moderate Case (SSP2-4.5)'
            },
            'worst': {
                'files': ['PH_Flood_100year_UTM_ProjectNOAH_Unmasked_COG_SSP585.tif'],
                'column_name': 'Flood Depth (meters) - Worst Case',
                'description': 'Future flood exposure - Worst Case (SSP5-8.5)'
            }
        }
        FLOOD_MGB_FILES = [
            'PH_FloodSusceptibility_MGB_UTM_Unmasked_COG.tif',
            'PH_FloodSusceptibility_MGB_UTM_Unmasked.tif'
        ]

        for scenario in scenarios:
            if scenario not in FLOOD_SCENARIOS:
                raise ValueError(f"Invalid scenario: {scenario}. Valid scenarios: {list(FLOOD_SCENARIOS.keys())}")

        output_csv_files = []
        output_png_files = []

        output_dir = os.path.join(settings.BASE_DIR, 'climate_hazards_analysis', 'static', 'input_files')
        os.makedirs(output_dir, exist_ok=True)

        def get_raster_path(filenames):
            """
            Given a list of candidate filenames, return the first that exists
            (search flood_exposure_analysis/static/input_files then climate_hazards_analysis/static/input_files).
            """
            search_dirs = [
                os.path.join(settings.BASE_DIR, 'flood_exposure_analysis', 'static', 'input_files'),
                os.path.join(settings.BASE_DIR, 'climate_hazards_analysis', 'static', 'input_files')
            ]

            for fname in filenames:
                for base in search_dirs:
                    candidate = os.path.join(base, fname)
                    if os.path.exists(candidate):
                        return candidate

            raise FileNotFoundError(f"Flood raster files {filenames} not found in input directories")

        def load_geofile(path):
            if not path or not os.path.exists(path):
                return None

            ext = os.path.splitext(path)[1].lower()
            if ext == '.zip':
                with tempfile.TemporaryDirectory() as tmpdir:
                    with zipfile.ZipFile(path, 'r') as zip_ref:
                        zip_ref.extractall(tmpdir)
                    shp_files = [p for p in os.listdir(tmpdir) if p.lower().endswith('.shp')]
                    if not shp_files:
                        return None
                    shp_path = os.path.join(tmpdir, shp_files[0])
                    return gpd.read_file(shp_path)
            if ext in ['.gpkg', '.shp']:
                return gpd.read_file(path)

            return None

        gdf = None
        if facility_geofile_path:
            try:
                gdf = load_geofile(facility_geofile_path)
            except Exception:
                gdf = None

        if gdf is None and facility_geojson_records:
            geo_rows = []
            geometries = []
            for record in facility_geojson_records:
                geom = record.get('geometry')
                if not geom:
                    continue
                try:
                    shapely_geom = shape(geom)
                except Exception:
                    continue
                geometries.append(shapely_geom)
                geo_rows.append({
                    'Facility': record.get('Facility') or record.get('Name') or record.get('Site'),
                    'Lat': record.get('Lat'),
                    'Long': record.get('Long'),
                })

            if geo_rows and geometries:
                gdf = gpd.GeoDataFrame(geo_rows, geometry=geometries, crs='EPSG:4326')

        # Load facility locations
        if gdf is None:
            df_fac = pd.read_csv(facility_csv_path)
        else:
            gdf = gdf.to_crs('EPSG:4326')
            if 'Facility' not in gdf.columns:
                for name_col in ['Name', 'Site', 'Facility', 'Asset', 'asset', 'facility']:
                    if name_col in gdf.columns:
                        gdf['Facility'] = gdf[name_col].astype(str)
                        break
            if 'Facility' not in gdf.columns:
                gdf['Facility'] = [f'Asset {i + 1}' for i in range(len(gdf))]

            if 'Lat' not in gdf.columns or 'Long' not in gdf.columns:
                gdf['Lat'] = gdf.geometry.centroid.y
                gdf['Long'] = gdf.geometry.centroid.x
            else:
                gdf['Lat'] = pd.to_numeric(gdf['Lat'], errors='coerce')
                gdf['Long'] = pd.to_numeric(gdf['Long'], errors='coerce')

            df_fac = gdf.drop(columns='geometry')

            try:
                debug_dir = os.path.join(settings.BASE_DIR, 'climate_hazards_analysis_v2', 'static', 'input_files')
                os.makedirs(debug_dir, exist_ok=True)
                debug_path = os.path.join(debug_dir, 'flood_polygon_input_debug.geojson')
                with open(debug_path, 'w', encoding='utf-8') as debug_file:
                    debug_file.write(gdf.to_json())
            except Exception:
                pass

        # Ensure Facility, Lat, Long columns exist
        rename_map = {}
        for col in df_fac.columns:
            low = col.strip().lower()
            if low in ['facility', 'site', 'site name', 'facility name', 'facilty name']:
                rename_map[col] = 'Facility'
        if rename_map:
            df_fac.rename(columns=rename_map, inplace=True)

        for coord in ['Long', 'Lat']:
            if coord not in df_fac.columns:
                raise ValueError(f"Missing '{coord}' column in facility CSV.")

        df_fac['Long'] = pd.to_numeric(df_fac['Long'], errors='coerce')
        df_fac['Lat'] = pd.to_numeric(df_fac['Lat'], errors='coerce')
        df_fac.dropna(subset=['Long', 'Lat'], inplace=True)

        if 'Facility' not in df_fac.columns:
            raise ValueError("Your facility CSV must include a 'Facility' column or equivalent header.")

        # Build geometries in raster CRS (EPSG:32651)
        raster_crs = CRS('epsg:32651')
        if gdf is None:
            points = gpd.GeoDataFrame(
                df_fac.copy(),
                geometry=gpd.points_from_xy(df_fac['Long'], df_fac['Lat']),
                crs='EPSG:4326'
            ).to_crs(raster_crs)

            # Use ~500m buffer (matches prior ~0.0045 deg buffer) for polygon stats
            buffer_distance_m = 500
            stats_geometries = [
                geom.buffer(buffer_distance_m, cap_style=3) for geom in points.geometry
            ]
        else:
            gdf_proj = gdf.to_crs(raster_crs)
            stats_geometries = []
            for geom in gdf_proj.geometry:
                if geom is None or geom.is_empty:
                    stats_geometries.append(geom)
                    continue
                if geom.geom_type in ['Polygon', 'MultiPolygon']:
                    stats_geometries.append(geom)
                else:
                    stats_geometries.append(geom.buffer(500, cap_style=3))

        def classify_depth(value):
            """
            Map percentile depth to categorical buckets using the updated flood logic.
            Mirrors flood_updated.py mapping (ceil -> int -> buckets).
            """
            try:
                v = int(np.ceil(0 if pd.isna(value) else float(value)))
            except Exception:
                return 'Unknown'

            mapping = {
                0: '<0.1',
                1: '0.1-0.5',
                2: '0.5-1.5',
                3: '>1.5',
            }
            return mapping.get(v, 'Unknown')

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
            raster_filenames = scenario_config['files']
            column_name = scenario_config['column_name']

            print(f"[{i}/{len(scenarios)}] PROCESSING SCENARIO: {scenario.upper()}")
            print(f"  Description: {scenario_config['description']}")
            print(f"  Raster File candidates: {raster_filenames}")
            print(f"  Output Column: {column_name}")

            raster_path = get_raster_path(raster_filenames)
            print(f"  Raster Path: {raster_path}")
            print(f"  Raster Exists: {os.path.exists(raster_path)}")

            print(f"  Extracting flood depths using zonal statistics (percentile_90)...")
            stats = zonal_stats(stats_geometries, raster_path, stats='percentile_90', nodata=255)
            print(f"  Zonal stats completed: {len(stats)} results")

            percentile_values = [
                stat.get('percentile_90') if stat.get('percentile_90') is not None else 0
                for stat in stats
            ]
            exposure_values = [classify_depth(p) for p in percentile_values]

            exposure_counts = {}
            for exp in exposure_values:
                exposure_counts[exp] = exposure_counts.get(exp, 0) + 1

            print(f"  Exposure Classification Results:")
            for exp_level, count in exposure_counts.items():
                print(f"    {exp_level}: {count} facilities")

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

        points_gdf = gpd.GeoDataFrame(
            combined_gdf[['Facility', 'Lat', 'Long']],
            geometry=gpd.points_from_xy(combined_gdf['Long'], combined_gdf['Lat']),
            crs='EPSG:4326'
        )

        points_gdf.plot(ax=ax, color='blue', markersize=100)

        title = f'Flood Exposure for Facility Locations'
        if len(scenarios) > 1:
            title += f' ({", ".join(scenarios).title()} scenarios)'
        else:
            title += f' ({scenarios[0].title()} scenario)'

        ax.set_title(title)
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')

        plot_filename = 'flood_exposure_plot.png'
        if len(scenarios) > 1:
            plot_filename = f'flood_exposure_plot_{"_".join(scenarios)}.png'

        plot_path = os.path.join(output_dir, plot_filename)
        plt.savefig(plot_path, format='png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        output_png_files.append(plot_path)

        output_csv = os.path.join(output_dir, 'flood_exposure_analysis_output.csv')
        combined_gdf[result_columns].to_csv(output_csv, index=False)
        output_csv_files.append(output_csv)

        print(f"Multi-scenario flood analysis output saved to: {output_csv}")
        print(f"Scenarios processed: {scenarios}")
        print(f"Result columns: {result_columns}")

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
