# Granular Risk Analysis - Implementation Guide

## 📊 Overview

The **Point Sampling Grid** strategy has been implemented to provide finer resolution analysis for polygon-based assets. Instead of analyzing just a single centroid point, the system now generates a grid of sample points across the entire polygon area.

## ✅ What's Been Implemented

### 1. Core Module (`granular_analysis.py`)

Located at: `climate_hazards_analysis_v2/granular_analysis.py`

**Functions:**
- `generate_sample_grid()` - Creates regular grid of points inside polygon
- `query_hazard_for_points()` - Batch queries hazard raster for multiple points
- `aggregate_risk_statistics()` - Computes comprehensive statistics from sampled data
- `calculate_optimal_grid_spacing()` - Determines grid density based on polygon size

### 2. Backend Integration (`views.py`)

**File Upload Flow** (Lines 103-161):
- Automatically detects polygon geometries from shapefiles/GeoPackages
- Calculates polygon area
- Generates sample grid with adaptive spacing
- Stores grid metadata in session

**Manual Facility Addition** (Lines 261-293):
- Supports city boundaries from search feature
- Generates sample grid for drawn polygons
- Stores grid metadata with facility data

### 3. Frontend Display (`results.html`)

**Table Enhancement** (Lines 512-521):
- 📊 Icon button appears next to polygon assets
- Clicking opens modal with analysis details

**Modal Dialog** (Lines 628-730):
- Shows polygon area, grid spacing, sample point count
- Displays current status (grid generated, hazard query pending)
- Provides instructions for enabling full analysis

## 🎯 Current Status

### ✅ Completed
1. ✅ Grid generation algorithm
2. ✅ Adaptive grid spacing (5m - 1000m based on polygon size)
3. ✅ Integration with file upload workflow
4. ✅ Integration with city boundary search
5. ✅ User interface for viewing grid metadata
6. ✅ Batch hazard query function (ready to use)
7. ✅ Statistical aggregation function (ready to use)

### ⏳ Pending (Next Steps)
1. ⏳ **Hazard raster configuration** - Need to specify actual raster file paths
2. ⏳ **Enable hazard queries** - Uncomment code in `views.py` lines 133-148
3. ⏳ **Risk visualization** - Add charts/graphs to modal when data available

## 🚀 How to Enable Full Analysis

### Step 1: Prepare Hazard Raster Files

Ensure you have GeoTIFF raster files for your hazards:
```
climate_hazards_analysis/static/hazard_data/
├── flood_hazard.tif
├── heat_stress.tif
├── water_stress.tif
└── ... (other hazards)
```

### Step 2: Enable Hazard Queries

**In `views.py` around line 133-148:**

Uncomment this block:
```python
hazard_raster_path = os.path.join(
    settings.BASE_DIR,
    'climate_hazards_analysis/static/hazard_data/flood_hazard.tif'
)

if os.path.exists(hazard_raster_path):
    # Query hazard data for all sample points
    hazard_results = query_hazard_for_points(sample_points, hazard_raster_path)

    # Aggregate statistics
    granular_stats = aggregate_risk_statistics(hazard_results, polygon_area_km2)

    record['granular_analysis'] = granular_stats
    logger.info(f"Granular analysis completed: {len(sample_points)} points sampled")
```

### Step 3: Update Raster Paths

Modify the `hazard_raster_path` to point to your actual raster files.

For multiple hazards, you can loop:
```python
hazards = {
    'flood': 'flood_hazard.tif',
    'heat': 'heat_stress.tif',
    'water_stress': 'water_stress.tif'
}

for hazard_name, raster_file in hazards.items():
    raster_path = os.path.join(settings.BASE_DIR, 'path/to/rasters', raster_file)
    if os.path.exists(raster_path):
        results = query_hazard_for_points(sample_points, raster_path)
        stats = aggregate_risk_statistics(results, polygon_area_km2)
        record[f'granular_analysis_{hazard_name}'] = stats
```

## 📈 Expected Output

### Grid Metadata (Currently Available)
```python
{
    'sample_points_count': 342,
    'grid_spacing_meters': 100,
    'polygon_area_km2': 4.2
}
```

### Full Granular Analysis (After Enabling Hazard Queries)
```python
{
    'statistics': {
        'sample_count': 342,
        'mean': 0.85,
        'median': 0.72,
        'min': 0.12,
        'max': 2.31,
        'std': 0.48
    },
    'risk_distribution': {
        'low': {'count': 123, 'percentage': 36.0, 'area_km2': 1.44},
        'medium': {'count': 137, 'percentage': 40.1, 'area_km2': 1.60},
        'high': {'count': 68, 'percentage': 19.9, 'area_km2': 0.80},
        'very_high': {'count': 14, 'percentage': 4.1, 'area_km2': 0.16}
    },
    'dominant_risk': 'Medium',
    'spatial_variability': 'High',
    'recommendation': 'WARNING: Significant high-risk areas detected...',
    'priority': 'High'
}
```

## 🧪 Testing

### Test with Sample Polygon

1. **Upload a shapefile** with polygon geometry
2. **Check logs** - Should see: "Generated X sample points for granular analysis"
3. **View results table** - Look for 📊 icon next to polygon assets
4. **Click icon** - Modal should show grid metadata

### Test with City Boundary Search

1. **Search for a city** (e.g., "Manila")
2. **Click "Save City Boundary"**
3. **Proceed to hazard analysis**
4. **View results** - Should see 📊 icon next to city boundary
5. **Click icon** - Modal shows grid details

## 📊 Adaptive Grid Spacing

The system automatically adjusts grid density based on polygon size:

| Polygon Size | Grid Spacing | Sample Points (approx) |
|--------------|--------------|------------------------|
| < 0.01 km² (building) | 5m | ~400 |
| 0.01-0.1 km² (compound) | 10m | ~1000 |
| 0.1-1 km² (facility) | 50m | ~400 |
| 1-10 km² (municipality) | 100m | ~1000 |
| 10-100 km² (city) | 500m | ~400 |
| > 100 km² (province) | 1000m | varies |

This balances accuracy with performance.

## 🔧 Architecture

```
User Upload → views.py → granular_analysis.py
                ↓              ↓
           Session Data    Sample Grid
                ↓              ↓
           Results Page   (Hazard Query)
                ↓              ↓
           Modal Dialog    Statistics
```

## 📝 Code Locations

1. **Core logic**: `climate_hazards_analysis_v2/granular_analysis.py`
2. **File upload integration**: `climate_hazards_analysis_v2/views.py` lines 103-161
3. **Manual add integration**: `climate_hazards_analysis_v2/views.py` lines 261-293
4. **Frontend display**: `climate_hazards_analysis_v2/templates/climate_hazards_analysis_v2/results.html` lines 512-730

## 💡 Key Benefits

### Before (Centroid-Only)
- ❌ Single value per polygon
- ❌ Misses spatial variability
- ❌ Cannot identify hotspots
- ❌ Crude for large areas

### After (Point Sampling Grid)
- ✅ Statistical distribution (min/mean/max)
- ✅ Risk percentage breakdown
- ✅ Spatial variability assessment
- ✅ Actionable recommendations
- ✅ Confidence levels

## 🎓 Example Use Case

**Scenario**: Manila City boundary (42 km²)

**Old Approach**:
- Centroid: 14.5995°N, 120.9842°E
- Result: "High flood risk"
- Problem: Where exactly?

**New Approach**:
- Sample grid: 168 points (500m spacing)
- Result:
  - 15% Very High Risk (6.3 km²)
  - 35% High Risk (14.7 km²)
  - 30% Medium Risk (12.6 km²)
  - 20% Low Risk (8.4 km²)
- Recommendation: "Focus mitigation on 50% high-risk zones in eastern districts"

## 🚀 Future Enhancements

1. **Heatmap visualization** - Show risk distribution on map
2. **Export sample points** - Download as shapefile/GeoJSON
3. **Configurable thresholds** - User-defined risk categories
4. **Multi-hazard aggregation** - Combined risk scores
5. **Time series analysis** - Compare scenarios

## 📞 Support

For questions or issues:
1. Check logs for error messages
2. Verify hazard raster paths are correct
3. Ensure rasterio library is installed
4. Review code comments in `granular_analysis.py`

## 📄 License

Part of CLIMATE-Build system. All rights reserved.
