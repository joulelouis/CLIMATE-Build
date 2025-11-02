# Upload Asset Data - Unit Test Documentation

## Overview

This document provides comprehensive testing guidelines and strategy for the "Upload Asset Data" functionality in the Climate Hazards Analysis Django application. The upload functionality supports multiple file formats including CSV, Excel (.xls/.xlsx), Shapefile (.shp), Zip archives (.zip) containing shapefiles, and GeoPackage (.gpkg) files.

## Test Strategy

### Testing Approach

1. **Black Box Testing**: Focus on input/output behavior without internal code knowledge
2. **White Box Testing**: Test internal logic, validation, and data processing functions
3. **Integration Testing**: Test interaction between views, models, utilities, and external libraries
4. **Performance Testing**: Validate performance with large files and concurrent uploads
5. **Security Testing**: Ensure malicious file uploads are properly handled

### Test Coverage Goals

- **Minimum Coverage**: 80% line coverage for all upload-related code
- **Critical Path Coverage**: 100% coverage for file validation, processing, and error handling
- **Edge Case Coverage**: All identified edge cases and boundary conditions

## Components to Test

### 1. Views (`views.py`)

#### `view_map(request)`
- **Purpose**: Main upload page view handling file uploads
- **Test Cases**:
  - GET request returns correct template
  - POST with valid CSV file
  - POST with valid Excel file
  - POST with valid Shapefile
  - POST with valid GeoPackage file
  - POST with invalid file format
  - POST with corrupted file
  - POST with no file
  - Session data preservation
  - Error handling and messages

#### `add_facility(request)`
- **Purpose**: API endpoint for adding facilities via coordinates
- **Test Cases**:
  - POST with valid point facility data
  - POST with valid polygon asset data
  - POST with missing required fields
  - POST with invalid coordinates
  - POST with empty name
  - Database integration
  - Session integration
  - Error responses

#### `preview_uploaded_file(request)`
- **Purpose**: Preview uploaded file content
- **Test Cases**:
  - Valid file path retrieval
  - File not found scenarios
  - Encoding handling (UTF-8, Latin-1)
  - Permission issues
  - Malformed file paths

### 2. Models (`models.py`)

#### `Asset` Model
- **Purpose**: Store point and polygon asset data
- **Test Cases**:
  - Model creation and validation
  - Point asset creation
  - Polygon asset creation
  - Auto-detection of asset type
  - Centroid calculation for polygons
  - GeoJSON property methods
  - Database constraints
  - Session key associations

### 3. Utilities (`utils.py`)

#### `standardize_facility_dataframe(df)`
- **Purpose**: Standardize column names and data structure
- **Test Cases**:
  - Various column name formats
  - Missing columns handling
  - Data type conversion
  - Invalid data handling
  - Empty dataframes
  - Large datasets

#### `validate_shapefile(gdf)`
- **Purpose**: Validate shapefile structure and content
- **Test Cases**:
  - Valid shapefiles with different geometry types
  - Empty shapefiles
  - Invalid geometry types
  - Missing required columns
  - Coordinate reference system validation
  - Multi-geometry handling

## Test Data Requirements

### Valid Test Files

1. **CSV Files**:
   ```
   facility.csv - Standard format with required columns
   facility_various_columns.csv - Different column naming conventions
   facility_with_special_chars.csv - Special characters and encoding
   facility_large.csv - Large dataset (1000+ records)
   ```

2. **Excel Files**:
   ```
   facility.xlsx - Excel 2007+ format
   facility.xls - Excel 97-2003 format
   facility_multiple_sheets.xlsx - Multiple worksheets
   facility_with_formulas.xlsx - Contains formulas
   ```

3. **Geospatial Files**:
   ```
   facilities.shp + associated files - Standard shapefile
   facilities.zip - Compressed shapefile
   facilities.gpkg - GeoPackage format
   facilities_multi_geom.shp - Multiple geometry types
   facilities_invalid_crs.shp - Invalid coordinate system
   ```

### Invalid Test Files

1. **Format Issues**:
   - Text files (.txt)
   - Image files (.jpg, .png)
   - PDF files (.pdf)
   - Executable files (.exe)

2. **Content Issues**:
   - Empty files
   - Corrupted files
   - Files with invalid headers
   - Files with invalid coordinate values
   - Files with missing required columns

## Test Environment Setup

### Requirements

```python
# Django Testing Framework
django.test.TestCase
django.test.client.Client
django.core.files.uploadedfile.SimpleUploadedFile

# External Libraries
pandas
geopandas
openpyxl
xlrd
shapely

# Testing Utilities
unittest.mock
tempfile
io.BytesIO
```

### Database Configuration

```python
# settings/test.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Use in-memory SQLite for faster tests
# Disable migrations for speed
# Create test fixtures for consistent data
```

### File System Setup

```python
# Test directory structure
tests/
├── __init__.py
├── test_views.py
├── test_models.py
├── test_utils.py
├── test_integration.py
├── fixtures/
│   ├── test_files/
│   │   ├── valid/
│   │   └── invalid/
│   └── data_fixtures.json
└── documentation/
    └── upload_asset_data_test_documentation.md
```

## Test Case Matrix

### File Upload Tests

| Test Case | File Type | Valid/Invalid | Expected Result | Priority |
|-----------|-----------|---------------|-----------------|----------|
| CSV-001 | CSV | Valid | Success | P1 |
| CSV-002 | CSV | Empty file | Error | P1 |
| CSV-003 | CSV | Invalid headers | Error | P1 |
| CSV-004 | CSV | Large file (>10MB) | Success/Performance | P2 |
| XLS-001 | Excel | Valid .xlsx | Success | P1 |
| XLS-002 | Excel | Valid .xls | Success | P1 |
| XLS-003 | Excel | Multiple sheets | Success | P2 |
| SHP-001 | Shapefile | Valid | Success | P1 |
| SHP-002 | Shapefile | Missing .shx | Error | P1 |
| SHP-003 | Shapefile | Invalid geometry | Error | P1 |
| ZIP-001 | Zip | Valid shapefile archive | Success | P1 |
| ZIP-002 | Zip | No shapefile inside | Error | P1 |
| GPKG-001 | GeoPackage | Valid | Success | P1 |
| GPKG-002 | GeoPackage | Invalid format | Error | P1 |
| INV-001 | Text file | Invalid format | Error | P1 |
| INV-002 | Binary file | Malicious content | Error | P1 |

### Data Validation Tests

| Test Case | Validation Type | Test Data | Expected Result | Priority |
|-----------|-----------------|-----------|-----------------|----------|
| VAL-001 | Coordinates | Valid lat/lng | Success | P1 |
| VAL-002 | Coordinates | Invalid lat (>90) | Error | P1 |
| VAL-003 | Coordinates | Invalid lng (>180) | Error | P1 |
| VAL-004 | Coordinates | Missing coordinates | Error | P1 |
| VAL-005 | Facility Name | Valid name | Success | P1 |
| VAL-006 | Facility Name | Empty name | Error | P1 |
| VAL-007 | Facility Name | Special characters | Success | P2 |
| VAL-008 | Data Types | Numeric validation | Success | P1 |
| VAL-009 | Data Types | String in numeric field | Error | P1 |

### Integration Tests

| Test Case | Integration | Scenario | Expected Result | Priority |
|-----------|-------------|----------|-----------------|----------|
| INT-001 | Session | Upload + Session storage | Data persisted | P1 |
| INT-002 | Database | Polygon asset creation | Asset saved | P1 |
| INT-003 | File System | File upload + storage | File saved | P1 |
| INT-004 | Map Display | Upload + Map rendering | Markers displayed | P1 |
| INT-005 | Error Recovery | Failed upload + retry | Success | P2 |

## Mocking Strategy

### External Dependencies

1. **File System Operations**:
   ```python
   @mock.patch('os.makedirs')
   @mock.patch('builtins.open')
   def test_file_storage_mock(self, mock_open, mock_makedirs):
       # Test file storage logic
   ```

2. **Pandas/GeoPandas Operations**:
   ```python
   @mock.patch('pandas.read_csv')
   @mock.patch('geopandas.read_file')
   def test_data_processing_mock(self, mock_read_csv, mock_read_file):
       # Test data processing without actual file I/O
   ```

3. **Database Operations**:
   ```python
   @mock.patch('django.db.models.Model.save')
   def test_database_operations_mock(self, mock_save):
       # Test database interactions
   ```

### Test Data Creation

```python
class TestDataFactory:
    @staticmethod
    def create_valid_csv_content():
        return "Facility,Lat,Long,Archetype\nTest Facility,40.7128,-74.0060,Office\n"

    @staticmethod
    def create_invalid_coordinates_csv():
        return "Facility,Lat,Long\nInvalid,95.0,200.0\n"

    @staticmethod
    def create_mock_geodataframe():
        return mock.Mock(spec=gpd.GeoDataFrame)
```

## Performance Testing

### Test Scenarios

1. **Large File Upload**:
   - Files: 1MB, 10MB, 50MB
   - Expected: Upload and process within 30 seconds

2. **Concurrent Uploads**:
   - Multiple simultaneous uploads
   - Expected: No data corruption, proper session handling

3. **Memory Usage**:
   - Monitor memory during large file processing
   - Expected: Memory usage scales appropriately

### Performance Test Implementation

```python
class PerformanceTestCase(TestCase):
    def test_large_file_upload_performance(self):
        """Test upload performance with large files"""
        with self.assertMaxQueries(10):  # Limit database queries
            # Test large file upload
```

## Security Testing

### Security Test Cases

1. **Path Traversal**:
   ```python
   def test_path_traversal_attack(self):
       # Attempt to upload files with malicious paths
       malicious_file = SimpleUploadedFile("../../../etc/passwd", b"content")
       response = self.client.post(reverse('upload'), {'file': malicious_file})
       self.assertEqual(response.status_code, 400)
   ```

2. **File Type Validation**:
   ```python
   def test_malicious_file_upload(self):
       # Test uploading executable files
       malicious_file = SimpleUploadedFile("malware.exe", b"malicious content")
       response = self.client.post(reverse('upload'), {'file': malicious_file})
       self.assertContains(response, "Invalid file type")
   ```

3. **Content Validation**:
   ```python
   def test_file_content_validation(self):
       # Test files with invalid content structure
       pass
   ```

## Error Handling Tests

### Error Scenarios

1. **File System Errors**:
   - Disk full
   - Permission denied
   - Invalid path

2. **Network Errors**:
   - Upload interruption
   - Timeout handling

3. **Data Processing Errors**:
   - Invalid data formats
   - Corrupted files
   - Memory errors

## Continuous Integration

### CI/CD Pipeline Configuration

```yaml
# .github/workflows/test.yml
name: Test Upload Functionality
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: |
          pytest climate_hazards_analysis_v2/tests/ --cov=climate_hazards_analysis_v2 --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v1
```

## Test Execution Commands

### Running Tests

```bash
# Run all upload-related tests
python manage.py test climate_hazards_analysis_v2.tests.test_views.UploadAssetDataTestCase

# Run with coverage
coverage run --source='.' manage.py test climate_hazards_analysis_v2.tests
coverage report
coverage html

# Run specific test categories
python manage.py test climate_hazards_analysis_v2.tests.test_views -k "test_csv"
python manage.py test climate_hazards_analysis_v2.tests.test_views -k "test_excel"
python manage.py test climate_hazards_analysis_v2.tests.test_views -k "test_shapefile"

# Run performance tests
python manage.py test climate_hazards_analysis_v2.tests.test_performance --settings=settings.test_performance
```

### Test Configuration

```python
# settings/test.py
INSTALLED_APPS += ['django_nose']
TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'

# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()
```

## Expected Outcomes

### Success Criteria

1. **All Test Cases Pass**: 100% test execution success
2. **Coverage Requirements**: Minimum 80% code coverage
3. **Performance Benchmarks**: All performance tests meet criteria
4. **Security Validation**: All security tests pass
5. **Documentation**: Complete test documentation maintained

### Failure Handling

1. **Test Failures**:
   - Immediate notification to development team
   - Detailed error reports with stack traces
   - Regression analysis for failed tests

2. **Coverage Shortfalls**:
   - Identify untested code paths
   - Create additional test cases
   - Prioritize critical functionality

3. **Performance Issues**:
   - Profile bottlenecks
   - Optimize code paths
   - Re-run performance tests

## Maintenance and Updates

### Test Maintenance

1. **Regular Updates**:
   - Review test cases monthly
   - Update for new features
   - Remove obsolete tests

2. **Test Data Updates**:
   - Refresh test fixtures
   - Update file format support
   - Maintain valid/invalid test files

3. **Documentation Updates**:
   - Keep documentation current
   - Add new test scenarios
   - Update coverage requirements

### Version Control

```bash
# Test file naming conventions
test_<component>_<functionality>.py
test_views_upload.py
test_models_asset.py
test_utils_validation.py

# Commit message standards
test: Add CSV upload validation tests
fix: Resolve Excel file processing test failures
refactor: Improve test data factory methods
```

## Conclusion

This comprehensive test documentation provides the foundation for robust testing of the Upload Asset Data functionality. Regular execution of these tests ensures reliability, security, and performance of the file upload features in the Climate Hazards Analysis application.

The testing strategy focuses on:
- **Comprehensive coverage** of all upload scenarios
- **Early detection** of bugs and issues
- **Performance validation** for scalability
- **Security assurance** against malicious uploads
- **Maintainable test suite** for long-term sustainability

Following this documentation will help maintain high code quality and user confidence in the upload functionality.