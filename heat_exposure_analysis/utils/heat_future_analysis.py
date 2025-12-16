import logging
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterstats as rstat
from shapely.geometry import Point
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


def generate_heat_future_analysis(df: pd.DataFrame, tiff_dir: str | Path | None = None) -> pd.DataFrame:
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
    lot_area_series = df_in['lot_area'] if 'lot_area' in df_in.columns else pd.Series(1000**2, index=df_in.index)
    df_in['lot_area'] = pd.to_numeric(lot_area_series, errors='coerce').fillna(1000**2)
    gdf = gpd.GeoDataFrame(
        df_in,
        geometry=[Point(xy) for xy in zip(df_in["Long"], df_in["Lat"])],
        crs="EPSG:4326",
    ).to_crs(epsg=32651)
    # Initialize output columns so they persist even if stats are missing
    for col in cols:
        gdf[col] = np.nan
    gdf['geometry'] = gdf.geometry.buffer(np.sqrt(gdf['lot_area'])/2, cap_style='square', join_style='mitre')

    # Primary extraction using percentile_75 (matching heat_updated baseline logic)
    for fp, col in col_map.items():
        try:
            stats = rstat.zonal_stats(
                gdf.to_crs(epsg=4326),
                str(fp),
                stats="percentile_75",
                all_touched=True,
                geojson_out=True,
            )
            ids = [int(f["id"]) for f in stats]
            vals = [f["properties"]["percentile_75"] for f in stats]
            gdf.loc[ids, col] = vals
        except Exception as exc:
            logger.warning("Zonal stats failed for %s: %s", fp, exc)

    mask = gdf[cols].isna().any(axis=1)
    if mask.any():
        buf = gdf.loc[mask, "geometry"].buffer(1000, cap_style=3).to_crs(epsg=4326)
        for fp, col in col_map.items():
            try:
                stats = rstat.zonal_stats(
                    buf,
                    str(fp),
                    stats="max",  # fallback uses max similar to standalone script
                    all_touched=True,
                    geojson_out=True,
                )
                ids = [int(f["id"]) for f in stats]
                vals = [f["properties"]["max"] for f in stats]
                gdf.loc[mask, col] = vals
            except Exception as exc:
                logger.warning("Buffered zonal stats failed for %s: %s", fp, exc)

    # Clamp future values so they are not lower than baseline if available
    base_col = next((c for c in cols if 'base_' in c), None)
    if base_col:
        for col in cols:
            if col == base_col:
                continue
            gdf[col] = gdf[[col, base_col]].max(axis=1)

    for col in cols:
        gdf[col] = pd.to_numeric(gdf[col], errors='coerce')
        gdf[col] = np.ceil(gdf[col]).astype('Int64')

    # Drop base column from output (baseline already provided elsewhere)
    drop_cols = ['geometry']
    if base_col:
        drop_cols.append(base_col)

    return gdf.drop(columns=drop_cols)


def apply_heat_future_analysis_to_csv(input_csv: str, tiff_dir: str | Path | None = None, output_csv: str | None = None) -> str:
    """Apply :func:`generate_heat_future_analysis` to a CSV file."""
    in_path = Path(input_csv)
    df = pd.read_csv(in_path)
    df = generate_heat_future_analysis(df, tiff_dir)
    if output_csv is None:
        output_csv = str(in_path.with_name(f"{in_path.stem}_heat_future.csv"))
    df.to_csv(output_csv, index=False)
    return output_csv
