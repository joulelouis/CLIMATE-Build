# 📖 User Flow: Granular Risk Analysis Feature

## 🎯 Overview

The **Granular Risk Analysis** feature automatically analyzes polygon-based assets using a sampling grid instead of a single centroid point. This provides detailed risk distribution statistics across the entire asset area.

---

## 🚪 Entry Points

There are **4 ways** to trigger granular analysis:

### **Method 1: Upload Shapefile/GeoPackage** ⬆️
### **Method 2: Search City Boundary** 🔍
### **Method 3: Draw Polygon Asset** ✏️
### **Method 4: Upload CSV (Point Data)** ❌ *No granular analysis*

---

## 📋 Complete User Flow

---

## 🔄 Method 1: Upload Shapefile/GeoPackage

### **Step 1: Navigate to Main Page**

```
URL: /climate-hazards-analysis-v2/
Page Title: "Exposure Overlay"
```

**What you see:**
- Left side: "Upload Asset Data File" card
- Right side: Interactive map

---

### **Step 2: Upload Polygon File**

**Location:** Left sidebar → "Upload Asset Data File"

**Actions:**
1. Click **"Choose File"** button or click on the upload box
2. Select your file:
   - ✅ `.zip` (Shapefile - must include .shp, .shx, .dbf, .prj)
   - ✅ `.gpkg` (GeoPackage)
   - ❌ `.csv` (No granular analysis - point data only)
   - ❌ `.xlsx` (No granular analysis - point data only)

3. File automatically uploads after selection

**Expected Result:**
```
✅ Success message appears:
"Successfully loaded X facilities from [filename]"

Console logs show:
"Generated Y sample points for granular analysis"
"Granular analysis completed for [Asset Name]: Y points sampled using Flood (100-year)"
```

**Visual Confirmation:**
- Map displays your polygon(s) as colored shapes
- Markers appear at polygon centroids

---

### **Step 3: Proceed to Hazard Analysis**

**Location:** Bottom right of screen

**Actions:**
1. Click yellow button: **"Proceed to Select Hazards and Scenarios"**

**Expected Result:**
- Navigates to: `/climate-hazards-analysis-v2/select-hazards/`

---

### **Step 4: Select Hazards**

**Location:** Hazard selection page

**Actions:**
1. Select desired hazards:
   - ☑️ Flood
   - ☑️ Water Stress
   - ☑️ Heat
   - ☑️ Sea Level Rise
   - ☑️ Tropical Cyclones
   - ☑️ Storm Surge
   - ☑️ Rainfall Induced Landslide

2. Select scenario (Baseline, SSP2-4.5, SSP5-8.5)
3. Select time period
4. Click **"Run Analysis"**

**Expected Result:**
- Processing message appears
- Redirects to results page

---

### **Step 5: View Results Table**

**Location:** `/climate-hazards-analysis-v2/results/`

**What you see:**
- Data table with all analyzed assets
- Columns: Asset, Location, Hazard exposures...

**Look for the 📊 icon:**

```
┌──────────────────┬──────────────┬─────────────┐
│ Asset            │ Location     │ Risk        │
├──────────────────┼──────────────┼─────────────┤
│ Manila City 📊   │ 14.5°, 121° │ HIGH        │
│ Building A  📊   │ 14.6°, 121° │ MEDIUM      │
│ Point Asset      │ 14.4°, 121° │ LOW         │  ← No icon (point data)
└──────────────────┴──────────────┴─────────────┘
```

**Key Indicators:**
- 📊 icon = Polygon asset with granular analysis
- No icon = Point asset (centroid only)

---

### **Step 6: Open Granular Analysis Modal**

**Location:** Results table, Asset name column

**Actions:**
1. **Click the 📊 icon** next to any polygon asset name

**Expected Result:**
- Modal dialog opens
- Title: "📊 Granular Analysis: [Asset Name]"

---

### **Step 7: View Granular Analysis Details**

**Modal Contents:**

#### **Top Section: Info Banner**
```
ℹ️ Point Sampling Grid Analysis
This polygon asset has been analyzed using a fine-resolution
sampling grid instead of a single centroid point.
Hazard Type: Flood (100-year return period)
```

#### **Analysis Details (Left Panel)**
```
┌─────────────────────────────┐
│ Analysis Details            │
├─────────────────────────────┤
│ Polygon Area:    42.88 km²  │
│ Grid Spacing:    500m        │
│ Sample Points:   171 points │
└─────────────────────────────┘
```

#### **Status Badges**
```
✓ Grid Generated
✓ Hazard Analysis Complete
```

#### **Risk Distribution (Visual Progress Bar)**
```
████████████████ 36% Low
████████████████████ 40% Medium
██████████ 20% High
██ 4% Very High
```

#### **Detailed Breakdown (4 Cards)**
```
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│    Low      │ │   Medium    │ │    High     │ │ Very High   │
│    36%      │ │    40%      │ │    20%      │ │     4%      │
│ 123 points  │ │ 137 points  │ │  68 points  │ │  14 points  │
│  15.1 km²   │ │  16.8 km²   │ │   8.4 km²   │ │   1.7 km²   │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

#### **Statistical Summary (Left Bottom)**
```
┌────────────────────────────┐
│ Sample Points:      171    │
│ Mean Value:         0.85   │
│ Median Value:       0.72   │
│ Range:         0.12 - 2.31 │
│ Std Deviation:      0.48   │
│ Spatial Variability: HIGH  │
└────────────────────────────┘
```

#### **Risk Assessment (Right Bottom)**
```
┌─────────────────────┐
│ Dominant Risk       │
│   [MEDIUM] badge    │
└─────────────────────┘

┌─────────────────────┐
│ Priority Level      │
│    [HIGH] badge     │
└─────────────────────┘
```

#### **Recommendation (Bottom)**
```
⚠️ WARNING: Significant high-risk areas detected.
Prioritize mitigation planning.
```

---

## 🔄 Method 2: Search City Boundary

### **Step 1: Navigate to Main Page**

```
URL: /climate-hazards-analysis-v2/
```

---

### **Step 2: Search for City**

**Location:** Top-right of map

**What you see:**
- Search box with placeholder: "Search for a city (e.g., Manila)"

**Actions:**
1. Click on search box
2. Type city name: e.g., "Manila", "Quezon City", "Cebu"
3. Select from dropdown suggestions
4. Press Enter or click suggestion

**Expected Result:**
- Map zooms to city
- "Fetching city boundaries..." notification appears
- Orange polygon outline appears on map
- "Boundary found for [City]!" notification

**Visual Confirmation:**
- City boundary displayed in orange/yellow
- "Save City Boundary" button appears (top-left, green)

---

### **Step 3: Save Boundary as Asset**

**Location:** Top-left of map

**Actions:**
1. Click green button: **"Save City Boundary"**
2. Enter asset name in prompt (default: city name)
3. Enter archetype (default: "City Boundary")
4. Click OK

**Expected Result:**
```
Console logs:
"Starting granular analysis for [City Name]"
"Generated X sample points for granular analysis"
"Granular analysis completed"

Notification:
"Boundary saved successfully!"
```

---

### **Step 4-7: Same as Method 1**
- Proceed to hazard analysis
- Run analysis
- View results
- Click 📊 icon
- View granular details

---

## 🔄 Method 3: Draw Polygon Asset

### **Step 1: Navigate to Main Page**

```
URL: /climate-hazards-analysis-v2/
```

---

### **Step 2: Enter Drawing Mode**

**Location:** Top-left of map

**Actions:**
1. Click yellow button: **"Draw Polygon Asset"**

**Expected Result:**
- Button changes to red: "Cancel Drawing"
- Drawing instructions appear below button:
  ```
  Drawing Polygon:
  • Click on map to add points
  • Click on first point to close polygon
  • Or press Enter key to finish
  ```

---

### **Step 3: Draw Polygon**

**Location:** On the map

**Actions:**
1. Click on map to add first point
2. Click to add more points (minimum 3)
3. Either:
   - Click on first point to close polygon, OR
   - Press **Enter** key

**Visual Confirmation:**
- Lines connect your points
- Polygon fills with semi-transparent color when closed

---

### **Step 4: Name and Save**

**Expected Result:**
- Modal appears: "Add Polygon Asset"

**Actions:**
1. Enter **Asset Name** (required)
2. Enter **Asset Archetype** (optional, default: "default archetype")
3. **Centroid Coordinates** display automatically
4. Click **"Add Asset"**

**Expected Result:**
```
Console logs:
"Starting granular analysis for [Asset Name]"
"Generated X sample points for granular analysis"
"Granular analysis completed"

Notification:
"Asset saved successfully!"
```

**Visual Confirmation:**
- Polygon changes from orange to teal/cyan
- Marker appears at centroid

---

### **Step 5-7: Same as Method 1**
- Proceed to hazard analysis
- Run analysis
- View results
- Click 📊 icon

---

## ❓ Troubleshooting

### **Issue 1: No 📊 icon appears**

**Possible Causes:**

1. **Point data uploaded (not polygon)**
   - ❌ CSV/Excel files only support points
   - ✅ Upload shapefile/GeoPackage with polygons

2. **Shapefile doesn't contain polygons**
   - Check in QGIS/ArcGIS: Geometry type should be "Polygon" or "MultiPolygon"
   - Not "Point" or "LineString"

3. **Granular analysis failed**
   - Check browser console (F12 → Console tab)
   - Look for errors mentioning "granular analysis"

**Solution:**
- Re-upload file ensuring polygon geometry
- Check server logs for detailed error messages

---

### **Issue 2: Modal shows "Hazard Query Pending"**

**What you see:**
```
✓ Grid Generated
⏳ Hazard Query Pending  ← Problem
```

**Possible Causes:**

1. **Hazard raster file not found**
   - File path incorrect
   - File missing from directory

2. **Rasterio library issue**
   - Library not installed
   - Import error

**Solution:**
```bash
# Check if rasterio is installed
pip list | grep rasterio

# Install if missing
pip install rasterio

# Verify file exists
ls "C:\CLIMATE\CLIMATE-Build\climate_hazards_analysis\static\input_files\PH_Flood_100year_UTM_ProjectNOAH_Unmasked.tif"
```

**Check logs:**
```
Look for:
"No hazard raster available for granular analysis"
"Hazard raster not found: [path]"
```

---

### **Issue 3: Modal doesn't open when clicking 📊**

**Possible Causes:**

1. **JavaScript error**
   - Bootstrap modal not loaded
   - jQuery conflict

2. **Modal ID mismatch**
   - Template rendering issue

**Solution:**
- Press F12 → Console tab
- Look for JavaScript errors
- Refresh page (Ctrl+F5)
- Clear browser cache

---

### **Issue 4: Upload succeeds but no map displayed**

**Possible Causes:**

1. **Mapbox token invalid/expired**
2. **Coordinate system not recognized**
3. **Geometry outside Philippines**

**Solution:**
- Check browser console for Mapbox errors
- Verify shapefile CRS is EPSG:4326 or similar
- Check coordinates are within Philippines (10-20°N, 117-127°E)

---

## 🎓 Visual Decision Tree

```
Start
  │
  ├─ Do you have polygon data?
  │   │
  │   ├─ YES ─→ Upload .shp/.gpkg ─→ See 📊 icon
  │   │
  │   └─ NO ─→ Options:
  │           │
  │           ├─ Search city boundary ─→ Save ─→ See 📊 icon
  │           │
  │           ├─ Draw polygon on map ─→ Save ─→ See 📊 icon
  │           │
  │           └─ Upload CSV/Excel ─→ No 📊 icon (point data only)
  │
  └─ Click 📊 icon ─→ View granular analysis
```

---

## 📊 Feature Availability Matrix

| Data Source | Geometry Type | 📊 Icon | Granular Analysis |
|-------------|---------------|---------|-------------------|
| Shapefile (.zip) | Polygon | ✅ YES | ✅ YES |
| Shapefile (.zip) | Point | ❌ NO | ❌ NO |
| GeoPackage (.gpkg) | Polygon | ✅ YES | ✅ YES |
| GeoPackage (.gpkg) | Point | ❌ NO | ❌ NO |
| CSV | Point | ❌ NO | ❌ NO |
| Excel | Point | ❌ NO | ❌ NO |
| City Boundary Search | Polygon | ✅ YES | ✅ YES |
| Draw Polygon | Polygon | ✅ YES | ✅ YES |
| Click on Map (Add Facility) | Point | ❌ NO | ❌ NO |

---

## 🎯 Quick Test Checklist

### **Test Scenario: Upload Shapefile**

- [ ] Navigate to `/climate-hazards-analysis-v2/`
- [ ] Click "Choose File"
- [ ] Select polygon shapefile (.zip)
- [ ] See success message
- [ ] See polygons on map
- [ ] Click "Proceed to Select Hazards"
- [ ] Select "Flood" hazard
- [ ] Click "Run Analysis"
- [ ] View results table
- [ ] **Find 📊 icon next to asset name**
- [ ] **Click 📊 icon**
- [ ] **See modal with risk distribution**
- [ ] **Verify statistics are displayed**
- [ ] **See recommendation text**

### **Test Scenario: City Boundary**

- [ ] Navigate to `/climate-hazards-analysis-v2/`
- [ ] Type "Manila" in search box (top-right of map)
- [ ] Select from dropdown
- [ ] See orange boundary on map
- [ ] **Click green "Save City Boundary" button**
- [ ] Enter name and save
- [ ] See teal polygon on map
- [ ] Click "Proceed to Select Hazards"
- [ ] Run analysis
- [ ] **Find 📊 icon next to "Manila"**
- [ ] **Click and view granular analysis**

---

## 💡 Tips for Best Results

### **1. Polygon Size Considerations**

| Size | Best Use Case | Grid Spacing | Sample Points |
|------|---------------|--------------|---------------|
| < 0.1 km² | Buildings | 5-10m | 400-1000 |
| 0.1-10 km² | Facilities | 50-100m | 400-1000 |
| 10-100 km² | Cities | 500m | 400 |
| > 100 km² | Provinces | 1000m | 200-400 |

### **2. File Preparation**

✅ **Good shapefile:**
- Contains Polygon or MultiPolygon geometry
- Has "Facility" or "Name" column
- Projected in EPSG:4326 (WGS84)
- File size < 50MB

❌ **Common issues:**
- Point data instead of polygons
- Missing .prj file (no CRS info)
- Column names don't match expected format
- ZIP file missing required components

### **3. Performance Tips**

- **Small polygons** (<1 km²): Analysis completes in < 1 second
- **Large cities** (>50 km²): May take 2-3 seconds
- **Multiple assets**: Processed sequentially (add times together)

---

## 📞 Support

If you're still unable to locate the feature:

1. **Check browser console** (F12 → Console)
   - Look for errors
   - Search for "granular"

2. **Check server logs**
   - Look for "Generated X sample points"
   - Look for "Granular analysis completed"

3. **Verify prerequisites**
   - Rasterio installed: `pip list | grep rasterio`
   - Hazard raster exists
   - Polygon geometry (not point)

4. **Test with known-good data**
   - Use city boundary search for "Manila"
   - Should always work if system configured correctly

---

## 🎉 Success Indicators

**You know it's working when you see:**

✅ Console logs: "Granular analysis completed for [Asset]"
✅ Results table has 📊 icon next to polygon assets
✅ Clicking icon opens modal with statistics
✅ Modal shows risk distribution breakdown
✅ Modal shows "✓ Hazard Analysis Complete" badge

---

**Last Updated:** 2025-01-12
**Feature Version:** 1.0
**Applies to:** climate_hazards_analysis_v2 module
