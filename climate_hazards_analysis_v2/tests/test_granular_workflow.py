"""
Comprehensive test suite for the complete granular analysis workflow.

This test suite validates the end-to-end functionality of the granular analysis
workflow service, including grid point generation, hazard analysis, results aggregation,
and table integration.
"""

import json
import time
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.test.client import Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch, Mock
from rest_framework.test import APITestCase

from climate_hazards_analysis_v2.models import (
    Asset, GranularAnalysisResult, HazardAnalysisResult, HeatmapData
)
from climate_hazards_analysis_v2.granular_workflow_service import (
    GranularAnalysisWorkflowService, execute_granular_analysis_workflow
)
from climate_hazards_analysis_v2.granular_utils import (
    generate_grid_points_from_polygon, calculate_granular_statistics
)


class GranularWorkflowServiceTest(TransactionTestCase):
    """Test the complete granular workflow service."""

    def setUp(self):
        """Set up test data."""
        self.test_polygon = {
            "type": "Polygon",
            "coordinates": [[
                [-122.4194, 37.7749],  # San Francisco area
                [-122.4194, 37.7849],
                [-122.4094, 37.7849],
                [-122.4094, 37.7749],
                [-122.4194, 37.7749]
            ]]
        }

        self.test_asset_name = "Test Polygon Asset"
        self.test_hazards = ["Heat", "Flooding"]
        self.test_archetype = "commercial"

        self.service = GranularAnalysisWorkflowService(grid_spacing=0.001)

    def test_grid_point_generation(self):
        """Test grid point generation within polygon boundaries."""
        grid_points = self.service._generate_grid_points(self.test_polygon)

        self.assertGreater(len(grid_points), 0, "Grid points should be generated")

        # Verify all points are within polygon bounds
        for lat, lng, row, col in grid_points:
            self.assertTrue(37.7749 <= lat <= 37.7849, f"Latitude {lat} out of bounds")
            self.assertTrue(-122.4194 <= lng <= -122.4094, f"Longitude {lng} out of bounds")
            self.assertIsInstance(row, int, "Grid row should be integer")
            self.assertIsInstance(col, int, "Grid column should be integer")

    def test_polygon_asset_creation(self):
        """Test polygon asset creation with granular analysis metadata."""
        grid_points = generate_grid_points_from_polygon(self.test_polygon, 0.001)

        asset = self.service._create_polygon_asset(
            self.test_polygon,
            self.test_asset_name,
            self.test_archetype,
            grid_points,
            self.test_hazards
        )

        self.assertIsNotNone(asset, "Asset should be created")
        self.assertEqual(asset.name, self.test_asset_name)
        self.assertEqual(asset.asset_type, 'polygon')
        self.assertTrue(asset.has_granular_analysis)
        self.assertEqual(asset.granular_analysis_status, 'pending')
        self.assertEqual(asset.granular_grid_spacing, 0.001)
        self.assertEqual(asset.granular_grid_points_count, len(grid_points) * len(self.test_hazards))

    @patch('climate_hazards_analysis_v2.granular_processor.load_cached_hazard_data')
    @patch('climate_hazards_analysis_v2.granular_processor.combine_facility_with_hazard_data')
    def test_hazard_analysis_execution(self, mock_combine_data, mock_load_hazard):
        """Test hazard analysis execution for grid points."""
        # Mock hazard data
        mock_load_hazard.return_value = {'test': 'data'}
        mock_combine_data.return_value = [
            {
                'Facility': 'Grid_0_0',
                'Lat': 37.7799,
                'Long': -122.4144,
                'Archetype': self.test_archetype,
                'Heat Exposure (%)': 25.5,
                'Flooding Exposure (%)': 10.2
            }
        ]

        # Create test asset
        asset = Asset.objects.create(
            name=self.test_asset_name,
            archetype=self.test_archetype,
            latitude=Decimal('37.7799'),
            longitude=Decimal('-122.4144'),
            polygon_geometry=self.test_polygon,
            asset_type='polygon',
            has_granular_analysis=True
        )

        # Create granular analysis results
        from climate_hazards_analysis_v2.granular_utils import create_granular_analysis_results
        grid_points = [(37.7799, -122.4144, 0, 0)]
        granular_results = create_granular_analysis_results(
            asset, grid_points, self.test_hazards
        )

        # Execute hazard analysis
        results = self.service._execute_hazard_analysis(asset, self.test_hazards)

        self.assertTrue(results.get('success'), "Hazard analysis should succeed")
        self.assertGreater(results.get('processed_points', 0), 0, "Points should be processed")

    def test_risk_summary_calculation(self):
        """Test risk summary calculation from statistics."""
        test_stats = {
            'grid_points_processed': 100,
            'total_grid_points': 100,
            'risk_distribution': {
                'low': 60,
                'medium': 30,
                'high': 10
            }
        }

        risk_summary = self.service._calculate_risk_summary(test_stats)

        self.assertEqual(risk_summary['overall_risk'], 'medium')
        self.assertEqual(risk_summary['risk_percentages']['high'], 10.0)
        self.assertEqual(risk_summary['risk_percentages']['medium'], 30.0)
        self.assertEqual(risk_summary['risk_percentages']['low'], 60.0)
        self.assertEqual(risk_summary['confidence_level'], 'high')

    def test_exposure_distribution_calculation(self):
        """Test exposure distribution calculation."""
        # Create test asset and granular results
        asset = Asset.objects.create(
            name=self.test_asset_name,
            archetype=self.test_archetype,
            latitude=Decimal('37.7799'),
            longitude=Decimal('-122.4144'),
            polygon_geometry=self.test_polygon,
            asset_type='polygon',
            has_granular_analysis=True
        )

        # Create test granular results with values
        test_values = [10.0, 20.0, 30.0, 40.0, 50.0]
        for i, value in enumerate(test_values):
            GranularAnalysisResult.objects.create(
                asset=asset,
                latitude=Decimal('37.7799'),
                longitude=Decimal('-122.4144'),
                grid_row=i,
                grid_col=0,
                grid_spacing=0.001,
                hazard_type='Heat',
                scenario='current',
                result_data={'value': value},
                processing_status='completed'
            )

        distribution = self.service._calculate_exposure_distribution(asset, 'Heat', 'current')

        self.assertEqual(distribution['min'], 10.0)
        self.assertEqual(distribution['max'], 50.0)
        self.assertEqual(distribution['mean'], 30.0)
        self.assertIn('percentiles', distribution)

    def test_table_results_preparation(self):
        """Test preparation of results for hazard exposure table."""
        # Create test asset
        asset = Asset.objects.create(
            name=self.test_asset_name,
            archetype=self.test_archetype,
            latitude=Decimal('37.7799'),
            longitude=Decimal('-122.4144'),
            polygon_geometry=self.test_polygon,
            asset_type='polygon',
            has_granular_analysis=True,
            granular_analysis_status='completed'
        )

        # Mock aggregated results
        aggregated_results = {
            'Heat': {
                'statistics': {
                    'grid_points_processed': 50,
                    'total_grid_points': 50,
                    'mean_value': 25.5,
                    'min_value': 10.0,
                    'max_value': 45.0,
                    'median_value': 24.0
                },
                'risk_summary': {
                    'overall_risk': 'medium',
                    'risk_percentages': {'low': 60.0, 'medium': 30.0, 'high': 10.0}
                },
                'exposure_distribution': {
                    'percentiles': {'p25': 15.0, 'p50': 24.0, 'p75': 35.0, 'p90': 40.0}
                }
            }
        }

        table_results = self.service._prepare_hazard_exposure_table(
            asset, ['Heat'], aggregated_results
        )

        self.assertEqual(len(table_results), 1, "Should have one table row")
        row = table_results[0]
        self.assertEqual(row['Facility'], self.test_asset_name)
        self.assertEqual(row['Hazard Type'], 'Heat')
        self.assertEqual(row['Mean Exposure'], 25.5)
        self.assertEqual(row['Grid Points Processed'], 50)
        self.assertEqual(row['Overall Risk'], 'medium')


class GranularWorkflowAPITest(APITestCase):
    """Test the granular workflow API endpoints."""

    def setUp(self):
        """Set up test client and data."""
        self.client = Client()
        self.test_polygon = {
            "type": "Polygon",
            "coordinates": [[
                [-122.4194, 37.7749],
                [-122.4194, 37.7849],
                [-122.4094, 37.7849],
                [-122.4094, 37.7749],
                [-122.4194, 37.7749]
            ]]
        }

        self.workflow_data = {
            'asset_name': 'Test Workflow Asset',
            'polygon_geometry': self.test_polygon,
            'selected_hazards': ['Heat', 'Flooding'],
            'archetype': 'commercial',
            'grid_spacing': 0.001,
            'scenario': 'current'
        }

    @patch('climate_hazards_analysis_v2.granular_workflow_service.execute_granular_analysis_workflow')
    def test_execute_complete_workflow_api(self, mock_execute_workflow):
        """Test the complete workflow execution API endpoint."""
        # Mock successful workflow execution
        mock_execute_workflow.return_value = {
            'success': True,
            'asset_id': 1,
            'asset_name': 'Test Workflow Asset',
            'grid_points_generated': 25,
            'table_results': [{'test': 'data'}],
            'selected_hazards': ['Heat', 'Flooding']
        }

        response = self.client.post(
            reverse('climate_hazards_analysis_v2:execute_complete_granular_workflow'),
            data=json.dumps(self.workflow_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['asset_id'], 1)

    def test_execute_workflow_api_validation(self):
        """Test API validation for required fields."""
        # Test missing asset name
        invalid_data = {
            'polygon_geometry': self.test_polygon,
            'selected_hazards': ['Heat']
        }

        response = self.client.post(
            reverse('climate_hazards_analysis_v2:execute_complete_granular_workflow'),
            data=json.dumps(invalid_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('Asset name is required', data['error'])

    def test_get_workflow_results_table_api(self):
        """Test the workflow results table API endpoint."""
        # Create test asset
        asset = Asset.objects.create(
            name='Test Asset',
            archetype='commercial',
            latitude=Decimal('37.7799'),
            longitude=Decimal('-122.4144'),
            polygon_geometry=self.test_polygon,
            asset_type='polygon',
            has_granular_analysis=True,
            granular_analysis_status='completed'
        )

        # Create test granular result
        GranularAnalysisResult.objects.create(
            asset=asset,
            latitude=Decimal('37.7799'),
            longitude=Decimal('-122.4144'),
            grid_row=0,
            grid_col=0,
            grid_spacing=0.001,
            hazard_type='Heat',
            scenario='current',
            result_data={'value': 25.5},
            processing_status='completed'
        )

        response = self.client.get(
            reverse('climate_hazards_analysis_v2:get_workflow_results_table', kwargs={'asset_id': asset.id})
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertIn('columns', data)
        self.assertIn('asset_info', data)


class GranularWorkflowIntegrationTest(TransactionTestCase):
    """Integration tests for the complete granular workflow."""

    def setUp(self):
        """Set up integration test data."""
        self.test_polygon = {
            "type": "Polygon",
            "coordinates": [[
                [-122.4194, 37.7749],
                [-122.4194, 37.7849],
                [-122.4094, 37.7849],
                [-122.4094, 37.7749],
                [-122.4194, 37.7749]
            ]]
        }

    @patch('climate_hazards_analysis_v2.granular_processor.load_cached_hazard_data')
    @patch('climate_hazards_analysis_v2.granular_processor.combine_facility_with_hazard_data')
    def test_end_to_end_workflow(self, mock_combine_data, mock_load_hazard):
        """Test the complete end-to-end workflow."""
        # Mock hazard data to simulate API calls
        mock_load_hazard.return_value = {'test': 'hazard_data'}
        mock_combine_data.return_value = [
            {
                'Facility': 'Grid_0_0',
                'Lat': 37.7799,
                'Long': -122.4144,
                'Archetype': 'commercial',
                'Heat Exposure (%)': 25.5,
                'Flooding Exposure (%)': 15.2
            },
            {
                'Facility': 'Grid_0_1',
                'Lat': 37.7799,
                'Long': -122.4134,
                'Archetype': 'commercial',
                'Heat Exposure (%)': 30.1,
                'Flooding Exposure (%)': 12.8
            }
        ]

        # Execute complete workflow
        results = execute_granular_analysis_workflow(
            polygon_geometry=self.test_polygon,
            asset_name='Integration Test Asset',
            selected_hazards=['Heat', 'Flooding'],
            archetype='commercial',
            scenario='current',
            grid_spacing=0.01  # Larger spacing for faster testing
        )

        # Verify workflow success
        self.assertTrue(results.get('success'), f"Workflow should succeed: {results.get('error')}")
        self.assertIsNotNone(results.get('asset_id'), "Asset should be created")

        # Verify database records
        asset = Asset.objects.get(id=results['asset_id'])
        self.assertEqual(asset.name, 'Integration Test Asset')
        self.assertTrue(asset.has_granular_analysis)
        self.assertEqual(asset.granular_analysis_status, 'completed')

        # Verify granular results
        granular_results = GranularAnalysisResult.objects.filter(asset=asset)
        self.assertGreater(granular_results.count(), 0, "Granular results should be created")

        # Verify aggregated results
        self.assertIn('aggregated_results', results)
        self.assertIn('table_results', results)

        # Verify heatmap data
        self.assertIn('heatmap_data_generated', results)

    def test_workflow_status_tracking(self):
        """Test workflow status tracking and progress monitoring."""
        # Create test asset
        asset = Asset.objects.create(
            name='Status Test Asset',
            archetype='commercial',
            latitude=Decimal('37.7799'),
            longitude=Decimal('-122.4144'),
            polygon_geometry=self.test_polygon,
            asset_type='polygon',
            has_granular_analysis=True,
            granular_analysis_status='processing',
            granular_analysis_progress=45.5
        )

        # Create some granular results
        for i in range(5):
            GranularAnalysisResult.objects.create(
                asset=asset,
                latitude=Decimal('37.7799'),
                longitude=Decimal('-122.4144'),
                grid_row=i,
                grid_col=0,
                grid_spacing=0.001,
                hazard_type='Heat',
                scenario='current',
                result_data={'value': 20.0 + i},
                processing_status='completed' if i < 3 else 'pending'
            )

        service = GranularAnalysisWorkflowService()
        status = service.get_workflow_status(asset.id)

        self.assertTrue(status['success'])
        self.assertEqual(status['asset_name'], 'Status Test Asset')
        self.assertEqual(status['workflow_status'], 'processing')
        self.assertIn('progress', status)
        self.assertIn('hazard_status', status)


def run_granular_workflow_tests():
    """Run all granular workflow tests."""
    import unittest

    # Create test suite
    suite = unittest.TestSuite()

    # Add test cases
    suite.addTest(unittest.makeSuite(GranularWorkflowServiceTest))
    suite.addTest(unittest.makeSuite(GranularWorkflowAPITest))
    suite.addTest(unittest.makeSuite(GranularWorkflowIntegrationTest))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    # Run tests when script is executed directly
    success = run_granular_workflow_tests()
    if success:
        print("\n✅ All granular workflow tests passed!")
    else:
        print("\n❌ Some tests failed!")
        exit(1)