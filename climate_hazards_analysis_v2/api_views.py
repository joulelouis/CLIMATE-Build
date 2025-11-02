"""
Stateless API Views for Climate Hazards Analysis

This module provides stateless API endpoints that work with the existing frontend components
while eliminating session dependencies and providing unified asset handling.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator
from django.views import View

from .asset_service import (
    AssetService, AssetAnalysisService, AssetType, AnalysisStatus,
    create_asset, get_asset_with_analysis
)
from .utils import load_cached_hazard_data
from .granular_utils import (
    generate_grid_points_from_polygon, create_heatmap_data,
    calculate_granular_statistics
)

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class AssetAPIView(View):
    """
    Base class for asset-related API views providing common functionality.
    """

    @staticmethod
    def success_response(data: Any = None, message: str = None) -> JsonResponse:
        """Create a success response."""
        response_data = {'success': True}
        if data is not None:
            response_data['data'] = data
        if message:
            response_data['message'] = message
        return JsonResponse(response_data)

    @staticmethod
    def error_response(message: str, status_code: int = 400) -> JsonResponse:
        """Create an error response."""
        return JsonResponse({
            'success': False,
            'error': message
        }, status=status_code)

    @staticmethod
    def parse_request_body(request) -> Dict[str, Any]:
        """Parse JSON request body."""
        try:
            return json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValidationError(f"Invalid request body: {str(e)}")


@method_decorator(csrf_exempt, name='dispatch')
class AssetListCreateView(AssetAPIView):
    """
    API view for listing and creating assets (both point and polygon).
    Replaces multiple session-dependent endpoints with a unified interface.
    """

    def get(self, request):
        """
        Get list of assets with optional filtering.
        Maintains compatibility with existing frontend asset loading.
        """
        try:
            # Parse query parameters for filtering
            asset_type = request.GET.get('asset_type')
            bounds = {}
            if all(key in request.GET for key in ['min_lat', 'max_lat', 'min_lng', 'max_lng']):
                bounds = {
                    'min_lat': float(request.GET['min_lat']),
                    'max_lat': float(request.GET['max_lat']),
                    'min_lng': float(request.GET['min_lng']),
                    'max_lng': float(request.GET['max_lng'])
                }

            hazard_types = request.GET.getlist('hazard_types')
            scenario = request.GET.get('scenario', 'current')

            # Get assets using unified service
            if bounds:
                assets = AssetService.get_assets_within_bounds(**bounds, asset_type=asset_type)
            else:
                assets = AssetService.get_all_assets(asset_type=asset_type)

            # Format response for frontend compatibility
            assets_data = []
            for asset in assets:
                asset_data = {
                    'id': asset.id,
                    'name': asset.name,
                    'archetype': asset.archetype,
                    'asset_type': asset.asset_type,
                    'latitude': float(asset.latitude),
                    'longitude': float(asset.longitude),
                    'geojson': asset.geojson,
                    'properties': asset.properties,
                    'has_granular_analysis': asset.has_granular_analysis,
                    'granular_status': asset.granular_analysis_status
                }

                # Add hazard analysis results if requested
                if hazard_types:
                    analysis_results = AssetService.get_asset_analysis_results(
                        asset.id, scenario=scenario
                    )
                    if 'error' not in analysis_results:
                        asset_data['hazard_data'] = analysis_results.get('analysis_results', {})

                assets_data.append(asset_data)

            return self.success_response(assets_data)

        except Exception as e:
            logger.error(f"Error in asset list: {str(e)}")
            return self.error_response(str(e), 500)

    def post(self, request):
        """
        Create a new asset (point or polygon).
        Replaces multiple asset creation endpoints with unified interface.
        """
        try:
            data = self.parse_request_body(request)

            # Validate required fields
            if 'name' not in data:
                return self.error_response("Asset name is required")

            name = data['name']
            asset_type = data.get('asset_type', AssetType.POINT)

            if asset_type == AssetType.POLYGON:
                # Create polygon asset
                if 'polygon_geometry' not in data:
                    return self.error_response("Polygon geometry is required for polygon assets")

                asset = AssetService.create_polygon_asset(
                    name=name,
                    polygon_geometry=data['polygon_geometry'],
                    archetype=data.get('archetype', 'default archetype'),
                    properties=data.get('properties', {})
                )
            else:
                # Create point asset
                if 'latitude' not in data or 'longitude' not in data:
                    return self.error_response("Latitude and longitude are required for point assets")

                asset = AssetService.create_point_asset(
                    name=name,
                    latitude=float(data['latitude']),
                    longitude=float(data['longitude']),
                    archetype=data.get('archetype', 'default archetype'),
                    properties=data.get('properties', {})
                )

            # Return asset data in format expected by frontend
            asset_data = {
                'id': asset.id,
                'name': asset.name,
                'archetype': asset.archetype,
                'asset_type': asset.asset_type,
                'latitude': float(asset.latitude),
                'longitude': float(asset.longitude),
                'geojson': asset.geojson,
                'properties': asset.properties
            }

            return self.success_response(asset_data, f"{asset_type.title()} asset created successfully")

        except ValidationError as e:
            return self.error_response(str(e))
        except Exception as e:
            logger.error(f"Error creating asset: {str(e)}")
            return self.error_response(str(e), 500)


@method_decorator(csrf_exempt, name='dispatch')
class AssetDetailView(AssetAPIView):
    """
    API view for retrieving, updating, and deleting individual assets.
    """

    def get(self, request, asset_id):
        """
        Get detailed asset information with analysis results.
        Compatible with existing frontend popup and detail views.
        """
        try:
            hazard_types = request.GET.getlist('hazard_types')
            scenario = request.GET.get('scenario', 'current')
            include_granular = request.GET.get('include_granular', 'false').lower() == 'true'

            # Get comprehensive asset data
            if include_granular:
                asset_data = get_asset_with_analysis(asset_id, hazard_types)
            else:
                asset_data = AssetService.get_asset_analysis_results(
                    asset_id, hazard_types[0] if hazard_types else None, scenario
                )

            if 'error' in asset_data:
                return self.error_response(asset_data['error'], 404)

            return self.success_response(asset_data)

        except Exception as e:
            logger.error(f"Error getting asset detail: {str(e)}")
            return self.error_response(str(e), 500)

    def put(self, request, asset_id):
        """Update asset properties."""
        try:
            data = self.parse_request_body(request)
            asset = AssetService.update_asset(asset_id, **data)

            asset_data = {
                'id': asset.id,
                'name': asset.name,
                'archetype': asset.archetype,
                'asset_type': asset.asset_type,
                'latitude': float(asset.latitude),
                'longitude': float(asset.longitude),
                'geojson': asset.geojson,
                'properties': asset.properties
            }

            return self.success_response(asset_data, "Asset updated successfully")

        except ValidationError as e:
            return self.error_response(str(e))
        except Exception as e:
            logger.error(f"Error updating asset: {str(e)}")
            return self.error_response(str(e), 500)

    def delete(self, request, asset_id):
        """Delete an asset."""
        try:
            success = AssetService.delete_asset(asset_id)
            if success:
                return self.success_response(message="Asset deleted successfully")
            else:
                return self.error_response("Asset not found", 404)

        except Exception as e:
            logger.error(f"Error deleting asset: {str(e)}")
            return self.error_response(str(e), 500)


@method_decorator(csrf_exempt, name='dispatch')
class AssetAnalysisView(AssetAPIView):
    """
    API view for asset hazard analysis operations.
    Replaces session-dependent analysis endpoints with stateless operations.
    """

    def get(self, request, asset_id):
        """Get analysis results for an asset."""
        try:
            hazard_type = request.GET.get('hazard_type')
            scenario = request.GET.get('scenario', 'current')

            results = AssetService.get_asset_analysis_results(asset_id, hazard_type, scenario)

            if 'error' in results:
                return self.error_response(results['error'], 404)

            return self.success_response(results)

        except Exception as e:
            logger.error(f"Error getting analysis results: {str(e)}")
            return self.error_response(str(e), 500)

    def post(self, request, asset_id):
        """Save or update analysis results for an asset."""
        try:
            data = self.parse_request_body(request)

            hazard_type = data.get('hazard_type')
            result_data = data.get('result_data')
            scenario = data.get('scenario', 'current')

            if not hazard_type or not result_data:
                return self.error_response("hazard_type and result_data are required")

            result = AssetService.save_hazard_analysis_result(
                asset_id, hazard_type, result_data, scenario
            )

            return self.success_response({
                'id': result.id,
                'hazard_type': result.hazard_type,
                'scenario': result.scenario,
                'analysis_date': result.analysis_date.isoformat()
            }, "Analysis results saved successfully")

        except ValidationError as e:
            return self.error_response(str(e))
        except Exception as e:
            logger.error(f"Error saving analysis results: {str(e)}")
            return self.error_response(str(e), 500)


@method_decorator(csrf_exempt, name='dispatch')
class GranularAnalysisView(AssetAPIView):
    """
    API view for granular analysis operations.
    Provides stateless alternative to session-based granular workflow.
    """

    def post(self, request, asset_id):
        """Initialize granular analysis for a polygon asset."""
        try:
            data = self.parse_request_body(request)
            grid_spacing = data.get('grid_spacing', 0.01)

            asset = AssetAnalysisService.initialize_granular_analysis(asset_id, grid_spacing)

            # Generate grid points for the polygon
            grid_points = generate_grid_points_from_polygon(
                asset.polygon_geometry, grid_spacing
            )

            # Update asset with grid point count
            AssetAnalysisService.update_granular_analysis_status(
                asset_id, AnalysisStatus.PROCESSING,
                grid_points_count=len(grid_points)
            )

            return self.success_response({
                'asset_id': asset.id,
                'grid_spacing': grid_spacing,
                'grid_points_count': len(grid_points),
                'grid_points': grid_points,
                'status': asset.granular_analysis_status
            }, "Granular analysis initialized successfully")

        except ValidationError as e:
            return self.error_response(str(e))
        except Exception as e:
            logger.error(f"Error initializing granular analysis: {str(e)}")
            return self.error_response(str(e), 500)

    def get(self, request, asset_id):
        """Get granular analysis status and results."""
        try:
            hazard_type = request.GET.get('hazard_type')
            scenario = request.GET.get('scenario', 'current')

            data = AssetAnalysisService.get_granular_analysis_data(
                asset_id, hazard_type, scenario
            )

            if 'error' in data:
                return self.error_response(data['error'], 404)

            return self.success_response(data)

        except Exception as e:
            logger.error(f"Error getting granular analysis: {str(e)}")
            return self.error_response(str(e), 500)

    def put(self, request, asset_id):
        """Update granular analysis status."""
        try:
            data = self.parse_request_body(request)
            status = data.get('status')
            progress = data.get('progress')
            grid_points_count = data.get('grid_points_count')
            error_message = data.get('error_message')

            if not status:
                return self.error_response("Status is required")

            asset = AssetAnalysisService.update_granular_analysis_status(
                asset_id, status, progress, grid_points_count, error_message
            )

            return self.success_response({
                'asset_id': asset.id,
                'status': asset.granular_analysis_status,
                'progress': asset.granular_analysis_progress,
                'grid_points_count': asset.granular_grid_points_count
            }, "Granular analysis status updated successfully")

        except ValidationError as e:
            return self.error_response(str(e))
        except Exception as e:
            logger.error(f"Error updating granular analysis: {str(e)}")
            return self.error_response(str(e), 500)


@method_decorator(csrf_exempt, name='dispatch')
class GranularAnalysisPointView(AssetAPIView):
    """
    API view for managing individual granular analysis points.
    """

    def post(self, request, asset_id):
        """Save granular analysis result for a grid point."""
        try:
            data = self.parse_request_body(request)

            # Validate required fields
            required_fields = ['latitude', 'longitude', 'grid_row', 'grid_col', 'hazard_type', 'result_data']
            for field in required_fields:
                if field not in data:
                    return self.error_response(f"{field} is required")

            result = AssetAnalysisService.save_granular_analysis_point(
                asset_id=asset_id,
                latitude=float(data['latitude']),
                longitude=float(data['longitude']),
                grid_row=int(data['grid_row']),
                grid_col=int(data['grid_col']),
                hazard_type=data['hazard_type'],
                result_data=data['result_data'],
                scenario=data.get('scenario', 'current')
            )

            return self.success_response({
                'id': result.id,
                'grid_position': {'row': result.grid_row, 'col': result.grid_col},
                'hazard_type': result.hazard_type,
                'status': result.processing_status
            }, "Granular analysis point saved successfully")

        except ValidationError as e:
            return self.error_response(str(e))
        except Exception as e:
            logger.error(f"Error saving granular analysis point: {str(e)}")
            return self.error_response(str(e), 500)


@method_decorator(csrf_exempt, name='dispatch')
class HeatmapDataView(AssetAPIView):
    """
    API view for heatmap data generation and retrieval.
    """

    def get(self, request, asset_id):
        """Get heatmap data for an asset."""
        try:
            hazard_type = request.GET.get('hazard_type')
            scenario = request.GET.get('scenario', 'current')

            if not hazard_type:
                return self.error_response("hazard_type parameter is required")

            asset = AssetService.get_asset_by_id(asset_id)
            if not asset:
                return self.error_response("Asset not found", 404)

            # Get existing heatmap data or generate new one
            heatmap = asset.heatmap_data.filter(
                hazard_type=hazard_type, scenario=scenario
            ).first()

            if not heatmap:
                # Generate heatmap data from granular results
                granular_results = asset.granular_results.filter(
                    hazard_type=hazard_type, scenario=scenario,
                    processing_status=AnalysisStatus.COMPLETED
                )

                if granular_results.exists():
                    heatmap = create_heatmap_data(asset, granular_results, hazard_type, scenario)
                else:
                    return self.error_response("No data available for heatmap generation")

            return self.success_response({
                'asset_id': asset_id,
                'hazard_type': hazard_type,
                'scenario': scenario,
                'heatmap_data': heatmap.get_heatmap_grid(),
                'statistics': {
                    'min_value': heatmap.min_value,
                    'max_value': heatmap.max_value,
                    'mean_value': heatmap.mean_value,
                    'median_value': heatmap.median_value
                }
            })

        except Exception as e:
            logger.error(f"Error getting heatmap data: {str(e)}")
            return self.error_response(str(e), 500)


@method_decorator(csrf_exempt, name='dispatch')
class AssetVisualizationView(AssetAPIView):
    """
    API view for getting assets formatted for visualization.
    Maintains compatibility with existing HazardLayerManager and frontend components.
    """

    def get(self, request):
        """
        Get assets formatted for map visualization with hazard data.
        Direct replacement for existing facility data API.
        """
        try:
            # Parse query parameters
            hazard_types = request.GET.getlist('hazard_types')
            scenario = request.GET.get('scenario', 'current')
            bounds = {}

            # Parse bounds if provided
            if all(key in request.GET for key in ['min_lat', 'max_lat', 'min_lng', 'max_lng']):
                bounds = {
                    'min_lat': float(request.GET['min_lat']),
                    'max_lat': float(request.GET['max_lat']),
                    'min_lng': float(request.GET['min_lng']),
                    'max_lng': float(request.GET['max_lng'])
                }

            # Get visualization data using unified service
            assets_data = AssetService.get_assets_for_visualization(
                hazard_types=hazard_types if hazard_types else None,
                bounds=bounds if bounds else None,
                scenario=scenario
            )

            # Transform asset data to match existing frontend HazardLayerManager format
            geojson_data = self._transform_assets_to_geojson(assets_data)

            # Extract heatmap layers for granular analysis compatibility
            heatmap_layers = {}
            for asset in assets_data:
                if asset['asset_type'] == 'polygon' and 'heatmaps' in asset:
                    for hazard_type, heatmap_data in asset['heatmaps'].items():
                        if heatmap_data and 'grid_points' in heatmap_data:
                            heatmap_layers[hazard_type] = heatmap_data

            # Create response that matches existing frontend expectations
            response_data = {
                'type': 'FeatureCollection',
                'features': geojson_data
            }

            # Include metadata for compatibility with existing frontend
            metadata = {
                'total_facilities': len(assets_data),
                'selected_hazards': hazard_types or ['all'],
                'hazard_configs': {
                    'Flood': {'icon': 'fas fa-water', 'color': '#5DADE2'},
                    'Water Stress': {'icon': 'fas fa-tint', 'color': '#1ABC9C'},
                    'Sea Level Rise': {'icon': 'fas fa-water', 'color': '#007bff'},
                    'Tropical Cyclones': {'icon': 'fas fa-wind', 'color': '#95A5A6'},
                    'Heat': {'icon': 'fas fa-temperature-high', 'color': '#E74C3C'},
                    'Storm Surge': {'icon': 'fas fa-water', 'color': '#0056b3'},
                    'Rainfall Induced Landslide': {'icon': 'fas fa-mountain', 'color': '#8E44AD'}
                },
                'scenario': scenario,
                'assets': assets_data,  # Include raw assets data for granular analysis
                'heatmap_layers': heatmap_layers  # Include heatmap data for granular analysis
            }

            # Return in the exact format the existing frontend expects
            return JsonResponse({
                'success': True,
                'data': response_data,
                'metadata': metadata
            })

        except Exception as e:
            logger.error(f"Error getting visualization data: {str(e)}")
            return self.error_response(str(e), 500)

    def _transform_assets_to_geojson(self, assets_data):
        """
        Transform asset data to GeoJSON format compatible with existing HazardLayerManager.
        This maintains exact compatibility with existing frontend JavaScript code.
        """
        features = []

        for asset in assets_data:
            if asset['asset_type'] == 'point':
                # Create point feature
                hazard_values = self._extract_hazard_values(asset['hazard_data'])

                feature = {
                    'type': 'Feature',
                    'properties': {
                        'name': asset['name'],
                        'archetype': asset['archetype'],
                        'asset_type': asset['asset_type'],
                        'hazard_values': hazard_values,
                        'selected_hazards': list(hazard_values.keys()),
                        'latitude': asset['coordinates'][1] if len(asset['coordinates']) >= 2 else 0,
                        'longitude': asset['coordinates'][0] if len(asset['coordinates']) >= 1 else 0,
                        'asset_id': asset['id'],
                        'feature_type': 'facility'
                    },
                    'geometry': {
                        'type': 'Point',
                        'coordinates': asset['coordinates']
                    }
                }
                features.append(feature)

            elif asset['asset_type'] == 'polygon':
                # Create polygon feature for granular analysis areas
                if 'heatmaps' in asset:
                    # Store granular analysis data for heatmap functionality
                    heatmap_layers = {}
                    for hazard_type, heatmap_grid in asset['heatmaps'].items():
                        if heatmap_grid and 'grid_points' in heatmap_grid:
                            heatmap_layers[hazard_type] = heatmap_grid

                    # Add polygon boundary feature
                    boundary_feature = {
                        'type': 'Feature',
                        'properties': {
                            'name': asset['name'],
                            'archetype': asset['archetype'],
                            'asset_type': 'polygon',
                            'feature_type': 'boundary',
                            'asset_id': asset['id'],
                            'hazard_values': self._extract_hazard_values(asset['hazard_data'])
                        },
                        'geometry': asset['geojson']
                    }
                    features.append(boundary_feature)

                # Create representative point feature for polygon (for popups and interaction)
                if asset['coordinates'] and len(asset['coordinates']) >= 2:
                    hazard_values = self._extract_hazard_values(asset['hazard_data'])

                    center_feature = {
                        'type': 'Feature',
                        'properties': {
                            'name': asset['name'],
                            'archetype': asset['archetype'],
                            'asset_type': 'polygon',
                            'hazard_values': hazard_values,
                            'selected_hazards': list(hazard_values.keys()),
                            'latitude': asset['coordinates'][1],
                            'longitude': asset['coordinates'][0],
                            'asset_id': asset['id'],
                            'feature_type': 'facility',
                            'is_polygon_center': True
                        },
                        'geometry': {
                            'type': 'Point',
                            'coordinates': asset['coordinates']
                        }
                    }
                    features.append(center_feature)

        return features

    def _extract_hazard_values(self, hazard_data):
        """
        Extract hazard values from asset hazard_data in the format expected by existing frontend.
        """
        hazard_values = {}

        for hazard_type, data in hazard_data.items():
            if isinstance(data, dict):
                # Extract the primary exposure value from the hazard data
                if 'exposure_percentage' in data:
                    hazard_values[hazard_type] = float(data['exposure_percentage'])
                elif 'risk_score' in data:
                    hazard_values[hazard_type] = float(data['risk_score'])
                elif 'value' in data:
                    hazard_values[hazard_type] = float(data['value'])
                else:
                    # Try to find a numeric value in the data
                    numeric_values = [float(v) for v in data.values() if isinstance(v, (int, float)) and v > 0]
                    if numeric_values:
                        hazard_values[hazard_type] = max(numeric_values)  # Use the maximum value as representative
                    else:
                        hazard_values[hazard_type] = 0.0
            elif isinstance(data, (int, float)):
                hazard_values[hazard_type] = float(data)
            else:
                hazard_values[hazard_type] = 0.0

        return hazard_values


@method_decorator(csrf_exempt, name='dispatch')
class AssetStatisticsView(AssetAPIView):
    """
    API view for getting asset and analysis statistics.
    """

    def get(self, request):
        """Get system statistics."""
        try:
            asset_type = request.GET.get('asset_type')
            stats = AssetService.get_asset_statistics(asset_type)
            return self.success_response(stats)

        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return self.error_response(str(e), 500)


# Function-based views for backward compatibility
@csrf_exempt
@require_http_methods(["GET", "POST"])
def assets_api(request):
    """
    Unified assets API endpoint.
    GET: List assets with optional filtering
    POST: Create new asset
    """
    view = AssetListCreateView()
    if request.method == 'GET':
        return view.get(request)
    elif request.method == 'POST':
        return view.post(request)


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def asset_detail_api(request, asset_id):
    """
    Asset detail API endpoint.
    GET: Get asset details
    PUT: Update asset
    DELETE: Delete asset
    """
    view = AssetDetailView()
    if request.method == 'GET':
        return view.get(request, asset_id)
    elif request.method == 'PUT':
        return view.put(request, asset_id)
    elif request.method == 'DELETE':
        return view.delete(request, asset_id)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def asset_analysis_api(request, asset_id):
    """
    Asset analysis API endpoint.
    GET: Get analysis results
    POST: Save analysis results
    """
    view = AssetAnalysisView()
    if request.method == 'GET':
        return view.get(request, asset_id)
    elif request.method == 'POST':
        return view.post(request, asset_id)


@csrf_exempt
@require_http_methods(["GET", "POST", "PUT"])
def granular_analysis_api(request, asset_id):
    """
    Granular analysis API endpoint.
    GET: Get granular analysis data
    POST: Initialize granular analysis
    PUT: Update granular analysis status
    """
    view = GranularAnalysisView()
    if request.method == 'GET':
        return view.get(request, asset_id)
    elif request.method == 'POST':
        return view.post(request, asset_id)
    elif request.method == 'PUT':
        return view.put(request, asset_id)


@csrf_exempt
@require_http_methods(["GET"])
def heatmap_data_api(request, asset_id):
    """
    Heatmap data API endpoint.
    GET: Get heatmap data for asset
    """
    view = HeatmapDataView()
    return view.get(request, asset_id)


@csrf_exempt
@require_http_methods(["GET"])
def visualization_data_api(request):
    """
    Visualization data API endpoint.
    GET: Get assets formatted for visualization
    """
    view = AssetVisualizationView()
    return view.get(request)