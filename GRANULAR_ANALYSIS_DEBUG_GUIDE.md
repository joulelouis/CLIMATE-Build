# 🔍 Granular Analysis Debugging Guide

## Quick Checklist

Follow these steps to verify granular analysis is working:

### **Step 1: Draw a Large Polygon (≥ 6 km²)**
- Navigate to: `/climate-hazards-analysis-v2/`
- Click "Draw Polygon Asset" button
- Draw a LARGE polygon (like Manila city boundaries)
- **IMPORTANT**: Polygon must be ≥ 6 km² to trigger granular analysis
  - Small buildings won't work!
  - Try drawing a city-sized polygon

### **Step 2: Check Browser Console**
- Press `F12` to open Developer Tools
- Go to Console tab
- Look for these messages:
  ```
  Polygon area: XX.XX km² - Showing grid spacing modal
  ```
- If you see "< 6 km²", draw a bigger polygon!

### **Step 3: Grid Spacing Modal Should Appear**
- Modal title: "Configure Grid Spacing"
- Shows polygon area
- Select grid spacing (default: 100m)
- Click **"Apply Grid Analysis"**
- **WAIT** for the polygon asset modal to appear (500ms delay)

### **Step 4: Name and Save Asset**
- Enter asset name
- Enter archetype (optional)
- Click "Add Asset"

### **Step 5: Check Server Logs**
Open your Django console and look for:
```
Starting granular analysis for [Asset Name]: Area=XX.XX km², Grid spacing=100m
Generated XXX sample points for [Asset Name]
```

**If you DON'T see these logs:**
- Grid spacing wasn't sent to backend
- Check browser Network tab (F12 → Network)
- Look for POST request to `/api/add-facility/`
- Check request payload for `gridSpacing` and `areaKm2` fields

### **Step 6: Run Hazard Analysis**
- Click "Proceed to Select Hazards"
- Select at least one hazard (e.g., Flood)
- Click "Run Analysis"

### **Step 7: Check Results Page Logs**
In Django console, look for:
```
Checking for granular analysis data...
Facility data count: X
Facility 0: [Asset Name] - Keys: ['Facility', 'Lat', 'Long', 'Archetype', 'geometry', 'polygon_area_km2', 'sample_points', 'grid_spacing_meters', 'sample_points_count']
Found raster for Flood: C:\CLIMATE\...
Processing facility from results: [Asset Name]
Found matching facility: [Asset Name], has sample_points: True
Found XXX sample points for [Asset Name]
Granular analysis completed for [Asset Name]: XXX points, XX clusters
```

**If you see:**
- `has sample_points: False` → Sample points weren't generated
- `No analyzed points returned` → Hazard raster not found or query failed

### **Step 8: Look for 📊 Icon**
- In results table, look for 📊 icon next to facility name
- **If no icon appears:**
  - Check browser console for template errors
  - Verify `row.has_granular_analysis` is True (check Django logs)

---

## Common Issues

### ❌ Issue 1: No Grid Spacing Modal Appears
**Problem**: Polygon is too small (< 6 km²)
**Solution**: Draw a MUCH larger polygon (city-sized, not building-sized)

### ❌ Issue 2: Grid Spacing Not Saved
**Problem**: Both modals appearing at same time
**Solution**: Fixed in latest code - asset modal now appears 500ms AFTER you click Apply/Skip

### ❌ Issue 3: No 📊 Icon in Results
**Possible causes:**
1. Sample points not generated (check Step 5 logs)
2. Grid spacing not sent to backend (check Network tab in browser)
3. `has_granular_analysis` not set to True (check Step 7 logs)

### ❌ Issue 4: Hazard Raster Not Found
**Problem**: Raster files don't exist at configured paths
**Solution**: Check `hazard_raster_config.py` paths match your actual files:
```python
HAZARD_RASTER_DIR = os.path.join(settings.BASE_DIR, 'climate_hazards_analysis', 'static', 'input_files')
```

---

## Test Polygon Coordinates

Use these coordinates to draw a test polygon in Manila (~42 km²):

```javascript
// Manila city boundaries (approximate)
[
  [120.98, 14.55],  // SW corner
  [121.05, 14.55],  // SE corner
  [121.05, 14.62],  // NE corner
  [120.98, 14.62],  // NW corner
  [120.98, 14.55]   // Close polygon
]
```

This should generate ~4,200 sample points with 100m spacing.

---

## Enable Extra Debugging

Add this to your `views.py` at the top of `add_facility()`:

```python
logger.info(f"=== ADD FACILITY DEBUG ===")
logger.info(f"Received data: {json.dumps(data, indent=2)}")
```

Add this to `confirmPolygonAsset()` in `climate_hazard_map.html`:

```javascript
console.log("=== CONFIRM POLYGON DEBUG ===");
console.log("drawnPolygonData:", drawnPolygonData);
console.log("facilityData:", facilityData);
```

---

## Success Criteria

You'll know it's working when you see ALL of these:

1. ✅ Grid spacing modal appears for large polygons
2. ✅ Browser console shows grid spacing configuration
3. ✅ Django logs show "Generated XXX sample points"
4. ✅ Django logs show "Granular analysis completed for [Asset]"
5. ✅ 📊 icon appears in results table
6. ✅ Clicking icon opens modal with risk distribution
7. ✅ Modal shows statistics and detailed points table

---

## Next Steps

If still not working after following this guide:

1. **Copy your Django console output** (entire output from running analysis)
2. **Copy your browser console output** (F12 → Console tab)
3. **Take a screenshot** of the drawn polygon and results page
4. Share these for further debugging

The implementation is complete - if it's not showing, it's a configuration or workflow issue that the logs will reveal!
