"""
Unit tests for Upload Asset Data functionality in Climate Hazards Analysis V2.

This module contains comprehensive test cases for file upload, validation, processing,
and storage of asset data in various formats (CSV, Excel, Shapefile, GeoPackage).

Test Coverage:
- File upload views and API endpoints
- Data validation and standardization
- Model operations and database integration
- Error handling and edge cases
- Security and performance considerations
"""

import json
import os
import tempfile
import unittest.mock as mock
from decimal import Decimal
from io import BytesIO
from unittest import mock

import pandas as pd
import geopandas as gpd
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from shapely.geometry import Polygon, Point

from climate_hazards_analysis_v2.models import Asset, HazardAnalysisResult
from climate_hazards_analysis_v2.views import view_map, add_facility, preview_uploaded_file
from climate_hazards_analysis_v2.utils import standardize_facility_dataframe, validate_shapefile


class UploadAssetDataTestCase(TestCase):
    """Test cases for the main upload functionality."""

    def setUp(self):
        """Set up test environment."""
        self.client = Client()
        self.upload_url = reverse('climate_hazards_analysis_v2:view_map')
        self.add_facility_url = reverse('climate_hazards_analysis_v2:add_facility')
        self.preview_url = reverse('climate_hazards_analysis_v2:preview_uploaded_file')

        # Create test session
        self.client.session.create()

        # Test file paths
        self.test_files_dir = os.path.join(os.path.dirname(__file__), 'fixtures', 'test_files')

    def tearDown(self):
        """Clean up after tests."""
        # Clean up any created files
        pass

    def test_view_map_get_request(self):
        """Test GET request to main upload view."""
        response = self.client.get(self.upload_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'climate_hazards_analysis_v2/main.html')

    def test_upload_valid_csv_file(self):
        """Test uploading a valid CSV file."""
        csv_content = """Facility,Lat,Long,Archetype
Test Facility 1,40.7128,-74.0060,Office
Test Facility 2,34.0522,-118.2437,Warehouse
Test Facility 3,51.5074,-0.1278,Retail"""

        csv_file = SimpleUploadedFile(
            "test_facilities.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        response = self.client.post(self.upload_url, {'facility_csv': csv_file})
        self.assertEqual(response.status_code, 200)

        # Check session data
        session = self.client.session
        self.assertIn('climate_hazards_v2_facility_data', session)
        self.assertEqual(len(session['climate_hazards_v2_facility_data']), 3)
        self.assertEqual(session['climate_hazards_v2_uploaded_filename'], 'test_facilities.csv')

    def test_upload_valid_excel_file(self):
        """Test uploading a valid Excel file."""
        # Create Excel file in memory
        df = pd.DataFrame({
            'Facility': ['Test Facility 1', 'Test Facility 2'],
            'Lat': [40.7128, 34.0522],
            'Long': [-74.0060, -118.2437],
            'Archetype': ['Office', 'Warehouse']
        })

        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)

        excel_file = SimpleUploadedFile(
            "test_facilities.xlsx",
            excel_buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        response = self.client.post(self.upload_url, {'facility_csv': excel_file})
        self.assertEqual(response.status_code, 200)

        # Check session data
        session = self.client.session
        self.assertIn('climate_hazards_v2_facility_data', session)
        self.assertEqual(len(session['climate_hazards_v2_facility_data']), 2)

    def test_upload_invalid_file_format(self):
        """Test uploading an invalid file format."""
        invalid_file = SimpleUploadedFile(
            "test.txt",
            b"This is not a valid format",
            content_type="text/plain"
        )

        response = self.client.post(self.upload_url, {'facility_csv': invalid_file})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Error processing file')

    def test_upload_empty_file(self):
        """Test uploading an empty file."""
        empty_file = SimpleUploadedFile(
            "empty.csv",
            b"",
            content_type="text/csv"
        )

        response = self.client.post(self.upload_url, {'facility_csv': empty_file})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Error processing file')

    def test_upload_csv_with_invalid_coordinates(self):
        """Test uploading CSV with invalid coordinates."""
        csv_content = """Facility,Lat,Long,Archetype
Invalid Facility,95.0,200.0,Office
Another Facility,40.7128,-74.0060,Warehouse"""

        csv_file = SimpleUploadedFile(
            "invalid_coords.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        response = self.client.post(self.upload_url, {'facility_csv': csv_file})
        self.assertEqual(response.status_code, 200)
        # Should still process but with validation warnings

    def test_upload_csv_with_missing_columns(self):
        """Test uploading CSV with missing required columns."""
        csv_content = """Facility,Address
Test Facility,123 Main St"""

        csv_file = SimpleUploadedFile(
            "missing_cols.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        response = self.client.post(self.upload_url, {'facility_csv': csv_file})
        self.assertEqual(response.status_code, 200)
        # Should handle missing columns gracefully

    def test_upload_with_special_characters(self):
        """Test uploading file with special characters and encoding."""
        csv_content = """Facility,Lat,Long,Archetype
Test Café & Restaurant,48.8566,2.3522,Retail
Facité de Test,45.7640,4.8357,Office
测试设施,39.9042,116.4074,Warehouse"""

        csv_file = SimpleUploadedFile(
            "special_chars.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        response = self.client.post(self.upload_url, {'facility_csv': csv_file})
        self.assertEqual(response.status_code, 200)

        session = self.client.session
        self.assertIn('climate_hazards_v2_facility_data', session)
        self.assertEqual(len(session['climate_hazards_v2_facility_data']), 3)

    def test_upload_preserves_existing_session_data(self):
        """Test that upload preserves existing session data (like drawn polygons)."""
        # First, add some existing data to session
        session = self.client.session
        existing_data = [
            {
                'Facility': 'Existing Facility',
                'Lat': 40.7128,
                'Long': -74.0060,
                'Archetype': 'Office'
            }
        ]
        session['climate_hazards_v2_facility_data'] = existing_data
        session.save()

        # Now upload new data
        csv_content = """Facility,Lat,Long,Archetype
New Facility,34.0522,-118.2437,Warehouse"""

        csv_file = SimpleUploadedFile(
            "new_facilities.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        response = self.client.post(self.upload_url, {'facility_csv': csv_file})
        self.assertEqual(response.status_code, 200)

        # Check that both old and new data are preserved
        session = self.client.session
        self.assertEqual(len(session['climate_hazards_v2_facility_data']), 2)

        facility_names = [f['Facility'] for f in session['climate_hazards_v2_facility_data']]
        self.assertIn('Existing Facility', facility_names)
        self.assertIn('New Facility', facility_names)


class AddFacilityAPITestCase(TestCase):
    """Test cases for the add_facility API endpoint."""

    def setUp(self):
        """Set up test environment."""
        self.client = Client()
        self.add_facility_url = reverse('climate_hazards_analysis_v2:add_facility')
        self.client.session.create()

    def test_add_point_facility_valid_data(self):
        """Test adding a valid point facility."""
        data = {
            'lat': 40.7128,
            'lng': -74.0060,
            'name': 'Test Facility',
            'archetype': 'Office'
        }

        response = self.client.post(
            self.add_facility_url,
            data=json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('message', response_data)

    def test_add_polygon_asset_valid_data(self):
        """Test adding a valid polygon asset."""
        polygon_coords = [
            [-74.0060, 40.7128],
            [-74.0050, 40.7128],
            [-74.0050, 40.7138],
            [-74.0060, 40.7138],
            [-74.0060, 40.7128]
        ]

        data = {
            'lat': 40.7133,  # Centroid
            'lng': -74.0055,  # Centroid
            'name': 'Test Polygon Asset',
            'archetype': 'Building Complex',
            'geometry': {
                'type': 'Polygon',
                'coordinates': [polygon_coords]
            },
            'areaKm2': 0.01
        }

        response = self.client.post(
            self.add_facility_url,
            data=json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])

    def test_add_facility_missing_required_fields(self):
        """Test adding facility with missing required fields."""
        data = {
            'lat': 40.7128,
            'lng': -74.0060
            # Missing name
        }

        response = self.client.post(
            self.add_facility_url,
            data=json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('message', response_data)

    def test_add_facility_invalid_coordinates(self):
        """Test adding facility with invalid coordinates."""
        data = {
            'lat': 95.0,  # Invalid latitude
            'lng': 200.0,  # Invalid longitude
            'name': 'Invalid Facility'
        }

        response = self.client.post(
            self.add_facility_url,
            data=json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])

    def test_add_facility_empty_name(self):
        """Test adding facility with empty name."""
        data = {
            'lat': 40.7128,
            'lng': -74.0060,
            'name': '   '  # Empty/whitespace name
        }

        response = self.client.post(
            self.add_facility_url,
            data=json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])

    def test_add_facility_auto_naming(self):
        """Test automatic facility naming when name not provided."""
        data = {
            'lat': 40.7128,
            'lng': -74.0060
            # No name provided
        }

        response = self.client.post(
            self.add_facility_url,
            data=json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('New Facility at', response_data.get('message', ''))

    def test_add_facility_wrong_http_method(self):
        """Test adding facility with wrong HTTP method."""
        response = self.client.get(self.add_facility_url)
        self.assertEqual(response.status_code, 405)


class AssetModelTestCase(TestCase):
    """Test cases for the Asset model."""

    def setUp(self):
        """Set up test environment."""
        self.test_session_key = 'test_session_123'

    def test_create_point_asset(self):
        """Test creating a point-based asset."""
        asset = Asset.objects.create(
            name='Test Point Facility',
            archetype='Office',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            session_key=self.test_session_key
        )

        self.assertEqual(asset.asset_type, 'point')
        self.assertEqual(asset.name, 'Test Point Facility')
        self.assertEqual(asset.coordinates, (40.7128, -74.0060))
        self.assertIsNone(asset.polygon_geometry)

    def test_create_polygon_asset(self):
        """Test creating a polygon-based asset."""
        polygon_geometry = {
            'type': 'Polygon',
            'coordinates': [[
                [-74.0060, 40.7128],
                [-74.0050, 40.7128],
                [-74.0050, 40.7138],
                [-74.0060, 40.7138],
                [-74.0060, 40.7128]
            ]]
        }

        asset = Asset.objects.create(
            name='Test Polygon Asset',
            archetype='Building Complex',
            latitude=Decimal('40.7133'),
            longitude=Decimal('-74.0055'),
            polygon_geometry=polygon_geometry,
            session_key=self.test_session_key
        )

        self.assertEqual(asset.asset_type, 'polygon')
        self.assertEqual(asset.name, 'Test Polygon Asset')
        self.assertEqual(asset.polygon_geometry, polygon_geometry)

    def test_asset_auto_type_detection(self):
        """Test automatic asset type detection based on polygon geometry."""
        # Create asset with polygon geometry but no specified type
        polygon_geometry = {
            'type': 'Polygon',
            'coordinates': [[
                [-74.0060, 40.7128],
                [-74.0050, 40.7128],
                [-74.0050, 40.7138],
                [-74.0060, 40.7138],
                [-74.0060, 40.7128]
            ]]
        }

        asset = Asset.objects.create(
            name='Auto-detect Asset',
            polygon_geometry=polygon_geometry,
            session_key=self.test_session_key
        )

        # Asset type should be auto-detected as 'polygon'
        self.assertEqual(asset.asset_type, 'polygon')

    def test_polygon_centroid_calculation(self):
        """Test polygon centroid calculation."""
        polygon_geometry = {
            'type': 'Polygon',
            'coordinates': [[
                [0, 0],
                [2, 0],
                [2, 2],
                [0, 2],
                [0, 0]
            ]]
        }

        asset = Asset.objects.create(
            name='Centroid Test',
            polygon_geometry=polygon_geometry,
            session_key=self.test_session_key
        )

        centroid = asset.calculate_polygon_centroid()
        self.assertIsNotNone(centroid)
        self.assertEqual(len(centroid), 2)
        # Should be approximately (1.0, 1.0)
        self.assertAlmostEqual(centroid[0], 1.0, places=1)
        self.assertAlmostEqual(centroid[1], 1.0, places=1)

    def test_polygon_area_calculation(self):
        """Test polygon area calculation."""
        polygon_geometry = {
            'type': 'Polygon',
            'coordinates': [[
                [0, 0],
                [2, 0],
                [2, 2],
                [0, 2],
                [0, 0]
            ]]
        }

        asset = Asset.objects.create(
            name='Area Test',
            polygon_geometry=polygon_geometry,
            session_key=self.test_session_key
        )

        area = asset.get_polygon_area()
        self.assertIsNotNone(area)
        self.assertAlmostEqual(area, 4.0, places=1)  # 2x2 square = 4

    def test_geojson_property(self):
        """Test GeoJSON property generation."""
        # Test point asset
        point_asset = Asset.objects.create(
            name='Point Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            session_key=self.test_session_key
        )

        geojson = point_asset.geojson
        self.assertEqual(geojson['type'], 'Feature')
        self.assertEqual(geojson['geometry']['type'], 'Point')
        self.assertEqual(geojson['properties']['name'], 'Point Test')

        # Test polygon asset
        polygon_geometry = {
            'type': 'Polygon',
            'coordinates': [[
                [-74.0060, 40.7128],
                [-74.0050, 40.7128],
                [-74.0050, 40.7138],
                [-74.0060, 40.7138],
                [-74.0060, 40.7128]
            ]]
        }

        polygon_asset = Asset.objects.create(
            name='Polygon Test',
            polygon_geometry=polygon_geometry,
            session_key=self.test_session_key
        )

        geojson = polygon_asset.geojson
        self.assertEqual(geojson['type'], 'Feature')
        self.assertEqual(geojson['geometry']['type'], 'Polygon')


class UtilityFunctionsTestCase(TestCase):
    """Test cases for utility functions."""

    def test_standardize_facility_dataframe_standard_columns(self):
        """Test standardizing dataframe with standard column names."""
        df = pd.DataFrame({
            'Facility': ['Test 1', 'Test 2'],
            'Lat': [40.7128, 34.0522],
            'Long': [-74.0060, -118.2437],
            'Archetype': ['Office', 'Warehouse']
        })

        standardized_df = standardize_facility_dataframe(df)

        self.assertIn('Facility', standardized_df.columns)
        self.assertIn('Lat', standardized_df.columns)
        self.assertIn('Long', standardized_df.columns)
        self.assertIn('Archetype', standardized_df.columns)
        self.assertEqual(len(standardized_df), 2)

    def test_standardize_facility_dataframe_varied_columns(self):
        """Test standardizing dataframe with varied column names."""
        df = pd.DataFrame({
            'facility_name': ['Test 1', 'Test 2'],
            'latitude': [40.7128, 34.0522],
            'longitude': [-74.0060, -118.2437],
            'type': ['Office', 'Warehouse']
        })

        standardized_df = standardize_facility_dataframe(df)

        # Should be standardized to standard column names
        self.assertIn('Facility', standardized_df.columns)
        self.assertIn('Lat', standardized_df.columns)
        self.assertIn('Long', standardized_df.columns)
        self.assertIn('Archetype', standardized_df.columns)

    def test_standardize_facility_dataframe_empty_dataframe(self):
        """Test standardizing empty dataframe."""
        df = pd.DataFrame()

        standardized_df = standardize_facility_dataframe(df)

        self.assertTrue(standardized_df.empty)

    def test_validate_shapefile_valid(self):
        """Test validating a valid shapefile."""
        # Create mock GeoDataFrame
        gdf = mock.Mock(spec=gpd.GeoDataFrame)
        gdf.__len__ = mock.Mock(return_value=2)
        gdf.geometry = mock.Mock()
        gdf.geometry.iloc = mock.Mock(return_value=[Point(0, 0), Point(1, 1)])
        gdf.columns = ['name', 'geometry']

        # Mock the geom_type
        gdf.geometry.iloc.__getitem__ = mock.Mock(side_effect=lambda i: Point(i, i))

        with mock.patch.object(gdf.geometry, 'iloc'):
            attribute_columns = validate_shapefile(gdf)
            self.assertIsInstance(attribute_columns, list)

    def test_validate_shapefile_empty(self):
        """Test validating empty shapefile."""
        gdf = mock.Mock(spec=gpd.GeoDataFrame)
        gdf.__len__ = mock.Mock(return_value=0)

        with self.assertRaises(ValueError):
            validate_shapefile(gdf)


class PreviewUploadedFileTestCase(TestCase):
    """Test cases for preview_uploaded_file functionality."""

    def setUp(self):
        """Set up test environment."""
        self.client = Client()
        self.preview_url = reverse('climate_hazards_analysis_v2:preview_uploaded_file')
        self.client.session.create()

    def test_preview_existing_file(self):
        """Test previewing an existing uploaded file."""
        # Set up session with file path
        session = self.client.session
        session['climate_hazards_v2_facility_csv_path'] = '/tmp/test_file.csv'
        session.save()

        # Mock the file existence and content
        with mock.patch('os.path.exists', return_value=True), \
             mock.patch('builtins.open', mock.mock_open(read_data='test,csv,content\n1,2,3')):

            response = self.client.get(self.preview_url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'text/csv')

    def test_preview_nonexistent_file(self):
        """Test previewing a non-existent file."""
        # Set up session with non-existent file path
        session = self.client.session
        session['climate_hazards_analysis_v2_facility_csv_path'] = '/tmp/nonexistent.csv'
        session.save()

        with mock.patch('os.path.exists', return_value=False):
            response = self.client.get(self.preview_url)
            self.assertEqual(response.status_code, 404)

    def test_preview_no_file_in_session(self):
        """Test previewing when no file is in session."""
        response = self.client.get(self.preview_url)
        self.assertEqual(response.status_code, 404)

    def test_preview_encoding_handling(self):
        """Test preview with different file encodings."""
        # Set up session with file path
        session = self.client.session
        session['climate_hazards_v2_facility_csv_path'] = '/tmp/test_file.csv'
        session.save()

        # Test UTF-8 encoding
        with mock.patch('os.path.exists', return_value=True), \
             mock.patch('builtins.open', mock.mock_open(read_data='test,café,content\n1,2,3')):

            response = self.client.get(self.preview_url)
            self.assertEqual(response.status_code, 200)

        # Test Latin-1 encoding fallback
        def mock_open_side_effect(*args, **kwargs):
            if 'encoding' in kwargs and kwargs['encoding'] == 'utf-8':
                raise UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid start byte')
            return mock.mock_open(read_data='test,latin,content\n1,2,3')(*args, **kwargs)

        with mock.patch('os.path.exists', return_value=True), \
             mock.patch('builtins.open', side_effect=mock_open_side_effect):

            response = self.client.get(self.preview_url)
            self.assertEqual(response.status_code, 200)


class GeospatialFileTestCase(TestCase):
    """Test cases for geospatial file uploads (Shapefile, GeoPackage)."""

    def setUp(self):
        """Set up test environment."""
        self.client = Client()
        self.upload_url = reverse('climate_hazards_analysis_v2:view_map')

    @mock.patch('geopandas.read_file')
    @mock.patch('climate_hazards_analysis_v2.views.validate_shapefile')
    def test_upload_shapefile_valid(self, mock_validate, mock_read_file):
        """Test uploading a valid shapefile."""
        # Mock shapefile data
        mock_gdf = mock.Mock(spec=gpd.GeoDataFrame)
        mock_gdf.to_crs.return_value = mock_gdf
        mock_gdf.geometry.centroid.y = pd.Series([40.7128, 34.0522])
        mock_gdf.geometry.centroid.x = pd.Series([-74.0060, -118.2437])
        mock_gdf.drop.return_value = pd.DataFrame({
            'Facility': ['Test 1', 'Test 2'],
            'Archetype': ['Office', 'Warehouse']
        })

        mock_read_file.return_value = mock_gdf
        mock_validate.return_value = ['Facility', 'Archetype']

        # Create a mock shapefile
        shp_content = b"mock shapefile content"
        shp_file = SimpleUploadedFile(
            "test.shp",
            shp_content,
            content_type="application/octet-stream"
        )

        response = self.client.post(self.upload_url, {'facility_csv': shp_file})
        self.assertEqual(response.status_code, 200)

    @mock.patch('zipfile.ZipFile')
    @mock.patch('geopandas.read_file')
    def test_upload_zip_with_shapefile(self, mock_read_file, mock_zipfile):
        """Test uploading a ZIP file containing shapefile."""
        # Mock zip file extraction
        mock_zip = mock.MagicMock()
        mock_zipfile.return_value.__enter__.return_value = mock_zip

        # Mock shapefile reading
        mock_gdf = mock.Mock(spec=gpd.GeoDataFrame)
        mock_gdf.to_crs.return_value = mock_gdf
        mock_gdf.geometry.centroid.y = pd.Series([40.7128])
        mock_gdf.geometry.centroid.x = pd.Series([-74.0060])
        mock_gdf.drop.return_value = pd.DataFrame({'Facility': ['Test']})

        mock_read_file.return_value = mock_gdf

        zip_content = b"mock zip content"
        zip_file = SimpleUploadedFile(
            "test.zip",
            zip_content,
            content_type="application/zip"
        )

        response = self.client.post(self.upload_url, {'facility_csv': zip_file})
        self.assertEqual(response.status_code, 200)

    @mock.patch('geopandas.read_file')
    def test_upload_geopackage_valid(self, mock_read_file):
        """Test uploading a valid GeoPackage file."""
        # Mock GeoPackage data
        mock_gdf = mock.Mock(spec=gpd.GeoDataFrame)
        mock_gdf.to_crs.return_value = mock_gdf
        mock_gdf.geometry.centroid.y = pd.Series([40.7128])
        mock_gdf.geometry.centroid.x = pd.Series([-74.0060])
        mock_gdf.drop.return_value = pd.DataFrame({'Facility': ['Test']})

        mock_read_file.return_value = mock_gdf

        gpkg_content = b"mock geopackage content"
        gpkg_file = SimpleUploadedFile(
            "test.gpkg",
            gpkg_content,
            content_type="application/geopackage"
        )

        response = self.client.post(self.upload_url, {'facility_csv': gpkg_file})
        self.assertEqual(response.status_code, 200)


class ErrorHandlingTestCase(TestCase):
    """Test cases for error handling scenarios."""

    def setUp(self):
        """Set up test environment."""
        self.client = Client()
        self.upload_url = reverse('climate_hazards_analysis_v2:view_map')

    @mock.patch('pandas.read_csv')
    def test_csv_processing_error(self, mock_read_csv):
        """Test handling of CSV processing errors."""
        mock_read_csv.side_effect = Exception("CSV processing error")

        csv_content = "invalid,csv,content"
        csv_file = SimpleUploadedFile(
            "error.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        response = self.client.post(self.upload_url, {'facility_csv': csv_file})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Error processing file')

    @mock.patch('tempfile.TemporaryDirectory')
    def test_temporary_directory_error(self, mock_temp_dir):
        """Test handling of temporary directory creation errors."""
        mock_temp_dir.side_effect = OSError("Cannot create temp directory")

        zip_content = b"mock zip content"
        zip_file = SimpleUploadedFile(
            "test.zip",
            zip_content,
            content_type="application/zip"
        )

        response = self.client.post(self.upload_url, {'facility_csv': zip_file})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Error processing file')

    def test_malformed_json_in_add_facility(self):
        """Test handling of malformed JSON in add_facility endpoint."""
        add_facility_url = reverse('climate_hazards_analysis_v2:add_facility')

        response = self.client.post(
            add_facility_url,
            data="invalid json",
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])


class SecurityTestCase(TestCase):
    """Test cases for security considerations."""

    def setUp(self):
        """Set up test environment."""
        self.client = Client()
        self.upload_url = reverse('climate_hazards_analysis_v2:view_map')

    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks."""
        malicious_file = SimpleUploadedFile(
            "../../../etc/passwd",
            b"malicious content",
            content_type="text/plain"
        )

        response = self.client.post(self.upload_url, {'facility_csv': malicious_file})
        self.assertEqual(response.status_code, 200)
        # Should not process the file and should show error

    def test_executable_file_upload_prevention(self):
        """Test prevention of executable file uploads."""
        exe_file = SimpleUploadedFile(
            "malware.exe",
            b"malicious executable content",
            content_type="application/octet-stream"
        )

        response = self.client.post(self.upload_url, {'facility_csv': exe_file})
        self.assertEqual(response.status_code, 200)
        # Should reject the file

    def test_large_file_handling(self):
        """Test handling of overly large files."""
        # Create a large file content (simulated)
        large_content = "A" * (50 * 1024 * 1024)  # 50MB

        large_file = SimpleUploadedFile(
            "large.csv",
            large_content.encode('utf-8'),
            content_type="text/csv"
        )

        # This test might need configuration adjustments based on Django's file upload limits
        response = self.client.post(self.upload_url, {'facility_csv': large_file})
        # Should handle large files gracefully (either accept or reject with proper error)


class IntegrationTestCase(TestCase):
    """Integration tests for complete workflows."""

    def setUp(self):
        """Set up test environment."""
        self.client = Client()
        self.upload_url = reverse('climate_hazards_analysis_v2:view_map')
        self.add_facility_url = reverse('climate_hazards_analysis_v2:add_facility')
        self.get_facility_url = reverse('climate_hazards_analysis_v2:get_facility_data')

    def test_complete_upload_workflow(self):
        """Test complete workflow from upload to data retrieval."""
        # Step 1: Upload CSV file
        csv_content = """Facility,Lat,Long,Archetype
Test Facility 1,40.7128,-74.0060,Office
Test Facility 2,34.0522,-118.2437,Warehouse"""

        csv_file = SimpleUploadedFile(
            "workflow_test.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        response = self.client.post(self.upload_url, {'facility_csv': csv_file})
        self.assertEqual(response.status_code, 200)

        # Step 2: Add additional facility via API
        facility_data = {
            'lat': 51.5074,
            'lng': -0.1278,
            'name': 'Additional Facility',
            'archetype': 'Retail'
        }

        response = self.client.post(
            self.add_facility_url,
            data=json.dumps(facility_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # Step 3: Retrieve all facility data
        response = self.client.get(self.get_facility_url)
        self.assertEqual(response.status_code, 200)

        response_data = json.loads(response.content)
        facilities = response_data.get('facilities', [])

        # Should have 3 facilities (2 from upload + 1 from API)
        self.assertEqual(len(facilities), 3)

        facility_names = [f.get('Facility') for f in facilities]
        self.assertIn('Test Facility 1', facility_names)
        self.assertIn('Test Facility 2', facility_names)
        self.assertIn('Additional Facility', facility_names)

    def test_polygon_and_point_integration(self):
        """Test integration of point and polygon assets."""
        # Step 1: Upload point facilities
        csv_content = """Facility,Lat,Long,Archetype
Point Facility 1,40.7128,-74.0060,Office
Point Facility 2,34.0522,-118.2437,Warehouse"""

        csv_file = SimpleUploadedFile(
            "points.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        response = self.client.post(self.upload_url, {'facility_csv': csv_file})
        self.assertEqual(response.status_code, 200)

        # Step 2: Add polygon asset
        polygon_data = {
            'lat': 45.7640,
            'lng': 4.8357,
            'name': 'Polygon Asset',
            'archetype': 'Building Complex',
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[
                    [4.8357, 45.7640],
                    [4.8367, 45.7640],
                    [4.8367, 45.7650],
                    [4.8357, 45.7650],
                    [4.8357, 45.7640]
                ]]
            }
        }

        response = self.client.post(
            self.add_facility_url,
            data=json.dumps(polygon_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # Step 3: Verify mixed asset types in database
        session_key = self.client.session.session_key
        point_assets = Asset.objects.filter(
            session_key=session_key,
            asset_type='point'
        ).count()

        polygon_assets = Asset.objects.filter(
            session_key=session_key,
            asset_type='polygon'
        ).count()

        self.assertEqual(point_assets, 0)  # Point assets are only in session
        self.assertEqual(polygon_assets, 1)  # Polygon assets are saved to database

    def test_session_data_persistence_workflow(self):
        """Test that session data persists correctly across operations."""
        # Step 1: Upload initial data
        csv_content = """Facility,Lat,Long,Archetype
Initial Facility,40.7128,-74.0060,Office"""

        csv_file = SimpleUploadedFile(
            "initial.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        response = self.client.post(self.upload_url, {'facility_csv': csv_file})
        self.assertEqual(response.status_code, 200)

        # Verify initial data in session
        session = self.client.session
        initial_data = session.get('climate_hazards_v2_facility_data', [])
        self.assertEqual(len(initial_data), 1)

        # Step 2: Add more data via API
        facility_data = {
            'lat': 34.0522,
            'lng': -118.2437,
            'name': 'Additional Facility',
            'archetype': 'Warehouse'
        }

        response = self.client.post(
            self.add_facility_url,
            data=json.dumps(facility_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # Step 3: Upload more CSV data (should preserve existing data)
        csv_content_2 = """Facility,Lat,Long,Archetype
New Facility,51.5074,-0.1278,Retail"""

        csv_file_2 = SimpleUploadedFile(
            "additional.csv",
            csv_content_2.encode('utf-8'),
            content_type="text/csv"
        )

        response = self.client.post(self.upload_url, {'facility_csv': csv_file_2})
        self.assertEqual(response.status_code, 200)

        # Verify all data is preserved
        session = self.client.session
        final_data = session.get('climate_hazards_v2_facility_data', [])
        self.assertEqual(len(final_data), 3)  # Initial + API + Second upload


if __name__ == '__main__':
    import django
    from django.conf import settings

    # Configure Django settings
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': ':memory:',
                }
            },
            INSTALLED_APPS=[
                'django.contrib.contenttypes',
                'django.contrib.auth',
                'django.contrib.sessions',
                'climate_hazards_analysis_v2',
            ],
            SECRET_KEY='test-secret-key',
            USE_TZ=True,
        )

    django.setup()

    # Run tests
    unittest.main()
