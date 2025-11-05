# Coordinate Validation Error Debug Report

## Problem Summary

Users uploading shapefiles (.zip, .shp) or geopackages (.gpkg) were encountering the following error when generating asset exposure:

```
Error in generate_climate_hazards_analysis: No valid facility locations after processing coordinates.
ValueError: No valid facility locations after processing coordinates.
Climate analysis failed: No valid facility locations after processing coordinates.
Unified CSV processing failed: Climate analysis failed: No valid facility locations after processing coordinates.
```

## Root Cause Analysis

The error was occurring in the `standardize_facility_dataframe()` function when called with `strict_mode=True` from the climate analysis module. The function was failing because:

1. **Invalid coordinate extraction**: Some shapefiles contained invalid geometries that resulted in NaN centroids
2. **Overly strict validation**: The coordinate validation was dropping all rows when coordinates were invalid
3. **Lack of debugging information**: No visibility into what was happening at each step of the pipeline

## Solution Implemented

### 1. Enhanced Shapefile Coordinate Processing (`views.py` lines 152-204)

**Before**: Simple centroid calculation without error handling
```python
gdf = gdf.to_crs('EPSG:4326')
gdf['Lat'] = gdf.geometry.centroid.y
gdf['Long'] = gdf.geometry.centroid.x
```

**After**: Robust coordinate extraction with multiple fallbacks
```python
# Check for empty/invalid geometries before calculating centroids
invalid_geoms = gdf.geometry.isna() | gdf.geometry.is_empty
invalid_count = invalid_geoms.sum()
if invalid_count > 0:
    logger.warning(f"[SHAPEFILE_DEBUG] Found {invalid_count} empty/invalid geometries")
    gdf = gdf[~invalid_geoms]

# Calculate centroids with error handling
try:
    gdf['Lat'] = gdf.geometry.centroid.y
    gdf['Long'] = gdf.geometry.centroid.x
except Exception as e:
    # Fallback: use representative point instead of centroid
    try:
        gdf['Lat'] = gdf.geometry.representative_point().y
        gdf['Long'] = gdf.geometry.representative_point().x
    except Exception as e2:
        raise ValueError(f"Failed to extract coordinates from shapefile: {e2}")

# Filter out rows with NaN coordinates
valid_coords = ~(gdf['Lat'].isna() | gdf['Long'].isna())
nan_count = (~valid_coords).sum()
if nan_count > 0:
    logger.warning(f"[SHAPEFILE_DEBUG] Filtering out {nan_count} rows with NaN coordinates")
    gdf = gdf[valid_coords]
```

### 2. Improved Coordinate Validation (`common_utils.py` lines 145-173)

**Before**: Only Philippines bounds validation with strict filtering
```python
bounds_mask = (df[lat_col].between(4, 21)) & (df[lon_col].between(116, 127))
if strict_mode:
    df = df[bounds_mask]
```

**After**: World bounds validation with permissive non-strict mode
```python
# Check for reasonable coordinate ranges (world bounds)
valid_lat_mask = df[lat_col].between(-90, 90)
valid_lon_mask = df[lon_col].between(-180, 180)
valid_coords_mask = valid_lat_mask & valid_lon_mask

out_of_bounds_count = (~valid_coords_mask).sum()
if out_of_bounds_count > 0:
    logger.warning(f"Found {out_of_bounds_count} facilities with coordinates outside world bounds")
    if strict_mode:
        logger.info(f"Dropping {out_of_bounds_count} out-of-bounds facilities in strict mode")
        df = df[valid_coords_mask]
    else:
        logger.warning(f"Keeping out-of-bounds facilities in non-strict mode")
```

### 3. Enhanced Unified CSV Processing (`views.py` lines 1111-1132)

**Before**: Direct coordinate addition without validation
```python
expanded_rows.append({
    'Facility': facility_name,
    'Lat': lat,
    'Long': lng,
    'Archetype': archetype
})
```

**After**: Coordinate validation and type conversion
```python
# Validate coordinates before adding to expanded rows
if lat is not None and lng is not None and str(lat).strip() != '' and str(lng).strip() != '':
    try:
        # Convert to float to ensure they're numeric
        lat_float = float(lat)
        lng_float = float(lng)

        # Check for reasonable coordinate ranges
        if -90 <= lat_float <= 90 and -180 <= lng_float <= 180:
            expanded_rows.append({
                'Facility': facility_name,
                'Lat': lat_float,
                'Long': lng_float,
                'Archetype': archetype
            })
        else:
            logger.warning(f"[UNIFIED_CSV_DEBUG] Skipping facility {facility_name} with out-of-bounds coordinates")
    except (ValueError, TypeError) as e:
        logger.warning(f"[UNIFIED_CSV_DEBUG] Skipping facility {facility_name} with invalid coordinates")
```

### 4. Comprehensive Debug Logging

Added detailed logging throughout the pipeline:

- **Shapefile Processing**: `[SHAPEFILE_DEBUG]` tags for geometry and coordinate extraction
- **Standardization**: `[COORD_DEBUG]` tags for coordinate validation steps
- **Unified CSV**: `[UNIFIED_CSV_DEBUG]` tags for CSV creation and coordinate handling
- **Climate Analysis**: `[CLIMATE_ANALYSIS_DEBUG]` tags for data reading and processing

## Files Modified

1. **`climate_hazards_analysis/utils/common_utils.py`**
   - Enhanced `standardize_facility_dataframe()` function with better coordinate validation
   - Added comprehensive debug logging
   - Implemented world bounds validation instead of Philippines-only bounds

2. **`climate_hazards_analysis_v2/views.py`**
   - Improved shapefile coordinate extraction with error handling
   - Added robust geometry validation
   - Enhanced unified CSV creation with coordinate validation
   - Added detailed debug logging throughout the pipeline

3. **`climate_hazards_analysis/utils/climate_hazards_analysis.py`**
   - Added debug logging for CSV reading and standardization process

## Key Improvements

### Error Handling
- Multiple fallback mechanisms for coordinate extraction
- Graceful handling of invalid geometries
- Better error messages with specific details

### Data Validation
- World bounds validation (-90 to 90 for latitude, -180 to 180 for longitude)
- Type conversion and NaN filtering
- Permissive vs strict mode handling

### Debugging Capabilities
- Comprehensive logging at every step of the pipeline
- Detailed coordinate value tracking
- Clear error messages with specific failure points

## Testing Recommendations

1. **Test with various shapefile formats**: Different coordinate systems, geometries, and data quality
2. **Test edge cases**: Invalid geometries, missing coordinates, out-of-bounds coordinates
3. **Monitor logs**: Check for `[SHAPEFILE_DEBUG]`, `[COORD_DEBUG]`, and `[UNIFIED_CSV_DEBUG]` messages
4. **Verify output**: Ensure coordinates are properly preserved through the entire pipeline

## Expected Outcome

The implemented solution should:
- ✅ Handle invalid geometries gracefully
- ✅ Provide clear debugging information when issues occur
- ✅ Preserve valid coordinates from shapefiles
- ✅ Support global coordinate ranges (not just Philippines)
- ✅ Give users actionable error messages
- ✅ Successfully process shapefiles that previously failed

This comprehensive fix addresses the root cause of coordinate validation failures while providing robust error handling and detailed debugging capabilities.