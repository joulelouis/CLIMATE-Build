"""
Compatibility Layer for Climate Hazards Analysis

This module provides backward compatibility for the existing frontend components
while using the new stateless backend architecture. It maintains the same API
contracts that the frontend expects while delegating to the new service layer.
"""

import logging
from typing import Dict, Any, List, Optional
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .asset_service import AssetService, AssetAnalysisService
from .asset_abstraction import AssetRepository, AssetCollection

logger = logging.getLogger(__name__)


class LegacyAPIAdapter:
    """
    Adapter class that provides legacy API compatibility using the new stateless architecture.
    This ensures existing frontend components continue to work without changes.
    """

    @staticmethod
    def format_legacy_facility_data(assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format asset data to match the legacy facility data format expected by frontend.

        Args:
            assets: List of assets from the new service layer

        Returns:
            List formatted for legacy frontend compatibility
        """
        legacy_data = []
        for asset in assets:
            # Convert to legacy format
            legacy_asset = {
                'id': asset['id'],
                'name': asset['name'],
                'archetype': asset.get('archetype', 'default archetype'),
                'latitude': asset.get('coordinates', {}).get('latitude', asset.get('latitude', 0)),
                'longitude': asset.get('coordinates', {}).get('longitude', asset.get('longitude', 0)),
                'asset_type': asset.get('asset_type', 'point'),
                'geojson': asset.get('geojson'),
                'properties': asset.get('properties', {}),
                # Legacy fields that frontend might expect
                'facility_type': asset.get('archetype', 'default archetype'),
                'hazard_data': asset.get('hazard_data', {}),
                'exposure_data': asset.get('hazard_exposures', []),
                'has_granular_data': asset.get('has_granular_data', False),
                'granular_status': asset.get('granular_status', 'none')
            }

            # Add hazard-specific data in expected format
            if 'hazard_data' in asset and asset['hazard_data']:
                for hazard_type, hazard_info in asset['hazard_data'].items():
                    if isinstance(hazard_info, dict):
                        # Add individual hazard fields
                        legacy_asset[f'{hazard_type}_severity'] = hazard_info.get('severity', 'unknown')
                        legacy_asset[f'{hazard_type}_value'] = hazard_info.get('value', 0)
                        legacy_asset[f'{hazard_type}_confidence'] = hazard_info.get('confidence', 0)

            legacy_data.append(legacy_asset)

        return legacy_data

    @staticmethod
    def format_legacy_analysis_result(asset_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format analysis results to match legacy format expected by frontend.

        Args:
            asset_data: Asset analysis data from new service layer

        Returns:
            Analysis results in legacy format
        """
        if 'error' in asset_data:
            return asset_data

        asset_info = asset_data.get('asset', {})
        analysis_results = asset_data.get('analysis_results', {})

        # Build legacy format response
        legacy_response = {
            'success': True,
            'asset_id': asset_info.get('id'),
            'asset_name': asset_info.get('name'),
            'asset_type': asset_info.get('type'),
            'coordinates': asset_info.get('coordinates'),
            'analysis_results': {},
            'has_granular_analysis': asset_data.get('has_granular_analysis', False),
            'granular_status': asset_data.get('granular_status', 'none'),
            'scenario': asset_data.get('scenario', 'current')
        }

        # Format each hazard type in expected legacy format
        for hazard_type, result_data in analysis_results.items():
            if isinstance(result_data, dict):
                legacy_response['analysis_results'][hazard_type] = {
                    'severity': result_data.get('severity', 'unknown'),
                    'value': result_data.get('value', 0),
                    'confidence': result_data.get('confidence', 0),
                    'exposure_level': result_data.get('severity', 'unknown'),
                    'risk_score': result_data.get('value', 0),
                    'metadata': result_data.get('metadata', {})
                }

        return legacy_response

    @staticmethod
    def create_success_response(data: Any, message: str = None) -> JsonResponse:
        """Create success response in format expected by legacy frontend."""
        response_data = {'success': True}
        if data is not None:
            response_data['data'] = data
        if message:
            response_data['message'] = message
        return JsonResponse(response_data)

    @staticmethod
    def create_error_response(message: str, status_code: int = 400) -> JsonResponse:
        """Create error response in format expected by legacy frontend."""
        return JsonResponse({
            'success': False,
            'error': message
        }, status=status_code)


# Legacy view wrappers that maintain existing API contracts

@csrf_exempt
@require_http_methods(["GET"])
def get_facility_data_legacy(request):
    """
    Legacy wrapper for getting facility data.
    Maintains exact same API contract as original get_facility_data view.
    """
    try:
        # Parse query parameters
        asset_type = request.GET.get('asset_type')
        hazard_types = request.GET.getlist('hazard_types')
        scenario = request.GET.get('scenario', 'current')

        # Parse bounds if provided
        bounds = None
        if all(key in request.GET for key in ['min_lat', 'max_lat', 'min_lng', 'max_lng']):
            bounds = {
                'min_lat': float(request.GET['min_lat']),
                'max_lat': float(request.GET['max_lat']),
                'min_lng': float(request.GET['min_lng']),
                'max_lng': float(request.GET['max_lng'])
            }

        # Use new service layer
        from .asset_abstraction import AssetBounds
        if bounds:
            asset_bounds = AssetBounds(**bounds)
            collection = AssetRepository.get_assets_within_bounds(**bounds)
        else:
            collection = AssetRepository.get_all_assets(asset_type)

        # Get visualization data
        assets_data = collection.to_visualization_data(hazard_types if hazard_types else None, scenario)

        # Format for legacy compatibility
        legacy_data = LegacyAPIAdapter.format_legacy_facility_data(
            [asset.to_leaflet_format() for asset in assets_data]
        )

        return LegacyAPIAdapter.create_success_response(legacy_data)

    except Exception as e:
        logger.error(f"Error in legacy get_facility_data: {str(e)}")
        return LegacyAPIAdapter.create_error_response(str(e), 500)


@csrf_exempt
@require_http_methods(["POST"])
def add_facility_legacy(request):
    """
    Legacy wrapper for adding facility data.
    Maintains exact same API contract as original add_facility view.
    """
    try:
        import json

        # Parse request data
        try:
            data = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return LegacyAPIAdapter.create_error_response("Invalid JSON data")

        # Extract required fields
        name = data.get('name')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        archetype = data.get('archetype', 'default archetype')
        properties = data.get('properties', {})

        if not name or latitude is None or longitude is None:
            return LegacyAPIAdapter.create_error_response("Missing required fields: name, latitude, longitude")

        # Use new service layer to create asset
        asset = AssetService.create_point_asset(
            name=name,
            latitude=float(latitude),
            longitude=float(longitude),
            archetype=archetype,
            properties=properties
        )

        # Format response for legacy compatibility
        asset_data = {
            'id': asset.id,
            'name': asset.name,
            'archetype': asset.archetype,
            'latitude': float(asset.latitude),
            'longitude': float(asset.longitude),
            'asset_type': asset.asset_type,
            'properties': asset.properties
        }

        return LegacyAPIAdapter.create_success_response(
            asset_data,
            "Facility added successfully"
        )

    except Exception as e:
        logger.error(f"Error in legacy add_facility: {str(e)}")
        return LegacyAPIAdapter.create_error_response(str(e), 500)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def polygon_assets_legacy(request):
    """
    Legacy wrapper for polygon assets operations.
    Maintains exact same API contract as original polygon endpoints.
    """
    try:
        if request.method == 'GET':
            # Get polygon assets
            assets = AssetService.get_all_assets(AssetType.POLYGON)

            polygon_data = []
            for asset in assets:
                polygon_data.append({
                    'id': asset.id,
                    'name': asset.name,
                    'archetype': asset.archetype,
                    'polygon_geometry': asset.polygon_geometry,
                    'coordinates': asset.coordinates,
                    'properties': asset.properties,
                    'has_granular_analysis': asset.has_granular_analysis,
                    'granular_status': asset.granular_analysis_status
                })

            return LegacyAPIAdapter.create_success_response(polygon_data)

        elif request.method == 'POST':
            # Create polygon asset
            import json
            data = json.loads(request.body.decode('utf-8'))

            name = data.get('name')
            polygon_geometry = data.get('polygon_geometry')
            archetype = data.get('archetype', 'default archetype')
            properties = data.get('properties', {})

            if not name or not polygon_geometry:
                return LegacyAPIAdapter.create_error_response("Missing required fields: name, polygon_geometry")

            asset = AssetService.create_polygon_asset(
                name=name,
                polygon_geometry=polygon_geometry,
                archetype=archetype,
                properties=properties
            )

            asset_data = {
                'id': asset.id,
                'name': asset.name,
                'archetype': asset.archetype,
                'polygon_geometry': asset.polygon_geometry,
                'coordinates': asset.coordinates,
                'asset_type': asset.asset_type,
                'properties': asset.properties
            }

            return LegacyAPIAdapter.create_success_response(
                asset_data,
                "Polygon asset created successfully"
            )

    except Exception as e:
        logger.error(f"Error in legacy polygon_assets: {str(e)}")
        return LegacyAPIAdapter.create_error_response(str(e), 500)


@csrf_exempt
@require_http_methods(["GET"])
def get_asset_analysis_results_legacy(request, asset_id):
    """
    Legacy wrapper for getting asset analysis results.
    Maintains exact same API contract as original get_asset_analysis_results view.
    """
    try:
        hazard_type = request.GET.get('hazard_type')
        scenario = request.GET.get('scenario', 'current')

        # Use new service layer
        analysis_data = AssetService.get_asset_analysis_results(asset_id, hazard_type, scenario)

        if 'error' in analysis_data:
            return LegacyAPIAdapter.create_error_response(analysis_data['error'], 404)

        # Format for legacy compatibility
        legacy_response = LegacyAPIAdapter.format_legacy_analysis_result(analysis_data)

        return JsonResponse(legacy_response)

    except Exception as e:
        logger.error(f"Error in legacy get_asset_analysis_results: {str(e)}")
        return LegacyAPIAdapter.create_error_response(str(e), 500)


@csrf_exempt
@require_http_methods(["GET"])
def get_heatmap_data_legacy(request, asset_id):
    """
    Legacy wrapper for getting heatmap data.
    Maintains exact same API contract as original get_heatmap_data view.
    """
    try:
        hazard_type = request.GET.get('hazard_type')
        scenario = request.GET.get('scenario', 'current')

        if not hazard_type:
            return LegacyAPIAdapter.create_error_response("hazard_type parameter is required")

        # Use new service layer through API views
        from .api_views import HeatmapDataView
        view = HeatmapDataView()
        return view.get(request, asset_id)

    except Exception as e:
        logger.error(f"Error in legacy get_heatmap_data: {str(e)}")
        return LegacyAPIAdapter.create_error_response(str(e), 500)


@csrf_exempt
@require_http_methods(["GET"])
def get_granular_analysis_status_legacy(request, asset_id):
    """
    Legacy wrapper for getting granular analysis status.
    Maintains exact same API contract as original get_granular_analysis_status view.
    """
    try:
        # Use new service layer
        granular_data = AssetAnalysisService.get_granular_analysis_data(asset_id)

        if 'error' in granular_data:
            return LegacyAPIAdapter.create_error_response(granular_data['error'], 404)

        # Format for legacy compatibility
        legacy_response = {
            'success': True,
            'asset_id': asset_id,
            'status': granular_data.get('granular_status', 'none'),
            'progress': granular_data.get('progress', 0.0),
            'grid_points_count': granular_data.get('grid_points_count', 0),
            'grid_spacing': granular_data.get('grid_spacing'),
            'results': granular_data.get('results_by_hazard', {}),
            'scenario': granular_data.get('scenario', 'current')
        }

        return JsonResponse(legacy_response)

    except Exception as e:
        logger.error(f"Error in legacy get_granular_analysis_status: {str(e)}")
        return LegacyAPIAdapter.create_error_response(str(e), 500)


@csrf_exempt
@require_http_methods(["POST"])
def clear_granular_workflow_legacy(request):
    """
    Legacy wrapper for clearing granular workflow.
    Since we're now stateless, this returns success without doing anything.
    """
    try:
        # In the new stateless architecture, there's no session state to clear
        # This is maintained for backward compatibility only
        return LegacyAPIAdapter.create_success_response(
            None,
            "Granular workflow cleared (stateless mode)"
        )

    except Exception as e:
        logger.error(f"Error in legacy clear_granular_workflow: {str(e)}")
        return LegacyAPIAdapter.create_error_response(str(e), 500)


@csrf_exempt
@require_http_methods(["GET"])
def get_granular_workflow_state_legacy(request):
    """
    Legacy wrapper for getting granular workflow state.
    Since we're now stateless, this returns default state.
    """
    try:
        # In the new stateless architecture, workflow state is asset-based, not session-based
        # Return a default state for backward compatibility
        state_response = {
            'success': True,
            'is_granular_workflow': False,  # No session-based workflow
            'workflow_step': 'none',
            'has_polygon_geometry': False,
            'has_grid_configuration': False,
            'asset_id': None,
            'mode': 'stateless'  # Indicate we're using the new architecture
        }

        return JsonResponse(state_response)

    except Exception as e:
        logger.error(f"Error in legacy get_granular_workflow_state: {str(e)}")
        return LegacyAPIAdapter.create_error_response(str(e), 500)


# Import AssetType for the functions above
from .asset_service import AssetType