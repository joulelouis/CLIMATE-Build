import logging
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterstats as rstat
from shapely.geometry import Point, shape
from django.conf import settings

logger = logging.getLogger(__name__)


def _load_tiff_files(tiff_dir: Path) -> list[Path]:
    pattern = "PH_DaysOver35degC_ANN_*.tif"
    files = sorted(tiff_dir.glob(pattern))
    if not files:
        logger.warning("No future heat GeoTIFFs found in %s", tiff_dir)
    return files


def _column_for_file(fp: Path) -> str | None:
    name = fp.stem.upper()
    # Extract timeframe from the last chunk (e.g., 2026-2030)
    parts = fp.stem.split("_")
    timeframe = parts[-1]
    short_tf = timeframe[2:4] + timeframe[-2:]

    if "BASELINE" in name or "2021-2025" in name:
        return f"DaysOver35C_base_{short_tf}"
    if "SSP245" in name:
        return f"DaysOver35C_ssp245_{short_tf}"
    if "SSP585" in name:
        return f"DaysOver35C_ssp585_{short_tf}"
    return None


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


def _load_polygon_gdf(facility_geofile_path, facility_geojson_records):
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
        return None

    gdf = gdf.to_crs("EPSG:4326")
    if "Facility" not in gdf.columns:
        for name_col in ["Name", "name", "NAME", "Site", "Asset", "asset", "facility"]:
            if name_col in gdf.columns:
                gdf["Facility"] = gdf[name_col].astype(str)
                break
    if "Facility" not in gdf.columns:
        gdf["Facility"] = [f"Facility {i + 1}" for i in range(len(gdf))]

    if "Lat" not in gdf.columns or "Long" not in gdf.columns:
        gdf["Lat"] = gdf.geometry.centroid.y
        gdf["Long"] = gdf.geometry.centroid.x
    else:
        gdf["Lat"] = pd.to_numeric(gdf["Lat"], errors="coerce")
        gdf["Long"] = pd.to_numeric(gdf["Long"], errors="coerce")

    return gdf


def generate_heat_future_analysis(
    df: pd.DataFrame,
    tiff_dir: str | Path | None = None,
    facility_geofile_path=None,
    facility_geojson_records=None,
) -> pd.DataFrame:
    """Calculate future heat exposure statistics for each facility.

    Parameters
    ----------
    df : DataFrame
        Input dataframe with ``Facility``, ``Lat`` and ``Long`` columns.
    tiff_dir : str or Path, optional
        Directory containing the future heat GeoTIFF files. Defaults to the
        ``climate_hazards_analysis/static/input_files`` directory.

    Returns
    -------
    DataFrame
        The input dataframe with additional future heat columns appended.
    """
    if tiff_dir is None:
        tiff_dir = Path(settings.BASE_DIR) / "climate_hazards_analysis" / "static" / "input_files"
    else:
        tiff_dir = Path(tiff_dir)

    files = _load_tiff_files(tiff_dir)
    if not files:
        return df

    # Map files to target columns (baseline + SSPs) to avoid misalignment
    col_map: dict[Path, str] = {}
    for fp in files:
        col = _column_for_file(fp)
        if col:
            col_map[fp] = col
    cols = list(col_map.values())

    df_in = df.reset_index(drop=True).copy()
    df_in = _collapse_duplicate_columns(df_in)
    lot_area_series = df_in['lot_area'] if 'lot_area' in df_in.columns else pd.Series(1000**2, index=df_in.index)
    df_in['lot_area'] = pd.to_numeric(lot_area_series, errors='coerce').fillna(1000**2)

    polygon_gdf = _load_polygon_gdf(facility_geofile_path, facility_geojson_records)
    polygon_mask = pd.Series(False, index=df_in.index)
    if polygon_gdf is not None:
        polygon_gdf['Facility_key'] = polygon_gdf['Facility'].astype(str).str.strip().str.lower()
        df_in['Facility_key'] = df_in['Facility'].astype(str).str.strip().str.lower()
        geom_lookup = polygon_gdf.set_index('Facility_key')['geometry'].to_dict()
        df_in['polygon_geometry'] = df_in['Facility_key'].map(geom_lookup)
        polygon_mask = df_in['polygon_geometry'].apply(
            lambda g: hasattr(g, 'geom_type') and g.geom_type in ['Polygon', 'MultiPolygon']
        )

    # Initialize output columns so they persist even if stats are missing
    for col in cols:
        df_in[col] = np.nan

    # Build buffered point geometries for point-based stats and fallback.
    gdf_points = gpd.GeoDataFrame(
        df_in,
        geometry=[Point(xy) for xy in zip(df_in["Long"], df_in["Lat"])],
        crs="EPSG:4326",
    ).to_crs(epsg=32651)
    gdf_points['geometry'] = gdf_points.geometry.buffer(
        np.sqrt(gdf_points['lot_area'])/2, cap_style='square', join_style='mitre'
    )

    # Primary extraction using percentile_75 (matching heat_updated baseline logic)
    for fp, col in col_map.items():
        try:
            if polygon_mask.any():
                poly_idx = df_in.index[polygon_mask].tolist()
                poly_gdf = gpd.GeoDataFrame(
                    df_in.loc[poly_idx],
                    geometry=df_in.loc[poly_idx, 'polygon_geometry'],
                    crs="EPSG:4326",
                )
                stats = rstat.zonal_stats(
                    poly_gdf,
                    str(fp),
                    stats="percentile_75",
                    all_touched=True,
                )
                if stats:
                    vals = [f.get("percentile_75") for f in stats]
                    df_in.loc[poly_idx, col] = vals

            point_mask = ~polygon_mask
            if point_mask.any():
                point_idx = df_in.index[point_mask].tolist()
                stats = rstat.zonal_stats(
                    gdf_points.loc[point_idx].to_crs(epsg=4326),
                    str(fp),
                    stats="percentile_75",
                    all_touched=True,
                )
                if stats:
                    vals = [f.get("percentile_75") for f in stats]
                    df_in.loc[point_idx, col] = vals
        except Exception as exc:
            logger.warning("Zonal stats failed for %s: %s", fp, exc)

    mask = df_in[cols].isna().any(axis=1)
    if mask.any():
        buf = gdf_points.loc[mask, "geometry"].buffer(1000, cap_style=3).to_crs(epsg=4326)
        for fp, col in col_map.items():
            try:
                stats = rstat.zonal_stats(
                    buf,
                    str(fp),
                    stats="max",  # fallback uses max similar to standalone script
                    all_touched=True,
                )
                if stats:
                    vals = [f.get("max") for f in stats]
                    df_in.loc[mask, col] = vals
            except Exception as exc:
                logger.warning("Buffered zonal stats failed for %s: %s", fp, exc)

    # Clamp future values so they are not lower than baseline if available
    base_col = next((c for c in cols if 'base_' in c), None)
    if base_col:
        for col in cols:
            if col == base_col:
                continue
            df_in[col] = df_in[[col, base_col]].max(axis=1)

    for col in cols:
        df_in[col] = pd.to_numeric(df_in[col], errors='coerce')
        df_in[col] = np.rint(df_in[col]).astype('Int64')

    # Drop helper columns; keep base column for downstream baseline fill
    drop_cols = ['geometry', 'polygon_geometry', 'Facility_key']

    drop_cols = [col for col in drop_cols if col in df_in.columns]
    return df_in.drop(columns=drop_cols)


def apply_heat_future_analysis_to_csv(input_csv: str, tiff_dir: str | Path | None = None, output_csv: str | None = None) -> str:
    """Apply :func:`generate_heat_future_analysis` to a CSV file."""
    in_path = Path(input_csv)
    df = pd.read_csv(in_path)
    df = generate_heat_future_analysis(df, tiff_dir)
    if output_csv is None:
        output_csv = str(in_path.with_name(f"{in_path.stem}_heat_future.csv"))
    df.to_csv(output_csv, index=False)
    return output_csv
