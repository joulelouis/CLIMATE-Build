import os
from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Point
import rasterstats as rstat
import math
from django.conf import settings


def _read_facility_csv(facility_csv_path: str) -> pd.DataFrame:
    """Load and normalize facility CSV with encoding fallbacks."""
    try:
        df = pd.read_csv(facility_csv_path, encoding='utf-8')
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(facility_csv_path, encoding='latin-1')
        except UnicodeDecodeError:
            df = pd.read_csv(facility_csv_path, encoding='cp1252')

    rename_map = {}
    for col in df.columns:
        low = col.strip().lower()
        if low in ['facility', 'site', 'site name', 'facility name', 'facilty name', 'name', 'asset name']:
            rename_map[col] = 'Facility'
        elif low in ['latitude', 'lat'] and 'Lat' not in df.columns:
            rename_map[col] = 'Lat'
        elif low in ['longitude', 'long', 'lon'] and 'Long' not in df.columns:
            rename_map[col] = 'Long'
    if rename_map:
        df.rename(columns=rename_map, inplace=True)

    for coord in ['Long', 'Lat']:
        if coord not in df.columns:
            raise ValueError(f"Missing '{coord}' column in facility CSV.")

    df['Long'] = pd.to_numeric(df['Long'], errors='coerce')
    df['Lat'] = pd.to_numeric(df['Lat'], errors='coerce')
    df.dropna(subset=['Long', 'Lat'], inplace=True)

    if 'Facility' not in df.columns:
        df['Facility'] = df.index.map(lambda i: f"Facility {i+1}")

    return df


def generate_heat_exposure_analysis(facility_csv_path):
    """
    Performs heat exposure analysis for facility locations using only >35°C baseline.

    Returns:
        dict: {"combined_csv_paths": [...], "png_paths": [...]}
    """
    try:
        output_csv_files = []
        output_png_files = []

        idir = Path(settings.BASE_DIR) / 'climate_hazards_analysis' / 'static' / 'input_files'
        os.makedirs(idir, exist_ok=True)

        # Prefer baseline raster if available, otherwise fall back to the non-baseline file.
        heat_file = idir / 'PH_DaysOver35degC_ANN_BASELINE_2021-2025.tif'
        if not heat_file.exists():
            heat_file = idir / 'PH_DaysOver35degC_ANN_2021-2025.tif'
        if not heat_file.exists():
            print(f"Warning: Missing heat exposure raster file: {heat_file}")

        df_fac = _read_facility_csv(facility_csv_path)

        heat_cols = ["n>35degC_2125"]
        df_heat = df_fac[['Facility', 'Lat', 'Long']].copy()
        df_heat[heat_cols[0]] = np.nan

        if heat_file.exists():
            try:
                gs = gpd.points_from_xy(df_fac['Long'], df_fac['Lat'], crs='EPSG:4326').to_crs('EPSG:32651')
                gdf_heat = gpd.GeoDataFrame(df_fac, geometry=gs, crs='EPSG:32651')

                gdf_heat['lot_area'] = gdf_heat.get('lot_area', 1000**2)
                gdf_heat['geometry'] = gdf_heat.geometry.buffer(
                    np.sqrt(gdf_heat['lot_area'])/2, cap_style='square', join_style='mitre')

                temp_geo = Path('temp.features.geojson')
                try:
                    gdf_heat.to_crs('EPSG:4326').to_file(str(temp_geo), driver='GeoJSON')
                    out = rstat.zonal_stats(
                        str(temp_geo), str(heat_file), stats='percentile_75',
                        all_touched=True, geojson_out=True
                    )
                    if out:
                        idxs = [int(feat['id']) for feat in out]
                        vals = [feat['properties']['percentile_75'] for feat in out]
                        gdf_heat[heat_cols[0]] = pd.Series(vals, index=idxs)
                        df_heat[heat_cols[0]] = gdf_heat[heat_cols[0]]
                finally:
                    if temp_geo.exists():
                        temp_geo.unlink()
            except Exception as e:
                print(f"Error in heat raster processing: {e}")

        for col in heat_cols:
            if col in df_heat.columns:
                df_heat.loc[:, col] = df_heat[col].apply(
                    lambda v: int(math.ceil(v)) if pd.notnull(v) else v)

        # Plot is optional; keep for compatibility
        fig, ax = plt.subplots(figsize=(12, 8))
        point_geom = gpd.points_from_xy(df_heat['Long'], df_heat['Lat'], crs='EPSG:4326')
        gdf_points = gpd.GeoDataFrame(df_heat, geometry=point_geom, crs='EPSG:4326')
        gdf_points.plot(ax=ax, color='red', markersize=100)
        ax.set_title('Heat Exposure Analysis for Facility Locations')
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')

        plot_path = idir / 'heat_exposure_plot.png'
        plt.savefig(plot_path, format='png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        output_png_files.append(str(plot_path))

        output_csv = idir / 'heat_exposure_analysis_output.csv'
        df_heat.to_csv(output_csv, index=False)
        output_csv_files.append(str(output_csv))

        print(f"Heat analysis output saved to: {output_csv}")

        return {
            "combined_csv_paths": output_csv_files,
            "png_paths": output_png_files
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
