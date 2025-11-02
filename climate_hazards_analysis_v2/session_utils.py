"""
Session management utilities for granular analysis workflow.
This module provides functions to manage session state for polygon drawing and granular analysis.
"""

import logging
from typing import Dict, Any, Optional, List
from django.http import HttpRequest
from django.utils import timezone

logger = logging.getLogger(__name__)


class GranularAnalysisSessionManager:
    """
    Manager class for handling granular analysis session state.
    Provides methods to store, retrieve, and manage workflow data across requests.
    """

    # Session keys for granular analysis workflow
    GRANULAR_WORKFLOW_KEY = 'climate_hazards_v2_granular_workflow'
    POLYGON_GEOMETRY_KEY = 'climate_hazards_v2_polygon_geometry'
    GRID_POINTS_KEY = 'climate_hazards_v2_grid_points'
    GRID_SPACING_KEY = 'climate_hazards_v2_grid_spacing'
    POLYGON_ASSET_ID_KEY = 'climate_hazards_v2_polygon_asset_id'
    WORKFLOW_STEP_KEY = 'climate_hazards_v2_workflow_step'

    @staticmethod
    def initialize_granular_workflow(request: HttpRequest) -> None:
        """
        Initialize the granular analysis workflow in session.

        Args:
            request: Django request object
        """
        if not request.session.session_key:
            request.session.create()

        request.session[GranularAnalysisSessionManager.GRANULAR_WORKFLOW_KEY] = True
        request.session[GranularAnalysisSessionManager.WORKFLOW_STEP_KEY] = 'drawing'
        request.session.modified = True

        logger.info(f"Initialized granular analysis workflow for session {request.session.session_key}")

    @staticmethod
    def is_granular_workflow(request: HttpRequest) -> bool:
        """
        Check if current session is in granular analysis workflow.

        Args:
            request: Django request object

        Returns:
            bool: True if in granular workflow
        """
        return request.session.get(GranularAnalysisSessionManager.GRANULAR_WORKFLOW_KEY, False)

    @staticmethod
    def store_polygon_geometry(request: HttpRequest, geometry: Dict[str, Any]) -> None:
        """
        Store polygon geometry in session.

        Args:
            request: Django request object
            geometry: GeoJSON polygon geometry
        """
        request.session[GranularAnalysisSessionManager.POLYGON_GEOMETRY_KEY] = geometry
        request.session[GranularAnalysisSessionManager.WORKFLOW_STEP_KEY] = 'grid_setup'
        request.session.modified = True

        logger.info(f"Stored polygon geometry in session {request.session.session_key}")

    @staticmethod
    def get_polygon_geometry(request: HttpRequest) -> Optional[Dict[str, Any]]:
        """
        Retrieve polygon geometry from session.

        Args:
            request: Django request object

        Returns:
            dict: GeoJSON polygon geometry or None if not found
        """
        return request.session.get(GranularAnalysisSessionManager.POLYGON_GEOMETRY_KEY)

    @staticmethod
    def store_grid_configuration(request: HttpRequest, grid_points: List, grid_spacing: float) -> None:
        """
        Store grid configuration in session.

        Args:
            request: Django request object
            grid_points: List of grid point coordinates
            grid_spacing: Grid spacing value
        """
        request.session[GranularAnalysisSessionManager.GRID_POINTS_KEY] = grid_points
        request.session[GranularAnalysisSessionManager.GRID_SPACING_KEY] = grid_spacing
        request.session[GranularAnalysisSessionManager.WORKFLOW_STEP_KEY] = 'asset_creation'
        request.session.modified = True

        logger.info(f"Stored grid configuration ({len(grid_points)} points) in session {request.session.session_key}")

    @staticmethod
    def get_grid_configuration(request: HttpRequest) -> tuple:
        """
        Retrieve grid configuration from session.

        Args:
            request: Django request object

        Returns:
            tuple: (grid_points, grid_spacing) or ([], None) if not found
        """
        grid_points = request.session.get(GranularAnalysisSessionManager.GRID_POINTS_KEY, [])
        grid_spacing = request.session.get(GranularAnalysisSessionManager.GRID_SPACING_KEY)
        return grid_points, grid_spacing

    @staticmethod
    def store_asset_id(request: HttpRequest, asset_id: int) -> None:
        """
        Store polygon asset ID in session.

        Args:
            request: Django request object
            asset_id: ID of the created asset
        """
        request.session[GranularAnalysisSessionManager.POLYGON_ASSET_ID_KEY] = asset_id
        request.session[GranularAnalysisSessionManager.WORKFLOW_STEP_KEY] = 'hazard_selection'
        request.session.modified = True

        logger.info(f"Stored asset ID {asset_id} in session {request.session.session_key}")

    @staticmethod
    def get_asset_id(request: HttpRequest) -> Optional[int]:
        """
        Retrieve polygon asset ID from session.

        Args:
            request: Django request object

        Returns:
            int: Asset ID or None if not found
        """
        return request.session.get(GranularAnalysisSessionManager.POLYGON_ASSET_ID_KEY)

    @staticmethod
    def get_workflow_step(request: HttpRequest) -> str:
        """
        Get current workflow step.

        Args:
            request: Django request object

        Returns:
            str: Current workflow step
        """
        return request.session.get(GranularAnalysisSessionManager.WORKFLOW_STEP_KEY, 'none')

    @staticmethod
    def set_workflow_step(request: HttpRequest, step: str) -> None:
        """
        Set current workflow step.

        Args:
            request: Django request object
            step: New workflow step
        """
        request.session[GranularAnalysisSessionManager.WORKFLOW_STEP_KEY] = step
        request.session.modified = True

    @staticmethod
    def clear_granular_workflow(request: HttpRequest) -> None:
        """
        Clear granular analysis workflow data from session.

        Args:
            request: Django request object
        """
        keys_to_remove = [
            GranularAnalysisSessionManager.GRANULAR_WORKFLOW_KEY,
            GranularAnalysisSessionManager.POLYGON_GEOMETRY_KEY,
            GranularAnalysisSessionManager.GRID_POINTS_KEY,
            GranularAnalysisSessionManager.GRID_SPACING_KEY,
            GranularAnalysisSessionManager.POLYGON_ASSET_ID_KEY,
            GranularAnalysisSessionManager.WORKFLOW_STEP_KEY
        ]

        for key in keys_to_remove:
            if key in request.session:
                del request.session[key]

        request.session.modified = True

        logger.info(f"Cleared granular workflow data from session {request.session.session_key}")

    @staticmethod
    def get_workflow_state(request: HttpRequest) -> Dict[str, Any]:
        """
        Get complete workflow state from session.

        Args:
            request: Django request object

        Returns:
            dict: Complete workflow state
        """
        return {
            'is_granular_workflow': GranularAnalysisSessionManager.is_granular_workflow(request),
            'workflow_step': GranularAnalysisSessionManager.get_workflow_step(request),
            'has_polygon_geometry': GranularAnalysisSessionManager.get_polygon_geometry(request) is not None,
            'has_grid_configuration': GranularAnalysisSessionManager.get_grid_configuration(request)[0] != [],
            'asset_id': GranularAnalysisSessionManager.get_asset_id(request),
            'session_key': request.session.session_key
        }

    @staticmethod
    def validate_workflow_state(request: HttpRequest) -> Dict[str, Any]:
        """
        Validate the current workflow state and return validation results.

        Args:
            request: Django request object

        Returns:
            dict: Validation results with any errors
        """
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'current_step': GranularAnalysisSessionManager.get_workflow_step(request)
        }

        if not GranularAnalysisSessionManager.is_granular_workflow(request):
            validation_result['valid'] = False
            validation_result['errors'].append('Not in granular analysis workflow')
            return validation_result

        current_step = validation_result['current_step']

        # Validate based on current step
        if current_step in ['grid_setup', 'asset_creation', 'hazard_selection', 'results']:
            polygon_geometry = GranularAnalysisSessionManager.get_polygon_geometry(request)
            if not polygon_geometry:
                validation_result['valid'] = False
                validation_result['errors'].append('No polygon geometry found')

        if current_step in ['asset_creation', 'hazard_selection', 'results']:
            grid_points, grid_spacing = GranularAnalysisSessionManager.get_grid_configuration(request)
            if not grid_points:
                validation_result['valid'] = False
                validation_result['errors'].append('No grid configuration found')
            elif grid_spacing and (grid_spacing <= 0 or grid_spacing > 1):
                validation_result['warnings'].append('Grid spacing may be outside optimal range')

        if current_step in ['hazard_selection', 'results']:
            asset_id = GranularAnalysisSessionManager.get_asset_id(request)
            if not asset_id:
                validation_result['valid'] = False
                validation_result['errors'].append('No asset ID found')

        return validation_result

    @staticmethod
    def create_workflow_summary(request: HttpRequest) -> Dict[str, Any]:
        """
        Create a summary of the granular analysis workflow.

        Args:
            request: Django request object

        Returns:
            dict: Workflow summary
        """
        workflow_state = GranularAnalysisSessionManager.get_workflow_state(request)
        validation_result = GranularAnalysisSessionManager.validate_workflow_state(request)

        summary = {
            'workflow_state': workflow_state,
            'validation': validation_result,
            'session_info': {
                'session_key': request.session.session_key,
                'session_age': None  # Could be calculated if needed
            }
        }

        # Add specific data based on current step
        current_step = workflow_state['current_step']
        if current_step not in ['none', 'drawing']:
            polygon_geometry = GranularAnalysisSessionManager.get_polygon_geometry(request)
            if polygon_geometry:
                summary['polygon_info'] = {
                    'type': polygon_geometry.get('type'),
                    'coordinates_count': len(polygon_geometry.get('coordinates', [[]])[0]) - 1 if polygon_geometry.get('coordinates') else 0
                }

        if current_step in ['asset_creation', 'hazard_selection', 'results']:
            grid_points, grid_spacing = GranularAnalysisSessionManager.get_grid_configuration(request)
            summary['grid_info'] = {
                'points_count': len(grid_points),
                'spacing': grid_spacing
            }

        if current_step in ['hazard_selection', 'results']:
            summary['asset_info'] = {
                'asset_id': GranularAnalysisSessionManager.get_asset_id(request)
            }

        return summary

    @staticmethod
    def store_workflow_results(request: HttpRequest, workflow_results: Dict[str, Any]) -> None:
        """
        Store complete workflow results in session for immediate display.

        Args:
            request: Django request object
            workflow_results: Complete workflow execution results
        """
        WORKFLOW_RESULTS_KEY = 'climate_hazards_v2_workflow_results'

        # Store only essential data to avoid session size issues
        essential_results = {
            'asset_id': workflow_results.get('asset_id'),
            'asset_name': workflow_results.get('asset_name'),
            'success': workflow_results.get('success'),
            'grid_points_generated': workflow_results.get('grid_points_generated', 0),
            'selected_hazards': workflow_results.get('selected_hazards', []),
            'workflow_duration': workflow_results.get('workflow_duration', 0),
            'table_results_count': len(workflow_results.get('table_results', [])),
            'timestamp': timezone.now().isoformat()
        }

        request.session[WORKFLOW_RESULTS_KEY] = essential_results
        request.session[GranularAnalysisSessionManager.WORKFLOW_STEP_KEY] = 'results'
        request.session.modified = True

        logger.info(f"Stored workflow results in session {request.session.session_key}")
        logger.info(f"Results: {essential_results}")


def get_session_manager() -> type:
    """
    Get the session manager class.

    Returns:
        GranularAnalysisSessionManager class
    """
    return GranularAnalysisSessionManager