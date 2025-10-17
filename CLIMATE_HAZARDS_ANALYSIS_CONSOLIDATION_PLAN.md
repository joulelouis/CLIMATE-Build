# Climate Hazards Analysis Module Consolidation Plan
## Merging V2 into V1

### Executive Summary

This document outlines a comprehensive migration strategy to consolidate the enhanced features from `climate_hazards_analysis_v2` into the main `climate_hazards_analysis` module while maintaining V1's simplicity and backward compatibility.

## 1. Current State Analysis

### V1 (Main Module) - `climate_hazards_analysis`
**Strengths:**
- Simple, focused workflow (Upload → Analyze → Results)
- Clean URL structure with dedicated map views for each hazard
- Well-integrated with existing analysis modules
- Maintainable codebase with clear separation of concerns

**Limitations:**
- Basic file upload (CSV only)
- No interactive map for facility management
- No sensitivity analysis features
- No real-time data editing capabilities

### V2 (Enhanced Module) - `climate_hazards_analysis_v2`
**Enhancements:**
- Interactive map with facility drawing capabilities
- Multi-format file support (CSV, Excel, Shapefile)
- Sensitivity analysis with archetype-specific parameters
- Real-time table editing and override functionality
- Advanced workflow with 5-step process
- RESTful API endpoints for dynamic data management

**Issues:**
- Debug logging statements need removal
- More complex workflow that may overwhelm new users
- Some code quality issues (duplicate logic, inconsistent error handling)

## 2. File Consolidation Strategy

### 2.1 Keep and Enhance (V1 Files)

**Primary V1 files to retain:**
- `views.py` - Will be enhanced with V2 features
- `urls.py` - Will be expanded with new V2 routes
- `templates/climate_hazards_analysis.html` - Will be enhanced
- Individual map template files (flood_exposure_mapbox.html, etc.) - Keep as-is
- Component templates (result_component.html, upload_facility_component.html) - Keep
- `utils/climate_hazards_analysis.py` - Keep with minor enhancements

### 2.2 Merge from V2

**Key V2 files to integrate:**
- Enhanced view functions from V2 `views.py`
- Interactive map template (`main.html` → rename to `interactive_map.html`)
- Sensitivity analysis templates (`sensitivity_parameters.html`, `sensitivity_results.html`)
- Enhanced results display (`results.html` features)
- Utility functions from V2 `utils.py`
- V2-specific CSS and JavaScript assets

### 2.3 Discard or Refactor

**V2 files to discard:**
- `views.py` (functions will be merged into V1)
- `urls.py` (routes will be merged into V1)
- Backup files (`*_backup.html`)
- Rollback documentation files
- Duplicate components that exist in V1

## 3. Code Migration Steps

### 3.1 Phase 1: Foundation Setup

1. **Backup Current V1 Module**
   ```bash
   cp -r climate_hazards_analysis climate_hazards_analysis_backup_$(date +%Y%m%d)
   ```

2. **Update Module Structure**
   - Create new subdirectories in V1:
     - `templates/climate_hazards_analysis/interactive/`
     - `templates/climate_hazards_analysis/sensitivity/`
     - `static/climate_hazards_analysis/js/interactive/`
     - `static/climate_hazards_analysis/css/sensitivity/`

3. **Consolidate Utils Modules**
   - Merge V2 utility functions into V1 utils
   - Create `utils/facility_management.py` for V2-specific functions
   - Create `utils/sensitivity_analysis.py` for sensitivity features

### 3.2 Phase 2: View Functions Integration

1. **Enhance V1 `views.py`**
   ```python
   # Add new imports from V2
   from .utils.facility_management import (
       standardize_facility_dataframe,
       load_cached_hazard_data,
       combine_facility_with_hazard_data,
       validate_shapefile
   )
   from .utils.sensitivity_analysis import (
       identify_high_risk_assets,
       compute_sensitivity_high_risk_counts
   )

   # Add V2 view functions
   def view_map(request):
       """Interactive map view from V2"""
       # Implementation from V2

   def select_hazards(request):
       """Hazard selection workflow step"""
       # Implementation from V2

   def sensitivity_parameters(request):
       """Sensitivity parameter configuration"""
       # Implementation from V2
   ```

2. **Maintain Backward Compatibility**
   - Keep all existing V1 view functions unchanged
   - Add new V2 functions alongside existing ones
   - Ensure existing URLs continue to work

3. **Clean Up Debug Logging**
   - Remove all `logger.info("🔥 SHOW_RESULTS FUNCTION CALLED! 🔥")` statements
   - Remove debug print statements
   - Keep essential logging for troubleshooting

### 3.3 Phase 3: URL Routing Updates

1. **Expand V1 `urls.py`**
   ```python
   urlpatterns = [
       # Existing V1 URLs (keep for backward compatibility)
       path('', upload_facility_csv, name='upload_facility_csv'),
       path('output-with-exposure/', climate_hazards_analysis, name='climate_hazards_analysis'),
       # ... existing V1 routes ...

       # New V2-inspired routes
       path('interactive/', view_map, name='interactive_map'),
       path('select-hazards/', select_hazards, name='select_hazards'),
       path('sensitivity/', sensitivity_parameters, name='sensitivity_parameters'),
       path('sensitivity-results/', sensitivity_results, name='sensitivity_results'),

       # API endpoints
       path('api/facilities/', get_facility_data, name='get_facility_data'),
       path('api/facilities/add/', add_facility, name='add_facility'),
       path('api/table/save/', save_table_changes, name='save_table_changes'),
   ]
   ```

2. **Maintain Namespace Compatibility**
   - Keep app_name as "climate_hazards_analysis"
   - Use path names that don't conflict with existing routes

### 3.4 Phase 4: Template Consolidation

1. **Reorganize Template Structure**
   ```
   templates/climate_hazards_analysis/
   ├── base.html                     # New base template
   ├── upload.html                   # Keep V1 upload
   ├── climate_hazards_analysis.html # Keep V1 results
   ├── interactive/
   │   ├── map.html                  # From V2 main.html
   │   ├── select_hazards.html       # From V2
   │   └── results.html              # Enhanced from V2
   ├── sensitivity/
   │   ├── parameters.html           # From V2
   │   └── results.html              # From V2
   └── components/
       ├── upload_facility.html      # Keep V1
       ├── result_table.html         # Keep V1
       └── interactive_map.html      # From V2
   ```

2. **Create Base Template System**
   - Extract common header/footer into `base.html`
   - Use template inheritance for consistency
   - Make components reusable across workflows

3. **Template Feature Integration**
   - Merge V2's interactive features into V1 templates
   - Add sensitivity analysis components
   - Implement progressive enhancement (basic features work without JavaScript)

### 3.5 Phase 5: Enhanced Features Integration

1. **File Upload Enhancement**
   ```python
   # Enhance existing upload_facility_csv to support multiple formats
   def upload_facility_csv(request):
       """Enhanced upload supporting CSV, Excel, and Shapefile"""
       if request.method == 'POST' and request.FILES.get('facility_csv'):
           try:
               file = request.FILES['facility_csv']
               ext = os.path.splitext(file.name)[1].lower()

               if ext in ['.xls', '.xlsx']:
                   df = pd.read_excel(file_path)
               elif ext in ['.shp', '.zip']:
                   # Handle shapefile upload
                   gdf = process_shapefile(file_path)
                   df = convert_geodataframe_to_df(gdf)
               else:
                   df = pd.read_csv(file_path)

               # Standardize and process
               df = standardize_facility_dataframe(df)
               # ... rest of processing
   ```

2. **Interactive Map Integration**
   - Add Leaflet.js for interactive mapping
   - Implement facility drawing capabilities
   - Add real-time coordinate validation

3. **Sensitivity Analysis Module**
   - Integrate archetype-specific parameters
   - Add dynamic threshold configuration
   - Implement results comparison views

## 4. Database/Session Data Migration

### 4.1 Session Key Standardization

**Current V1 Keys:**
- `facility_csv_path`
- `selected_dynamic_fields`

**Current V2 Keys:**
- `climate_hazards_v2_facility_data`
- `climate_hazards_v2_selected_hazards`
- `climate_hazards_v2_archetype_params`

**Migration Strategy:**
```python
def migrate_session_data(request):
    """Migrate V2 session data to V1 format during transition"""
    # Check for V2 session data and migrate
    if 'climate_hazards_v2_facility_data' in request.session:
        # Convert to V1 format
        request.session['facility_data'] = request.session['climate_hazards_v2_facility_data']
        request.session['selected_fields'] = request.session['climate_hazards_v2_selected_hazards']

        # Clean up old keys
        del request.session['climate_hazards_v2_facility_data']
        del request.session['climate_hazards_v2_selected_hazards']
```

### 4.2 Backward Compatibility Layer

```python
def get_session_data(request, key, fallback_key=None):
    """Get session data with backward compatibility"""
    if key in request.session:
        return request.session[key]
    elif fallback_key and fallback_key in request.session:
        # Migrate and return
        data = request.session[fallback_key]
        request.session[key] = data
        del request.session[fallback_key]
        return data
    return None
```

## 5. URL Routing Updates

### 5.1 Comprehensive URL Structure

```python
# climate_hazards_analysis/urls.py
from django.urls import path
from .views import (
    # Original V1 views
    upload_facility_csv,
    climate_hazards_analysis,
    water_stress_mapbox_fetch,
    flood_exposure_mapbox_fetch,
    heat_exposure_mapbox_fetch,
    sea_level_rise_mapbox_fetch,
    tropical_cyclone_mapbox_fetch,
    multi_hazard_mapbox_fetch,
    generate_report,

    # New V2-inspired views
    view_map,
    select_hazards,
    show_results,
    sensitivity_parameters,
    sensitivity_results,

    # API endpoints
    get_facility_data,
    add_facility,
    save_table_changes,
    reset_table_data,
    preview_uploaded_file,
)

app_name = "climate_hazards_analysis"

urlpatterns = [
    # Legacy V1 workflow (maintain for backward compatibility)
    path('', upload_facility_csv, name='upload_facility_csv'),
    path('output-with-exposure/', climate_hazards_analysis, name='climate_hazards_analysis'),
    path('generate-report/', generate_report, name='generate_report'),

    # Individual hazard maps (keep V1 approach)
    path('water-stress-mapbox/', water_stress_mapbox_fetch, name='water_stress_mapbox_fetch'),
    path('flood-exposure-mapbox/', flood_exposure_mapbox_fetch, name='flood_exposure_mapbox_fetch'),
    path('heat-exposure-mapbox/', heat_exposure_mapbox_fetch, name='heat_exposure_mapbox_fetch'),
    path('sea-level-rise-mapbox/', sea_level_rise_mapbox_fetch, name='sea_level_rise_mapbox_fetch'),
    path('tropical-cyclone-mapbox/', tropical_cyclone_mapbox_fetch, name='tropical_cyclone_mapbox_fetch'),
    path('multi-hazard-mapbox/', multi_hazard_mapbox_fetch, name='multi_hazard_mapbox_fetch'),

    # Enhanced interactive workflow (new from V2)
    path('interactive/', view_map, name='interactive_map'),
    path('select-hazards/', select_hazards, name='select_hazards'),
    path('results/', show_results, name='show_results'),

    # Sensitivity analysis workflow
    path('sensitivity/', sensitivity_parameters, name='sensitivity_parameters'),
    path('sensitivity/results/', sensitivity_results, name='sensitivity_results'),

    # API endpoints for dynamic functionality
    path('api/facilities/', get_facility_data, name='get_facility_data'),
    path('api/facilities/add/', add_facility, name='add_facility'),
    path('api/preview/', preview_uploaded_file, name='preview_uploaded_file'),
    path('api/table/save/', save_table_changes, name='save_table_changes'),
    path('api/table/reset/', reset_table_data, name='reset_table_data'),
]
```

### 5.2 URL Compatibility Strategy

1. **Permanent Redirects for Deprecated URLs**
   ```python
   # In views.py
   from django.shortcuts import redirect

   def legacy_view_redirect(request):
       return redirect('climate_hazards_analysis:interactive_map', permanent=True)
   ```

2. **Feature Detection in Templates**
   ```html
   {% if request.resolver_match.url_name == 'interactive_map' %}
       <!-- Show enhanced interface -->
   {% else %}
       <!-- Show basic interface -->
   {% endif %}
   ```

## 6. Template Consolidation

### 6.1 Template Hierarchy

```
templates/climate_hazards_analysis/
├── base.html                           # New base template
├── legacy/                             # Original V1 templates
│   ├── upload.html
│   ├── climate_hazards_analysis.html
│   ├── flood_exposure_mapbox.html
│   └── ...
├── interactive/                        # V2-inspired interactive templates
│   ├── map.html                       # From V2 main.html
│   ├── select_hazards.html
│   ├── results.html
│   └── components/
│       ├── facility_marker.html
│       └── drawing_tools.html
├── sensitivity/                        # Sensitivity analysis templates
│   ├── parameters.html
│   ├── results.html
│   └── components/
│       ├── threshold_editor.html
│       └── archetype_selector.html
└── components/                         # Shared components
    ├── upload_form.html
    ├── results_table.html
    ├── map_base.html
    └── navigation.html
```

### 6.2 Base Template Creation

```html
<!-- templates/climate_hazards_analysis/base.html -->
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Climate Hazards Analysis{% endblock %}</title>

    <!-- Base CSS -->
    <link href="{% static 'climate_hazards_analysis/css/base.css' %}" rel="stylesheet">
    {% block extra_css %}{% endblock %}
</head>
<body>
    <!-- Navigation -->
    {% include "climate_hazards_analysis/components/navigation.html" %}

    <!-- Messages -->
    {% if messages %}
        {% for message in messages %}
            <div class="alert alert-{{ message.tags }}">{{ message }}</div>
        {% endfor %}
    {% endif %}

    <!-- Main Content -->
    <main class="container-fluid">
        {% block content %}{% endblock %}
    </main>

    <!-- Footer -->
    {% include "climate_hazards_analysis/components/footer.html" %}

    <!-- Base JavaScript -->
    <script src="{% static 'climate_hazards_analysis/js/base.js' %}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### 6.3 Progressive Enhancement Strategy

```html
<!-- Example: Enhanced upload template -->
{% extends "climate_hazards_analysis/base.html" %}

{% block content %}
<div class="row">
    <div class="col-md-8">
        <!-- Basic upload form (works without JavaScript) -->
        <form id="basic-upload-form" method="post" enctype="multipart/form-data">
            {% csrf_token %}
            <!-- Basic file upload fields -->
        </form>
    </div>

    <div class="col-md-4">
        <!-- Enhanced features (JavaScript-dependent) -->
        <div id="interactive-upload" class="d-none">
            <!-- Drag & drop, file preview, etc. -->
        </div>
    </div>
</div>

<script>
// Progressive enhancement
if (window.FileReader && window.FormData) {
    // Show enhanced features
    document.getElementById('interactive-upload').classList.remove('d-none');
    initializeAdvancedUpload();
}
</script>
{% endblock %}
```

## 7. Utility Function Consolidation

### 7.1 Utils Module Reorganization

```
climate_hazards_analysis/utils/
├── __init__.py
├── climate_hazards_analysis.py    # Main analysis functions (V1, enhanced)
├── facility_management.py         # V2 facility handling functions
├── sensitivity_analysis.py        # Sensitivity analysis utilities
├── data_processing.py            # Shared data processing utilities
├── file_handlers.py              # File format handlers
└── validation.py                 # Input validation utilities
```

### 7.2 Consolidated Utility Functions

**facility_management.py** (from V2 utils.py):
```python
import pandas as pd
import geopandas as gpd
import logging

logger = logging.getLogger(__name__)

def standardize_facility_dataframe(df):
    """Enhanced version with V2 improvements"""
    # Combine best features from both V1 and V2
    pass

def validate_shapefile(gdf):
    """From V2 - validate shapefile structure"""
    pass

def load_cached_hazard_data(hazard_type):
    """From V2 - load pre-computed hazard data"""
    pass

def combine_facility_with_hazard_data(facilities, hazard_data_list):
    """From V2 - enrich facility data"""
    pass

def process_uploaded_file(file, file_path):
    """Handle multiple file formats"""
    ext = os.path.splitext(file.name)[1].lower()

    if ext in ['.xls', '.xlsx']:
        return pd.read_excel(file_path)
    elif ext in ['.shp', '.zip']:
        return process_shapefile(file_path)
    else:
        return pd.read_csv(file_path)
```

**sensitivity_analysis.py** (new module):
```python
def identify_high_risk_assets(data, selected_hazards):
    """From V2 - identify high-risk assets for reporting"""
    pass

def compute_sensitivity_high_risk_counts(sensitivity_results, selected_hazards):
    """From V2 - compute risk counts for scenarios"""
    pass

def apply_sensitivity_parameters(facility_data, archetype_params):
    """Apply archetype-specific sensitivity parameters"""
    pass
```

### 7.3 Enhanced Main Analysis Function

Update `climate_hazards_analysis.py` with V2 enhancements:

```python
def generate_climate_hazards_analysis(
    facility_csv_path=None,
    selected_fields=None,
    buffer_size=0.0009,
    sensitivity_params=None,
    flood_scenarios=None,
    facility_data=None  # New: support direct data input
):
    """
    Enhanced analysis function supporting both V1 and V2 workflows.

    Args:
        facility_csv_path: Path to CSV file (V1 workflow)
        facility_data: Direct facility data (V2 workflow)
        selected_fields: List of selected hazards
        sensitivity_params: Sensitivity analysis parameters
        flood_scenarios: Flood analysis scenarios
    """
    # Handle both file-based and data-based inputs
    if facility_data is None and facility_csv_path:
        facility_data = load_facility_data_from_csv(facility_csv_path)
    elif facility_data is None:
        raise ValueError("Either facility_csv_path or facility_data must be provided")

    # Rest of analysis logic...
```

## 8. Testing Strategy

### 8.1 Test Categories

1. **Backward Compatibility Tests**
   - Verify all V1 URLs still work
   - Test V1 workflow produces same results
   - Ensure session data migration works

2. **New Feature Tests**
   - Test interactive map functionality
   - Verify multi-format file upload
   - Test sensitivity analysis workflow
   - Validate API endpoints

3. **Integration Tests**
   - Test mixed workflows (V1 → V2 features)
   - Verify data consistency between workflows
   - Test error handling and edge cases

### 8.2 Test Implementation

```python
# tests/test_backward_compatibility.py
class TestBackwardCompatibility(TestCase):
    def test_legacy_urls_work(self):
        """Test that all V1 URLs still return 200"""
        legacy_urls = [
            reverse('climate_hazards_analysis:upload_facility_csv'),
            reverse('climate_hazards_analysis:climate_hazards_analysis'),
            reverse('climate_hazards_analysis:flood_exposure_mapbox_fetch'),
        ]

        for url in legacy_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_legacy_workflow_same_results(self):
        """Test that V1 workflow produces identical results"""
        # Upload test file using V1 method
        # Compare results with expected output
        pass

# tests/test_new_features.py
class TestNewFeatures(TestCase):
    def test_interactive_map_upload(self):
        """Test interactive map file upload"""
        pass

    def test_sensitivity_analysis(self):
        """Test sensitivity analysis workflow"""
        pass

    def test_api_endpoints(self):
        """Test new API endpoints"""
        pass

# tests/test_integration.py
class TestIntegration(TestCase):
    def test_mixed_workflow(self):
        """Test using V1 and V2 features together"""
        pass
```

### 8.3 Manual Testing Checklist

1. **File Upload Testing**
   - [ ] CSV upload works (basic and complex files)
   - [ ] Excel file upload (.xlsx, .xls)
   - [ ] Shapefile upload (.shp, .zip)
   - [ ] Invalid file handling
   - [ ] Large file handling

2. **Interactive Map Testing**
   - [ ] Map loads correctly
   - [ ] Facility markers display
   - [ ] Drawing tools work
   - [ ] Coordinate validation
   - [ ] Save/cancel functionality

3. **Analysis Testing**
   - [ ] All hazard types work
   - [ ] Multi-hazard analysis
   - [ ] Error handling
   - [ ] Result display
   - [ ] Export functionality

4. **Sensitivity Analysis Testing**
   - [ ] Parameter configuration
   - [ ] Archetype selection
   - [ ] Results comparison
   - [ ] Report generation

## 9. Rollback Plan

### 9.1 Pre-Migration Backup Strategy

```bash
# Create comprehensive backup
./scripts/pre_migration_backup.sh

#!/bin/bash
# scripts/pre_migration_backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups/migration_${DATE}"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup V1 module
cp -r climate_hazards_analysis $BACKUP_DIR/climate_hazards_analysis_v1

# Backup V2 module
cp -r climate_hazards_analysis_v2 $BACKUP_DIR/climate_hazards_analysis_v2

# Backup database
python manage.py dumpdata > $BACKUP_DIR/database_backup.json

# Create migration rollback script
cat > $BACKUP_DIR/rollback.sh << 'EOF'
#!/bin/bash
echo "Rolling back migration..."
rm -rf climate_hazards_analysis
mv backups/migration_*/climate_hazards_analysis_v1 climate_hazards_analysis
python manage.py migrate
echo "Rollback complete"
EOF

chmod +x $BACKUP_DIR/rollback.sh
echo "Backup complete. Rollback script created at $BACKUP_DIR/rollback.sh"
```

### 9.2 Database Migration Rollback

```python
# migrations/0002_merge_v2_features.py
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('climate_hazards_analysis', '0001_initial'),
    ]

    operations = [
        # Add new fields for V2 features
        migrations.AddField(
            model_name='facility',
            name='geometry',
            field=models.JSONField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='analysis',
            name='sensitivity_parameters',
            field=models.JSONField(null=True, blank=True),
        ),
    ]

# Rollback migration
# migrations/0003_remove_v2_features.py
class Migration(migrations.Migration):
    dependencies = [
        ('climate_hazards_analysis', '0002_merge_v2_features'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='facility',
            name='geometry',
        ),
        migrations.RemoveField(
            model_name='analysis',
            name='sensitivity_parameters',
        ),
    ]
```

### 9.3 Quick Rollback Procedures

1. **Code Rollback (If migration fails early)**
   ```bash
   git checkout main
   git checkout -- climate_hazards_analysis/
   python manage.py migrate climate_hazards_analysis 0001
   ```

2. **Data Rollback (If issues discovered after deployment)**
   ```bash
   # Use backup script
   ./backups/migration_YYYYMMDD_HHMMSS/rollback.sh

   # Or manually restore database
   python manage.py loaddata backups/migration_YYYYMMDD_HHMMSS/database_backup.json
   ```

3. **Feature Flags for Gradual Rollout**
   ```python
   # settings.py
   FEATURES = {
       'INTERACTIVE_MAP': env.bool('ENABLE_INTERACTIVE_MAP', default=False),
       'SENSITIVITY_ANALYSIS': env.bool('ENABLE_SENSITIVITY_ANALYSIS', default=False),
       'ADVANCED_UPLOAD': env.bool('ENABLE_ADVANCED_UPLOAD', default=False),
   }

   # views.py
   if settings.FEATURES['INTERACTIVE_MAP']:
       # Enable interactive map features
   ```

## 10. Deployment Considerations

### 10.1 Deployment Strategy

1. **Blue-Green Deployment**
   - Deploy consolidated module to staging environment
   - Run comprehensive test suite
   - Switch production traffic gradually

2. **Feature Flag Rollout**
   - Deploy with all new features disabled
   - Enable features one by one after monitoring
   - Quick rollback capability if issues arise

3. **Database Migration Strategy**
   - Create migration scripts that preserve existing data
   - Test migrations on copy of production database
   - Schedule maintenance window for database changes

### 10.2 Environment Configuration

```python
# settings/production.py
from .base import *

# Feature flags for production rollout
FEATURES = {
    'INTERACTIVE_MAP': True,      # Enable on day 1
    'SENSITIVITY_ANALYSIS': False, # Enable on day 7
    'ADVANCED_UPLOAD': True,      # Enable on day 1
}

# Logging configuration for monitoring
LOGGING = {
    'loggers': {
        'climate_hazards_analysis': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### 10.3 Monitoring and Alerting

1. **Performance Monitoring**
   - Track response times for new features
   - Monitor memory usage for large file uploads
   - Alert on increased error rates

2. **Usage Analytics**
   - Track which features are being used
   - Monitor workflow completion rates
   - Identify bottlenecks in user journeys

3. **Error Tracking**
   - Enhanced logging for new features
   - Integration with error tracking service (Sentry)
   - Automated alerts for critical errors

### 10.4 Post-Deployment Validation

```bash
# scripts/post_deployment_validation.sh

#!/bin/bash

echo "Validating deployment..."

# Test basic functionality
curl -f http://localhost:8000/climate-hazards/ || exit 1
curl -f http://localhost:8000/climate-hazards/interactive/ || exit 1

# Run automated tests
python manage.py test climate_hazards_analysis.tests.test_integration || exit 1

# Check database migrations
python manage.py showmigrations climate_hazards_analysis | grep -q "\[ \]" || exit 1

echo "Deployment validation successful!"
```

## 11. Implementation Timeline

### Week 1: Preparation and Backup
- [ ] Create comprehensive backups
- [ ] Set up development environment
- [ ] Review and document current functionality

### Week 2: Foundation Work
- [ ] Consolidate utility modules
- [ ] Create new template structure
- [ ] Implement base template system

### Week 3: View Integration
- [ ] Merge V2 view functions into V1
- [ ] Update URL routing
- [ ] Implement session data migration

### Week 4: Template and Frontend
- [ ] Consolidate templates
- [ ] Implement progressive enhancement
- [ ] Add interactive features

### Week 5: Testing and Validation
- [ ] Run comprehensive test suite
- [ ] Perform manual testing
- [ ] Fix identified issues

### Week 6: Deployment
- [ ] Deploy to staging environment
- [ ] User acceptance testing
- [ ] Production deployment with feature flags

### Week 7: Monitoring and Optimization
- [ ] Monitor system performance
- [ ] Collect user feedback
- [ ] Optimize based on usage patterns

## 12. Success Criteria

### Technical Success Criteria
- [ ] All V1 functionality preserved and working
- [ ] New V2 features integrated without breaking existing workflows
- [ ] Performance not degraded (response times within 10% of current)
- [ ] Zero critical bugs in production for first 30 days

### User Experience Success Criteria
- [ ] Users can access both simple (V1) and advanced (V2) workflows
- [ ] Interactive map improves user efficiency
- [ ] Sensitivity analysis provides valuable insights
- [ ] User feedback positive on consolidated interface

### Maintenance Success Criteria
- [ ] Code complexity manageable
- [ ] Documentation complete and up-to-date
- [ ] Team trained on new features
- [ ] Automated tests covering all functionality

This migration plan provides a comprehensive approach to consolidating the enhanced features from V2 into the main V1 module while maintaining backward compatibility and ensuring a smooth transition for users.