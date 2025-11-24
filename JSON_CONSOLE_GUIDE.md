# JSON Console Display Guide for Climate Hazards Analysis

This guide explains how to view JSON data in the console for each step of the climate hazards analysis workflow.

## Overview

The JSON Console Display feature shows you the underlying JSON data at each step of the workflow:
1. **Upload Asset Data** - Shows uploaded facility data and database records created
2. **Select Hazards and Scenarios** - Shows hazard selections and parameters
3. **Hazard Exposure Results** - Shows analysis results and table structure

## How to Use

### Method 1: Run Django Development Server

```bash
cd C:\CLIMATE\CLIMATE-Build
python manage.py runserver
```

The console window where you run the server will display JSON data for each workflow step.

### Method 2: Check Console in Real-time

1. Start the Django development server
2. Open your browser and go to `http://localhost:8000/climate-hazards-analysis-v2/`
3. Perform the workflow steps
4. Watch the console window for JSON output

## What You Will See

### Step 1: Upload Asset Data

When you upload a file (CSV, Excel, Shapefile, GeoPackage), you'll see:

```
============================================================
🔍 UPLOAD ASSET DATA - JSON WORKFLOW - 2024-01-15 14:30:25
============================================================
📋 JSON DATA:

{
  "step": "UPLOAD ASSET DATA",
  "summary": {
    "total_facilities": 50,
    "file_uploaded": "my_assets.csv",
    "file_size": 2048,
    "database_records_created": 50
  },
  "file_metadata": {
    "name": "my_assets.csv",
    "size": 2048,
    "type": "text/csv"
  },
  "sample_facilities": [
    {
      "Facility": "Factory A",
      "Lat": 14.5,
      "Long": 121.0,
      "Asset Archetype": "Manufacturing"
    }
  ],
  "created_asset_ids": [1, 2, 3, 4, 5]
}
============================================================
```

### Step 2: Select Hazards and Scenarios

When you select hazards and submit the form, you'll see:

```
============================================================
🔍 HAZARD SELECTION - JSON WORKFLOW - 2024-01-15 14:32:10
============================================================
📋 JSON DATA:

{
  "step": "SELECT HAZARDS AND SCENARIOS",
  "summary": {
    "total_assets_selected": 50,
    "hazards_selected": 3,
    "selected_hazards": ["Flood", "Heat", "Water Stress"],
    "parameters_provided": true
  },
  "asset_ids": [1, 2, 3, 4, 5],
  "hazards": ["Flood", "Heat", "Water Stress"],
  "parameters": {
    "source": "hazard_selection_form",
    "total_hazards_available": 7,
    "session_updated": true
  }
}
============================================================
```

### Step 3: Hazard Exposure Results

When you view the results page, you'll see:

```
============================================================
🔍 RESULTS DISPLAY - JSON WORKFLOW - 2024-01-15 14:35:45
============================================================
📋 JSON DATA:

{
  "step": "HAZARD EXPOSURE RESULTS",
  "summary": {
    "total_results_rows": 50,
    "total_columns": 15,
    "column_groups": ["Facility Information", "Flood", "Heat", "Water Stress"],
    "asset_count": 50
  },
  "table_structure": {
    "columns": ["Facility", "Asset Archetype", "Lat", "Long", "Flood Depth (meters)", "Days over 35° Celsius"],
    "groups": {
      "Facility Information": 4,
      "Flood": 1,
      "Heat": 1,
      "Water Stress": 1
    }
  },
  "sample_results": [
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
============================================================
```

## Benefits

1. **Debug Data Issues**: See exactly what data is being processed at each step
2. **Verify JSON Workflow**: Confirm data is being stored in JSON format correctly
3. **Monitor Performance**: Track how many records are being processed
4. **Understand Data Flow**: See how data moves from upload through analysis to results

## Configuration

The JSON console logger is automatically enabled when you run the Django development server. The output is configured to:

- Show a maximum of 500 characters per display (truncated for long data)
- Use formatted JSON with proper indentation
- Include timestamps for each log entry
- Display sample data (first 2-3 records) to avoid overwhelming the console

## Troubleshooting

### No Console Output

If you don't see JSON output in the console:

1. Make sure you're running the development server (`python manage.py runserver`)
2. Check that you're performing the workflow steps in the browser
3. Verify the `json_console_logger.py` file exists in the `climate_hazards_analysis_v2` directory

### Too Much Output

If the console output is too verbose:

1. The logger automatically truncates long JSON data
2. Only sample records are shown (first 2-3)
3. You can modify the `max_length` parameter in `json_console_logger.py` if needed

### Error Messages

If you see error messages in the JSON display:

1. Check the error details in the JSON output
2. Verify your input data format
3. Ensure coordinates are valid (latitude/longitude)

## Integration with Development

The JSON console display integrates seamlessly with:

- **Django Development Server**: Automatic console output
- **Database Storage**: Shows what's being saved to Asset records
- **Session Management**: Displays session data for workflow state
- **API Endpoints**: Logs JSON workflow API calls

This makes it easy to debug and monitor your climate hazards analysis workflow in real-time!