# %%
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, box
import matplotlib.pyplot as plt

# %%
# Step 1: Load the shapefile of hydrobasins
hydrobasins = gpd.read_file("ws/input_files/hybas_lake_au_lev06_v1c.shp")
# Standardize pfaf column naming just in case
if "pfaf_id" in hydrobasins.columns and "PFAF_ID" not in hydrobasins.columns:
    hydrobasins = hydrobasins.rename(columns={"pfaf_id": "PFAF_ID"})

# Step 2: Load the aqueduct water stress data
ws_current = pd.read_csv("ws/input_files/Aqueduct40_baseline_annual_y2023m07d05.csv")
ws_future = pd.read_csv("ws/input_files/Aqueduct40_future_annual_y2023m07d05.csv")
# Standardize pfaf column naming for both tables
if "pfaf_id" in ws_current.columns and "PFAF_ID" not in ws_current.columns:
    ws_current = ws_current.rename(columns={"pfaf_id": "PFAF_ID"})
if "pfaf_id" in ws_future.columns and "PFAF_ID" not in ws_future.columns:
    ws_future = ws_future.rename(columns={"pfaf_id": "PFAF_ID"})

# %%
# Step 3: Merge the data based on the PFAF_ID
merged_ws_current = hydrobasins.merge(ws_current, on='PFAF_ID')
merged_ws_future = hydrobasins.merge(ws_future, on='PFAF_ID')

# %%
# Step 4: Save the merged data to a new shapefile
output_shapefile_path1 = 'ws/output_files/Aqueduct40_baseline_annual_y2023m07d05.shp'
merged_ws_current.to_file(output_shapefile_path1)

output_shapefile_path2 = 'ws/output_files/Aqueduct40_future_annual_y2023m07d05.shp'

merged_ws_future = merged_ws_future.rename(columns={
    'bau30_ws_x_r': 'bau30_ws',
    'bau50_ws_x_r': 'bau50_ws',
    'pes30_ws_x_r': 'pes30_ws',
    'pes50_ws_x_r': 'pes50_ws',
    'location_name': 'loc_name'
})

merged_ws_future.to_file(output_shapefile_path2)

# %%
# Step 5: Load the merged shapefile
gdf1 = gpd.read_file(output_shapefile_path1)
gdf2 = gpd.read_file(output_shapefile_path2)

# Step 6: Load the facility locations CSV
facility_csv_path = 'ws/sample_locs_v2.csv'
facility_locs = pd.read_csv(facility_csv_path)

# Step 7: Convert facility locations to GeoDataFrame
geometry = [Point(xy) for xy in zip(facility_locs['Long'], facility_locs['Lat'])]
facility_gdf = gpd.GeoDataFrame(facility_locs, geometry=geometry, crs=gdf1.crs)

facility_gdf

# %%
# Step 8: Create square buffers around each facility location
buffer_size = 0.0009  # degree, ~100 meters radius
facility_gdf['geometry'] = facility_gdf.geometry.apply(lambda x: box(x.x - buffer_size, x.y - buffer_size, x.x + buffer_size, x.y + buffer_size))

# Step 9: Filter the data to focus on the specified latitude and longitude bounds
min_lat, max_lat = 0, 20
min_lon, max_lon = 114, 130
gdf1 = gdf1.cx[min_lon:max_lon, min_lat:max_lat]
gdf2 = gdf2.cx[min_lon:max_lon, min_lat:max_lat]

# %%
# Step 10: Spatial join
facility_gdf = gpd.sjoin(facility_gdf, gdf1[['geometry', 'bws_raw']], how='left', predicate='intersects')
facility_gdf = facility_gdf.drop(columns=['index_right'], errors='ignore')

facility_gdf = gpd.sjoin(facility_gdf, gdf2[['geometry', 'bau30_ws', 'bau50_ws', 'pes30_ws', 'pes50_ws']], how='left', predicate='intersects')
facility_gdf = facility_gdf.drop_duplicates(subset='Site')
facility_gdf = facility_gdf.drop(columns=['index_right'], errors='ignore')
facility_gdf.head()

# %%
# Step 11: Assign water stress values
facility_locs['Baseline Water Stress (%)'] = (facility_gdf['bws_raw']* 100).round(1)
facility_locs['SSP3-7.0 (2030) Water Stress (%)'] = (facility_gdf['bau30_ws']* 100).round(1)
facility_locs['SSP3-7.0 (2050) Water Stress (%)'] = (facility_gdf['bau50_ws']* 100).round(1)
facility_locs['SSP5-8.5 (2030) Water Stress (%)'] = (facility_gdf['pes30_ws']* 100).round(1)
facility_locs['SSP5-8.5 (2050) Water Stress (%)'] = (facility_gdf['pes50_ws']* 100).round(1)

facility_locs.head()

# %%
# Step 12: Save the updated CSV with water stress categories and labels
output_csv_path = 'ws/output_files/sample_locs_ws.csv'
facility_locs.to_csv(output_csv_path, index=False)

print(f'Updated facility locations with water stress values saved to {output_csv_path}')

