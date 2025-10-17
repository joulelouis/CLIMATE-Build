# Climate Hazards Analysis - Percentile Methods Documentation

## Overview

This document outlines the statistical percentile methods used across all climate hazards analyses in the CLIMATE-Build system. All analyses use consistent statistical methods regardless of input geometry type (CSV points, shapefile points, or shapefile polygons).

## Percentile Methods by Hazard Type

### 75th Percentile Analyses (Standard)
**Statistical Method**: `percentile_75` (75th percentile)

1. **Flood Exposure Analysis**
   - File: `flood_exposure_analysis/utils/flood_exposure_analysis.py`
   - Uses zonal statistics with buffered polygon areas
   - Classification: 0.1-0.5m, 0.5-1.5m, >1.5m

2. **Heat Exposure Analysis**
   - File: `heat_exposure_analysis/utils/heat_exposure_analysis.py`
   - Counts days over temperature thresholds (30°C, 33°C, 35°C)
   - Applies to both historical and future projections

3. **Storm Surge Analysis**
   - File: `climate_hazards_analysis/utils/climate_hazards_analysis.py`
   - Zonal statistics on storm surge raster data
   - Buffered square geometries around facility points

### 90th Percentile Analysis
**Statistical Method**: `percentile_90` (90th percentile)

1. **Rainfall-Induced Landslide Analysis**
   - File: `climate_hazards_analysis/utils/rainfall_induced_landslide_future_analysis.py`
   - Applied to both moderate (RCP26) and worst (RCP85) case scenarios
   - Only hazard analysis using 90th percentile

### No Percentile Analyses
**Statistical Method**: Direct calculations without percentile statistics

1. **Water Stress Exposure Analysis**
   - File: `water_stress/utils/water_stress_analysis.py`
   - Uses basin-wide averages with hydrobasin intersection
   - No percentile calculations involved

2. **Sea Level Rise Analysis**
   - File: `sea_level_rise_analysis/utils/slr_analysis.py`
   - Binary intersection with Storm Surge Advisory (SSA) zones
   - Provides projections for 2030, 2040, 2050 scenarios

3. **Tropical Cyclone Analysis**
   - File: `tropical_cyclone_analysis/utils/tropical_cyclone_analysis.py`
   - Distance-based interpolation from cyclone data points
   - Windspeed estimates for various return periods

## Input Geometry Handling

### Standardization Process
All input types are standardized to centroid coordinates before analysis:

**File**: `climate_hazards_analysis_v2/views.py` (lines 85-88)
```python
gdf = gdf.to_crs('EPSG:4326')
gdf['Lat'] = gdf.geometry.centroid.y
gdf['Long'] = gdf.geometry.centroid.x
df = pd.DataFrame(gdf.drop(columns='geometry'))
```

### Supported Input Types
- **CSV files**: Used directly with lat/long coordinate columns
- **Excel files**: Used directly with lat/long coordinate columns
- **Shapefile/ZIP files**:
  - Point, MultiPoint, Polygon, MultiPolygon geometries
  - All converted to centroid coordinates
  - Attribute data extracted as regular columns

### Critical Point
**No conditional logic exists** that applies different statistical methods based on input geometry type. All analyses use the same percentile method regardless of whether the input is a CSV point or shapefile polygon.

## Summary Table

| Hazard Analysis | Percentile Used | Input Type Handling | Statistical Method |
|-----------------|-----------------|-------------------|-------------------|
| Flood Exposure | 75th percentile | Uniform (centroids) | Zonal statistics |
| Heat Exposure | 75th percentile | Uniform (centroids) | Zonal statistics |
| Storm Surge | 75th percentile | Uniform (centroids) | Zonal statistics |
| Landslide Analysis | 90th percentile | Uniform (centroids) | Zonal statistics |
| Water Stress | None | Basin intersection | Direct averaging |
| Sea Level Rise | None | Binary intersection | Direct calculation |
| Tropical Cyclone | None | Distance-based | Direct interpolation |

---

**Document Version**: 1.0
**Date**: October 16, 2025
**System**: CLIMATE-Build Climate Hazards Analysis