# Climate Hazards Analysis V2 - New Architecture Documentation

## Overview

The Climate Hazards Analysis V2 system has been completely refactored to use a stateless, database-first architecture that eliminates session dependencies while maintaining full backward compatibility with existing frontend components.

## Key Architectural Changes

### 1. **Session Dependency Elimination**
- **Before**: Session-based workflow management with complex state tracking
- **After**: Stateless API endpoints with asset-based state management
- **Benefits**: Improved scalability, reliability, and easier testing

### 2. **Unified Asset Handling**
- **Before**: Separate handling for point and polygon assets
- **After**: Unified asset abstraction layer treating all assets consistently
- **Benefits**: Cleaner codebase, reduced complexity, improved maintainability

### 3. **Database-First Approach**
- **Before**: Session data stored temporarily, analysis workflow tied to user sessions
- **After**: All asset and analysis data persisted in database with proper ownership tracking
- **Benefits**: Data persistence, better audit trail, multi-user support

## New Architecture Components

### Core Service Layer

#### `asset_service.py`
The main service layer providing stateless operations for asset management:

```python
# Create assets
asset = AssetService.create_point_asset(name="Facility A", latitude=40.7, longitude=-74.0)
polygon_asset = AssetService.create_polygon_asset(name="Zone B", polygon_geometry=geojson)

# Query assets
assets = AssetService.get_all_assets()
filtered_assets = AssetService.get_assets_within_bounds(min_lat, max_lat, min_lng, max_lng)

# Analysis operations
results = AssetService.get_asset_analysis_results(asset_id)
AssetService.save_hazard_analysis_result(asset_id, hazard_type, result_data)
```

#### `asset_abstraction.py`
Abstraction layer providing unified interface for different asset types:

```python
# Create asset objects
asset = AssetFactory.create_asset(asset_model)
point_asset = AssetFactory.create_point_asset(name, lat, lng)
polygon_asset = AssetFactory.create_polygon_asset(name, geometry)

# Work with collections
collection = AssetRepository.get_all_assets()
filtered = collection.filter_by_bounds(bounds).filter_by_hazard(hazard_types)
```

#### `api_views.py`
Stateless API endpoints that replace session-dependent views:

```python
# Core asset APIs
GET /api/v2/assets/                    # List assets
POST /api/v2/assets/                   # Create asset
GET /api/v2/assets/{id}/               # Get asset details
PUT /api/v2/assets/{id}/               # Update asset
DELETE /api/v2/assets/{id}/            # Delete asset

# Analysis APIs
GET /api/v2/assets/{id}/analysis/      # Get analysis results
POST /api/v2/assets/{id}/analysis/     # Save analysis results

# Granular analysis APIs
POST /api/v2/assets/{id}/granular/     # Initialize granular analysis
GET /api/v2/assets/{id}/granular/      # Get granular analysis data
PUT /api/v2/assets/{id}/granular/      # Update analysis status
```

### Database Schema Changes

#### Asset Model Enhancements
```python
class Asset(models.Model):
    # Original fields maintained
    name = models.CharField(max_length=255)
    archetype = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=10, decimal_places=6)
    longitude = models.DecimalField(max_digits=10, decimal_places=6)
    polygon_geometry = models.JSONField(null=True, blank=True)
    asset_type = models.CharField(max_length=20, choices=[...])

    # NEW: Ownership tracking (replaces session dependencies)
    owner = models.CharField(max_length=255, null=True, blank=True)
    source = models.CharField(max_length=100, null=True, blank=True)
    batch_id = models.CharField(max_length=100, null=True, blank=True)

    # NEW: Analysis workflow tracking
    last_analysis_date = models.DateTimeField(null=True, blank=True)
    analysis_version = models.CharField(max_length=20, default='v1.0')

    # NEW: Quality and validation
    is_validated = models.BooleanField(default=False)
    validation_errors = models.JSONField(default=list, blank=True)
    quality_score = models.FloatField(null=True, blank=True)
```

#### New Database Indexes
- Owner-based indexing for multi-tenant support
- Source and batch_id for data lineage tracking
- Analysis status for workflow management
- Validation status for data quality monitoring

### Backward Compatibility Layer

#### `compatibility_layer.py`
Ensures existing frontend components work without changes:

```python
# Legacy endpoints that use new backend
GET /api/facility-data/          # Still works, uses new service layer
POST /api/add-facility/          # Still works, uses new service layer
GET /api/polygon-assets/         # Still works, uses new service layer
GET /api/assets/{id}/analysis/   # Still works, uses new service layer
```

## Migration Guide

### For Frontend Development

#### No Changes Required!
All existing frontend components continue to work exactly as before:
- HazardLayerManager class unchanged
- Interactive popup system unchanged
- Search functionality unchanged
- Severity-based visualization unchanged
- Display mode toggles unchanged
- CSS styling unchanged

#### Optional: Use New API Endpoints
When ready, frontend can migrate to new stateless endpoints:

```javascript
// Old way (still works)
fetch('/climate-hazards-analysis-v2/api/facility-data/')

// New way (recommended)
fetch('/climate-hazards-analysis-v2/api/v2/assets/')
```

### For Backend Development

#### New Service Usage
```python
# OLD: Session-based workflow
session_manager = GranularAnalysisSessionManager()
session_manager.initialize_granular_workflow(request)
session_manager.store_polygon_geometry(request, geometry)

# NEW: Stateless asset management
asset = AssetService.create_polygon_asset(name, geometry)
analysis = AssetAnalysisService.initialize_granular_analysis(asset.id, grid_spacing)
```

#### Asset Ownership
```python
# NEW: Track asset ownership instead of session
asset = AssetService.create_point_asset(
    name="Facility",
    latitude=40.7,
    longitude=-74.0,
    owner="organization_123",
    source="csv_upload_2024",
    batch_id="batch_456"
)
```

### Database Migration

The migration has been applied automatically:
- Session dependencies removed
- New ownership fields added
- Database indexes optimized
- Data constraints added

## API Usage Examples

### Creating Assets

```python
# Point asset
asset = AssetService.create_point_asset(
    name="Main Office",
    latitude=40.7128,
    longitude=-74.0060,
    archetype="commercial",
    properties={"floors": 5, "year_built": 2010}
)

# Polygon asset
polygon_geometry = {
    "type": "Polygon",
    "coordinates": [[
        [-74.0060, 40.7128],
        [-74.0050, 40.7128],
        [-74.0050, 40.7138],
        [-74.0060, 40.7138],
        [-74.0060, 40.7128]
    ]]
}

polygon_asset = AssetService.create_polygon_asset(
    name="Property Boundary",
    polygon_geometry=polygon_geometry,
    owner="company_xyz"
)
```

### Running Analysis

```python
# Save analysis results
result_data = {
    "severity": "high",
    "value": 0.85,
    "confidence": 0.92,
    "metadata": {"source": "model_v2", "date": "2024-01-15"}
}

AssetService.save_hazard_analysis_result(
    asset_id=asset.id,
    hazard_type="sea_level_rise",
    result_data=result_data,
    scenario="rcp_8.5_2050"
)

# Initialize granular analysis for polygon
AssetAnalysisService.initialize_granular_analysis(
    asset_id=polygon_asset.id,
    grid_spacing=0.01
)
```

### Querying Assets

```python
# Get assets with analysis
assets_with_data = AssetRepository.get_assets_with_analysis()

# Filter by location
bounds = AssetBounds(40.0, 41.0, -75.0, -73.0)
nearby_assets = AssetRepository.get_assets_within_bounds(**bounds.as_dict())

# Filter by owner
company_assets = Asset.objects.filter(owner="company_xyz")

# Get statistics
stats = AssetService.get_asset_statistics()
```

## Benefits of New Architecture

### 1. **Scalability**
- Stateless design allows horizontal scaling
- Database-first approach supports load balancing
- Session independence enables multi-server deployments

### 2. **Reliability**
- No session loss during server restarts
- Persistent analysis state
- Better error handling and recovery

### 3. **Maintainability**
- Unified asset handling reduces code duplication
- Clear separation of concerns
- Comprehensive test coverage possible

### 4. **Multi-Tenant Support**
- Owner-based asset isolation
- Source tracking for data lineage
- Batch operations support

### 5. **Data Quality**
- Built-in validation framework
- Quality scoring system
- Comprehensive audit trail

## Testing

### Backend Testing
```python
# Test asset creation
def test_create_point_asset():
    asset = AssetService.create_point_asset("Test", 40.7, -74.0)
    assert asset.asset_type == "point"
    assert asset.name == "Test"

# Test analysis results
def test_analysis_results():
    results = AssetService.get_asset_analysis_results(asset.id)
    assert 'analysis_results' in results
```

### Integration Testing
```python
# Test API endpoints
def test_api_endpoints():
    client = APIClient()
    response = client.get('/api/v2/assets/')
    assert response.status_code == 200
    assert len(response.data['data']) > 0
```

## Troubleshooting

### Common Issues

#### 1. GIS Dependencies Missing
- **Issue**: GIS libraries not available in deployment environment
- **Solution**: New architecture removes GIS dependencies, uses pure Python geometry

#### 2. Session Data Loss
- **Issue**: Analysis workflow lost between requests
- **Solution**: All state is now stored in database, use asset_id for workflow tracking

#### 3. Memory Usage
- **Issue**: High memory usage with large datasets
- **Solution**: Use database pagination and filtering instead of in-memory processing

### Migration Checklist

- [ ] Database migration applied successfully
- [ ] New service layer functions correctly
- [ ] Legacy compatibility layer working
- [ ] Frontend components unchanged behavior
- [ ] API endpoints responding correctly
- [ ] Analysis workflow functioning
- [ ] Performance testing completed

## Future Enhancements

### Planned Features
1. **Async Processing**: Background task processing for large analyses
2. **Caching Layer**: Redis-based caching for frequently accessed data
3. **API Versioning**: Formal API versioning strategy
4. **Webhooks**: Real-time notifications for analysis completion
5. **Export Features**: Enhanced data export capabilities

### Extension Points
- Custom hazard analysis plugins
- Additional asset types support
- Third-party integrations
- Advanced visualization components

---

## Support

For questions about the new architecture or migration issues:
1. Check this documentation
2. Review the code comments in service layer
3. Test with the compatibility layer
4. Gradually migrate to new API endpoints

The new architecture maintains full backward compatibility while providing a solid foundation for future enhancements.