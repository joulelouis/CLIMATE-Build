# %%
import geopandas as gpd
import pandas as pd
import numpy as np
import shapely as shp

import rasterio as rio
import re
import rasterstats as rstat

import matplotlib.pyplot as plt

from pathlib import Path

# %%
# Base directories (unused legacy paths removed)
WORK_DIR = Path().resolve().parent.parent

# %%
# HEAT_DIR = DATA_DIR / "Temp_CMIP6_BL2016-2020_Outputs"
# HEAT_DIR = DATA_DIR / "Temp_CMIP6_BL1981-2010_Outputs_10yrTimeframes"
# HEAT_DIR = DATA_DIR / "Temp_CMIP6_BL1981-2010_Outputs"
# HEAT_DIR = HAZARD_DIR / "EXTREME_HEAT"
HEAT_DIR = Path(__file__).resolve().parent / "input_files"
assert HEAT_DIR.exists(), f"File path does not exist: {HEAT_DIR}"

# %%
fps_daysover = list(HEAT_DIR.glob("PH_DaysOver3[0|3|5]degC_ANN_*_20[2-4][1|6]-20[2-5][0|5].tif"))
fps_daysover

# %%
# fp_asset = DATA_DIR / "PH_AssetsSMC_CleanedLatLon_20250306.xlsx"
# fp_asset = DATA_DIR / "PH_AssetsSMC_CleanedLatLon_20250217.xlsx"
# fp_asset = WORK_DIR.parent / "2_IONICS" / "1_DATA" / "PH_AssetsIonics_CleanedLatLon_20250326.xlsx"
# fp_asset = WORK_DIR.parent / "5_FDC" / "1_DATA" / "FDC_Polygons_288" / "FDC_Polygons_288.shp"
# fp_asset = Path("D:\\1_WORK\\1_SGV\\8_SMCGP_CRST\\1_DATA\\SMCGP Power Plants.kml")
# fp_asset = Path("D:\\1_WORK\\1_SGV\\5_FDC\\1_DATA\\FDC_4_Hospitality_Assets_LatLonArea.gpkg")
# fp_asset = Path("D:\\1_WORK\\1_SGV\\5_FDC\\1_DATA\\FDC Asset Polygons Unique LatLonArea.gpkg")
# fp_asset = Path("D:\\1_WORK\\1_SGV\\5_FDC\\1_DATA\\PH_AssetsPolygonsCompleteFDC_LatLonArea.parquet")
# fp_asset = ENGMT_DIR / "1_DATA" / "ASSETS" / "FDC New Assets Batch 1_20250910.gpkg"
# fp_asset = ENGMT_DIR / "1_DATA" / "ASSETS" / "FDC New Assets Batch 2.gpkg"
# fp_asset = ENGMT_DIR / "PH_PuregoldLocations_New.gpkg"
fp_asset = Path(__file__).resolve().parent / "sample_locs_v2.csv"

# Set outputs to heat/output_files
OUTPUT_DIR = Path(__file__).resolve().parent / "output_files"
OUTPUT_DIR.mkdir(exist_ok=True)

fp_output_parquet = OUTPUT_DIR / (fp_asset.stem + "_HeatExposure.parquet")
fp_output_xlsx = OUTPUT_DIR / (fp_asset.stem + "_HeatExposure.xlsx")
fp_output_csv = OUTPUT_DIR / (fp_asset.stem + "_HeatExposure.csv")
assert fp_asset.exists()

# %%
df_assets = pd.read_csv(
    fp_asset,
    # usecols="B:H"
)

df_assets.head()

# %%
# is_lotarea_missing = df_assets["lot_area"].isna()
# df_assets.loc[is_lotarea_missing, "lot_area"] = 1_000**2 # 1 square kilometer (pixel resolution of heat)
df_assets["lot_area"] = 1_000 ** 2

# %%
def clean_numerical_col(orig_value):
    if type(orig_value) == str:
        new_value = float(re.findall(r"[\d\.]+", orig_value.replace(",", ""))[0])
        return new_value
    else:
        return orig_value

df_assets["lot_area"] = df_assets["lot_area"].apply(clean_numerical_col).astype(float)
# df_assets["lot_area"] = df_assets["lot_area"].str.replace(",", "").str.extract(r"([\d\.]+)").astype(float)
if len(df_assets) >= 5:
    df_assets.sample(5, replace=False)

# %%
gs_pts = gpd.points_from_xy(
    # x=df_assets["longitude"],
    # y=df_assets["latitude"],
    x=df_assets["Long"],
    y=df_assets["Lat"],
    crs="EPSG:4326"
).to_crs("EPSG:32651")

gdf_assets = gpd.GeoDataFrame(
    data=df_assets,
    geometry=gs_pts,
    crs="EPSG:32651"
)

gdf_assets.head()

# %%
gdf_assets["geometry"] = gdf_assets["geometry"].buffer(
    np.sqrt(gdf_assets["lot_area"]) / 2,
    cap_style="square",
    join_style="mitre"
)

# %%
# gdf_assets[gdf_assets["geometry"].is_empty]

# %%
# [fp[2:4] + fp[-2:] for fp in list(set([fp.stem[-9:] for fp in fps_daysover]))]

# %%
# gdf_assets = gpd.read_parquet(fp_asset)[["Facility Name", "geometry"]]
# gdf_assets = gpd.read_file(fp_asset, engine="pyogrio")[["name", "ADM1_EN","ADM2_EN", "ADM3_EN", "ADM4_EN", "geometry"]]
# gdf_assets = gpd.read_file(fp_asset, engine="pyogrio")
# gdf_assets.geometry = gdf_assets.geometry.make_valid(method="structure")
# gdf_assets.geometry = gpd.GeoSeries([shp.MultiPolygon([geom]) if geom.geom_type == "Polygon" else geom for geom in gdf_assets.geometry])
gdf_assets.head()

# %%
poles = gdf_assets.geometry.to_crs(epsg=32651).centroid.to_crs(epsg=4326)

gdf_assets["longitude"] = poles.x
gdf_assets["latitude"] = poles.y
gdf_assets["area_sqm"] = gdf_assets.to_crs(epsg=32651).area.round(2)

# gdf_assets["longitude"] = gdf_assets.geometry.x
# gdf_assets["latitude"] = gdf_assets.geometry.y

# gdf_assets.head()

# gdf_assets_points = gpd.GeoDataFrame(
#     data=gdf_assets[["Name"]],
#     geometry=poles_of_inaccessibility,
#     crs=gdf_assets.crs
# )

# gdf_assets_points

# %%
temp_cols = []

# for temp in [30, 33, 35]:
for temp in [35]:
    for timeframe in list(set([fp.stem[-9:] for fp in fps_daysover])):
        timeframe = timeframe[2:4] + timeframe[-2:]
        if timeframe == "2125":
            scenario = "base"
            temp_cols.append(f"n>{temp}degC_{scenario}_{timeframe}")
        else:
            for scenario in ["ssp245", "ssp585"]:
                temp_cols.append(f"n>{temp}degC_{scenario}_{timeframe}")

temp_cols = sorted(temp_cols)
     
temp_cols

# %%
# for col, fp_raster in zip(temp_cols, fps_daysover):
#     out_geojson = rstat.point_query(
#         gdf_assets.set_geometry("pole_inacc")[["Name", "pole_inacc"]],
#         fp_raster,
#         geojson_out=True,
#         interpolate="nearest"
#     )
#     print(out_geojson)

# %%
# for geom_col in ["geometry", "pole_inacc"]:
#     gdf_assets = gdf_assets.set_geometry(geom_col)
    
#     for col, fp_raster in zip(temp_cols, fps_daysover):
#         rstat_args = (gdf_assets, fp_raster)
        
#         rstat_kwargs = {
#             # "vectors": gdf_assets,
#             # "raster": fp_raster,
#             "stats": "percentile_75",
#             # "nodata": 255
#             "all_touched": True,
#             "geojson_out": True
#         }

#         rstat_func = rstat.zonal_stats
#         raster_value = rstat_kwargs["stats"]

#         if geom_col == "pole_inacc":
#             rstat_func = rstat.point_query
#             col = col + "_pole"
#             raster_value = "value"
#             del rstat_kwargs["stats"]
#             del rstat_kwargs["all_touched"]
#             rstat_kwargs["interpolate"] = "nearest"
        

#         out_geojson = rstat_func(*rstat_args, **rstat_kwargs)
#         out_idxs = [int(feat["id"]) for feat in out_geojson]
#         out_stat = [feat["properties"][raster_value] for feat in out_geojson]

#         gdf_assets[col] = pd.Series(data=out_stat, index=out_idxs)
    
#     heat_cols = temp_cols
#     if geom_col == "pole_inacc":
#         heat_cols = [col + "_pole" for col in heat_cols]
    
#     for col in heat_cols[1:]:
#         gdf_assets[col] = gdf_assets[[heat_cols[0], col]].apply(np.max, axis=1)
        
# gdf_assets

# %%
# def pixels_to_points(fp_raster, raster_col="value"):
#     """
#     Converts raster pixels to a GeoDataFrame of points.
#     """
#     src = rio.open(fp_raster)
#     height, width = src.shape
#     cols, rows = np.meshgrid(np.arange(width), np.arange(height))
#     x, y = rio.transform.xy(src.transform, rows, cols)
    
#     x = np.array(x).flatten()
#     y = np.array(y).flatten()
#     z = src.read(1).flatten()

#     points = gpd.points_from_xy(x, y, crs=src.crs)
#     return gpd.GeoDataFrame(data={raster_col: z}, geometry=points)

# %%
# id_cols = ["Name", "geometry", "pole_inacc"]

# for col, fp_raster in zip(temp_cols, fps_daysover):
#     col = col + "_nearest"
#     gdf_raster_points = pixels_to_points(fp_raster, raster_col=col)
#     gdf_raster_points = gdf_raster_points[~gdf_raster_points[col].isna()]

#     gdf_assets_raw = gdf_assets.set_geometry("pole_inacc").sjoin_nearest(gdf_raster_points).drop(columns=["index_right"])
#     gdf_assets = gpd.GeoDataFrame(gdf_assets_raw.groupby(id_cols).mean().reset_index())

# heat_cols = [col + "_nearest" for col in temp_cols]

# for col in heat_cols[1:]:
#     gdf_assets[col] = gdf_assets[[heat_cols[0], col]].apply(np.max, axis=1)

# gdf_assets

# %%
# gdf_assets_melt = gdf_assets.melt(
#     id_vars=id_cols,
#     value_vars=gdf_assets.drop(columns=id_cols).columns,
#     var_name="variable",
#     value_name="nhot_days"
# )

# gdf_assets_melt[["scenario", "timeframe"]] = gdf_assets_melt["variable"].str.removeprefix("n>35degC_").str.split("_", expand=True, n=1)
# gdf_assets_melt["sample_method"] = gdf_assets_melt["timeframe"].apply(lambda timeframe: timeframe.split("_")[-1] if "_" in timeframe else "polygon")
# gdf_assets_melt["timeframe"] = gdf_assets_melt["timeframe"].str.split("_").apply(lambda timeframe: timeframe[0])

# gdf_assets_melt = gdf_assets_melt.drop(columns=["variable"])

# gdf_assets_melt.head()

# %%
# gdf_assets_melt.tail()

# %%
# gdf_assets_melt["sample_method"].unique()

# %%
# import seaborn as sns
# import matplotlib.pyplot as plt

# fig, ax = plt.subplots(figsize=(9,6))

# sns.barplot(
#     data=gdf_assets_melt[(gdf_assets_melt["scenario"] == "ssp585") & (gdf_assets_melt["timeframe"] == "4655")],
#     x="Name",
#     y="nhot_days",
#     hue="sample_method",
#     ax=ax
# )

# plt.tick_params(labelsize="x-small", rotation=90)

# %%
# zonal_stat = "max"
zonal_stat = "percentile_75"

for col, fp in zip(temp_cols, fps_daysover):
    out_geojson = rstat.zonal_stats(
        gdf_assets.to_crs("EPSG:4326"),
        fp,
        stats=zonal_stat,
        all_touched=True,
        geojson_out=True
    )

    # gdf_assets[col] = rstat.point_query(
    #     gdf_assets.to_crs(epsg=4326),
    #     fp,
        # geojson_out=True
    # )

    out_idxs = [int(feat["id"]) for feat in out_geojson]
    out_stat = [feat["properties"][zonal_stat] for feat in out_geojson]
    # out_stat = [feat["properties"]["value"] for feat in out_geojson]

    gdf_assets[col] = pd.Series(data=out_stat, index=out_idxs)

gdf_assets[gdf_assets["n>35degC_base_2125"].isna()]

# %%
is_temp_missing = (gdf_assets["n>35degC_base_2125"].isna())

if len(gdf_assets[is_temp_missing]) > 0:
    for col, fp in zip(temp_cols, fps_daysover):
        # out_geojson = rstat.zonal_stats(
        #     gdf_assets.loc[is_temp_missing].to_crs(epsg="32651").buffer(
        #         1_000,
        #         cap_style="square",
        #         join_style="mitre"
        #     ).to_crs("EPSG:4326"),
        #     fp,
        #     stats=zonal_stat,
        #     all_touched=True,
        #     geojson_out=True
        # )

        out_list = rstat.zonal_stats(
            gdf_assets.loc[is_temp_missing].to_crs(epsg="32651").buffer(
                1_000,
                cap_style="square",
                join_style="mitre"
            ).to_crs("EPSG:4326"),
            fp,
            stats=zonal_stat,
            all_touched=True,
            # geojson_out=True
        )

        gdf_assets.loc[is_temp_missing, col] = [feat["max"] for feat in out_list]

        # out_idxs = [int(feat["id"]) for feat in out_geojson]
        # out_stat = [feat["properties"][zonal_stat] for feat in out_geojson]

        # gdf_assets.loc[is_temp_missing, col] = pd.Series(data=out_stat, index=out_idxs)

gdf_assets[is_temp_missing]

# %%
for col in temp_cols[1:]:
    is_lower_vs_baseline = gdf_assets[col] < gdf_assets["n>35degC_base_2125"]
    gdf_assets.loc[is_lower_vs_baseline, col] = gdf_assets.loc[is_lower_vs_baseline, "n>35degC_base_2125"]

gdf_assets.head()

# %%
# is_west_palm_palawan = gdf_assets["Facility Name"] == "West Palm Palawan"

# index_nearest = gdf_assets.geometry.sindex.nearest(gdf_assets.loc[is_west_palm_palawan, "geometry"], exclusive=True)[1][0]

# is_nearest = gdf_assets.index == index_nearest

# gdf_assets.loc[is_west_palm_palawan, temp_cols] = gdf_assets.loc[is_nearest, temp_cols].values

# gdf_assets.loc[is_west_palm_palawan]

# %%
# for col in temp_cols:
#     gdf_assets[col] = np.ceil(gdf_assets[col]).astype(int)

# gdf_assets.head()

# %%
# for suffix in ["", "_pole", "_nearest"]:
for col in temp_cols:
        # col = col + suffix
    gdf_assets[col] = gdf_assets[col].round(1)
    gdf_assets[col] = np.ceil(gdf_assets[col])

# gdf_assets.loc[gdf_assets["lot_area"] == 1_000**2, "lot_area"] = np.nan

# gdf_assets.to_parquet(DATA_DIR / "PH_AssetsSMC_HeatExposure_AllScenarios_AllTimeframes.parquet")
# gdf_assets.to_parquet(WORK_DIR.parent / "2_IONICS" / "1_DATA" / "PH_AssetsIonics_HeatExposure_AllScenarios_AllTimeframes.parquet")
# gdf_assets.to_parquet(fp_asset.parent.parent / "PH_AssetsPolygonsFDC_HeatExposure_AllScenarios_AllTimeframes.parquet")
try:
    gdf_assets.to_parquet(fp_output_parquet)
except ImportError:
    print("pyarrow not installed; skipping parquet export.")

# %%
df_assets = gdf_assets.drop(columns=["geometry"])

# df_assets.to_excel(DATA_DIR / "PH_AssetsSMC_HeatExposure_AllScenarios_AllTimeframes.xlsx")
# df_assets.to_excel(WORK_DIR.parent / "2_IONICS" / "1_DATA" / "PH_AssetsIonics_HeatExposure_AllScenarios_AllTimeframes.xlsx")
# df_assets.to_excel(fp_asset.parent.parent / "PH_AssetsPolygonsFDC_HeatExposure_AllScenarios_AllTimeframes.xlsx")
df_assets.to_excel(fp_output_xlsx)
df_assets.to_csv(fp_output_csv, index=False)

# %%
fig, axes = plt.subplots(ncols=3, figsize=(16, 6), sharey=True)
cols_35degC = [col for col in temp_cols if "35degC" in col]

for ax, timeframe in zip(axes.ravel(), ["2630", "3140", "4150"]):
    cols_to_plot = ["n>35degC_base_2125"] + [col for col in cols_35degC if timeframe in col]
    gdf_assets[cols_to_plot].plot(kind="kde", bw_method=0.4, xlim=(0, 200), ax=ax)

# %%


