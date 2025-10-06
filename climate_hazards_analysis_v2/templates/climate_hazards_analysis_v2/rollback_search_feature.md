# Rollback Instructions for Column Search Feature

## Files Modified
1. `column_selector.html` - Added search input UI
2. `results.html` - Added JavaScript search functionality

## Quick Rollback Commands

### Option 1: Restore from Backups
```bash
# Restore column selector
cp "C:/SGV/python/CRA/CRAproject/climate_hazards_analysis_v2/templates/climate_hazards_analysis_v2/column_selector_backup.html" "C:/SGV/python/CRA/CRAproject/climate_hazards_analysis_v2/templates/climate_hazards_analysis_v2/column_selector.html"

# Restore results file
cp "C:/SGV/python/CRA/CRAproject/climate_hazards_analysis_v2/templates/climate_hazards_analysis_v2/results_backup.html" "C:/SGV/python/CRA/CRAproject/climate_hazards_analysis_v2/templates/climate_hazards_analysis_v2/results.html"
```

### Option 2: Manual Rollback

#### In column_selector.html:
Remove lines 7-16 (the search input section):
```html
<!-- Search Input -->
<div class="mb-3">
    <div class="input-group">
        <input type="text" class="form-control" id="column-search" placeholder="Search columns..." autocomplete="off">
        <button class="btn btn-outline-secondary" type="button" id="clear-search" title="Clear search">
            <i class="fas fa-times"></i>
        </button>
    </div>
    <small class="text-muted">Type to filter columns by name, scenario, or year</small>
</div>
```

#### In results.html:
Remove lines 1420-1521 (the search functionality):
- Remove `setupColumnSearch();` call
- Remove `setupColumnSearch()` function
- Remove `filterColumnsBySearch()` function
- Remove `updateSearchMatchCount()` function

## Error Indicators
If the search feature causes issues, you may see:
- JavaScript console errors mentioning "column-search"
- Column selector not working properly
- Search input not responding
- Browser freezing when typing in search

## Testing After Rollback
1. Load the climate hazards analysis page
2. Verify column selector checkboxes work
3. Check browser console for JavaScript errors
4. Confirm all existing functionality works normally