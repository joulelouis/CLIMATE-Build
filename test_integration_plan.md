# Integration Test Plan for Polygon Assets in Main Workflow

## Test Scenario 1: Mixed Assets (Regular Facilities + Polygon Assets)

### Setup
1. Upload a CSV file with regular facilities (point assets)
2. Draw one or more polygon assets on the map
3. Navigate to hazard selection page

### Expected Behavior
1. Hazard selection page should show:
   - "You have X regular assets and Y polygon asset(s) with Z total granular point(s) loaded."
   - All available hazard types for selection

### Test Steps
1. Select multiple hazard types (e.g., Flood, Heat, Water Stress)
2. Click "Generate Asset Exposure" button
3. Observe the loading progress

### Expected Results
1. Results page should display:
   - Mixed assets indicator at the top
   - Regular facility rows (normal styling)
   - Polygon asset rows (yellow background, "Polygon" badge)
   - Granular point rows (blue background, "Point X" badge, initially hidden)
   - Expand/collapse buttons on polygon parent rows

### Validation Points
- Regular facilities show analysis results immediately
- Polygon assets show aggregated results as parent rows
- Clicking expand button on polygon rows shows granular child points
- Child points show individual hazard analysis results
- All hazard types are analyzed for both asset types

## Test Scenario 2: Polygon Assets Only

### Setup
1. Clear any regular facilities
2. Draw only polygon assets on the map
3. Navigate to hazard selection page

### Expected Behavior
1. Hazard selection page should show:
   - "You have 0 regular assets and Y polygon asset(s) with Z total granular point(s) loaded."

### Test Steps
1. Select hazard types
2. Click "Generate Asset Exposure"
3. Verify hierarchical display works correctly

## Test Scenario 3: Regular Facilities Only (Backward Compatibility)

### Setup
1. Upload only regular facility CSV
2. No polygon assets
3. Navigate to hazard selection page

### Expected Behavior
1. System should work exactly as before
2. No hierarchical features should be visible
3. No mixed assets indicator

## Implementation Validation Checklist

### Backend Integration
- [ ] `_prepare_unified_asset_inventory()` correctly separates asset types
- [ ] `_handle_unified_mixed_assets_results()` processes both asset types
- [ ] `_process_regular_facilities_unified()` handles regular facilities
- [ ] `_process_polygon_assets_unified()` handles polygon assets
- [ ] `_create_hierarchical_results_structure()` creates proper hierarchy

### Frontend Display
- [ ] CSS styles for hierarchical rows work correctly
- [ ] JavaScript expand/collapse functionality works
- [ ] Asset type badges display correctly
- [ ] Mixed assets indicator appears when needed
- [ ] Backward compatibility maintained for regular facilities

### Error Handling
- [ ] Graceful handling when polygon processing fails
- [ ] Fallback to regular workflow when no mixed assets
- [ ] Proper error messages displayed to users

## Manual Testing Commands

### Test Data Preparation
```python
# Create test regular facilities CSV
test_regular_facilities = [
    {"Facility": "Test Facility 1", "Lat": 14.6, "Long": 121.0, "Archetype": "commercial"},
    {"Facility": "Test Facility 2", "Lat": 14.5, "Long": 120.9, "Archetype": "residential"}
]

# Create test polygon data
test_polygon = {
    "name": "Test Polygon Area",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[121.0, 14.6], [121.1, 14.6], [121.1, 14.5], [121.0, 14.5], [121.0, 14.6]]]
    },
    "archetype": "industrial"
}
```

### Verification Steps
1. Check browser console for hierarchical initialization logs
2. Verify network requests show both regular and polygon processing
3. Inspect generated HTML for correct hierarchical classes
4. Test expand/collapse functionality
5. Verify data accuracy in displayed results

## Performance Considerations

### Metrics to Monitor
- Processing time for mixed asset scenarios
- Memory usage during hierarchical data processing
- Frontend rendering performance with large numbers of granular points
- Database query efficiency for granular results

### Optimization Points
- Lazy loading of granular child rows
- Efficient database queries for granular analysis results
- Minimal DOM manipulation for hierarchical display
- Caching of processed results where possible