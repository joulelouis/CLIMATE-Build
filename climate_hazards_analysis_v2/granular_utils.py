"""
Utility functions for granular analysis of polygon assets.
This module provides functions for grid point generation, batch hazard querying,
and statistical aggregation for granular climate hazard analysis.
"""

import math
import json
import logging
from decimal import Decimal
from typing import List, Tuple, Dict, Any, Optional
from django.db import transaction

from .models import Asset, GranularAnalysisResult, HeatmapData

logger = logging.getLogger(__name__)


def generate_grid_points_from_polygon(polygon_geometry: Dict, grid_spacing: float) -> List[Tuple[float, float, int, int]]:
    """
    Generate grid points within a polygon geometry.

    Args:
        polygon_geometry: GeoJSON polygon geometry dictionary
        grid_spacing: Grid spacing in degrees

    Returns:
        List of tuples: (latitude, longitude, grid_row, grid_col)
    """
    try:
        # Extract coordinates from GeoJSON polygon
        if polygon_geometry.get('type') != 'Polygon' or not polygon_geometry.get('coordinates'):
            logger.error("Invalid polygon geometry - expected GeoJSON Polygon")
            return []

        coordinates = polygon_geometry['coordinates'][0]  # Exterior ring
        if len(coordinates) < 4:  # Need at least 3 points for valid polygon
            logger.error("Invalid polygon geometry - need at least 3 points")
            return []

        # Calculate bounding box
        lats = [coord[1] for coord in coordinates]
        lngs = [coord[0] for coord in coordinates]
        min_lat, max_lat = min(lats), max(lats)
        min_lng, max_lng = min(lngs), max(lngs)

        # Simple point-in-polygon check using ray casting algorithm
        def point_in_polygon(lat, lng, poly_coords):
            """Simple ray casting algorithm to check if point is in polygon"""
            inside = False
            j = len(poly_coords) - 1
            for i in range(len(poly_coords)):
                xi, yi = poly_coords[i]
                xj, yj = poly_coords[j]

                # Check if ray intersects with edge
                if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
                    inside = not inside
                j = i
            return inside

        grid_points = []
        row = 0
        col = 0

        # Generate grid points
        lat = min_lat
        while lat <= max_lat:
            col = 0
            lng = min_lng
            while lng <= max_lng:
                # Check if point is within polygon
                if point_in_polygon(lat, lng, coordinates):
                    grid_points.append((lat, lng, row, col))
                lng += grid_spacing
                col += 1
            lat += grid_spacing
            row += 1

        logger.info(f"Generated {len(grid_points)} grid points for polygon with spacing {grid_spacing}°")
        return grid_points

    except Exception as e:
        logger.exception(f"Error generating grid points: {str(e)}")
        return []


def calculate_polygon_bounding_box(polygon_geometry: Dict) -> Optional[Tuple[float, float, float, float]]:
    """
    Calculate bounding box for polygon geometry.

    Args:
        polygon_geometry: GeoJSON polygon geometry dictionary

    Returns:
        Tuple of (min_lat, max_lat, min_lng, max_lng) or None if error
    """
    try:
        # Extract coordinates from GeoJSON polygon
        if polygon_geometry.get('type') != 'Polygon' or not polygon_geometry.get('coordinates'):
            logger.error("Invalid polygon geometry - expected GeoJSON Polygon")
            return None

        coordinates = polygon_geometry['coordinates'][0]  # Exterior ring
        if len(coordinates) < 3:
            logger.error("Invalid polygon geometry - need at least 3 points")
            return None

        # Calculate bounding box
        lats = [coord[1] for coord in coordinates]
        lngs = [coord[0] for coord in coordinates]
        min_lat, max_lat = min(lats), max(lats)
        min_lng, max_lng = min(lngs), max(lngs)

        return (min_lat, max_lat, min_lng, max_lng)

    except Exception as e:
        logger.exception(f"Error calculating bounding box: {str(e)}")
        return None


def is_point_in_polygon(latitude: float, longitude: float, polygon_geometry: Dict) -> bool:
    """
    Check if a point is within a polygon using ray casting algorithm.

    Args:
        latitude: Point latitude
        longitude: Point longitude
        polygon_geometry: GeoJSON polygon geometry dictionary

    Returns:
        True if point is within polygon, False otherwise
    """
    try:
        # Extract coordinates from GeoJSON polygon
        if polygon_geometry.get('type') != 'Polygon' or not polygon_geometry.get('coordinates'):
            logger.error("Invalid polygon geometry - expected GeoJSON Polygon")
            return False

        coordinates = polygon_geometry['coordinates'][0]  # Exterior ring
        if len(coordinates) < 3:
            return False

        # Ray casting algorithm
        inside = False
        j = len(coordinates) - 1
        for i in range(len(coordinates)):
            xi, yi = coordinates[i]
            xj, yj = coordinates[j]

            # Check if ray intersects with edge
            if ((yi > latitude) != (yj > latitude)) and (longitude < (xj - xi) * (latitude - yi) / (yj - yi) + xi):
                inside = not inside
            j = i

        return inside

    except Exception as e:
        logger.exception(f"Error checking point in polygon: {str(e)}")
        return False


def create_granular_analysis_results(asset: Asset, grid_points: List[Tuple[float, float, int, int]],
                                   hazard_types: List[str], scenario: str = 'current') -> List[GranularAnalysisResult]:
    """
    Create granular analysis result records for grid points.

    Args:
        asset: Asset instance
        grid_points: List of (lat, lng, row, col) tuples
        hazard_types: List of hazard types to analyze
        scenario: Analysis scenario

    Returns:
        List of created GranularAnalysisResult instances
    """
    try:
        with transaction.atomic():
            results = []

            # Clear existing granular results for this asset
            GranularAnalysisResult.objects.filter(asset=asset).delete()

            # Calculate grid spacing from points
            if len(grid_points) < 2:
                grid_spacing = 0.001  # Default ~100m
            else:
                # Use spacing between first two points in same row
                lat_diff = abs(grid_points[1][0] - grid_points[0][0])
                lng_diff = abs(grid_points[1][1] - grid_points[0][1])
                grid_spacing = max(lat_diff, lng_diff)

            for lat, lng, row, col in grid_points:
                for hazard_type in hazard_types:
                    result = GranularAnalysisResult.objects.create(
                        asset=asset,
                        latitude=Decimal(str(lat)),
                        longitude=Decimal(str(lng)),
                        grid_row=row,
                        grid_col=col,
                        grid_spacing=grid_spacing,
                        hazard_type=hazard_type,
                        scenario=scenario,
                        processing_status='pending'
                    )
                    results.append(result)

            # Update asset metadata
            asset.has_granular_analysis = True
            asset.granular_grid_spacing = grid_spacing
            asset.granular_grid_points_count = len(grid_points) * len(hazard_types)
            asset.granular_analysis_status = 'pending'
            asset.granular_analysis_progress = 0.0
            asset.save()

            logger.info(f"Created {len(results)} granular analysis records for asset {asset.name}")
            return results

    except Exception as e:
        logger.exception(f"Error creating granular analysis results: {str(e)}")
        return []


def calculate_granular_statistics(asset: Asset, hazard_type: str, scenario: str = 'current') -> Dict[str, Any]:
    """
    Calculate statistical summaries for granular analysis results.

    Args:
        asset: Asset instance
        hazard_type: Hazard type to analyze
        scenario: Analysis scenario

    Returns:
        Dictionary with statistical summaries
    """
    try:
        results = GranularAnalysisResult.objects.filter(
            asset=asset,
            hazard_type=hazard_type,
            scenario=scenario,
            processing_status='completed'
        )

        if not results.exists():
            return {}

        # Extract values from result_data
        values = []
        for result in results:
            if result.result_data and 'value' in result.result_data:
                values.append(float(result.result_data['value']))

        if not values:
            return {}

        # Calculate statistics
        values.sort()
        n = len(values)

        stats = {
            'count': n,
            'min_value': values[0],
            'max_value': values[-1],
            'mean_value': sum(values) / n,
            'median_value': values[n // 2] if n % 2 == 1 else (values[n // 2 - 1] + values[n // 2]) / 2,
            'grid_points_processed': n,
            'total_grid_points': GranularAnalysisResult.objects.filter(
                asset=asset, hazard_type=hazard_type, scenario=scenario
            ).count()
        }

        # Calculate risk distribution
        if 'risk_level' in results.first().result_data:
            risk_levels = {}
            for result in results:
                risk_level = result.result_data.get('risk_level', 'unknown')
                risk_levels[risk_level] = risk_levels.get(risk_level, 0) + 1

            stats['risk_distribution'] = risk_levels

        return stats

    except Exception as e:
        logger.exception(f"Error calculating granular statistics: {str(e)}")
        return {}


def create_heatmap_data(asset: Asset, hazard_type: str, scenario: str = 'current',
                       grid_resolution: int = 50) -> Optional[HeatmapData]:
    """
    Create heatmap data from granular analysis results.

    Args:
        asset: Asset instance
        hazard_type: Hazard type for heatmap
        scenario: Analysis scenario
        grid_resolution: Number of grid cells for heatmap resolution

    Returns:
        HeatmapData instance or None if error
    """
    try:
        # Get granular results
        results = GranularAnalysisResult.objects.filter(
            asset=asset,
            hazard_type=hazard_type,
            scenario=scenario,
            processing_status='completed'
        )

        if not results.exists():
            logger.warning(f"No completed granular results for asset {asset.name}, hazard {hazard_type}")
            return None

        # Calculate bounding box from polygon
        if not asset.polygon_geometry:
            logger.error(f"Asset {asset.name} has no polygon geometry")
            return None

        bbox = calculate_polygon_bounding_box(asset.polygon_geometry)
        if not bbox:
            logger.error(f"Could not calculate bounding box for asset {asset.name}")
            return None

        min_lat, max_lat, min_lng, max_lng = bbox

        # Create heatmap grid
        lat_step = (max_lat - min_lat) / grid_resolution
        lng_step = (max_lng - min_lng) / grid_resolution

        # Initialize heatmap values matrix
        heatmap_values = [[0.0 for _ in range(grid_resolution)] for _ in range(grid_resolution)]
        point_counts = [[0 for _ in range(grid_resolution)] for _ in range(grid_resolution)]

        # Aggregate values into heatmap cells
        for result in results:
            lat = float(result.latitude)
            lng = float(result.longitude)

            # Find grid cell
            row = int((lat - min_lat) / lat_step)
            col = int((lng - min_lng) / lng_step)

            # Ensure within bounds
            row = max(0, min(row, grid_resolution - 1))
            col = max(0, min(col, grid_resolution - 1))

            # Add value to cell
            if result.result_data and 'value' in result.result_data:
                heatmap_values[row][col] += float(result.result_data['value'])
                point_counts[row][col] += 1

        # Calculate averages
        all_values = []
        for row in range(grid_resolution):
            for col in range(grid_resolution):
                if point_counts[row][col] > 0:
                    heatmap_values[row][col] /= point_counts[row][col]
                    all_values.append(heatmap_values[row][col])
                else:
                    # Set to None for empty cells (will be filtered in frontend)
                    heatmap_values[row][col] = None

        # Calculate statistics
        if all_values:
            min_value = min(all_values)
            max_value = max(all_values)
            mean_value = sum(all_values) / len(all_values)
            sorted_values = sorted(all_values)
            median_value = sorted_values[len(sorted_values) // 2]
        else:
            min_value = max_value = mean_value = median_value = None

        # Create heatmap data record
        heatmap_data = HeatmapData.objects.create(
            asset=asset,
            hazard_type=hazard_type,
            scenario=scenario,
            grid_rows=grid_resolution,
            grid_cols=grid_resolution,
            grid_spacing=max(lat_step, lng_step),
            min_lat=Decimal(str(min_lat)),
            max_lat=Decimal(str(max_lat)),
            min_lng=Decimal(str(min_lng)),
            max_lng=Decimal(str(max_lng)),
            heatmap_values=heatmap_values,
            min_value=min_value,
            max_value=max_value,
            mean_value=mean_value,
            median_value=median_value,
            processing_status='completed'
        )

        logger.info(f"Created heatmap data for asset {asset.name}, hazard {hazard_type}")
        return heatmap_data

    except Exception as e:
        logger.exception(f"Error creating heatmap data: {str(e)}")
        return None


def get_granular_analysis_progress(asset: Asset) -> Dict[str, Any]:
    """
    Get progress information for granular analysis of an asset.

    Args:
        asset: Asset instance

    Returns:
        Dictionary with progress information
    """
    try:
        total_points = GranularAnalysisResult.objects.filter(asset=asset).count()
        completed_points = GranularAnalysisResult.objects.filter(
            asset=asset, processing_status='completed'
        ).count()
        failed_points = GranularAnalysisResult.objects.filter(
            asset=asset, processing_status='failed'
        ).count()
        processing_points = GranularAnalysisResult.objects.filter(
            asset=asset, processing_status='processing'
        ).count()

        progress = {
            'total_points': total_points,
            'completed_points': completed_points,
            'failed_points': failed_points,
            'processing_points': processing_points,
            'pending_points': total_points - completed_points - failed_points - processing_points,
            'progress_percentage': (completed_points / total_points * 100) if total_points > 0 else 0,
            'status': asset.granular_analysis_status
        }

        return progress

    except Exception as e:
        logger.exception(f"Error getting granular analysis progress: {str(e)}")
        return {'error': str(e)}


def prepare_hierarchical_exposure_data(asset: Asset, selected_hazards: List[str]) -> Dict[str, Any]:
    """
    Prepare hierarchical data for polygon asset exposure table.

    Creates a simple parent-child structure where:
    - Parent row: Asset centroid
    - Child rows: Individual granular analysis points

    Args:
        asset: Asset instance with granular analysis
        selected_hazards: List of hazard types to include

    Returns:
        Dictionary with hierarchical data structure for template rendering
    """
    try:
        # Get all granular results for this asset
        granular_results = GranularAnalysisResult.objects.filter(
            asset=asset,
            hazard_type__in=selected_hazards,
            processing_status='completed'
        ).order_by('grid_row', 'grid_col', 'hazard_type')

        if not granular_results.exists():
            logger.warning(f"No completed granular results for asset {asset.name}")
            return {
                'success': False,
                'error': 'No completed analysis results found',
                'data': []
            }

        # Group results by grid point (lat/lng combination)
        grid_points = {}
        for result in granular_results:
            point_key = (float(result.latitude), float(result.longitude))
            if point_key not in grid_points:
                grid_points[point_key] = {
                    'latitude': float(result.latitude),
                    'longitude': float(result.longitude),
                    'grid_row': result.grid_row,
                    'grid_col': result.grid_col,
                    'hazards': {}
                }
            grid_points[point_key]['hazards'][result.hazard_type] = result.result_data

        # Create parent row (centroid)
        parent_row = {
            'id': f'asset_{asset.id}',
            'type': 'parent',
            'name': asset.name,
            'archetype': asset.archetype,
            'latitude': float(asset.latitude),
            'longitude': float(asset.longitude),
            'asset_type': 'Polygon (Centroid)',
            'is_parent': True,
            'children_count': len(grid_points),
            'hazards': {}
        }

        # Calculate centroid statistics for parent row
        for hazard_type in selected_hazards:
            hazard_values = []
            hazard_risks = []

            for point_data in grid_points.values():
                if hazard_type in point_data['hazards']:
                    hazard_data = point_data['hazards'][hazard_type]
                    if 'value' in hazard_data:
                        hazard_values.append(float(hazard_data['value']))
                    if 'risk_level' in hazard_data:
                        hazard_risks.append(hazard_data['risk_level'])

            if hazard_values:
                parent_row['hazards'][hazard_type] = {
                    'mean_value': sum(hazard_values) / len(hazard_values),
                    'min_value': min(hazard_values),
                    'max_value': max(hazard_values),
                    'median_value': sorted(hazard_values)[len(hazard_values) // 2],
                    'point_count': len(hazard_values)
                }

                # Add risk distribution
                if hazard_risks:
                    risk_dist = {}
                    for risk in hazard_risks:
                        risk_dist[risk] = risk_dist.get(risk, 0) + 1
                    parent_row['hazards'][hazard_type]['risk_distribution'] = risk_dist

        # Create child rows (individual grid points)
        child_rows = []
        for i, (point_key, point_data) in enumerate(grid_points.items()):
            child_row = {
                'id': f'asset_{asset.id}_point_{i}',
                'type': 'child',
                'parent_id': f'asset_{asset.id}',
                'name': f"{asset.name} - Point {i+1}",
                'archetype': asset.archetype,
                'latitude': point_data['latitude'],
                'longitude': point_data['longitude'],
                'grid_row': point_data['grid_row'],
                'grid_col': point_data['grid_col'],
                'asset_type': 'Grid Point',
                'is_parent': False,
                'hazards': {}
            }

            # Add hazard data for this point
            for hazard_type in selected_hazards:
                if hazard_type in point_data['hazards']:
                    hazard_data = point_data['hazards'][hazard_type]
                    child_row['hazards'][hazard_type] = {
                        'value': float(hazard_data.get('value', 0)),
                        'risk_level': hazard_data.get('risk_level', 'unknown'),
                        'unit': hazard_data.get('unit', ''),
                        'raw_data': hazard_data
                    }
                else:
                    child_row['hazards'][hazard_type] = {
                        'value': None,
                        'risk_level': 'no_data',
                        'unit': '',
                        'raw_data': {}
                    }

            child_rows.append(child_row)

        # Combine all data
        hierarchical_data = [parent_row] + child_rows

        # Get column definitions
        columns = ['Name', 'Archetype', 'Latitude', 'Longitude', 'Asset Type']
        hazard_columns = []

        for hazard_type in selected_hazards:
            hazard_columns.append(f'{hazard_type} Value')
            hazard_columns.append(f'{hazard_type} Risk')

        columns.extend(hazard_columns)

        return {
            'success': True,
            'data': hierarchical_data,
            'columns': columns,
            'parent_row': parent_row,
            'child_rows': child_rows,
            'asset': asset,
            'selected_hazards': selected_hazards,
            'grid_points_count': len(grid_points),
            'analysis_summary': {
                'total_points': len(grid_points),
                'hazards_analyzed': selected_hazards,
                'asset_name': asset.name,
                'analysis_status': asset.granular_analysis_status
            }
        }

    except Exception as e:
        logger.exception(f"Error preparing hierarchical exposure data: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'data': []
        }