#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import pandas as pd
import numpy as np
from shapely.wkt import loads
from shapely.geometry import Point
from scipy.spatial import distance


# In[ ]:


# Load known points CSV
known_csv = "tc/input_files/tokyo_1min_latest.csv"  # Change to actual file path
df_known = pd.read_csv(known_csv)

# Load target points CSV (prefer input_files, fallback to tc/)
target_csv = "tc/input_files/sample_locs_v2.csv"  # Change to actual file path
try:
    df_target = pd.read_csv(target_csv)
except FileNotFoundError:
    df_target = pd.read_csv("tc/sample_locs_v2.csv")


# In[ ]:


# Ensure required columns exist (support common variants)
lat_candidates = ["Latitude", "Lat", "latitude", "lat"]
lon_candidates = ["Longitude", "Long", "longitude", "long", "Lon", "lon"]
lat_col = next((c for c in lat_candidates if c in df_target.columns), None)
lon_col = next((c for c in lon_candidates if c in df_target.columns), None)
if not lat_col or not lon_col:
    raise ValueError("Target CSV must contain latitude/longitude columns (e.g., 'Latitude'/'Longitude' or 'Lat'/'Long').")

# Standardize coordinate column names for downstream steps
df_target = df_target.rename(columns={lat_col: "Latitude", lon_col: "Longitude"})

# Optional name/SBU-like columns
name_col = next((c for c in ["Name", "Site", "Asset", "Facility", "location name"] if c in df_target.columns), None)
sbu_col = next((c for c in ["SBU", "Archetype"] if c in df_target.columns), None)

# Convert latitude & longitude to Point geometry
df_target["geometry"] = df_target.apply(lambda row: Point(row["Longitude"], row["Latitude"]), axis=1)

# Save and reload target file (optional, avoids potential formatting issues)
df_target.to_csv("tc/output_files/assets_coords.csv", index=False)
df_target = pd.read_csv("tc/output_files/assets_coords.csv")

# Parse WKT geometry in known points
df_known["geometry"] = df_known["geometry"].apply(lambda x: loads(x).coords[0])  # Convert WKT to (x, y)

# Convert target points to (x, y) tuples
df_target["geometry"] = df_target.apply(lambda row: (row["Longitude"], row["Latitude"]), axis=1)


# In[ ]:


# Function to find the nearest known point for a given target
def find_nearest(target_point):
    df_known["distance"] = df_known["geometry"].apply(lambda x: distance.euclidean(target_point, x))
    nearest_row = df_known.loc[df_known["distance"].idxmin()]
    return nearest_row.drop(["geometry", "distance"])  # Drop extra columns

# Apply function and **expand results into separate columns**
df_nearest = df_target["geometry"].apply(find_nearest).apply(pd.Series)
# Drop distance if it leaked in
df_nearest = df_nearest.drop(columns=["distance"], errors="ignore")
df_known = df_known.drop(columns=["distance"], errors="ignore")

# Merge nearest values back into target DataFrame
df_result = df_target.drop(columns=["geometry"]).join(df_nearest)

# Standardize identifier columns for output
if name_col and name_col != "Name":
    df_result["Name"] = df_result[name_col]
elif not name_col:
    df_result["Name"] = df_result.index.astype(str)
if sbu_col and sbu_col != "SBU":
    df_result["SBU"] = df_result[sbu_col]


# In[ ]:


# Hazard columns are whatever comes from the nearest lookup
hazard_columns = list(df_nearest.columns)
# List the column names you want to round
columns_to_round = hazard_columns
# Apply "round half up" while preserving NaNs
df_result[columns_to_round] = df_result[columns_to_round].apply(
    lambda col: np.floor(col + 0.5) if col.dtype.kind in 'fc' else col
).astype("Int64")


# In[ ]:


# Define percent changes for the 75th percentile future projections
percent_changes_75p = {
    "4.5": {"2025-2035": 0.0203, "2035-2045": 0.0279, "2045-2055": 0.0351},
    "8.5": {"2025-2035": 0.0237, "2035-2045": 0.0355, "2045-2055": 0.0493}
}

# Identify all RP columns from hazard set
rp_columns = hazard_columns
if not rp_columns:
    raise ValueError("No return-period hazard columns found!")

# Initialize result dataframe with identifiers
identifier_cols = ["Name"]
if "SBU" in df_result.columns:
    identifier_cols.append("SBU")
identifier_cols += ["Latitude", "Longitude"]
result_df = df_result[identifier_cols].copy()

# Process each RP column
for rp_col in rp_columns:
    # Add base/current values
    rp_label = rp_col.replace("1-min MSW ", "")  # e.g. "100 yr RP"
    base_col_name = f"{rp_label}_Current"
    result_df[base_col_name] = df_result[rp_col]

    # Loop through each scenario/year and apply percent changes
    for scenario, years in percent_changes_75p.items():
        for year, pct in years.items():
            col_name = f"{rp_label}_RCP{scenario}_{year}"
            adjusted_values = df_result[rp_col] * (1 + pct)

            # Round half up while keeping NaNs
            adjusted_values = adjusted_values.apply(
                lambda x: np.floor(x + 0.5) if pd.notnull(x) else pd.NA
            )
            result_df[col_name] = adjusted_values.astype("Int64")

# Save the compiled current climate and future climate exposure data to a single CSV
result_df.to_csv("tc/output_files/tc_exposure_results.csv", index=False)
print("Saved: Compiled current and 75th percentile future projections")

result_df
