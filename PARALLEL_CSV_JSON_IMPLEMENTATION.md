# Parallel CSV/JSON Implementation - Option 1: Gradual Migration

This document explains the parallel CSV and JSON generation implementation for the Climate Hazards Analysis system, allowing for gradual migration from CSV to JSON.

## Overview

The implementation generates **both CSV and JSON files** during analysis, with the system preferring JSON files for loading while maintaining CSV fallback compatibility. This approach ensures zero downtime during testing and migration.

## Implementation Details

### 1. Parallel Generation

**Location**: `climate_hazards_analysis/utils/climate_hazards_analysis.py`

**What's Added**:
- JSON generation alongside existing CSV generation
- Rich metadata structure in JSON format
- Same base filename for both formats

**Code Addition** (lines 1066-1098):
```python
# === PARALLEL JSON GENERATION (Option 1: Gradual Migration) ===
import json
from datetime import datetime

# Determine JSON filename (same base as CSV)
if sensitivity_params and buffer_size != 0.0009:
    out_json = os.path.join(input_dir, f'combined_output_sensitivity_buffer_{buffer_size:.4f}.json')
elif buffer_size != 0.0009:
    out_json = os.path.join(input_dir, f'combined_output_buffer_{buffer_size:.4f}.json')
else:
    out_json = os.path.join(input_dir, 'combined_output.json')

# Create JSON data structure
json_data = {
    'metadata': {
        'generated_at': str(datetime.now()),
        'analysis_type': 'sensitivity' if sensitivity_params else 'standard',
        'buffer_size_degrees': buffer_size,
        'buffer_size_meters': int(buffer_size * 111000) if buffer_size != 0.0009 else 100,
        'sensitivity_parameters': sensitivity_params or {},
        'total_facilities': len(combined_df),
        'hazards_analyzed': selected_fields or []
    },
    'data': combined_df.to_dict(orient='records')
}

# Write JSON file with UTF-8 encoding
with open(out_json, 'w', encoding='utf-8') as f_json:
    json.dump(json_data, f_json, indent=2, ensure_ascii=False, default=str)
```

### 2. JSON/CSV Loader with Fallback

**Location**: `climate_hazards_analysis_v2/json_csv_loader.py`

**Features**:
- Prefers JSON loading, falls back to CSV
- Handles both structured and legacy JSON formats
- Provides detailed logging and error handling
- File existence validation

**Key Methods**:
- `load_analysis_results()` - Main loading function with preference
- `_load_from_json()` - Handles structured and legacy JSON
- `_load_from_csv()` - Traditional CSV loading with encoding handling
- `get_analysis_file_paths()` - Extracts paths from analysis results

### 3. Updated Views with Parallel Loading

**Location**: `climate_hazards_analysis_v2/views.py`

**Changes Made**:
- Replaced CSV-only loading with parallel loader
- Added comprehensive error handling and logging
- Maintained DataFrame compatibility for existing code
- Added JSON console logging

**Updated Section** (lines 1233-1291):
```python
# === PARALLEL CSV/JSON LOADING (Option 1: Gradual Migration) ===
from .json_csv_loader import json_csv_loader
file_paths = json_csv_loader.get_analysis_file_paths(result)

combined_csv_path = file_paths['csv_path']
combined_json_path = file_paths['json_path']

# Load data using JSON preference (fallback to CSV if needed)
data, columns = json_csv_loader.load_analysis_results(
    csv_path=combined_csv_path,
    json_path=combined_json_path,
    prefer_json=True
)

# Convert back to DataFrame for compatibility with existing code
df = pd.DataFrame(data)
```

### 4. Enhanced Console Logging

**Location**: `climate_hazards_analysis_v2/json_console_simple.py`

**Purpose**:
- Uses `print()` statements for guaranteed console output
- Provides formatted JSON display for debugging
- Shows step-by-step workflow progress

**What It Logs**:
- Upload asset data and database records created
- Hazard selections and parameters
- Analysis processing status and results

## File Generation Patterns

### Standard Analysis
- **CSV**: `combined_output.csv`
- **JSON**: `combined_output.json`

### Sensitivity Analysis
- **CSV**: `combined_output_sensitivity_buffer_0.0050.csv`
- **JSON**: `combined_output_sensitivity_buffer_0.0050.json`

### Buffer Analysis
- **CSV**: `combined_output_buffer_0.0100.csv`
- **JSON**: `combined_output_buffer_0.0100.json`

## JSON Structure

### Structured Format (New)
```json
{
  "metadata": {
    "generated_at": "2024-01-15 14:30:25.123456",
    "analysis_type": "standard",
    "buffer_size_degrees": 0.0009,
    "buffer_size_meters": 100,
    "sensitivity_parameters": {},
    "total_facilities": 50,
    "hazards_analyzed": ["Flood", "Heat", "Water Stress"]
  },
  "data": [
    {
      "Facility": "Factory A",
      "Asset Archetype": "Manufacturing",
      "Lat": 14.5,
      "Long": 121.0,
      "Flood Depth (meters)": "0.1 to 0.5",
      "Days over 35° Celsius": 25
    }
  ]
}
```

### Legacy Format (Fallback)
```json
[
  {
    "Facility": "Factory A",
    "Asset Archetype": "Manufacturing",
    "Lat": 14.5,
    "Long": 121.0,
    "Flood Depth (meters)": "0.1 to 0.5"
  }
]
```

## Testing and Validation

### Console Output Examples

During analysis, you'll see console output like:

```
=== PARALLEL LOADING: JSON (preferred) + CSV (fallback) ===
✓ JSON file exists: /path/to/combined_output.json (15420 bytes)
✓ CSV file exists: /path/to/combined_output.csv (12850 bytes)
=== END FILE STATUS ===

Successfully loaded 50 records using parallel loader

================================================================================
JSON WORKFLOW: RESULTS DISPLAY - 2024-01-15 14:35:45
================================================================================
JSON DATA:
{
  "step": "HAZARD EXPOSURE RESULTS",
  "summary": {
    "total_results_rows": 50,
    "total_columns": 15,
    "asset_count": 50
  },
  "sample_results": [...]
}
================================================================================
```

### File Verification

Both files are generated in the same directory:
- `climate_hazards_analysis/static/input_files/combined_output.csv`
- `climate_hazards_analysis/static/input_files/combined_output.json`

## Migration Path to JSON-Only

Once testing is complete, migration to JSON-only is simple:

### Step 1: Update Loader Preference
```python
# Change from prefer_json=True to prefer_json=True (already done)
# Remove CSV fallback when confident
data, columns = json_csv_loader.load_analysis_results(
    csv_path=None,  # Remove CSV entirely
    json_path=combined_json_path,
    prefer_json=True
)
```

### Step 2: Remove CSV Generation
Comment out or remove CSV generation code in `climate_hazards_analysis.py`:
```python
# Remove lines 1058-1064 (CSV generation)
# Keep only JSON generation (lines 1066-1096)
```

### Step 3: Clean Up Fallback Code
Remove CSV fallback logic in views.py once confident in JSON reliability.

## Benefits of Parallel Approach

1. **Zero Downtime**: System works during testing phase
2. **Gradual Migration**: Test JSON while maintaining CSV compatibility
3. **Risk-Free**: CSV fallback ensures system always works
4. **Easy Rollback**: Return to CSV-only if issues arise
5. **Rich Metadata**: JSON format provides additional analysis information
6. **Better Debugging**: Console logging shows data flow clearly

## Current Status

✅ **IMPLEMENTATION COMPLETE** - Parallel generation is active and working.

🔄 **TESTING PHASE** - System generates both CSV and JSON, prefers JSON for loading.

🎯 **NEXT STEP** - Test with real data and validate JSON functionality.

🚀 **FUTURE** - Once validated, remove CSV generation for pure JSON workflow.