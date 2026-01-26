"""
Complete Granular Analysis Workflow Service

This module provides a comprehensive end-to-end workflow for granular climate hazard analysis.
It orchestrates the entire pipeline from polygon drawing to final results display with proper
error handling, progress tracking, and result aggregation.
"""

import logging
import json
import time
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from climate_hazards_analysis.models import Asset
from .models import GranularAnalysisResult, HazardAnalysisResult, HeatmapData
from .granular_utils import (
    generate_grid_points_from_polygon, create_granular_analysis_results,
    calculate_granular_statistics, create_heatmap_data, get_granular_analysis_progress,
    calculate_polygon_bounding_box, is_point_in_polygon
)
from .granular_processor import GranularAnalysisProcessor
from .utils import load_cached_hazard_data, combine_facility_with_hazard_data

logger = logging.getLogger(__name__)

# Thread lock for workflow coordination
workflow_lock = threading.Lock()


class GranularAnalysisWorkflowService:
    """
    Complete workflow service for granular climate hazard analysis.

    This service manages the entire pipeline:
    1. Polygon drawing → Grid generation
    2. Grid point creation → Hazard analysis
    3. Batch processing → Results aggregation
    4. Heatmap generation → Results table integration
    """

    def __init__(self, grid_spacing: float = 0.001, batch_size: int = 50, max_workers: int = 4):
        """
        Initialize the workflow service.

        Args:
            grid_spacing: Default grid spacing in degrees
            batch_size: Number of grid points to process in each batch
            max_workers: Maximum number of concurrent worker threads
        """
        self.grid_spacing = grid_spacing
        self.batch_size = batch_size
        self.max_workers = max_workers

    def execute_complete_workflow(self, polygon_geometry: Dict, asset_name: str,
                                 selected_hazards: List[str] = None, archetype: str = 'default archetype',
                                 scenario: str = 'current') -> Dict[str, Any]:
        """
        Execute the complete granular analysis workflow.

        Args:
            polygon_geometry: GeoJSON polygon geometry
            asset_name: Name for the polygon asset
            selected_hazards: List of hazard types to analyze
            archetype: Asset archetype
            scenario: Analysis scenario

        Returns:
            Dictionary with workflow results and metadata
        """
        try:
            with workflow_lock:
                logger.info(f"Starting complete granular analysis workflow for {asset_name}")

                workflow_start_time = timezone.now()

                # Step 1: Generate grid points from polygon
                logger.info("Step 1: Generating grid points from polygon")
                grid_points = self._generate_grid_points(polygon_geometry)
                if not grid_points:
                    return {
                        'success': False,
                        'error': 'Failed to generate grid points from polygon geometry',
                        'step': 'grid_generation'
                    }

                logger.info(f"Generated {len(grid_points)} grid points")

                # If no hazards provided, return grid points only (pure point generation)
                if not selected_hazards:
                    logger.info("No hazards provided - returning grid points only")
                    return {
                        'success': True,
                        'message': f'Successfully generated {len(grid_points)} grid points for {asset_name}',
                        'asset_id': f'points_{asset_name.lower().replace(" ", "_")}',
                        'grid_points': grid_points,
                        'point_count': len(grid_points),
                        'workflow_type': 'point_generation_only',
                        'step': 'completed'
                    }

                # Step 2: Create polygon asset with granular analysis setup
                logger.info("Step 2: Creating polygon asset")
                asset = self._create_polygon_asset(polygon_geometry, asset_name, archetype, grid_points, selected_hazards)
                if not asset:
                    return {
                        'success': False,
                        'error': 'Failed to create polygon asset',
                        'step': 'asset_creation'
                    }

                # Step 3: Create granular analysis records for all grid points
                logger.info("Step 3: Creating granular analysis records")
                granular_results = self._setup_granular_analysis(asset, grid_points, selected_hazards, scenario)
                if not granular_results:
                    return {
                        'success': False,
                        'error': 'Failed to setup granular analysis',
                        'step': 'granular_setup'
                    }

                # Step 4: Execute hazard analysis for all grid points
                logger.info("Step 4: Executing hazard analysis for grid points")
                analysis_results = self._execute_hazard_analysis(asset, selected_hazards, scenario)
                if not analysis_results.get('success'):
                    return {
                        'success': False,
                        'error': f'Hazard analysis failed: {analysis_results.get("error")}',
                        'step': 'hazard_analysis',
                        'partial_results': analysis_results
                    }

                # Step 5: Aggregate results and create summaries
                logger.info("Step 5: Aggregating analysis results")
                aggregated_results = self._aggregate_analysis_results(asset, selected_hazards, scenario)

                # Step 6: Generate heatmap data for visualization
                logger.info("Step 6: Generating heatmap data")
                heatmap_data = self._generate_heatmap_data(asset, selected_hazards, scenario)

                # Step 7: Prepare final results for hazard exposure table
                logger.info("Step 7: Preparing final results table")
                table_results = self._prepare_hazard_exposure_table(asset, selected_hazards, aggregated_results)

                workflow_end_time = timezone.now()
                workflow_duration = (workflow_end_time - workflow_start_time).total_seconds()

                # Update final asset status
                asset.update_analysis_status('completed', 100.0)

                logger.info(f"Completed granular analysis workflow for {asset_name} in {workflow_duration:.2f} seconds")

                return {
                    'success': True,
                    'asset_id': asset.id,
                    'asset_name': asset.name,
                    'workflow_duration': workflow_duration,
                    'grid_points_generated': len(grid_points),
                    'granular_results_created': len(granular_results),
                    'hazard_analysis_results': analysis_results,
                    'aggregated_results': aggregated_results,
                    'heatmap_data_generated': len(heatmap_data),
                    'table_results': table_results,
                    'selected_hazards': selected_hazards,
                    'scenario': scenario,
                    'message': f'Successfully completed granular analysis for {len(grid_points)} grid points'
                }

        except Exception as e:
            logger.exception(f"Error in complete granular analysis workflow: {str(e)}")
            return {
                'success': False,
                'error': f'Workflow failed: {str(e)}',
                'step': 'unknown'
            }

    def _generate_grid_points(self, polygon_geometry: Dict) -> List[Tuple[float, float, int, int]]:
        """
        Generate grid points within polygon boundaries.

        Args:
            polygon_geometry: GeoJSON polygon geometry

        Returns:
            List of (latitude, longitude, grid_row, grid_col) tuples
        """
        try:
            grid_points = generate_grid_points_from_polygon(polygon_geometry, self.grid_spacing)
            logger.info(f"Generated {len(grid_points)} grid points with spacing {self.grid_spacing}°")
            return grid_points
        except Exception as e:
            logger.exception(f"Error generating grid points: {str(e)}")
            return []

    def _create_polygon_asset(self, polygon_geometry: Dict, asset_name: str, archetype: str,
                            grid_points: List[Tuple[float, float, int, int]],
                            selected_hazards: List[str]) -> Optional[Asset]:
        """
        Create polygon asset with granular analysis metadata.

        Args:
            polygon_geometry: GeoJSON polygon geometry
            asset_name: Name for the asset
            archetype: Asset archetype
            grid_points: Generated grid points
            selected_hazards: Selected hazard types

        Returns:
            Created Asset instance or None if failed
        """
        try:
            # Calculate centroid from grid points
            if grid_points:
                centroid_lat = sum(point[0] for point in grid_points) / len(grid_points)
                centroid_lng = sum(point[1] for point in grid_points) / len(grid_points)
            else:
                # Calculate centroid from polygon
                coords = polygon_geometry.get('coordinates', [[]])[0]
                if coords:
                    centroid_lat = sum(coord[1] for coord in coords) / len(coords)
                    centroid_lng = sum(coord[0] for coord in coords) / len(coords)
                else:
                    return None

            with transaction.atomic():
                asset = Asset.objects.create(
                    name=asset_name,
                    archetype=archetype,
                    latitude=Decimal(str(centroid_lat)),
                    longitude=Decimal(str(centroid_lng)),
                    polygon_geometry=polygon_geometry,
                    asset_type='polygon',
                    has_granular_analysis=True,
                    granular_grid_spacing=self.grid_spacing,
                    granular_grid_points_count=len(grid_points) * len(selected_hazards),
                    granular_analysis_status='pending',
                    granular_analysis_progress=0.0
                )

                logger.info(f"Created polygon asset: {asset.name} (ID: {asset.id})")
                return asset

        except Exception as e:
            logger.exception(f"Error creating polygon asset: {str(e)}")
            return None

    def _setup_granular_analysis(self, asset: Asset, grid_points: List[Tuple[float, float, int, int]],
                                selected_hazards: List[str], scenario: str) -> List[GranularAnalysisResult]:
        """
        Setup granular analysis records for all grid points.

        Args:
            asset: Asset instance
            grid_points: List of grid points
            selected_hazards: Selected hazard types
            scenario: Analysis scenario

        Returns:
            List of created GranularAnalysisResult instances
        """
        try:
            granular_results = create_granular_analysis_results(
                asset, grid_points, selected_hazards, scenario
            )
            logger.info(f"Created {len(granular_results)} granular analysis records")
            return granular_results
        except Exception as e:
            logger.exception(f"Error setting up granular analysis: {str(e)}")
            return []

    def _execute_hazard_analysis(self, asset: Asset, selected_hazards: List[str],
                                scenario: str) -> Dict[str, Any]:
        """
        Execute hazard analysis for all grid points using the processor.

        Args:
            asset: Asset instance
            selected_hazards: Selected hazard types
            scenario: Analysis scenario

        Returns:
            Dictionary with analysis results
        """
        try:
            processor = GranularAnalysisProcessor(
                asset=asset,
                batch_size=self.batch_size,
                max_workers=self.max_workers
            )

            results = processor.process_granular_analysis(selected_hazards, scenario)
            logger.info(f"Hazard analysis completed: {results}")
            return results
        except Exception as e:
            logger.exception(f"Error executing hazard analysis: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _aggregate_analysis_results(self, asset: Asset, selected_hazards: List[str],
                                  scenario: str) -> Dict[str, Any]:
        """
        Aggregate analysis results from all grid points.

        Args:
            asset: Asset instance
            selected_hazards: Selected hazard types
            scenario: Analysis scenario

        Returns:
            Dictionary with aggregated results
        """
        try:
            aggregated_data = {}

            for hazard_type in selected_hazards:
                stats = calculate_granular_statistics(asset, hazard_type, scenario)
                if stats:
                    aggregated_data[hazard_type] = {
                        'statistics': stats,
                        'risk_summary': self._calculate_risk_summary(stats),
                        'exposure_distribution': self._calculate_exposure_distribution(asset, hazard_type, scenario)
                    }

            logger.info(f"Aggregated results for {len(aggregated_data)} hazard types")
            return aggregated_data
        except Exception as e:
            logger.exception(f"Error aggregating analysis results: {str(e)}")
            return {}

    def _calculate_risk_summary(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate risk summary from statistics.

        Args:
            stats: Statistical data for a hazard type

        Returns:
            Dictionary with risk summary
        """
        try:
            risk_dist = stats.get('risk_distribution', {})
            total_points = stats.get('grid_points_processed', 0)

            if total_points == 0:
                return {'overall_risk': 'unknown', 'risk_percentages': {}}

            risk_percentages = {}
            for risk_level, count in risk_dist.items():
                risk_percentages[risk_level] = (count / total_points) * 100

            # Determine overall risk
            if risk_percentages.get('high', 0) > 30:
                overall_risk = 'high'
            elif risk_percentages.get('high', 0) > 10 or risk_percentages.get('medium', 0) > 40:
                overall_risk = 'medium'
            else:
                overall_risk = 'low'

            return {
                'overall_risk': overall_risk,
                'risk_percentages': risk_percentages,
                'confidence_level': 'high' if total_points > 50 else 'medium'
            }
        except Exception as e:
            logger.exception(f"Error calculating risk summary: {str(e)}")
            return {'overall_risk': 'unknown', 'risk_percentages': {}}

    def _calculate_exposure_distribution(self, asset: Asset, hazard_type: str,
                                       scenario: str) -> Dict[str, Any]:
        """
        Calculate exposure distribution across different value ranges.

        Args:
            asset: Asset instance
            hazard_type: Hazard type
            scenario: Analysis scenario

        Returns:
            Dictionary with exposure distribution
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

            # Extract values
            values = []
            for result in results:
                if result.result_data and 'value' in result.result_data:
                    values.append(float(result.result_data['value']))

            if not values:
                return {}

            # Calculate distribution
            values.sort()
            n = len(values)

            distribution = {
                'min': values[0],
                'max': values[-1],
                'mean': sum(values) / n,
                'percentiles': {
                    'p25': values[int(n * 0.25)],
                    'p50': values[int(n * 0.5)],
                    'p75': values[int(n * 0.75)],
                    'p90': values[int(n * 0.9)],
                    'p95': values[int(n * 0.95)]
                }
            }

            return distribution
        except Exception as e:
            logger.exception(f"Error calculating exposure distribution: {str(e)}")
            return {}

    def _generate_heatmap_data(self, asset: Asset, selected_hazards: List[str],
                              scenario: str) -> List[HeatmapData]:
        """
        Generate heatmap data for visualization.

        Args:
            asset: Asset instance
            selected_hazards: Selected hazard types
            scenario: Analysis scenario

        Returns:
            List of created HeatmapData instances
        """
        try:
            heatmap_data_list = []

            for hazard_type in selected_hazards:
                heatmap_data = create_heatmap_data(asset, hazard_type, scenario)
                if heatmap_data:
                    heatmap_data_list.append(heatmap_data)
                    logger.info(f"Generated heatmap data for {hazard_type}")

            return heatmap_data_list
        except Exception as e:
            logger.exception(f"Error generating heatmap data: {str(e)}")
            return []

    def _prepare_hazard_exposure_table(self, asset: Asset, selected_hazards: List[str],
                                     aggregated_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Prepare results data for the hazard exposure table.

        Args:
            asset: Asset instance
            selected_hazards: Selected hazard types
            aggregated_results: Aggregated analysis results

        Returns:
            List of table row data
        """
        try:
            table_rows = []

            for hazard_type in selected_hazards:
                hazard_data = aggregated_results.get(hazard_type, {})
                stats = hazard_data.get('statistics', {})
                risk_summary = hazard_data.get('risk_summary', {})

                if stats:
                    row = {
                        'Facility': asset.name,
                        'Lat': float(asset.latitude),
                        'Long': float(asset.longitude),
                        'Archetype': asset.archetype,
                        'Asset Type': 'Polygon (Granular Analysis)',
                        'Asset ID': asset.id,
                        'Hazard Type': hazard_type,
                        'Grid Points Processed': stats.get('grid_points_processed', 0),
                        'Total Grid Points': stats.get('total_grid_points', 0),
                        'Analysis Status': asset.granular_analysis_status,
                        'Overall Risk': risk_summary.get('overall_risk', 'unknown'),
                        'Mean Exposure': stats.get('mean_value', 0),
                        'Min Exposure': stats.get('min_value', 0),
                        'Max Exposure': stats.get('max_value', 0),
                        'Median Exposure': stats.get('median_value', 0),
                        'Success Rate': (stats.get('grid_points_processed', 0) / stats.get('total_grid_points', 1)) * 100
                    }

                    # Add risk distribution percentages
                    risk_percentages = risk_summary.get('risk_percentages', {})
                    for risk_level, percentage in risk_percentages.items():
                        row[f'{risk_level.title()} Risk %'] = f"{percentage:.1f}%"

                    # Add exposure distribution percentiles
                    exposure_dist = hazard_data.get('exposure_distribution', {})
                    if exposure_dist and 'percentiles' in exposure_dist:
                        percentiles = exposure_dist['percentiles']
                        for p_key, p_value in percentiles.items():
                            row[f'{hazard_type} {p_key.upper()}'] = p_value

                    table_rows.append(row)

            logger.info(f"Prepared {len(table_rows)} table rows for hazard exposure")
            return table_rows
        except Exception as e:
            logger.exception(f"Error preparing hazard exposure table: {str(e)}")
            return []

    def get_workflow_status(self, asset_id: int) -> Dict[str, Any]:
        """
        Get current status of the granular analysis workflow for an asset.

        Args:
            asset_id: ID of the asset

        Returns:
            Dictionary with workflow status
        """
        try:
            asset = Asset.objects.get(asset_id=asset_id)

            if not asset.has_granular_analysis:
                return {
                    'success': False,
                    'error': 'Asset does not have granular analysis enabled'
                }

            progress = get_granular_analysis_progress(asset)

            # Get hazard-wise status
            hazard_status = {}
            hazard_types = GranularAnalysisResult.objects.filter(
                asset=asset
            ).values_list('hazard_type', flat=True).distinct()

            for hazard_type in hazard_types:
                stats = calculate_granular_statistics(asset, hazard_type)
                if stats:
                    hazard_status[hazard_type] = {
                        'processed_points': stats.get('grid_points_processed', 0),
                        'total_points': stats.get('total_grid_points', 0),
                        'completion_rate': (stats.get('grid_points_processed', 0) / stats.get('total_grid_points', 1)) * 100,
                        'mean_value': stats.get('mean_value', 0),
                        'risk_level': self._calculate_risk_summary(stats).get('overall_risk', 'unknown')
                    }

            return {
                'success': True,
                'asset_id': asset.id,
                'asset_name': asset.name,
                'workflow_status': asset.granular_analysis_status,
                'progress': progress,
                'hazard_status': hazard_status,
                'estimated_completion_time': self._estimate_completion_time(progress),
                'last_updated': asset.updated_at.isoformat()
            }

        except Asset.DoesNotExist:
            return {'success': False, 'error': 'Asset not found'}
        except Exception as e:
            logger.exception(f"Error getting workflow status: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _estimate_completion_time(self, progress: Dict[str, Any]) -> Optional[str]:
        """
        Estimate completion time based on current progress.

        Args:
            progress: Progress information

        Returns:
            Estimated completion time string or None
        """
        try:
            total_points = progress.get('total_points', 0)
            completed_points = progress.get('completed_points', 0)
            processing_points = progress.get('processing_points', 0)

            if total_points == 0 or completed_points == 0:
                return None

            # Simple estimation based on current rate
            remaining_points = total_points - completed_points - processing_points

            # Assume ~0.1 seconds per point processing time
            estimated_seconds = remaining_points * 0.1 / self.max_workers

            if estimated_seconds < 60:
                return f"~{int(estimated_seconds)} seconds"
            elif estimated_seconds < 3600:
                return f"~{int(estimated_seconds / 60)} minutes"
            else:
                return f"~{int(estimated_seconds / 3600)} hours"

        except Exception:
            return None


# Convenience function for easy access
def execute_granular_analysis_workflow(polygon_geometry: Dict, asset_name: str,
                                     selected_hazards: List[str] = None, archetype: str = 'default archetype',
                                     scenario: str = 'current', grid_spacing: float = 0.001) -> Dict[str, Any]:
    """
    Convenience function to execute the complete granular analysis workflow.

    Args:
        polygon_geometry: GeoJSON polygon geometry
        asset_name: Name for the polygon asset
        selected_hazards: List of hazard types to analyze
        archetype: Asset archetype
        scenario: Analysis scenario
        grid_spacing: Grid spacing in degrees

    Returns:
        Dictionary with workflow results
    """
    service = GranularAnalysisWorkflowService(grid_spacing=grid_spacing)
    return service.execute_complete_workflow(
        polygon_geometry=polygon_geometry,
        asset_name=asset_name,
        selected_hazards=selected_hazards,
        archetype=archetype,
        scenario=scenario
    )
