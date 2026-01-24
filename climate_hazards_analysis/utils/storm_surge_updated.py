import geopandas as gpd
import pandas as pd
import numpy as np
import rasterstats as rstat
import rasterio
import zipfile
from pathlib import Path
from shapely.geometry import shape

WORK_DIR = Path(__file__).resolve().parent
HAZARD_DIR = WORK_DIR / "static"

def map_flood_stormsurge(value):
    mapping = {
        0: "<0.1",
        1: "0.1-0.5",
        2: "0.5-1.5",
        3: ">1.5",
    }
    return mapping.get(value, "Unknown")


def _zonal_max_to_categories(gdf_assets, raster_path):
    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
    gdf_assets_projected = gdf_assets.to_crs(raster_crs)

    vals = pd.DataFrame(
        rstat.zonal_stats(gdf_assets_projected, raster_path, stats="max", nodata=255)
    ).fillna(0).apply(np.ceil).astype("int")
    return vals["max"].map(map_flood_stormsurge)


def _load_geofile(path):
    if not path or not Path(path).exists():
        return None

    ext = Path(path).suffix.lower()
    if ext == ".zip":
        try:
            return gpd.read_file(path)
        except Exception:
            try:
                with zipfile.ZipFile(path, "r") as zip_ref:
                    members = zip_ref.namelist()
                shp_files = [m for m in members if m.lower().endswith(".shp")]
                if not shp_files:
                    return None
                return gpd.read_file(f"zip://{path}!{shp_files[0]}")
            except Exception:
                return None
    if ext in [".gpkg", ".shp"]:
        return gpd.read_file(path)

    return None


def _build_polygon_gdf(facility_geofile_path, facility_geojson_records):
    gdf = None
    if facility_geofile_path:
        try:
            gdf = _load_geofile(facility_geofile_path)
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
        for name_col in ["Name", "Site", "Asset", "asset", "facility"]:
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


def generate_storm_surge_analysis(
    df_fac,
    current_raster,
    future_raster,
    facility_geofile_path=None,
    facility_geojson_records=None,
):
    polygon_gdf = _build_polygon_gdf(facility_geofile_path, facility_geojson_records)
    if polygon_gdf is not None:
        df_out = polygon_gdf.drop(columns=["geometry"]).copy()
        df_out["Storm Surge Flood Depth (meters)"] = _zonal_max_to_categories(
            polygon_gdf, current_raster
        )
        df_out[
            "Storm Surge Flood Depth (meters) - Worst Case"
        ] = _zonal_max_to_categories(polygon_gdf, future_raster)
        polygon_keys = set(
            df_out["Facility"].astype(str).str.strip().str.lower().tolist()
        )
        df_points = df_fac.copy()
        df_points["Facility"] = df_points["Facility"].astype(str)
        df_points["Facility_key"] = df_points["Facility"].str.strip().str.lower()
        df_points = df_points[~df_points["Facility_key"].isin(polygon_keys)]

        if not df_points.empty:
            df_points["Lat"] = pd.to_numeric(df_points["Lat"], errors="coerce")
            df_points["Long"] = pd.to_numeric(df_points["Long"], errors="coerce")
            df_points = df_points.dropna(subset=["Lat", "Long"])

            if not df_points.empty:
                gdf_points = gpd.GeoDataFrame(
                    df_points,
                    geometry=gpd.points_from_xy(df_points["Long"], df_points["Lat"]),
                    crs="EPSG:4326",
                )

                df_points["Storm Surge Flood Depth (meters)"] = _zonal_max_to_categories(
                    gdf_points, current_raster
                )
                df_points["Storm Surge Flood Depth (meters) - Worst Case"] = _zonal_max_to_categories(
                    gdf_points, future_raster
                )

                df_out = pd.concat(
                    [df_out, df_points.drop(columns=["geometry", "Facility_key"], errors="ignore")],
                    ignore_index=True
                )

        return df_out

    df = df_fac.copy()
    df["Lat"] = pd.to_numeric(df["Lat"], errors="coerce")
    df["Long"] = pd.to_numeric(df["Long"], errors="coerce")
    df = df.dropna(subset=["Lat", "Long"])

    gdf_assets = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["Long"], df["Lat"]),
        crs="EPSG:4326",
    )

    df["Storm Surge Flood Depth (meters)"] = _zonal_max_to_categories(
        gdf_assets, current_raster
    )
    df["Storm Surge Flood Depth (meters) - Worst Case"] = _zonal_max_to_categories(
        gdf_assets, future_raster
    )

    return df.drop(columns=["geometry"], errors="ignore")


if __name__ == "__main__":
    fp_asset = (
        WORK_DIR
        / ".."
        / "static"
        / "output_files"
        / "Sample Polygons.zip"
    ).resolve()
    print("fp_asset =", fp_asset)
    print("Exists?", fp_asset.exists())
    assert fp_asset.exists()

    fp_output = WORK_DIR / "output_files" / "storm_surge_output.xlsx"
    fp_output.parent.mkdir(parents=True, exist_ok=True)

    gdf_assets = gpd.read_file(fp_asset, engine="pyogrio")

    # Normalize expected asset columns, falling back to available fields.
    required_cols = ["gid", "layer", "path", "name", "geometry"]
    alias_map = {
        "gid": ["fid", "id", "objectid"],
        "name": ["Name", "NAME", "asset_name"],
        "layer": ["Layer", "LAYER"],
        "path": ["Path", "PATH"],
    }

    for col in required_cols:
        if col in gdf_assets.columns:
            continue
        for alias in alias_map.get(col, []):
            if alias in gdf_assets.columns:
                gdf_assets = gdf_assets.rename(columns={alias: col})
                break
        else:
            if col != "geometry":
                gdf_assets[col] = pd.NA

    gdf_assets = gdf_assets[required_cols].to_crs(epsg="4326")

    hazard_types = ["StormSurge_Advisory4", "StormSurge_Advisory4_Future"]

    for hazard in hazard_types:
        hazard_raster = HAZARD_DIR / f"PH_{hazard}_UTM_ProjectNOAH_Unmasked.tif"
        if "Future" in hazard:
            hazard_raster = HAZARD_DIR / f"PH_{hazard}_UTM_ProjectNOAH-GIRI_Unmasked.tif"

        gdf_assets[hazard.lower()] = _zonal_max_to_categories(gdf_assets, hazard_raster)

    # Convert to a DataFrame (drop geometry for Excel)
    df_assets = gdf_assets.drop(columns=["geometry"], errors="ignore")

    # Save the updated DataFrame
    df_assets.to_excel(fp_output, index=False)

    print(f"Updated data saved to {fp_output}")
