import geopandas as gpd
import pandas as pd
import numpy as np
import rasterstats as rstat
from pathlib import Path

WORK_DIR = Path(__file__).resolve().parent
HAZARD_DIR = WORK_DIR / "static"

fp_asset = WORK_DIR / "input_files" / "Sample Polygons.shp"
assert fp_asset.exists()

fp_output = WORK_DIR / "output_files" / "flood_output_1.xlsx"
fp_output.parent.mkdir(parents=True, exist_ok=True)

# Load assets

gdf_assets = gpd.read_file(fp_asset, engine="pyogrio").to_crs(epsg="32651")

# Flood hazards

hazard_files = {
    "flood_100year": "PH_Flood_100year_UTM_ProjectNOAH_Unmasked.tif",
    "flood_100year_ssp245": "PH_Flood_100year_UTM_ProjectNOAH_Unmasked_COG_SSP245.tif",
    "flood_100year_ssp585": "PH_Flood_100year_UTM_ProjectNOAH_Unmasked_COG_SSP585.tif",
}

for col_name, filename in hazard_files.items():
    hazard_raster = HAZARD_DIR / filename
    gdf_assets[col_name] = pd.DataFrame(
        rstat.zonal_stats(gdf_assets, hazard_raster, stats="percentile_90", nodata=255)
    ).fillna(0).apply(np.ceil).astype("int")

fp_flood_mgb = HAZARD_DIR / "PH_FloodSusceptibility_MGB_UTM_Unmasked_COG.tif"

gdf_assets["flood_mgb"] = (
    pd.DataFrame(
        rstat.zonal_stats(gdf_assets, fp_flood_mgb, stats="percentile_90", nodata=255)
    )
    .fillna(0)
    .apply(np.ceil)
    .astype("int")
    .apply(np.clip, a_min=0, a_max=3)
)

gdf_assets["flood_adjusted"] = gdf_assets[["flood_100year", "flood_mgb"]].apply(
    lambda row: row["flood_mgb"] if row["flood_100year"] == 0 else row["flood_100year"],
    axis=1,
)

gdf_assets["flag:noah<mgb"] = (
    (gdf_assets["flood_100year"] < gdf_assets["flood_mgb"]) &
    (gdf_assets["flood_100year"] == 0)
)

# Convert to a DataFrame (drop geometry for Excel)

df_assets = gdf_assets.drop(columns=["geometry"], errors="ignore")

# Define mapping function

def map_flood_stormsurge(value):
    mapping = {
        0: "<0.1",
        1: "0.1-0.5",
        2: "0.5-1.5",
        3: ">1.5",
    }
    return mapping.get(value, "Unknown")

# Apply mapping

df_assets["flood_100year"] = df_assets["flood_100year"].map(map_flood_stormsurge)
df_assets["flood_100year_ssp245"] = df_assets["flood_100year_ssp245"].map(
    map_flood_stormsurge
)
df_assets["flood_100year_ssp585"] = df_assets["flood_100year_ssp585"].map(
    map_flood_stormsurge
)
df_assets["flood_mgb"] = df_assets["flood_mgb"].map(map_flood_stormsurge)

adjusted_flood_cols = [col for col in df_assets.columns if "adjusted" in col]
for col in adjusted_flood_cols:
    df_assets[col] = df_assets[col].map(map_flood_stormsurge)

# Save the updated DataFrame

df_assets.to_excel(fp_output, index=False)
print(f"Updated data saved to {fp_output}")
