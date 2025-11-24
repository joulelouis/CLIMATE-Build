# Unified JSON System for Multiple Asset File Uploads

## Overview

Successfully implemented a unified JSON system that consolidates all uploaded asset data from multiple files into a single, comprehensive JSON structure. This allows users to upload multiple asset data files and have them automatically stored in the same JSON database.

## Key Features Implemented

### 1. **Unified JSON Structure**
All uploaded assets are automatically consolidated into a single JSON structure per upload session:

```json
{
  "metadata": {
    "total_assets": 5,
    "upload_session_id": "abc123def456789",
    "created_at": "2024-01-15T14:30:00.123456",
    "files_uploaded": [
      {
        "filename": "philippine_facilities.csv",
        "file_type": "text/csv",
        "upload_id": "file-uuid-1",
        "asset_count": 2
      },
      {
        "filename": "regional_assets.xlsx",
        "file_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "upload_id": "file-uuid-2",
        "asset_count": 2
      },
      {
        "filename": "land_management.shp",
        "file_type": "application/octet-stream",
        "upload_id": "file-uuid-3",
        "asset_count": 1
      }
    ],
    "asset_types": {
      "point_assets": 4,
      "polygon_assets": 1
    }
  },
  "assets": [
    {
      "database_id": 1,
      "name": "Manila Factory",
      "latitude": 14.5,
      "longitude": 121.0,
      "archetype": "Manufacturing",
      "asset_type": "point",
      "source": "uploaded_file",
      "properties": {
        "original_filename": "philippine_facilities.csv",
        "file_upload_id": "file-uuid-1",
        "upload_method": "json_workflow",
        "original_data": {...}
      }
    },
    // ... additional assets
  ]
}
```

### 2. **Session-Based Consolidation**
- **Single Session ID**: All uploads in the same session share a unified JSON
- **Automatic Consolidation**: New files are automatically added to existing unified JSON
- **File Tracking**: Each asset maintains reference to its source file
- **Real-time Updates**: Unified JSON updates with each new file upload

### 3. **Enhanced Console Logging**
Real-time console display shows consolidated upload progress:

```
================================================================================
JSON WORKFLOW: UPLOAD ASSET DATA - 2025-11-17 20:06:03
================================================================================
JSON DATA:
{
  "step": "UPLOAD ASSET DATA",
  "summary": {
    "total_facilities": 2,
    "file_uploaded": "philippine_facilities.csv",
    "database_records_created": 2
  },
  "unified_assets": {
    "session_total_assets": 5,
    "total_files_uploaded": 3,
    "session_asset_types": {"point_assets": 4, "polygon_assets": 1},
    "uploaded_files": [
      {"filename": "philippine_facilities.csv", "asset_count": 2},
      {"filename": "regional_assets.xlsx", "asset_count": 2},
      {"filename": "land_management.shp", "asset_count": 1}
    ],
    "upload_session_id": "abc123..."
  }
}
================================================================================
```

## Implementation Details

### Updated Files

#### `climate_hazards_analysis_v2/views.py`
- **NEW**: `_create_unified_assets_json()` - Creates consolidated JSON from all uploaded assets
- **NEW**: `_get_all_uploaded_assets_json()` - Retrieves unified JSON for session
- **NEW**: `_update_unified_json_on_file_removal()` - Updates JSON when files are removed
- **NEW**: `_export_unified_assets_to_file()` - Exports unified JSON to file
- **UPDATED**: `_remove_file_from_session()` - Now updates unified JSON on file removal
- **UPDATED**: Main upload flow - Creates unified JSON after each upload

#### `climate_hazards_analysis_v2/json_console_simple.py`
- **ENHANCED**: `log_upload_step()` - Now displays unified assets information
- **NEW**: Shows session totals, file count, and consolidated progress

### Core Functions

#### Unified JSON Creation
```python
def _create_unified_assets_json(request):
    """
    Consolidates all uploaded assets from database into single JSON structure.
    - Tracks files uploaded and their asset counts
    - Maintains file-to-asset relationships
    - Counts point vs polygon assets
    - Stores in session for easy access
    """
```

#### Unified JSON Retrieval
```python
def _get_all_uploaded_assets_json(request):
    """
    Gets or creates unified JSON for current session.
    - Checks session cache first
    - Creates if not exists
    - Returns complete consolidated structure
    """
```

## How It Works

### 1. **First File Upload**
```
User uploads: philippine_facilities.csv (2 assets)
Unified JSON Created:
- Total Assets: 2
- Total Files: 1
- Files: [philippine_facilities.csv (2 assets)]
```

### 2. **Second File Upload**
```
User uploads: regional_assets.xlsx (2 assets)
Unified JSON Updated:
- Total Assets: 4
- Total Files: 2
- Files: [philippine_facilities.csv (2), regional_assets.xlsx (2)]
```

### 3. **Third File Upload**
```
User uploads: land_management.shp (1 polygon asset)
Unified JSON Final:
- Total Assets: 5
- Total Files: 3
- Files: [philippine_facilities.csv (2), regional_assets.xlsx (2), land_management.shp (1)]
- Asset Types: Point(4), Polygon(1)
```

## Storage Architecture

### **Database Storage** (Primary)
- All individual assets stored in `Asset` table with JSON fields
- Each asset has `properties` containing original file data and metadata
- Unified JSON stored in session as reference to database records

### **Session Storage** (Cache)
- `unified_uploaded_assets_json`: Complete consolidated structure
- `climate_hazards_v2_uploaded_asset_ids`: List of asset IDs in session
- `climate_hazards_v2_uploaded_files`: Per-file tracking metadata

### **File Export** (Optional)
- `_export_unified_assets_to_file()` can create downloadable JSON files
- Includes all metadata and consolidated structure
- Timestamped filenames for version control

## Benefits Achieved

1. **Single Source of Truth**: All uploaded assets in one unified structure
2. **File Traceability**: Each asset maintains link to its source file
3. **Session Management**: Automatic consolidation per upload session
4. **Real-time Progress**: Console shows cumulative upload progress
5. **Type Consolidation**: Handles both point and polygon assets seamlessly
6. **Easy Export**: Can export all assets as single JSON file
7. **Database Efficiency**: Individual asset storage with unified view
8. **Flexible Queries**: Can query all assets or filter by source file

## Usage Instructions

### For Users
1. **Upload Multiple Files**: Sequentially upload any combination of CSV, XLSX, SHP, GPKG files
2. **Watch Console Progress**: See real-time JSON display showing total consolidated assets
3. **All Assets Combined**: System automatically consolidates all files into single JSON structure
4. **Export if Needed**: Unified JSON can be exported for backup or analysis

### For Developers
```python
# Get unified JSON for current session
unified_assets = _get_all_uploaded_assets_json(request)

# Get all asset IDs from session
asset_ids = request.session.get('climate_hazards_v2_uploaded_asset_ids', [])

# Query all uploaded assets
assets = Asset.objects.filter(source='uploaded_file', id__in=asset_ids)

# Export unified JSON to file
file_path, error = _export_unified_assets_to_file(request, 'my_assets.json')
```

## Console Output Examples

### After Multiple Files Upload:
```
{
  "unified_assets": {
    "session_total_assets": 5,
    "total_files_uploaded": 3,
    "session_asset_types": {
      "point_assets": 4,
      "polygon_assets": 1
    },
    "uploaded_files": [
      {
        "filename": "philippine_facilities.csv",
        "file_type": "text/csv",
        "asset_count": 2
      },
      {
        "filename": "regional_assets.xlsx",
        "file_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "asset_count": 2
      },
      {
        "filename": "land_management.shp",
        "file_type": "application/octet-stream",
        "asset_count": 1
      }
    ],
    "upload_session_id": "abc123..."
  }
}
```

## Status

✅ **IMPLEMENTATION COMPLETE** - All features fully implemented and tested

🎯 **PRODUCTION READY** - System ready for multiple file uploads

📊 **UNIFIED JSON ACTIVE** - All uploaded assets automatically consolidated

🔄 **REAL-TIME DISPLAY** - Console shows cumulative upload progress

🗄️ **DATABASE INTEGRATION** - Individual asset storage with unified view

---

*This unified JSON system provides comprehensive consolidation of multiple asset file uploads into a single, manageable JSON structure with full traceability and real-time progress tracking.*