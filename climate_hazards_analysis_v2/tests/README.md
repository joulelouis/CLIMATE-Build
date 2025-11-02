# Climate Hazards Analysis V2 - Testing Guide

This directory contains comprehensive test suites for the Climate Hazards Analysis V2 Django application, with a focus on the Upload Asset Data functionality.

## Directory Structure

```
tests/
├── __init__.py
├── test_upload_asset_data.py          # Main upload functionality tests
├── test_views.py                      # View-specific tests (if separated)
├── test_models.py                     # Model tests (if separated)
├── test_utils.py                      # Utility function tests (if separated)
├── test_integration.py                # Integration tests (if separated)
├── test_performance.py                # Performance tests (if separated)
├── fixtures/
│   ├── __init__.py
│   ├── test_data_factory.py           # Test data factory
│   ├── data_fixtures.json             # Database fixtures
│   └── test_files/
│       ├── valid/                     # Valid test files
│       │   ├── standard_facilities.csv
│       │   ├── varied_columns.csv
│       │   └── special_characters.csv
│       └── invalid/                   # Invalid test files
│           ├── invalid_coordinates.csv
│           ├── malformed.csv
│           ├── missing_columns.csv
│           └── empty.csv
└── documentation/
    ├── upload_asset_data_test_documentation.md
    └── testing_setup_guide.md
```

## Quick Start

### Prerequisites

- Python 3.8+
- Django 4.0+
- Required packages: pandas, geopandas, openpyxl, xlrd, shapely

### Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install pytest pytest-django pytest-cov
   ```

2. **Set Up Test Database**:
   ```bash
   python manage.py migrate --settings=project.settings.test
   ```

3. **Run Tests**:
   ```bash
   # Run all upload-related tests
   python manage.py test climate_hazards_analysis_v2.tests.test_upload_asset_data

   # Run with coverage
   coverage run --source='.' manage.py test climate_hazards_analysis_v2.tests
   coverage report
   coverage html
   ```

## Test Configuration

### Settings Configuration

Create a test settings file or update your existing settings:

```python
# settings/test.py
import os
from base import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Logging for tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# Media and file upload settings for testing
MEDIA_ROOT = tempfile.mkdtemp()
FILE_UPLOAD_TEMP_DIR = tempfile.mkdtemp()
```

### Environment Variables

Set up environment variables for testing:

```bash
export DJANGO_SETTINGS_MODULE=project.settings.test
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

## Running Tests

### Basic Test Commands

```bash
# Run all tests in the module
python manage.py test climate_hazards_analysis_v2.tests

# Run specific test class
python manage.py test climate_hazards_analysis_v2.tests.test_upload_asset_data.UploadAssetDataTestCase

# Run specific test method
python manage.py test climate_hazards_analysis_v2.tests.test_upload_asset_data.UploadAssetDataTestCase.test_upload_valid_csv_file

# Run with verbose output
python manage.py test climate_hazards_analysis_v2.tests --verbosity=2

# Run with parallel execution (if installed)
python manage.py test climate_hazards_analysis_v2.tests --parallel
```

### Test Categories

```bash
# File upload tests
python manage.py test climate_hazards_analysis_v2.tests -k "upload"

# Validation tests
python manage.py test climate_hazards_analysis_v2.tests -k "validation"

# Error handling tests
python manage.py test climate_hazards_analysis_v2.tests -k "error"

# Security tests
python manage.py test climate_hazards_analysis_v2.tests -k "security"

# Integration tests
python manage.py test climate_hazards_analysis_v2.tests -k "integration"
```

### Performance Testing

```bash
# Run performance tests
python manage.py test climate_hazards_analysis_v2.tests.test_performance --settings=project.settings.test_performance

# Run with profiling
python -m cProfile -o profile.stats manage.py test climate_hazards_analysis_v2.tests.test_performance
```

## Coverage Analysis

### Basic Coverage

```bash
# Generate coverage report
coverage run --source='climate_hazards_analysis_v2' manage.py test climate_hazards_analysis_v2.tests
coverage report

# Generate HTML report
coverage html
open htmlcov/index.html
```

### Coverage Configuration

Create `.coveragerc`:

```ini
[run]
source = climate_hazards_analysis_v2
omit =
    */migrations/*
    */tests/*
    */venv/*
    */env/*
    manage.py
    settings.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:

[html]
directory = htmlcov
```

## Test Data Management

### Using the Test Data Factory

```python
from tests.fixtures.test_data_factory import TestDataFactory

# Create test files
csv_file = TestDataFactory.create_valid_csv_file()
excel_file = TestDataFactory.create_excel_file()
zip_file = TestDataFactory.create_shapefile_zip()

# Create mock data
mock_assets = TestDataFactory.create_mock_asset_objects()
session_data = TestDataFactory.create_test_session_data()
```

### Loading Fixtures

```python
# Load database fixtures
python manage.py loaddata tests/fixtures/data_fixtures.json

# In tests
from django.core.management import call_command
call_command('loaddata', 'tests/fixtures/data_fixtures.json')
```

## Continuous Integration

### GitHub Actions Configuration

```yaml
# .github/workflows/test.yml
name: Test Climate Hazards Analysis

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-django pytest-cov

    - name: Run tests
      run: |
        python manage.py test climate_hazards_analysis_v2.tests --cov=climate_hazards_analysis_v2 --cov-report=xml

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v1
      with:
        file: ./coverage.xml
```

### Local CI Simulation

```bash
# Run tests with multiple Python versions
pyenv local 3.8 3.9 3.10

for version in 3.8 3.9 3.10; do
    pyenv local $version
    python -m venv env-$version
    source env-$version/bin/activate
    pip install -r requirements.txt
    python manage.py test climate_hazards_analysis_v2.tests
done
```

## Debugging Tests

### Using pdb

```python
# In your test method
import pdb; pdb.set_trace()

# Or use Django's test client debugging
response = self.client.post(url, data)
print(response.content.decode())
```

### Using Django Debug Toolbar

```python
# settings/test.py
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
INTERNAL_IPS = ['127.0.0.1']
```

### Test Logging

```python
import logging
logger = logging.getLogger(__name__)

class TestCase(TestCase):
    def test_something(self):
        logger.info("Starting test")
        # Test logic
        logger.debug("Test data: %s", test_data)
```

## Test Best Practices

### Writing Tests

1. **Descriptive Test Names**:
   ```python
   def test_upload_valid_csv_file_with_standard_columns(self):
       # Good: descriptive

   def test_csv(self):
       # Bad: not descriptive
   ```

2. **Test Independence**:
   ```python
   def setUp(self):
       # Each test gets fresh data
       self.test_data = TestDataFactory.create_valid_csv_file()

   def tearDown(self):
       # Clean up after each test
       pass
   ```

3. **One Assertion Per Test**:
   ```python
   def test_upload_success_response(self):
       response = self.client.post(self.upload_url, {'file': self.test_file})
       self.assertEqual(response.status_code, 200)

   def test_upload_session_data_created(self):
       self.client.post(self.upload_url, {'file': self.test_file})
       self.assertIn('climate_hazards_v2_facility_data', self.client.session)
   ```

### Mocking

```python
from unittest.mock import patch, Mock

@patch('climate_hazards_analysis_v2.views.pandas.read_csv')
def test_csv_processing_with_mock(self, mock_read_csv):
    mock_read_csv.return_value = pd.DataFrame({'Facility': ['Test']})
    # Test logic
```

### Test Data Factory Usage

```python
class TestCase(TestCase):
    def setUp(self):
        self.test_files = {
            'valid_csv': TestDataFactory.create_valid_csv_file(),
            'invalid_csv': TestDataFactory.create_malformed_csv_file(),
            'excel_file': TestDataFactory.create_excel_file(),
        }
```

## Troubleshooting

### Common Issues

1. **Database Errors**:
   ```bash
   # Reset test database
   python manage.py flush --noinput
   python manage.py migrate --fake
   ```

2. **Import Errors**:
   ```bash
   # Check Python path
   python -c "import sys; print(sys.path)"
   export PYTHONPATH=$PYTHONPATH:$(pwd)
   ```

3. **File Permission Issues**:
   ```bash
   # Set proper permissions
   chmod -R 755 climate_hazards_analysis_v2/static/
   ```

4. **Memory Issues with Large Tests**:
   ```python
   # Use transactions for faster cleanup
   class TransactionTestCase(TestCase):
       def setUp(self):
           self.transaction = transaction.atomic()

       def tearDown(self):
           self.transaction.rollback()
   ```

### Performance Optimization

```python
# Use setUpClass for expensive operations
class UploadTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.large_file = TestDataFactory.create_large_csv_file(1000)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # Cleanup
```

## Advanced Testing

### Browser Testing with Selenium

```python
from django.test import LiveServerTestCase
from selenium import webdriver

class UploadIntegrationTestCase(LiveServerTestCase):
    def setUp(self):
        self.selenium = webdriver.Chrome()
        super().setUp()

    def tearDown(self):
        self.selenium.quit()
        super().tearDown()

    def test_file_upload_via_browser(self):
        self.selenium.get(f'{self.live_server_url}/upload/')
        # Browser automation logic
```

### API Testing

```python
from rest_framework.test import APITestCase

class UploadAPITestCase(APITestCase):
    def test_upload_api_endpoint(self):
        response = self.client.post('/api/upload/', {
            'file': self.test_file
        }, format='multipart')
        self.assertEqual(response.status_code, 201)
```

## Contributing

When adding new tests:

1. Follow the existing naming conventions
2. Add test data to the factory if reusable
3. Update documentation
4. Ensure minimum 80% coverage
5. Run tests before submitting

## Resources

- [Django Testing Documentation](https://docs.djangoproject.com/en/stable/topics/testing/)
- [pytest-django Documentation](https://pytest-django.readthedocs.io/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Factory Boy Documentation](https://factoryboy.readthedocs.io/)

For specific questions or issues, refer to the comprehensive test documentation in `documentation/upload_asset_data_test_documentation.md`.