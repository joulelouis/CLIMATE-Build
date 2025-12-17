import logging
import os
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from django.conf import settings
from scipy.spatial import distance
from shapely.geometry import Point
from shapely.wkt import loads

logger = logging.getLogger(__name__)

# Percent change factors mapped to desired horizons
PERCENT_CHANGES: Dict[str, Dict[str, float]] = {
    "RCP4.5": {"2030": 0.0203, "2040": 0.0279, "2050": 0.0351},
    "RCP8.5": {"2030": 0.0237, "2040": 0.0355, "2050": 0.0493},
}


def _round_half_up(series: pd.Series) -> pd.Series:
    """Round positive numeric values half-up, preserve NaN."""
    return series.apply(
        lambda x: np.floor(x + 0.5) if pd.notnull(x) else pd.NA
    ).astype("Int64")


def _load_csv(path: str) -> pd.DataFrame:
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, encoding="utf-8", errors="ignore")


def _parse_geometry(series: pd.Series) -> pd.Series:
    try:
        return series.apply(lambda x: loads(x).coords[0])
    except Exception:
        def extract_coords(val):
            if isinstance(val, str) and val.startswith("POINT"):
                try:
                    lon, lat = map(float, val.replace("POINT(", "").replace(")", "").split())
                    return (lon, lat)
                except Exception:
                    return (0.0, 0.0)
            return (0.0, 0.0)

        return series.apply(extract_coords)


def _standardize_lat_long(df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    lat_candidates = ["Lat", "Latitude", "lat", "latitude"]
    lon_candidates = ["Long", "Longitude", "Lon", "lon", "longitude"]
    lat_col = next((c for c in lat_candidates if c in df.columns), None)
    lon_col = next((c for c in lon_candidates if c in df.columns), None)
    if not lat_col or not lon_col:
        raise ValueError("Target CSV must contain latitude/longitude columns.")
    if lat_col != "Lat":
        df = df.rename(columns={lat_col: "Lat"})
    if lon_col != "Long":
        df = df.rename(columns={lon_col: "Long"})
    return df, "Facility" if "Facility" in df.columns else (df.columns[0] if df.columns else "Facility")


def _apply_percent_changes(base: pd.Series, pct_map: Dict[str, Dict[str, float]]) -> Dict[str, pd.Series]:
    outputs = {}
    for scenario, year_map in pct_map.items():
        for year, pct in year_map.items():
            col_name = f"{year} - Extreme Windspeed 100 year Return Period (km/h)"
            if scenario == "RCP8.5":
                col_name += " - RCP8.5"
            outputs[col_name] = _round_half_up(base * (1 + pct))
    return outputs


def generate_tropical_cyclone_analysis(facilty_csv_path: str):
    """
    Match facilities to nearest CLIMADA tropical cyclone points and emit
    current and future 100-year return period winds (2030/2040/2050 for RCP4.5/8.5).
    """
    output_csv_files: List[str] = []

    try:
        primary_known = os.path.join(
            settings.BASE_DIR, "tropical_cyclone_analysis", "static", "input_files", "climada_output_01.csv"
        )
        fallback_known = os.path.join(
            settings.BASE_DIR, "climate_hazards_analysis", "static", "input_files", "climada_output_01.csv"
        )

        if os.path.exists(primary_known):
            df_known = _load_csv(primary_known)
            logger.info("Loaded CLIMADA data from primary path")
        elif os.path.exists(fallback_known):
            df_known = _load_csv(fallback_known)
            logger.info("Loaded CLIMADA data from fallback path")
        else:
            raise FileNotFoundError("climada_output_01.csv not found in expected locations.")

        # Map known columns
        column_map = {
            "geometry": "geometry",
            "100": "min_i_1_100",
            "1-min MSW 100 yr RP": "min_i_1_100",
        }
        df_known = df_known.rename(columns={k: v for k, v in column_map.items() if k in df_known.columns})

        if "geometry" not in df_known.columns or "min_i_1_100" not in df_known.columns:
            raise ValueError("CLIMADA file must contain geometry and 100-year RP columns.")

        df_known["geometry"] = _parse_geometry(df_known["geometry"])

        df_target = _load_csv(facilty_csv_path)
        df_target, facility_col = _standardize_lat_long(df_target)

        # Keep facility identifier as 'Facility'
        if facility_col != "Facility":
            df_target.rename(columns={facility_col: "Facility"}, inplace=True)

        df_target["geometry"] = df_target.apply(lambda row: (row["Long"], row["Lat"]), axis=1)

        def find_nearest(target_point):
            df_known["distance"] = df_known["geometry"].apply(lambda x: distance.euclidean(target_point, x))
            nearest_row = df_known.loc[df_known["distance"].idxmin()]
            return nearest_row.drop(labels=["geometry", "distance"])

        df_nearest = df_target["geometry"].apply(find_nearest).apply(pd.Series)
        df_nearest = df_nearest.drop(columns=["distance"], errors="ignore")

        df_result = df_target.drop(columns=["geometry"]).join(df_nearest)

        # Current 100-year RP
        df_result["Extreme Windspeed 100 year Return Period (km/h)"] = _round_half_up(
            pd.to_numeric(df_result.get("min_i_1_100", pd.NA), errors="coerce")
        )

        # Future horizons
        future_cols = _apply_percent_changes(
            pd.to_numeric(df_result.get("min_i_1_100", pd.NA), errors="coerce"), PERCENT_CHANGES
        )
        for col, series in future_cols.items():
            df_result[col] = series

        # Final columns
        ordered_cols = ["Facility", "Lat", "Long", "Extreme Windspeed 100 year Return Period (km/h)"] + [
            "2030 - Extreme Windspeed 100 year Return Period (km/h)",
            "2040 - Extreme Windspeed 100 year Return Period (km/h)",
            "2050 - Extreme Windspeed 100 year Return Period (km/h)",
            "2030 - Extreme Windspeed 100 year Return Period (km/h) - RCP8.5",
            "2040 - Extreme Windspeed 100 year Return Period (km/h) - RCP8.5",
            "2050 - Extreme Windspeed 100 year Return Period (km/h) - RCP8.5",
        ]
        for col in ordered_cols:
            if col not in df_result.columns:
                df_result[col] = pd.NA

        df_output = df_result[ordered_cols]

        output_csv = os.path.join(
            settings.BASE_DIR,
            "tropical_cyclone_analysis",
            "static",
            "input_files",
            "exposure_results_01.csv",
        )
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        df_output.to_csv(output_csv, index=False)
        output_csv_files.append(output_csv)
        logger.info("Tropical cyclone analysis completed and saved.")

    except Exception as e:
        logger.exception(f"Error in tropical cyclone analysis: {e}")
        output_dir = os.path.join(settings.BASE_DIR, "tropical_cyclone_analysis", "static", "input_files")
        os.makedirs(output_dir, exist_ok=True)
        output_csv = os.path.join(output_dir, "exposure_results_01.csv")
        placeholder = pd.DataFrame(
            {
                "Facility": ["Placeholder due to error"],
                "Lat": [0],
                "Long": [0],
                "Extreme Windspeed 100 year Return Period (km/h)": ["N/A"],
                "2030 - Extreme Windspeed 100 year Return Period (km/h)": ["N/A"],
                "2040 - Extreme Windspeed 100 year Return Period (km/h)": ["N/A"],
                "2050 - Extreme Windspeed 100 year Return Period (km/h)": ["N/A"],
                "2030 - Extreme Windspeed 100 year Return Period (km/h) - RCP8.5": ["N/A"],
                "2040 - Extreme Windspeed 100 year Return Period (km/h) - RCP8.5": ["N/A"],
                "2050 - Extreme Windspeed 100 year Return Period (km/h) - RCP8.5": ["N/A"],
            }
        )
        placeholder.to_csv(output_csv, index=False)
        output_csv_files.append(output_csv)

    return {"combined_csv_paths": output_csv_files}
