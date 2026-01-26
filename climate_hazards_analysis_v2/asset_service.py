"""
Unified Asset Service Layer

This module provides a stateless service layer for handling both point and polygon assets
in the climate hazards analysis system. It abstracts away the differences between asset types
and provides a unified interface for asset management, analysis, and visualization.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from climate_hazards_analysis.models import Asset
from .models import HazardAnalysisResult, GranularAnalysisResult, HeatmapData

logger = logging.getLogger(__name__)


class AssetType:
    """Constants for asset types"""
    POINT = 'point'
    POLYGON = 'polygon'


class AnalysisStatus:
    """Constants for analysis status"""
    NONE = 'none'
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'


class AssetService:
    """
    Unified service for managing both point and polygon assets.

    This service provides stateless operations for:
    - Asset creation and management
    - Hazard analysis operations
    - Data retrieval for visualization
    - Granular analysis and heatmap generation
    """

    @staticmethod
    def create_point_asset(name: str, latitude: float, longitude: float,
                         archetype: str = 'default archetype',
                         properties: Optional[Dict[str, Any]] = None) -> Asset:
        """
        Create a point-based asset.

        Args:
            name: Asset name
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            archetype: Asset archetype
            properties: Additional properties as JSON

        Returns:
            Created Asset instance
        """
        try:
            with transaction.atomic():
                asset = Asset.objects.create(
                    name=name,
                    archetype=archetype,
                    latitude=Decimal(str(latitude)),
                    longitude=Decimal(str(longitude)),
                    asset_type=AssetType.POINT,
                    properties=properties or {}
                )
                logger.info(f"Created point asset: {asset.name} (ID: {asset.id})")
                return asset
        except Exception as e:
            logger.error(f"Failed to create point asset {name}: {str(e)}")
            raise ValidationError(f"Failed to create point asset: {str(e)}")

    @staticmethod
    def create_polygon_asset(name: str, polygon_geometry: Dict[str, Any],
                           archetype: str = 'default archetype',
                           properties: Optional[Dict[str, Any]] = None) -> Asset:
        """
        Create a polygon-based asset.

        Args:
            name: Asset name
            polygon_geometry: GeoJSON polygon geometry
            archetype: Asset archetype
            properties: Additional properties as JSON

        Returns:
            Created Asset instance
        """
        try:
            with transaction.atomic():
                # Validate polygon geometry
                if not AssetService._validate_polygon_geometry(polygon_geometry):
                    raise ValidationError("Invalid polygon geometry")

                asset = Asset.objects.create(
                    name=name,
                    archetype=archetype,
                    latitude=Decimal('0'),  # Will be updated by save() method
                    longitude=Decimal('0'),  # Will be updated by save() method
                    polygon_geometry=polygon_geometry,
                    asset_type=AssetType.POLYGON,
                    properties=properties or {}
                )
                logger.info(f"Created polygon asset: {asset.name} (ID: {asset.id})")
                return asset
        except Exception as e:
            logger.error(f"Failed to create polygon asset {name}: {str(e)}")
            raise ValidationError(f"Failed to create polygon asset: {str(e)}")

    @staticmethod
    def get_asset_by_id(asset_id: int) -> Optional[Asset]:
        """
        Retrieve asset by ID with related analysis results.

        Args:
            asset_id: Asset ID

        Returns:
            Asset instance or None if not found
        """
        try:
            return Asset.objects.select_related().prefetch_related(
                'hazard_results', 'granular_results', 'heatmap_data'
            ).get(id=asset_id)
        except Asset.DoesNotExist:
            return None

    @staticmethod
    def get_all_assets(asset_type: Optional[str] = None) -> List[Asset]:
        """
        Get all assets, optionally filtered by type.

        Args:
            asset_type: Filter by asset type ('point' or 'polygon')

        Returns:
            List of Asset instances
        """
        queryset = Asset.objects.all()
        if asset_type:
            queryset = queryset.filter(asset_type=asset_type)
        return list(queryset)

    @staticmethod
    def get_assets_within_bounds(min_lat: float, max_lat: float,
                               min_lng: float, max_lng: float,
                               asset_type: Optional[str] = None) -> List[Asset]:
        """
        Get assets within specified bounding box.

        Args:
            min_lat, max_lat: Latitude bounds
            min_lng, max_lng: Longitude bounds
            asset_type: Filter by asset type

        Returns:
            List of Asset instances within bounds
        """
        queryset = Asset.objects.filter(
            latitude__gte=min_lat,
            latitude__lte=max_lat,
            longitude__gte=min_lng,
            longitude__lte=max_lng
        )
        if asset_type:
            queryset = queryset.filter(asset_type=asset_type)
        return list(queryset)

    @staticmethod
    def update_asset(asset_id: int, **kwargs) -> Asset:
        """
        Update asset properties.

        Args:
            asset_id: Asset ID
            **kwargs: Fields to update

        Returns:
            Updated Asset instance
        """
        try:
            with transaction.atomic():
                asset = Asset.objects.get(asset_id=asset_id)
                for field, value in kwargs.items():
                    if hasattr(asset, field):
                        setattr(asset, field, value)
                asset.save()
                logger.info(f"Updated asset: {asset.name} (ID: {asset.id})")
                return asset
        except Asset.DoesNotExist:
            raise ValidationError(f"Asset with ID {asset_id} not found")
        except Exception as e:
            logger.error(f"Failed to update asset {asset_id}: {str(e)}")
            raise ValidationError(f"Failed to update asset: {str(e)}")

    @staticmethod
    def delete_asset(asset_id: int) -> bool:
        """
        Delete an asset and all associated analysis results.

        Args:
            asset_id: Asset ID

        Returns:
            True if deleted successfully
        """
        try:
            with transaction.atomic():
                asset = Asset.objects.get(asset_id=asset_id)
                asset_name = asset.name
                asset.delete()
                logger.info(f"Deleted asset: {asset_name} (ID: {asset_id})")
                return True
        except Asset.DoesNotExist:
            logger.warning(f"Asset with ID {asset_id} not found for deletion")
            return False
        except Exception as e:
            logger.error(f"Failed to delete asset {asset_id}: {str(e)}")
            raise ValidationError(f"Failed to delete asset: {str(e)}")

    @staticmethod
    def get_asset_analysis_results(asset_id: int, hazard_type: Optional[str] = None,
                                  scenario: str = 'current') -> Dict[str, Any]:
        """
        Get hazard analysis results for an asset.

        Args:
            asset_id: Asset ID
            hazard_type: Optional hazard type filter
            scenario: Analysis scenario

        Returns:
            Dictionary with analysis results
        """
        try:
            asset = AssetService.get_asset_by_id(asset_id)
            if not asset:
                return {'error': 'Asset not found'}

            results_query = asset.hazard_results.filter(scenario=scenario)
            if hazard_type:
                results_query = results_query.filter(hazard_type=hazard_type)

            results = {}
            for result in results_query:
                results[result.hazard_type] = result.result_data

            return {
                'asset': {
                    'id': asset.id,
                    'name': asset.name,
                    'type': asset.asset_type,
                    'coordinates': asset.coordinates,
                    'geojson': asset.geojson
                },
                'analysis_results': results,
                'scenario': scenario,
                'has_granular_analysis': asset.has_granular_analysis,
                'granular_status': asset.granular_analysis_status
            }
        except Exception as e:
            logger.error(f"Failed to get analysis results for asset {asset_id}: {str(e)}")
            return {'error': str(e)}

    @staticmethod
    def save_hazard_analysis_result(asset_id: int, hazard_type: str,
                                  result_data: Dict[str, Any],
                                  scenario: str = 'current') -> HazardAnalysisResult:
        """
        Save hazard analysis result for an asset.

        Args:
            asset_id: Asset ID
            hazard_type: Type of hazard
            result_data: Analysis result data
            scenario: Analysis scenario

        Returns:
            Created/updated HazardAnalysisResult
        """
        try:
            with transaction.atomic():
                asset = Asset.objects.get(asset_id=asset_id)

                result, created = HazardAnalysisResult.objects.update_or_create(
                    asset=asset,
                    hazard_type=hazard_type,
                    scenario=scenario,
                    defaults={'result_data': result_data}
                )

                action = "Created" if created else "Updated"
                logger.info(f"{action} analysis result for {asset.name}: {hazard_type}")
                return result
        except Asset.DoesNotExist:
            raise ValidationError(f"Asset with ID {asset_id} not found")
        except Exception as e:
            logger.error(f"Failed to save analysis result: {str(e)}")
            raise ValidationError(f"Failed to save analysis result: {str(e)}")

    @staticmethod
    def get_assets_for_visualization(hazard_types: List[str] = None,
                                   bounds: Optional[Dict[str, float]] = None,
                                   scenario: str = 'current') -> List[Dict[str, Any]]:
        """
        Get assets formatted for visualization with hazard data.

        Args:
            hazard_types: List of hazard types to include
            bounds: Optional bounding box filter
            scenario: Analysis scenario

        Returns:
            List of asset dictionaries with visualization data
        """
        try:
            # Start with base queryset
            queryset = Asset.objects.all()

            # Apply bounds filter if provided
            if bounds:
                queryset = queryset.filter(
                    latitude__gte=bounds.get('min_lat', -90),
                    latitude__lte=bounds.get('max_lat', 90),
                    longitude__gte=bounds.get('min_lng', -180),
                    longitude__lte=bounds.get('max_lng', 180)
                )

            assets = queryset.select_related().prefetch_related(
                'hazard_results__granular_results', 'heatmap_data'
            )

            visualization_data = []
            for asset in assets:
                asset_data = {
                    'id': asset.id,
                    'name': asset.name,
                    'archetype': asset.archetype,
                    'asset_type': asset.asset_type,
                    'coordinates': asset.coordinates,
                    'geojson': asset.geojson,
                    'properties': asset.properties,
                    'has_granular_analysis': asset.has_granular_analysis,
                    'granular_status': asset.granular_analysis_status,
                    'hazard_data': {}
                }

                # Add hazard analysis results
                hazard_results = asset.hazard_results.filter(scenario=scenario)
                if hazard_types:
                    hazard_results = hazard_results.filter(hazard_type__in=hazard_types)

                for result in hazard_results:
                    asset_data['hazard_data'][result.hazard_type] = result.result_data

                # Add heatmap data if available
                if asset.asset_type == AssetType.POLYGON:
                    heatmap_data = asset.heatmap_data.filter(scenario=scenario)
                    if hazard_types:
                        heatmap_data = heatmap_data.filter(hazard_type__in=hazard_types)

                    asset_data['heatmaps'] = {
                        hm.hazard_type: hm.get_heatmap_grid()
                        for hm in heatmap_data
                    }

                visualization_data.append(asset_data)

            return visualization_data

        except Exception as e:
            logger.error(f"Failed to get assets for visualization: {str(e)}")
            raise ValidationError(f"Failed to get visualization data: {str(e)}")

    @staticmethod
    def _validate_polygon_geometry(geometry: Dict[str, Any]) -> bool:
        """
        Validate GeoJSON polygon geometry.

        Args:
            geometry: GeoJSON geometry object

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(geometry, dict):
            return False

        if geometry.get('type') != 'Polygon':
            return False

        coordinates = geometry.get('coordinates')
        if not isinstance(coordinates, list) or len(coordinates) == 0:
            return False

        # Check exterior ring
        exterior_ring = coordinates[0]
        if not isinstance(exterior_ring, list) or len(exterior_ring) < 4:
            return False

        # Check that first and last points are the same (closed polygon)
        if exterior_ring[0] != exterior_ring[-1]:
            return False

        # Validate coordinate format
        for point in exterior_ring:
            if not isinstance(point, list) or len(point) != 2:
                return False
            lng, lat = point
            if not isinstance(lng, (int, float)) or not isinstance(lat, (int, float)):
                return False
            if not (-180 <= lng <= 180) or not (-90 <= lat <= 90):
                return False

        return True

    @staticmethod
    def get_asset_statistics(asset_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about assets in the system.

        Args:
            asset_type: Filter by asset type

        Returns:
            Statistics dictionary
        """
        queryset = Asset.objects.all()
        if asset_type:
            queryset = queryset.filter(asset_type=asset_type)

        stats = {
            'total_assets': queryset.count(),
            'point_assets': queryset.filter(asset_type=AssetType.POINT).count(),
            'polygon_assets': queryset.filter(asset_type=AssetType.POLYGON).count(),
            'assets_with_granular_analysis': queryset.filter(has_granular_analysis=True).count(),
            'completed_granular_analyses': queryset.filter(
                granular_analysis_status=AnalysisStatus.COMPLETED
            ).count(),
            'pending_granular_analyses': queryset.filter(
                granular_analysis_status=AnalysisStatus.PENDING
            ).count(),
        }

        # Add hazard analysis statistics
        hazard_stats = {}
        for hazard in ['sea_level_rise', 'heat_stress', 'flooding', 'wind_speed', 'landslide']:
            count = HazardAnalysisResult.objects.filter(
                asset__in=queryset,
                hazard_type=hazard
            ).count()
            if count > 0:
                hazard_stats[hazard] = count

        stats['hazard_analyses'] = hazard_stats

        return stats


class AssetAnalysisService:
    """
    Service for handling asset analysis operations including granular analysis.
    """

    @staticmethod
    def initialize_granular_analysis(asset_id: int, grid_spacing: float) -> Asset:
        """
        Initialize granular analysis for a polygon asset.

        Args:
            asset_id: Asset ID (must be polygon type)
            grid_spacing: Grid spacing in degrees

        Returns:
            Updated Asset instance
        """
        try:
            with transaction.atomic():
                asset = Asset.objects.get(asset_id=asset_id, asset_type=AssetType.POLYGON)

                if not asset.polygon_geometry:
                    raise ValidationError("Asset has no polygon geometry")

                # Update asset metadata
                asset.has_granular_analysis = True
                asset.granular_grid_spacing = grid_spacing
                asset.granular_analysis_status = AnalysisStatus.PENDING
                asset.granular_analysis_progress = 0.0
                asset.save()

                logger.info(f"Initialized granular analysis for {asset.name} (ID: {asset.id})")
                return asset

        except Asset.DoesNotExist:
            raise ValidationError(f"Polygon asset with ID {asset_id} not found")
        except Exception as e:
            logger.error(f"Failed to initialize granular analysis: {str(e)}")
            raise ValidationError(f"Failed to initialize granular analysis: {str(e)}")

    @staticmethod
    def update_granular_analysis_status(asset_id: int, status: str,
                                      progress: Optional[float] = None,
                                      grid_points_count: Optional[int] = None,
                                      error_message: Optional[str] = None) -> Asset:
        """
        Update granular analysis status for an asset.

        Args:
            asset_id: Asset ID
            status: New status
            progress: Progress percentage (0-100)
            grid_points_count: Number of grid points processed
            error_message: Error message if status is failed

        Returns:
            Updated Asset instance
        """
        try:
            with transaction.atomic():
                asset = Asset.objects.get(asset_id=asset_id)

                asset.granular_analysis_status = status
                if progress is not None:
                    asset.granular_analysis_progress = min(100.0, max(0.0, progress))
                if grid_points_count is not None:
                    asset.granular_grid_points_count = grid_points_count

                asset.save()

                logger.info(f"Updated granular analysis status for {asset.name}: {status}")
                return asset

        except Asset.DoesNotExist:
            raise ValidationError(f"Asset with ID {asset_id} not found")
        except Exception as e:
            logger.error(f"Failed to update granular analysis status: {str(e)}")
            raise ValidationError(f"Failed to update status: {str(e)}")

    @staticmethod
    def save_granular_analysis_point(asset_id: int, latitude: float, longitude: float,
                                   grid_row: int, grid_col: int, hazard_type: str,
                                   result_data: Dict[str, Any],
                                   scenario: str = 'current') -> GranularAnalysisResult:
        """
        Save granular analysis result for a single grid point.

        Args:
            asset_id: Asset ID
            latitude, longitude: Grid point coordinates
            grid_row, grid_col: Grid position
            hazard_type: Type of hazard
            result_data: Analysis result data
            scenario: Analysis scenario

        Returns:
            Created GranularAnalysisResult
        """
        try:
            with transaction.atomic():
                asset = Asset.objects.get(asset_id=asset_id)

                result, created = GranularAnalysisResult.objects.update_or_create(
                    asset=asset,
                    latitude=Decimal(str(latitude)),
                    longitude=Decimal(str(longitude)),
                    hazard_type=hazard_type,
                    scenario=scenario,
                    defaults={
                        'grid_row': grid_row,
                        'grid_col': grid_col,
                        'grid_spacing': asset.granular_grid_spacing or 0.01,
                        'result_data': result_data,
                        'processing_status': AnalysisStatus.COMPLETED
                    }
                )

                action = "Created" if created else "Updated"
                logger.info(f"{action} granular analysis point for {asset.name}: ({grid_row},{grid_col})")
                return result

        except Asset.DoesNotExist:
            raise ValidationError(f"Asset with ID {asset_id} not found")
        except Exception as e:
            logger.error(f"Failed to save granular analysis point: {str(e)}")
            raise ValidationError(f"Failed to save analysis point: {str(e)}")

    @staticmethod
    def get_granular_analysis_data(asset_id: int, hazard_type: Optional[str] = None,
                                  scenario: str = 'current') -> Dict[str, Any]:
        """
        Get granular analysis data for an asset.

        Args:
            asset_id: Asset ID
            hazard_type: Optional hazard type filter
            scenario: Analysis scenario

        Returns:
            Dictionary with granular analysis data
        """
        try:
            asset = AssetService.get_asset_by_id(asset_id)
            if not asset:
                return {'error': 'Asset not found'}

            if not asset.has_granular_analysis:
                return {'error': 'No granular analysis available for this asset'}

            results_query = asset.granular_results.filter(scenario=scenario)
            if hazard_type:
                results_query = results_query.filter(hazard_type=hazard_type)

            # Group results by hazard type
            results_by_hazard = {}
            for result in results_query:
                hazard = result.hazard_type
                if hazard not in results_by_hazard:
                    results_by_hazard[hazard] = []

                results_by_hazard[hazard].append({
                    'coordinates': result.coordinates,
                    'grid_position': {'row': result.grid_row, 'col': result.grid_col},
                    'result_data': result.result_data,
                    'status': result.processing_status
                })

            return {
                'asset': {
                    'id': asset.id,
                    'name': asset.name,
                    'type': asset.asset_type
                },
                'granular_status': asset.granular_analysis_status,
                'grid_spacing': asset.granular_grid_spacing,
                'grid_points_count': asset.granular_grid_points_count,
                'progress': asset.granular_analysis_progress,
                'results_by_hazard': results_by_hazard,
                'scenario': scenario
            }

        except Exception as e:
            logger.error(f"Failed to get granular analysis data: {str(e)}")
            return {'error': str(e)}

    @staticmethod
    def run_comprehensive_analysis(asset_data_list: List[Dict[str, Any]], hazard_types: List[str]) -> List[Dict[str, Any]]:
        """
        Run comprehensive climate hazards analysis for multiple assets using JSON workflow.

        Args:
            asset_data_list: List of asset data with coordinates and properties
            hazard_types: List of hazard types to analyze

        Returns:
            List of analysis results in template-compatible format
        """
        try:
            # For now, return a simple mock structure to test the workflow
            # This can be enhanced to integrate with the actual analysis engines later
            results = []
            for asset_data in asset_data_list:
                result = {
                    'Facility': asset_data.get('name', 'Unknown'),
                    'Asset Archetype': asset_data.get('archetype', 'default'),
                    'Lat': asset_data.get('latitude', 0.0),
                    'Long': asset_data.get('longitude', 0.0),
                    'asset_id': asset_data.get('asset_id', 0)
                }

                # Add placeholder hazard columns
                for hazard in hazard_types:
                    result[f'{hazard} Exposure'] = 'Low'
                    result[f'{hazard} Risk'] = 'Low'

                results.append(result)

            logger.info(f"Mock analysis completed for {len(results)} assets with hazards: {hazard_types}")
            return results

        except Exception as e:
            logger.error(f"Error in comprehensive analysis: {str(e)}")
            # Return basic structure on error
            error_results = []
            for asset_data in asset_data_list:
                error_result = {
                    'Facility': asset_data.get('name', 'Unknown'),
                    'Asset Archetype': asset_data.get('archetype', 'default'),
                    'Lat': asset_data.get('latitude', 0.0),
                    'Long': asset_data.get('longitude', 0.0),
                    'asset_id': asset_data.get('asset_id', 0),
                    'Error': f'Analysis failed: {str(e)}'
                }
                error_results.append(error_result)

            return error_results


def create_asset(name: str, coordinates: Union[Tuple[float, float], Dict[str, Any]],
                asset_type: str = AssetType.POINT, **kwargs) -> Asset:
    """
    Convenience function to create any type of asset.

    Args:
        name: Asset name
        coordinates: Either (lat, lng) tuple for point assets or GeoJSON geometry for polygons
        asset_type: Type of asset ('point' or 'polygon')
        **kwargs: Additional asset properties

    Returns:
        Created Asset instance
    """
    if asset_type == AssetType.POLYGON:
        return AssetService.create_polygon_asset(name, coordinates, **kwargs)
    else:
        lat, lng = coordinates
        return AssetService.create_point_asset(name, lat, lng, **kwargs)


def get_asset_with_analysis(asset_id: int, hazard_types: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Convenience function to get asset with all analysis data.

    Args:
        asset_id: Asset ID
        hazard_types: Optional list of hazard types to include

    Returns:
        Complete asset data with analysis results
    """
    analysis_data = AssetService.get_asset_analysis_results(asset_id)
    granular_data = AssetAnalysisService.get_granular_analysis_data(asset_id)

    if 'error' in analysis_data:
        return analysis_data

    if hazard_types:
        # Filter results by requested hazard types
        filtered_results = {}
        for hazard_type in hazard_types:
            if hazard_type in analysis_data.get('analysis_results', {}):
                filtered_results[hazard_type] = analysis_data['analysis_results'][hazard_type]
        analysis_data['analysis_results'] = filtered_results

    analysis_data['granular_data'] = granular_data
    return analysis_data

    @staticmethod
    def run_comprehensive_analysis(asset_data_list: List[Dict[str, Any]], hazard_types: List[str]) -> List[Dict[str, Any]]:
        """
        Run comprehensive climate hazards analysis for multiple assets using JSON workflow.

        Args:
            asset_data_list: List of asset data with coordinates and properties
            hazard_types: List of hazard types to analyze

        Returns:
            List of analysis results in template-compatible format
        """
        try:
            # Import legacy analysis engines for compatibility
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'climate_hazards_analysis'))

            from climate_hazards_analysis import generate_climate_hazards_analysis
            import pandas as pd
            import tempfile

            # Convert JSON asset data to DataFrame for existing analysis engines
            facility_records = []
            for asset_data in asset_data_list:
                record = {
                    'Facility': asset_data.get('name', 'Unknown Facility'),
                    'Lat': asset_data.get('latitude', 0.0),
                    'Long': asset_data.get('longitude', 0.0),
                    'Asset Archetype': asset_data.get('archetype', 'default'),
                    'Asset ID': asset_data.get('asset_id', 0)
                }
                facility_records.append(record)

            # Create DataFrame
            df_facilities = pd.DataFrame(facility_records)

            # Create temporary CSV file for existing analysis engine compatibility
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp_file:
                df_facilities.to_csv(tmp_file.name, index=False)
                temp_csv_path = tmp_file.name

            try:
                # Run analysis using existing engine
                analysis_results = generate_climate_hazards_analysis(
                    facility_csv_path=temp_csv_path,
                    hazards_selected=hazard_types,
                    scenarios_selected=['moderate', 'worst']  # Default scenarios
                )

                # Read the combined output results
                combined_csv_path = analysis_results.get('combined_csv_path')
                if combined_csv_path and os.path.exists(combined_csv_path):
                    df_results = pd.read_csv(combined_csv_path, encoding='utf-8')

                    # Convert to list of dictionaries for template compatibility
                    results_list = df_results.to_dict(orient='records')

                    # Add asset IDs back to results
                    for i, result in enumerate(results_list):
                        if i < len(asset_data_list):
                            result['asset_id'] = asset_data_list[i].get('asset_id')

                    return results_list
                else:
                    # Fallback: Create basic results structure
                    basic_results = []
                    for i, asset_data in enumerate(asset_data_list):
                        result = {
                            'Facility': asset_data.get('name', 'Unknown'),
                            'Asset Archetype': asset_data.get('archetype', 'default'),
                            'Lat': asset_data.get('latitude', 0.0),
                            'Long': asset_data.get('longitude', 0.0),
                            'asset_id': asset_data.get('asset_id', 0)
                        }

                        # Add placeholder hazard columns
                        for hazard in hazard_types:
                            result[f'{hazard} Exposure'] = 'N/A'
                            result[f'{hazard} Risk'] = 'Unknown'

                        basic_results.append(result)

                    return basic_results

            finally:
                # Clean up temporary files
                try:
                    if os.path.exists(temp_csv_path):
                        os.unlink(temp_csv_path)

                    # Clean up analysis output files
                    output_files = analysis_results.get('output_files', {})
                    for file_path in output_files.values():
                        if os.path.exists(file_path):
                            os.unlink(file_path)
                except:
                    pass  # Ignore cleanup errors

        except Exception as e:
            logger.error(f"Error in comprehensive analysis: {str(e)}")
            # Return basic structure on error
            error_results = []
            for asset_data in asset_data_list:
                error_result = {
                    'Facility': asset_data.get('name', 'Unknown'),
                    'Asset Archetype': asset_data.get('archetype', 'default'),
                    'Lat': asset_data.get('latitude', 0.0),
                    'Long': asset_data.get('longitude', 0.0),
                    'asset_id': asset_data.get('asset_id', 0),
                    'Error': f'Analysis failed: {str(e)}'
                }
                error_results.append(error_result)

            return error_results
