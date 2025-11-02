"""
Test suite for the streamlined draw polygon workflow.

This test suite validates the streamlined workflow that bypasses the 6-step process
and goes directly from hazard selection to hazard analysis results.
"""

import json
from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, Mock
from django.contrib.sessions.middleware import SessionMiddleware

from climate_hazards_analysis_v2.session_utils import GranularAnalysisSessionManager


class StreamlinedWorkflowTest(TestCase):
    """Test the streamlined draw polygon workflow."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

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

        self.test_hazards = [
            'Flood',
            'Water Stress',
            'Heat',
            'Sea Level Rise',
            'Tropical Cyclones',
            'Storm Surge',
            'Rainfall Induced Landslide'
        ]

    def _add_session_to_request(self, request):
        """Add session middleware to request."""
        middleware = SessionMiddleware()
        middleware.process_request(request)
        request.session.save()

    def test_select_hazards_streamlined_redirect(self):
        """Test that streamlined hazard selection redirects properly."""
        # Initialize session with granular workflow
        session = self.client.session
        session['streamlined_workflow'] = True
        session.save()

        # Mock the session manager
        with patch('climate_hazards_analysis_v2.views.GranularAnalysisSessionManager.is_granular_workflow') as mock_check:
            mock_check.return_value = True
            with patch('climate_hazards_analysis_v2.views.GranularAnalysisSessionManager.get_polygon_geometry') as mock_geometry:
                mock_geometry.return_value = self.test_polygon

                # Test streamlined hazard selection
                response = self.client.get(reverse('climate_hazards_analysis_v2:select_hazards_streamlined'))

                # Should redirect to results (auto-selects hazards)
                self.assertEqual(response.status_code, 302)
                self.assertIn('hazard-exposure-results-streamlined', response.url)

    @patch('climate_hazards_analysis_v2.views.generate_grid_points_from_polygon')
    @patch('climate_hazards_analysis_v2.views._get_hazard_value_at_point')
    def test_hazard_analysis_results_streamlined(self, mock_hazard_value, mock_grid_points):
        """Test the streamlined hazard analysis results view."""

        # Mock grid points generation
        mock_grid_points.return_value = [
            {'latitude': 37.7799, 'longitude': -122.4144},
            {'latitude': 37.7799, 'longitude': -122.4144}
        ]

        # Mock hazard values
        mock_hazard_value.return_value = 1.5  # Medium risk value

        # Initialize session with polygon data
        session = self.client.session
        session['climate_hazards_v2_selected_hazards'] = ['Flood', 'Heat']
        session.save()

        # Mock the session manager
        with patch('climate_hazards_analysis_v2.views.GranularAnalysisSessionManager.get_polygon_geometry') as mock_geometry:
            mock_geometry.return_value = self.test_polygon

            # Test streamlined results
            response = self.client.get(reverse('climate_hazards_analysis_v2:hazard_exposure_results_streamlined'))

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'hazardResultsTable')
            self.assertContains(response, 'Drawn Polygon Asset')

    def test_draw_polygon_complete_sets_streamlined_flag(self):
        """Test that draw polygon completion sets streamlined workflow flag."""
        response = self.client.post(reverse('climate_hazards_analysis_v2:draw_polygon_complete'),
                                  json.dumps({'geometry': self.test_polygon}),
                                  content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        self.assertEqual(data['next_step'], 'streamlined_hazard_analysis')
        self.assertIn('redirect_url', data)

    def test_polygon_centroid_calculation(self):
        """Test polygon centroid calculation."""
        from climate_hazards_analysis_v2.views import calculate_polygon_centroid

        centroid = calculate_polygon_centroid(self.test_polygon)

        # Should return a tuple of (lat, lng)
        self.assertIsInstance(centroid, tuple)
        self.assertEqual(len(centroid), 2)

        # Should be within the polygon bounds
        self.assertTrue(37.7749 <= centroid[0] <= 37.7849)  # Latitude
        self.assertTrue(-122.4194 <= centroid[1] <= -122.4094)  # Longitude

    def test_polygon_area_calculation(self):
        """Test polygon area calculation."""
        from climate_hazards_analysis_v2.views import calculate_polygon_area_km2

        area = calculate_polygon_area_km2(self.test_polygon)

        # Should return a positive area value
        self.assertGreater(area, 0)
        self.assertIsInstance(area, float)

    def test_risk_level_calculation(self):
        """Test risk level calculation for different hazards."""
        from climate_hazards_analysis_v2.views import _calculate_risk_level

        # Test flood risk levels
        self.assertEqual(_calculate_risk_level(None, 'Flood'), 'No Data')
        self.assertEqual(_calculate_risk_level(0, 'Flood'), 'No Risk')
        self.assertEqual(_calculate_risk_level(0.3, 'Flood'), 'Low')
        self.assertEqual(_calculate_risk_level(1.0, 'Flood'), 'Medium')
        self.assertEqual(_calculate_risk_level(2.0, 'Flood'), 'High')
        self.assertEqual(_calculate_risk_level(4.0, 'Flood'), 'Very High')

        # Test heat risk levels
        self.assertEqual(_calculate_risk_level(0.5, 'Heat'), 'Low')
        self.assertEqual(_calculate_risk_level(1.5, 'Heat'), 'Medium')
        self.assertEqual(_calculate_risk_level(3.0, 'Heat'), 'High')
        self.assertEqual(_calculate_risk_level(4.0, 'Heat'), 'Very High')

    def test_hazard_value_formatting(self):
        """Test hazard value formatting for display."""
        from climate_hazards_analysis_v2.views import _format_hazard_value

        # Test different hazard types
        self.assertEqual(_format_hazard_value(1.5, 'Flood'), '1.50 m')
        self.assertEqual(_format_hazard_value(2.3, 'Heat'), '2.3°C')
        self.assertEqual(_format_hazard_value(0.25, 'Water Stress'), '25.0%')
        self.assertEqual(_format_hazard_value(None, 'Flood'), 'N/A')

    def test_risk_color_mapping(self):
        """Test risk color mapping."""
        from climate_hazards_analysis_v2.views import _get_risk_color

        self.assertEqual(_get_risk_color('No Data'), '#6c757d')
        self.assertEqual(_get_risk_color('No Risk'), '#28a745')
        self.assertEqual(_get_risk_color('Low'), '#ffc107')
        self.assertEqual(_get_risk_color('Medium'), '#fd7e14')
        self.assertEqual(_get_risk_color('High'), '#dc3545')
        self.assertEqual(_get_risk_color('Very High'), '#6f42c1')

    @patch('climate_hazards_analysis_v2.views.generate_grid_points_from_polygon')
    def test_prepare_hierarchical_results(self, mock_grid_points):
        """Test hierarchical results preparation."""
        from climate_hazards_analysis_v2.views import _prepare_hierarchical_results_streamlined

        # Mock analysis results
        mock_analysis_results = {
            'centroid': {
                'point_id': 'centroid',
                'latitude': 37.7799,
                'longitude': -122.4144,
                'hazards': {
                    'Flood': 1.5,
                    'Heat': 2.0
                }
            },
            'granular_points': [
                {
                    'point_id': 'point_1',
                    'latitude': 37.7799,
                    'longitude': -122.4144,
                    'hazards': {
                        'Flood': 1.2,
                        'Heat': 2.1
                    }
                }
            ],
            'aggregated_stats': {}
        }

        results = _prepare_hierarchical_results_streamlined(
            mock_analysis_results, ['Flood', 'Heat']
        )

        # Should have parent row and child rows
        self.assertEqual(len(results), 2)

        # First row should be parent (centroid)
        self.assertTrue(results[0]['is_parent'])
        self.assertEqual(results[0]['facility_name'], 'Drawn Polygon Asset (Centroid)')

        # Second row should be child
        self.assertTrue(results[1]['is_child'])
        self.assertEqual(results[1]['facility_name'], 'Analysis Point 1')