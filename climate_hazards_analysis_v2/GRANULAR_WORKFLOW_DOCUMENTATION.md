# Complete Granular Analysis Workflow Documentation

## Overview

The Granular Analysis Workflow provides a comprehensive end-to-end pipeline for climate hazard analysis of polygon assets. It transforms user-drawn polygons into detailed exposure assessments through multiple grid points, providing rich insights into hazard exposure across entire geographic areas.

## Workflow Architecture

### Pipeline Stages

1. **Polygon Drawing** → User draws polygon boundary on map
2. **Grid Generation** → System creates uniform grid points within polygon
3. **Hazard Analysis** → API calls for each grid point and selected hazard
4. **Results Processing** → Aggregation and statistical analysis
5. **Table Integration** → Formatted results for hazard exposure table
6. **Visualization** → Heatmap generation for spatial analysis

### Key Components

- **GranularAnalysisWorkflowService**: Main orchestration service
- **GranularAnalysisProcessor**: Batch processing engine
- **GranularAnalysisResult**: Database model for grid point results
- **HeatmapData**: Pre-computed visualization data
- **Session Management**: Workflow state tracking

## API Endpoints

### Execute Complete Workflow

**Endpoint**: `POST /api/granular/workflow/execute/`

**Description**: Executes the complete end-to-end granular analysis workflow

**Request Body**:
```json
{
    "asset_name": "My Polygon Asset",
    "polygon_geometry": {
        "type": "Polygon",
        "coordinates": [[
            [-122.4194, 37.7749],
            [-122.4194, 37.7849],
            [-122.4094, 37.7849],
            [-122.4094, 37.7749],
            [-122.4194, 37.7749]
        ]]
    },
    "selected_hazards": ["Heat", "Flooding", "Sea Level Rise"],
    "archetype": "commercial",
    "grid_spacing": 0.001,
    "scenario": "current"
}
```

**Response**:
```json
{
    "success": true,
    "workflow_results": {
        "asset_id": 123,
        "asset_name": "My Polygon Asset",
        "workflow_duration": 45.2,
        "grid_points_generated": 150,
        "granular_results_created": 450,
        "hazard_analysis_results": {...},
        "aggregated_results": {...},
        "heatmap_data_generated": 3,
        "table_results": [...],
        "selected_hazards": ["Heat", "Flooding"],
        "message": "Successfully completed granular analysis"
    },
    "asset_id": 123,
    "redirect_url": "/results/?asset_id=123&granular_analysis=true"
}
```

### Get Workflow Results Table

**Endpoint**: `GET /api/granular/workflow/results/{asset_id}/`

**Description**: Retrieves formatted results for the hazard exposure table

**Query Parameters**:
- `hazards`: List of hazard types (optional, defaults to all available)

**Response**:
```json
{
    "success": true,
    "data": [
        {
            "Facility": "My Polygon Asset",
            "Lat": 37.7799,
            "Long": -122.4144,
            "Archetype": "commercial",
            "Asset Type": "Polygon (Granular Analysis)",
            "Hazard Type": "Heat",
            "Grid Points Processed": 150,
            "Total Grid Points": 150,
            "Analysis Status": "completed",
            "Overall Risk": "medium",
            "Mean Exposure": 25.5,
            "Min Exposure": 10.2,
            "Max Exposure": 45.8,
            "Median Exposure": 24.1,
            "Success Rate": 100.0,
            "Low Risk %": "60.0%",
            "Medium Risk %": "30.0%",
            "High Risk %": "10.0%"
        }
    ],
    "columns": ["Facility", "Lat", "Long", ...],
    "asset_info": {...},
    "summary": {...}
}
```

### Get Workflow Status

**Endpoint**: `GET /api/granular/status/{asset_id}/`

**Description**: Retrieves current workflow status and progress

**Response**:
```json
{
    "success": true,
    "asset_id": 123,
    "analysis_status": "completed",
    "progress": {
        "total_points": 150,
        "completed_points": 150,
        "failed_points": 0,
        "progress_percentage": 100.0
    },
    "hazard_statistics": {
        "Heat": {
            "count": 150,
            "mean_value": 25.5,
            "risk_distribution": {"low": 90, "medium": 45, "high": 15}
        }
    }
}
```

## Usage Examples

### JavaScript/Frontend Integration

```javascript
// Execute complete workflow
async function executeGranularWorkflow(polygonGeometry, assetName, hazards) {
    const response = await fetch('/api/granular/workflow/execute/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            asset_name: assetName,
            polygon_geometry: polygonGeometry,
            selected_hazards: hazards,
            archetype: 'commercial',
            grid_spacing: 0.001
        })
    });

    const result = await response.json();
    if (result.success) {
        // Redirect to results page
        window.location.href = result.redirect_url;
    } else {
        // Handle error
        console.error('Workflow failed:', result.error);
    }
}

// Get workflow results table
async function getWorkflowResultsTable(assetId) {
    const response = await fetch(`/api/granular/workflow/results/${assetId}/`);
    const result = await response.json();

    if (result.success) {
        // Display results in data table
        displayResultsTable(result.data, result.columns);
    }
}

// Monitor workflow progress
async function monitorWorkflowProgress(assetId) {
    const response = await fetch(`/api/granular/status/${assetId}/`);
    const result = await response.json();

    if (result.success) {
        updateProgressBar(result.progress.progress_percentage);
        updateStatusDisplay(result.analysis_status);
    }
}
```

### Python/Django Integration

```python
from climate_hazards_analysis_v2.granular_workflow_service import (
    GranularAnalysisWorkflowService, execute_granular_analysis_workflow
)

# Direct service usage
def run_granular_analysis():
    polygon_geometry = {
        "type": "Polygon",
        "coordinates": [[
            [-122.4194, 37.7749],
            [-122.4194, 37.7849],
            [-122.4094, 37.7849],
            [-122.4094, 37.7749],
            [-122.4194, 37.7749]
        ]]
    }

    results = execute_granular_analysis_workflow(
        polygon_geometry=polygon_geometry,
        asset_name="Analysis Area",
        selected_hazards=["Heat", "Flooding", "Sea Level Rise"],
        archetype="commercial",
        grid_spacing=0.001
    )

    if results['success']:
        print(f"Analysis completed for asset {results['asset_id']}")
        print(f"Generated {results['grid_points_generated']} grid points")
        return results
    else:
        print(f"Analysis failed: {results['error']}")
        return None

# Service class usage
def advanced_workflow():
    service = GranularAnalysisWorkflowService(
        grid_spacing=0.0005,  # Higher resolution
        batch_size=100,       # Larger batches
        max_workers=8         # More parallelism
    )

    # Execute with custom parameters
    results = service.execute_complete_workflow(
        polygon_geometry=custom_polygon,
        asset_name="High Resolution Analysis",
        selected_hazards=["Heat", "Water Stress", "Coastal Flooding"],
        archetype="industrial"
    )

    return results
```

## Configuration Options

### Grid Spacing

Controls the resolution of grid points within the polygon:
- **0.001°**: ~100m spacing (default)
- **0.0005°**: ~50m spacing (higher resolution)
- **0.002°**: ~200m spacing (faster processing)

### Batch Processing Parameters

- **batch_size**: Number of grid points processed per batch (default: 50)
- **max_workers**: Maximum concurrent threads (default: 4)

### Hazard Types

Supported hazard types:
- `Heat`: Heat exposure analysis
- `Flooding`: Flood risk assessment
- `Sea Level Rise`: Coastal inundation
- `Water Stress`: Water scarcity analysis
- `Storm Surge`: Extreme weather events
- `Landslide`: Slope stability assessment

## Data Models

### Asset Model

```python
class Asset(models.Model):
    name = models.CharField(max_length=255)
    archetype = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=10, decimal_places=6)
    longitude = models.DecimalField(max_digits=10, decimal_places=6)
    polygon_geometry = models.JSONField(null=True, blank=True)
    asset_type = models.CharField(max_length=20, choices=[
        ('point', 'Point Facility'),
        ('polygon', 'Polygon Asset'),
    ])

    # Granular analysis fields
    has_granular_analysis = models.BooleanField(default=False)
    granular_grid_spacing = models.FloatField(null=True, blank=True)
    granular_analysis_status = models.CharField(max_length=20, choices=[
        ('none', 'No Granular Analysis'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ])
    granular_grid_points_count = models.IntegerField(default=0)
    granular_analysis_progress = models.FloatField(default=0.0)
```

### GranularAnalysisResult Model

```python
class GranularAnalysisResult(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='granular_results')
    latitude = models.DecimalField(max_digits=10, decimal_places=6)
    longitude = models.DecimalField(max_digits=10, decimal_places=6)
    grid_row = models.IntegerField()
    grid_col = models.IntegerField()
    grid_spacing = models.FloatField()

    hazard_type = models.CharField(max_length=50)
    scenario = models.CharField(max_length=50, default='current')
    result_data = models.JSONField(default=dict)

    processing_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ])
    analysis_date = models.DateTimeField(auto_now_add=True)
```

### HeatmapData Model

```python
class HeatmapData(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='heatmap_data')
    hazard_type = models.CharField(max_length=50)
    scenario = models.CharField(max_length=50, default='current')

    grid_rows = models.IntegerField()
    grid_cols = models.IntegerField()
    grid_spacing = models.FloatField()

    min_lat = models.DecimalField(max_digits=10, decimal_places=6)
    max_lat = models.DecimalField(max_digits=10, decimal_places=6)
    min_lng = models.DecimalField(max_digits=10, decimal_places=6)
    max_lng = models.DecimalField(max_digits=10, decimal_places=6)

    heatmap_values = models.JSONField(default=list)

    # Statistical summaries
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    mean_value = models.FloatField(null=True, blank=True)
    median_value = models.FloatField(null=True, blank=True)
```

## Performance Considerations

### Scalability

The workflow is designed to handle:
- **Small polygons**: < 100 grid points (seconds)
- **Medium polygons**: 100-1000 grid points (minutes)
- **Large polygons**: 1000-10000 grid points (tens of minutes)

### Optimization Tips

1. **Grid Spacing**: Use appropriate spacing for your use case
2. **Batch Size**: Tune batch_size based on available memory
3. **Max Workers**: Set based on CPU cores (avoid over-threading)
4. **Hazard Selection**: Only analyze required hazards

### Resource Management

- Automatic cleanup of failed processing
- Memory-efficient batch processing
- Database connection pooling
- Progress tracking for long-running jobs

## Error Handling

### Common Error Scenarios

1. **Invalid Polygon Geometry**
   ```json
   {
       "success": false,
       "error": "Invalid polygon geometry - expected GeoJSON Polygon"
   }
   ```

2. **Grid Spacing Out of Range**
   ```json
   {
       "success": false,
       "error": "Grid spacing must be between 0 and 1 degree"
   }
   ```

3. **Hazard Data Unavailable**
   ```json
   {
       "success": false,
       "error": "No hazard data available for Heat"
   }
   ```

### Recovery Strategies

- **Partial Success**: Workflow continues even if some grid points fail
- **Retry Mechanism**: Failed batches can be retried individually
- **Rollback**: Database transactions ensure data consistency

## Testing

### Running Tests

```bash
# Run all granular workflow tests
python manage.py test climate_hazards_analysis_v2.tests.test_granular_workflow

# Run with coverage
coverage run --source='climate_hazards_analysis_v2' manage.py test climate_hazards_analysis_v2.tests.test_granular_workflow
coverage report

# Specific test categories
python manage.py test climate_hazards_analysis_v2.tests.test_granular_workflow.GranularWorkflowServiceTest
```

### Test Coverage

- ✅ Grid point generation
- ✅ Polygon asset creation
- ✅ Hazard analysis execution
- ✅ Results aggregation
- ✅ API endpoint validation
- ✅ Error handling
- ✅ End-to-end workflow
- ✅ Performance benchmarks

## Troubleshooting

### Common Issues

**Issue**: Workflow takes too long
**Solution**:
- Reduce grid spacing (larger grid cells)
- Decrease max_workers to avoid system overload
- Select fewer hazard types

**Issue**: Memory errors
**Solution**:
- Reduce batch_size parameter
- Use smaller grid spacing
- Monitor system resources

**Issue**: Failed grid points
**Solution**:
- Check hazard data availability
- Validate polygon geometry
- Review API connectivity

### Debug Mode

Enable debug logging:
```python
import logging
logging.getLogger('climate_hazards_analysis_v2').setLevel(logging.DEBUG)
```

## Security Considerations

### Input Validation
- Polygon geometry validation
- Coordinate range checking
- Grid spacing limits
- Hazard type whitelist

### Rate Limiting
- API endpoint rate limiting
- Concurrent job limiting
- Resource usage monitoring

### Data Protection
- Session-based authentication
- CSRF token validation
- Input sanitization
- SQL injection prevention

## Future Enhancements

### Planned Features
- Real-time processing with WebSockets
- Advanced grid generation algorithms
- Machine learning-based risk assessment
- Multi-scenario analysis
- Export to additional formats

### Performance Improvements
- Distributed processing support
- Caching optimization
- Database query optimization
- Asynchronous task processing

---

**Version**: 1.0.0
**Last Updated**: 2025-10-29
**Maintainer**: Climate Hazards Analysis Team