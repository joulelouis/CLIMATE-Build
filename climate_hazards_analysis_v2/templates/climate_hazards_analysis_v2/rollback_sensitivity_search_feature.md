# Rollback Instructions for Sensitivity Column Search Feature

## Files Modified
1. `sensitivity_column_selector.html` - Added search input UI
2. `sensitivity_results.html` - Added JavaScript search functionality

## Quick Rollback Commands

### Option 1: Restore from Backup
```bash
# Restore sensitivity column selector
cp "C:/SGV/python/CRA/CRAproject/climate_hazards_analysis_v2/templates/climate_hazards_analysis_v2/sensitivity_column_selector_backup.html" "C:/SGV/python/CRA/CRAproject/climate_hazards_analysis_v2/templates/climate_hazards_analysis_v2/sensitivity_column_selector.html"
```

### Option 2: Manual Rollback

#### In sensitivity_column_selector.html:
Remove lines 7-16 (the search input section):
```html
<!-- Search Input -->
<div class="mb-3">
    <div class="input-group">
        <input type="text" class="form-control" id="sensitivity-column-search" placeholder="Search columns..." autocomplete="off">
        <button class="btn btn-outline-secondary" type="button" id="clear-sensitivity-search" title="Clear search">
            <i class="fas fa-times"></i>
        </button>
    </div>
    <small class="text-muted">Type to filter columns by name, scenario, or year</small>
</div>
```

#### In sensitivity_results.html:
Remove lines 1220-1361 (the search functionality):
- Remove `setupSensitivityColumnSearch();` call (line 1221)
- Remove `setupSensitivityColumnSearch()` function (lines 1225-1259)
- Remove `filterSensitivityColumnsBySearch()` function (lines 1261-1342)
- Remove `updateSensitivitySearchMatchCount()` function (lines 1344-1361)

## Error Indicators
If the search feature causes issues, you may see:
- JavaScript console errors mentioning "sensitivity-column-search"
- Sensitivity column selector not working properly
- Search input not responding
- Browser freezing when typing in search

## Testing After Rollback
1. Load the sensitivity analysis results page
2. Verify sensitivity column selector checkboxes work
3. Check browser console for JavaScript errors
4. Confirm all existing functionality works normally