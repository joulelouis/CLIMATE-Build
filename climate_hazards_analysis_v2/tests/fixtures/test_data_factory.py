"""
Test Data Factory for Upload Asset Data functionality.

This module provides factory methods for creating test data files, mock objects,
and fixtures for comprehensive testing of the upload functionality.

Supported file formats:
- CSV files with various column naming conventions
- Excel files (.xls, .xlsx)
- Shapefile components and zip archives
- GeoPackage files
- Invalid and corrupted files for error testing
"""

import io
import json
import zipfile
from io import BytesIO
from unittest.mock import Mock

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon, MultiPolygon
from django.core.files.uploadedfile import SimpleUploadedFile


class TestDataFactory:
    """Factory class for creating test data and files."""

    # Standard test facility data
    STANDARD_FACILITIES = [
        {
            'Facility': 'New York Office',
            'Lat': 40.7128,
            'Long': -74.0060,
            'Archetype': 'Office'
        },
        {
            'Facility': 'Los Angeles Warehouse',
            'Lat': 34.0522,
            'Long': -118.2437,
            'Archetype': 'Warehouse'
        },
        {
            'Facility': 'London Retail Store',
            'Lat': 51.5074,
            'Long': -0.1278,
            'Archetype': 'Retail'
        },
        {
            'Facility': 'Tokyo Facility',
            'Lat': 35.6762,
            'Long': 139.6503,
            'Archetype': 'Manufacturing'
        },
        {
            'Facility': 'Sydney Distribution Center',
            'Lat': -33.8688,
            'Long': 151.2093,
            'Archetype': 'Distribution'
        }
    ]

    # Facilities with various column naming conventions
    FACILITIES_VARIED_COLUMNS = [
        {
            'facility_name': 'Test Facility A',
            'latitude': 48.8566,
            'longitude': 2.3522,
            'type': 'Office'
        },
        {
            'facility_name': 'Test Facility B',
            'latitude': 52.5200,
            'longitude': 13.4050,
            'type': 'Warehouse'
        }
    ]

    # Facilities with special characters and encoding issues
    FACILITIES_SPECIAL_CHARS = [
        {
            'Facility': 'Café du Monde',
            'Lat': 29.9511,
            'Long': -90.0715,
            'Archetype': 'Restaurant'
        },
        {
            'Facility': 'Müller GmbH',
            'Lat': 48.1351,
            'Long': 11.5820,
            'Archetype': 'Office'
        },
        {
            'Facility': '北京办公室',
            'Lat': 39.9042,
            'Long': 116.4074,
            'Archetype': 'Office'
        },
        {
            'Facility': 'Oficina Principal',
            'Lat': 19.4326,
            'Long': -99.1332,
            'Archetype': 'Corporate'
        }
    ]

    # Facilities with invalid coordinates
    FACILITIES_INVALID_COORDINATES = [
        {
            'Facility': 'Invalid Latitude',
            'Lat': 95.0,  # Invalid latitude (>90)
            'Long': -74.0060,
            'Archetype': 'Office'
        },
        {
            'Facility': 'Invalid Longitude',
            'Lat': 40.7128,
            'Long': 200.0,  # Invalid longitude (>180)
            'Archetype': 'Warehouse'
        },
        {
            'Facility': 'Invalid Both',
            'Lat': -100.0,  # Invalid latitude (<-90)
            'Long': 250.0,   # Invalid longitude (>180)
            'Archetype': 'Retail'
        }
    ]

    # Large dataset for performance testing
    def generate_large_facility_dataset(self, count=1000):
        """Generate a large facility dataset for performance testing."""
        facilities = []
        for i in range(count):
            facilities.append({
                'Facility': f'Facility {i+1}',
                'Lat': round(-90 + (180 * i / count), 6),
                'Long': round(-180 + (360 * i / count), 6),
                'Archetype': ['Office', 'Warehouse', 'Retail', 'Manufacturing'][i % 4]
            })
        return facilities

    @classmethod
    def create_valid_csv_file(cls, filename='test_facilities.csv', data=None):
        """Create a valid CSV file for testing."""
        if data is None:
            data = cls.STANDARD_FACILITIES

        df = pd.DataFrame(data)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()

        return SimpleUploadedFile(
            filename,
            csv_content.encode('utf-8'),
            content_type='text/csv'
        )

    @classmethod
    def create_varied_columns_csv_file(cls, filename='varied_columns.csv'):
        """Create a CSV file with varied column names."""
        return cls.create_valid_csv_file(
            filename=filename,
            data=cls.FACILITIES_VARIED_COLUMNS
        )

    @classmethod
    def create_special_chars_csv_file(cls, filename='special_chars.csv'):
        """Create a CSV file with special characters."""
        return cls.create_valid_csv_file(
            filename=filename,
            data=cls.FACILITIES_SPECIAL_CHARS
        )

    @classmethod
    def create_invalid_coordinates_csv_file(cls, filename='invalid_coords.csv'):
        """Create a CSV file with invalid coordinates."""
        return cls.create_valid_csv_file(
            filename=filename,
            data=cls.FACILITIES_INVALID_COORDINATES
        )

    @classmethod
    def create_large_csv_file(cls, filename='large_facilities.csv', count=1000):
        """Create a large CSV file for performance testing."""
        data = cls.generate_large_facility_dataset(count)
        return cls.create_valid_csv_file(filename=filename, data=data)

    @classmethod
    def create_empty_csv_file(cls, filename='empty.csv'):
        """Create an empty CSV file."""
        return SimpleUploadedFile(
            filename,
            b'',
            content_type='text/csv'
        )

    @classmethod
    def create_malformed_csv_file(cls, filename='malformed.csv'):
        """Create a malformed CSV file."""
        malformed_content = "Facility,Lat,Long,Archetype\nTest1,40.7128,-74.0060,Office\nTest2,34.0522"
        # Missing last column value for second row

        return SimpleUploadedFile(
            filename,
            malformed_content.encode('utf-8'),
            content_type='text/csv'
        )

    @classmethod
    def create_excel_file(cls, filename='test_facilities.xlsx', data=None, engine='openpyxl'):
        """Create a valid Excel file for testing."""
        if data is None:
            data = cls.STANDARD_FACILITIES

        df = pd.DataFrame(data)
        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False, engine=engine)
        excel_buffer.seek(0)

        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        if engine == 'xlwt':
            content_type = 'application/vnd.ms-excel'

        return SimpleUploadedFile(
            filename,
            excel_buffer.getvalue(),
            content_type=content_type
        )

    @classmethod
    def create_excel_with_multiple_sheets(cls, filename='multi_sheet.xlsx'):
        """Create an Excel file with multiple worksheets."""
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Write facilities data to first sheet
            df1 = pd.DataFrame(cls.STANDARD_FACILITIES)
            df1.to_excel(writer, sheet_name='Facilities', index=False)

            # Write different data to second sheet
            df2 = pd.DataFrame(cls.FACILITIES_VARIED_COLUMNS)
            df2.to_excel(writer, sheet_name='Alternative Data', index=False)

        # Read the created file and return as SimpleUploadedFile
        with open(filename, 'rb') as f:
            content = f.read()

        return SimpleUploadedFile(
            filename,
            content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    @classmethod
    def create_mock_geodataframe(cls, data=None, geometry_type='Point'):
        """Create a mock GeoDataFrame for testing."""
        if data is None:
            data = cls.STANDARD_FACILITIES[:3]  # Use first 3 facilities

        # Create geometries
        geometries = []
        for facility in data:
            if geometry_type == 'Point':
                geom = Point(facility['Long'], facility['Lat'])
            elif geometry_type == 'Polygon':
                # Create a small polygon around the point
                lat, lng = facility['Lat'], facility['Long']
                coords = [
                    [lng - 0.001, lat - 0.001],
                    [lng + 0.001, lat - 0.001],
                    [lng + 0.001, lat + 0.001],
                    [lng - 0.001, lat + 0.001],
                    [lng - 0.001, lat - 0.001]
                ]
                geom = Polygon(coords)
            else:
                geom = Point(facility['Long'], facility['Lat'])
            geometries.append(geom)

        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(data, geometry=geometries)
        gdf.crs = 'EPSG:4326'  # Set coordinate reference system

        return gdf

    @classmethod
    def create_shapefile_zip(cls, filename='test_shapefile.zip', data=None):
        """Create a ZIP file containing shapefile components."""
        if data is None:
            data = cls.STANDARD_FACILITIES[:3]

        # Create mock GeoDataFrame
        gdf = cls.create_mock_geodataframe(data, 'Point')

        # Create ZIP file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            # Add mock shapefile components
            zip_file.writestr('test.shp', b'mock shp content')
            zip_file.writestr('test.shx', b'mock shx content')
            zip_file.writestr('test.dbf', b'mock dbf content')
            zip_file.writestr('test.prj', b'mock prj content')
            zip_file.writestr('test.cpg', b'UTF-8')

        zip_buffer.seek(0)

        return SimpleUploadedFile(
            filename,
            zip_buffer.getvalue(),
            content_type='application/zip'
        )

    @classmethod
    def create_invalid_files(cls):
        """Create various invalid files for error testing."""
        invalid_files = []

        # Text file
        text_file = SimpleUploadedFile(
            'test.txt',
            b'This is not a valid data file',
            content_type='text/plain'
        )
        invalid_files.append(('text_file', text_file))

        # Image file
        image_file = SimpleUploadedFile(
            'test.jpg',
            b'\xff\xd8\xff\xe0\x00\x10JFIF',  # JPEG header
            content_type='image/jpeg'
        )
        invalid_files.append(('image_file', image_file))

        # PDF file
        pdf_file = SimpleUploadedFile(
            'test.pdf',
            b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj',
            content_type='application/pdf'
        )
        invalid_files.append(('pdf_file', pdf_file))

        # Executable file
        exe_file = SimpleUploadedFile(
            'test.exe',
            b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff',  # PE header
            content_type='application/octet-stream'
        )
        invalid_files.append(('exe_file', exe_file))

        return invalid_files

    @classmethod
    def create_mock_polygon_geometry(cls, center_lng=-74.0060, center_lat=40.7128, size=0.01):
        """Create mock polygon geometry for testing."""
        coords = [
            [center_lng - size, center_lat - size],
            [center_lng + size, center_lat - size],
            [center_lng + size, center_lat + size],
            [center_lng - size, center_lat + size],
            [center_lng - size, center_lat - size]
        ]

        return {
            'type': 'Polygon',
            'coordinates': [coords]
        }

    @classmethod
    def create_mock_multipolygon_geometry(cls, center_lng=-74.0060, center_lat=40.7128):
        """Create mock multipolygon geometry for testing."""
        # Create two adjacent polygons
        polygon1 = cls.create_mock_polygon_geometry(
            center_lng - 0.02, center_lat, 0.01
        )
        polygon2 = cls.create_mock_polygon_geometry(
            center_lng + 0.02, center_lat, 0.01
        )

        return {
            'type': 'MultiPolygon',
            'coordinates': [
                polygon1['coordinates'],
                polygon2['coordinates']
            ]
        }

    @classmethod
    def create_test_session_data(cls):
        """Create test session data for facility uploads."""
        return {
            'climate_hazards_v2_facility_data': cls.STANDARD_FACILITIES,
            'climate_hazards_v2_uploaded_filename': 'test_upload.csv',
            'climate_hazards_v2_selected_hazards': ['Flood', 'Heat', 'Water Stress']
        }

    @classmethod
    def create_mock_asset_objects(cls):
        """Create mock Asset objects for testing."""
        mock_assets = []

        # Point asset
        point_asset = Mock(spec=Asset)
        point_asset.id = 1
        point_asset.name = 'Test Point Asset'
        point_asset.asset_type = 'point'
        point_asset.latitude = 40.7128
        point_asset.longitude = -74.0060
        point_asset.archetype = 'Office'
        point_asset.session_key = 'test_session_123'
        point_asset.polygon_geometry = None

        # Polygon asset
        polygon_asset = Mock(spec=Asset)
        polygon_asset.id = 2
        polygon_asset.name = 'Test Polygon Asset'
        polygon_asset.asset_type = 'polygon'
        polygon_asset.latitude = 40.7133
        polygon_asset.longitude = -74.0055
        polygon_asset.archetype = 'Building Complex'
        polygon_asset.session_key = 'test_session_123'
        polygon_asset.polygon_geometry = cls.create_mock_polygon_geometry()

        mock_assets.extend([point_asset, polygon_asset])
        return mock_assets


class FileFormatTestFactory:
    """Factory for creating files in various formats for format testing."""

    @staticmethod
    def create_utf8_encoded_file():
        """Create a file with UTF-8 encoding."""
        content = "Facility,Lat,Long,Archetype\nCafé Paris,48.8566,2.3522,Restaurant\n"
        return SimpleUploadedFile(
            'utf8_test.csv',
            content.encode('utf-8'),
            content_type='text/csv'
        )

    @staticmethod
    def create_latin1_encoded_file():
        """Create a file with Latin-1 encoding."""
        content = "Facility,Lat,Long,Archetype\nCafé Paris,48.8566,2.3522,Restaurant\n"
        return SimpleUploadedFile(
            'latin1_test.csv',
            content.encode('latin-1'),
            content_type='text/csv'
        )

    @staticmethod
    def create_file_with_bom():
        """Create a file with UTF-8 BOM."""
        content = '\ufeffFacility,Lat,Long,Archetype\nTest Facility,40.7128,-74.0060,Office\n'
        return SimpleUploadedFile(
            'bom_test.csv',
            content.encode('utf-8-sig'),
            content_type='text/csv'
        )

    @staticmethod
    def create_file_with_different_line_endings():
        """Create files with different line endings."""
        # Windows line endings
        windows_content = "Facility,Lat,Long,Archetype\r\nTest Facility,40.7128,-74.0060,Office\r\n"
        # Unix line endings
        unix_content = "Facility,Lat,Long,Archetype\nTest Facility,40.7128,-74.0060,Office\n"
        # Old Mac line endings
        mac_content = "Facility,Lat,Long,Archetype\rTest Facility,40.7128,-74.0060,Office\r"

        files = [
            ('windows_line_endings.csv', windows_content.encode('utf-8')),
            ('unix_line_endings.csv', unix_content.encode('utf-8')),
            ('mac_line_endings.csv', mac_content.encode('utf-8'))
        ]

        return [SimpleUploadedFile(name, content, 'text/csv') for name, content in files]


class PerformanceTestDataFactory:
    """Factory for creating performance test data."""

    @staticmethod
    def create_large_excel_file(filename='large_excel.xlsx', rows=10000):
        """Create a large Excel file for performance testing."""
        # Generate large dataset
        data = {
            'Facility': [f'Facility {i}' for i in range(rows)],
            'Lat': [round(-90 + (180 * i / rows), 6) for i in range(rows)],
            'Long': [round(-180 + (360 * i / rows), 6) for i in range(rows)],
            'Archetype': [['Office', 'Warehouse', 'Retail'][i % 3] for i in range(rows)]
        }

        df = pd.DataFrame(data)
        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)

        return SimpleUploadedFile(
            filename,
            excel_buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    @staticmethod
    def create_complex_geodataframe(rows=1000):
        """Create a complex GeoDataFrame with various geometry types."""
        data = []
        geometries = []

        for i in range(rows):
            # Create data
            facility_data = {
                'Facility': f'Complex Facility {i}',
                'Archetype': ['Office', 'Warehouse', 'Retail', 'Manufacturing'][i % 4],
                'Area': i * 100,
                'Value': i * 1000
            }

            # Create varied geometries
            if i % 4 == 0:
                # Point
                geom = Point(-180 + (360 * i / rows), -90 + (180 * i / rows))
            elif i % 4 == 1:
                # Polygon
                base_lng = -180 + (360 * i / rows)
                base_lat = -90 + (180 * i / rows)
                coords = [
                    [base_lng, base_lat],
                    [base_lng + 0.01, base_lat],
                    [base_lng + 0.01, base_lat + 0.01],
                    [base_lng, base_lat + 0.01],
                    [base_lng, base_lat]
                ]
                geom = Polygon(coords)
            elif i % 4 == 2:
                # MultiPolygon
                poly1 = Polygon([[-74.0, 40.7], [-73.9, 40.7], [-73.9, 40.8], [-74.0, 40.8], [-74.0, 40.7]])
                poly2 = Polygon([[-73.8, 40.7], [-73.7, 40.7], [-73.7, 40.8], [-73.8, 40.8], [-73.8, 40.7]])
                geom = MultiPolygon([poly1, poly2])
            else:
                # Point (fallback)
                geom = Point(-180 + (360 * i / rows), -90 + (180 * i / rows))

            data.append(facility_data)
            geometries.append(geom)

        return gpd.GeoDataFrame(data, geometry=geometries, crs='EPSG:4326')


# Utility functions for test data management
def cleanup_test_files(file_paths):
    """Clean up test files after testing."""
    import os
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Warning: Could not remove file {file_path}: {e}")


def save_test_file_factory_data(factory_method, output_dir='test_files'):
    """Save test files from factory methods to disk for manual testing."""
    os.makedirs(output_dir, exist_ok=True)

    # Example usage
    csv_file = TestDataFactory.create_valid_csv_file()
    with open(os.path.join(output_dir, csv_file.name), 'wb') as f:
        f.write(csv_file.read())

    excel_file = TestDataFactory.create_excel_file()
    with open(os.path.join(output_dir, excel_file.name), 'wb') as f:
        f.write(excel_file.read())

    zip_file = TestDataFactory.create_shapefile_zip()
    with open(os.path.join(output_dir, zip_file.name), 'wb') as f:
        f.write(zip_file.read())

    print(f"Test files saved to {output_dir} directory")


if __name__ == '__main__':
    # Generate test files for manual testing
    save_test_file_factory_data(TestDataFactory.create_valid_csv_file)