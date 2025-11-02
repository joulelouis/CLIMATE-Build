"""
Django test settings for Climate Hazards Analysis V2.

This module contains test-specific configuration optimized for running
the upload asset data functionality tests efficiently.
"""

import os
import tempfile
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'test-secret-key-for-climate-hazards-analysis-v2-do-not-use-in-production'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'climate_hazards_analysis_v2',
    # Testing-specific apps
    'django_nose',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'climate_hazards_analysis.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'climate_hazards_analysis.wsgi.application'

# Database
# https://docs.djangoproject.com/en/stable/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = []

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(tempfile.mkdtemp(), 'static')
STATICFILES_DIRS = [
    BASE_DIR / 'climate_hazards_analysis_v2' / 'static',
]

# Media files (uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(tempfile.mkdtemp(), 'media')
FILE_UPLOAD_TEMP_DIR = tempfile.mkdtemp()

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Logging configuration for testing
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(tempfile.mkdtemp(), 'test.log'),
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'climate_hazards_analysis_v2': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
    },
}

# File upload settings for testing
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
UPLOAD_FILE_MAX_SIZE = 50 * 1024 * 1024  # 50MB

# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Test-specific settings
TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'
NOSE_ARGS = [
    '--verbosity=2',
    '--with-coverage',
    '--cover-package=climate_hazards_analysis_v2',
    '--cover-html',
    '--cover-html-dir=htmlcov',
    '--cover-erase',
]

# Email settings for testing (console backend)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Cache settings for testing (dummy cache)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Session settings for testing
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400  # 24 hours

# Security settings (relaxed for testing)
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = False
SECURE_BROWSER_XSS_FILTER = False
X_FRAME_OPTIONS = 'DONT-CROSS-SITE-SCRIPT-URL'  # Disable for testing

# CSRF settings for testing
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = False

# Performance test settings
PERFORMANCE_TEST_DATA_SIZE = 1000  # Number of records for performance tests
PERFORMANCE_TEST_TIMEOUT = 30  # Seconds

# External API settings (mocked for testing)
MOCK_EXTERNAL_APIS = True
HAZARD_DATA_API_URL = 'http://mock-api.example.com/hazard-data'

# Geospatial libraries test settings
GEOS_LIBRARY_PATH = None  # Use system default
GDAL_LIBRARY_PATH = None  # Use system default
PROJ_LIBRARY_PATH = None  # Use system default

# Test data generation settings
GENERATE_TEST_DATA_ON_DEMAND = True
TEST_DATA_CACHE_DIR = tempfile.mkdtemp()

# Integration test settings
INTEGRATION_TEST_TIMEOUT = 60  # Seconds
INTEGRATION_TEST_MAX_RETRIES = 3

# Performance monitoring for tests
ENABLE_PERFORMANCE_MONITORING = False  # Set to True to enable detailed profiling

# Test fixtures settings
FIXTURE_DIRS = [
    BASE_DIR / 'climate_hazards_analysis_v2' / 'tests' / 'fixtures',
]

# Celery settings (disabled for testing)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Django Debug Toolbar (disabled for tests, but available if needed)
DEBUG_TOOLBAR = False
if DEBUG_TOOLBAR:
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ['127.0.0.1']

# Selenium settings for browser tests (if needed)
SELENIUM_WEBDRIVER = 'chromedriver'
SELENIUM_HEADLESS = True
SELENIUM_WINDOW_SIZE = (1920, 1080)

# Coverage settings
COVERAGE_THRESHOLD = 80  # Minimum coverage percentage
COVERAGE_EXCLUDE_FILES = [
    '*/migrations/*',
    '*/tests/*',
    '*/venv/*',
    '*/env/*',
    'manage.py',
    'settings/*',
    'wsgi.py',
]

# Test parallel execution settings
TEST_PARALLEL = False
TEST_PROCESSES = 4

# Memory profiling settings
MEMORY_PROFILING = False
MEMORY_PROFILING_THRESHOLD = 100 * 1024 * 1024  # 100MB

# Time travel testing settings (if needed)
FREEZE_TIME = False
TEST_TIMEZONE = 'UTC'

# Mock data settings
MOCK_HAZARD_DATA = True
MOCK_GEOCODING_API = True

# File format validation settings
ALLOWED_UPLOAD_FORMATS = ['.csv', '.xls', '.xlsx', '.shp', '.zip', '.gpkg']
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB

# Test-specific middleware
if os.environ.get('DJANGO_TEST_ENVIRONMENT') == 'true':
    # Add test-specific middleware
    MIDDLEWARE.insert(0, 'django.middleware.common.BrokenLinkEmailsMiddleware')

# Database connection settings for testing
DATABASE_CONNECTION_TIMEOUT = 30
DATABASE_POOL_SIZE = 5

# Async test settings
ASYNC_TEST_TIMEOUT = 30

# Security scanning settings for tests
SECURITY_SCAN_ENABLED = False

# Documentation generation settings
GENERATE_TEST_DOCUMENTATION = False

# Test data cleanup settings
CLEANUP_TEST_FILES_AFTER_RUN = True
CLEANUP_TEST_DATABASE_AFTER_RUN = True

# Performance benchmarking settings
ENABLE_BENCHMARKING = False
BENCHMARK_RESULTS_DIR = tempfile.mkdtemp()

# Error reporting settings for tests
ERROR_REPORTING_ENABLED = False
SENTRY_DSN = None

# Feature flags for testing
FEATURE_FLAGS = {
    'ENABLE_LARGE_FILE_UPLOADS': True,
    'ENABLE_ADVANCED_VALIDATION': True,
    'ENABLE_PERFORMANCE_MONITORING': False,
    'ENABLE_BETA_FEATURES': False,
}

# Import test utilities
try:
    from .test_utils import configure_test_environment
    configure_test_environment()
except ImportError:
    pass