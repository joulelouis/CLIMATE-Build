import os
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point, box
from django.conf import settings


def _read_facility_csv(facility_csv_path):
    """Load facility CSV with encoding fallbacks and normalize column names."""
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


def generate_water_stress_analysis(facility_csv_path, buffer_size=0.0009):
    """
    Performs water stress baseline analysis for facility locations (no plot).

    Returns:
        dict: {"combined_csv_paths": [...], "png_paths": [], "buffer_size": float, "buffer_meters": int}
    """
    try:
        output_csv_files = []

        water_dir = os.path.join(settings.BASE_DIR, 'water_stress', 'static', 'input_files')
        output_dir = os.path.join(settings.BASE_DIR, 'climate_hazards_analysis', 'static', 'input_files')
        os.makedirs(output_dir, exist_ok=True)

        shapefile_base = os.path.join(water_dir, 'hybas_lake_au_lev06_v1c')
        shapefile_path = f"{shapefile_base}.shp"
        dbf_path = f"{shapefile_base}.dbf"
        shx_path = f"{shapefile_base}.shx"
        baseline_csv_path = os.path.join(water_dir, 'Aqueduct40_baseline_annual_y2023m07d05.csv')

        required = [shapefile_path, dbf_path, shx_path, baseline_csv_path]
        missing = [f for f in required if not os.path.exists(f)]
        if missing:
            print(f"Warning: Missing water stress files: {', '.join(missing)}")
            df_fac = _read_facility_csv(facility_csv_path)
            df_fac['Water Stress Exposure (%)'] = np.nan
            df_fac['pfaf_id'] = pd.NA
            output_filename = f'water_stress_analysis_output_buffer_{buffer_size:.4f}.csv'
            output_csv = os.path.join(output_dir, output_filename)
            df_fac[['Facility', 'Lat', 'Long', 'pfaf_id', 'Water Stress Exposure (%)']].to_csv(
                output_csv, index=False, encoding='utf-8'
            )
            output_csv_files.append(output_csv)
            return {
                "combined_csv_paths": output_csv_files,
                "png_paths": [],
                "buffer_size": buffer_size,
                "buffer_meters": int(buffer_size * 111000)
            }

        df_fac = _read_facility_csv(facility_csv_path)

        hydrobasins = gpd.read_file(shapefile_path)
        if hydrobasins.crs is None:
            hydrobasins.set_crs("EPSG:4326", inplace=True)

        ws_current = pd.read_csv(baseline_csv_path)
        # Normalize pfaf_id column names
        if 'pfaf_id' in hydrobasins.columns and 'PFAF_ID' not in hydrobasins.columns:
            hydrobasins.rename(columns={'pfaf_id': 'PFAF_ID'}, inplace=True)
        if 'pfaf_id' in ws_current.columns and 'PFAF_ID' not in ws_current.columns:
            ws_current.rename(columns={'pfaf_id': 'PFAF_ID'}, inplace=True)

        if 'PFAF_ID' not in hydrobasins.columns or 'PFAF_ID' not in ws_current.columns:
            raise ValueError("'PFAF_ID' must exist in both shapefile and baseline CSV")

        merged = hydrobasins.merge(ws_current, on='PFAF_ID')
        gdf = merged
        if gdf.crs is None:
            gdf.set_crs("EPSG:4326", inplace=True)
        gdf = gdf.cx[114:130, 0:20].reset_index(drop=True)
        gdf['bws_raw'] = gdf['bws_raw'].astype(float)

        facility_gdf = gpd.GeoDataFrame(
            df_fac,
            geometry=[Point(x, y) for x, y in zip(df_fac['Long'], df_fac['Lat'])],
            crs="EPSG:4326"
        )
        if facility_gdf.crs != gdf.crs:
            facility_gdf = facility_gdf.to_crs(gdf.crs)

        buf = buffer_size
        facility_gdf['geometry'] = facility_gdf.geometry.apply(
            lambda p: box(p.x - buf, p.y - buf, p.x + buf, p.y + buf)
        )

        facility_join = gpd.sjoin(
            facility_gdf, gdf[['geometry', 'PFAF_ID', 'bws_raw']],
            how='left', predicate='intersects'
        )
        # gpd.sjoin keeps the left index by default; dedupe and align to the original order.
        facility_join = facility_join[~facility_join.index.duplicated(keep='first')]
        aligned = facility_join.reindex(facility_gdf.index)

        # Safeguard against missing join results so callers don't break table rendering
        df_fac['pfaf_id'] = pd.to_numeric(aligned.get('PFAF_ID'), errors='coerce').astype('Int64')
        df_fac['Water Stress Exposure (%)'] = (
            aligned.get('bws_raw')
            .astype(float)
            .mul(100)
            .round(1)
            if 'bws_raw' in aligned.columns
            else np.nan
        )
        if df_fac['Water Stress Exposure (%)'].isna().all():
            print("Warning: Water stress join returned no matches; columns filled with NA.")

        output_filename = f'water_stress_analysis_output_buffer_{buffer_size:.4f}.csv'
        output_csv = os.path.join(output_dir, output_filename)
        df_fac[['Facility', 'Lat', 'Long', 'pfaf_id', 'Water Stress Exposure (%)']].to_csv(
            output_csv, index=False
        )
        output_csv_files.append(output_csv)

        return {
            "combined_csv_paths": output_csv_files,
            "png_paths": [],
            "buffer_size": buffer_size,
            "buffer_meters": int(buffer_size * 111000)
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
