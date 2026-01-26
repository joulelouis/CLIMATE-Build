"""
Granular analysis processor for batch hazard querying of grid points.
This module handles the batch processing of climate hazard analysis for multiple grid points
within polygon assets, optimizing performance and managing processing workflow.
"""

import logging
import time
from typing import List, Dict, Any, Optional
from django.db import transaction
from django.utils import timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from django.db import models
from climate_hazards_analysis.models import Asset
from .models import GranularAnalysisResult, HazardAnalysisResult, HeatmapData
from .granular_utils import create_heatmap_data
from .utils import load_cached_hazard_data, combine_facility_with_hazard_data

logger = logging.getLogger(__name__)

# Global thread lock for batch processing
batch_processing_lock = threading.Lock()


class GranularAnalysisProcessor:
    """
    Processor class for handling granular analysis of polygon assets.
    Manages batch processing of grid points and hazard analysis.
    """

    def __init__(self, asset: Asset, batch_size: int = 50, max_workers: int = 4):
        """
        Initialize the processor for a specific asset.

        Args:
            asset: Asset instance to process
            batch_size: Number of grid points to process in each batch
            max_workers: Maximum number of concurrent worker threads
        """
        self.asset = asset
        self.batch_size = batch_size
        self.max_workers = max_workers

    def process_granular_analysis(self, hazard_types: List[str], scenario: str = 'current') -> Dict[str, Any]:
        """
        Process granular analysis for all grid points of the asset.

        Args:
            hazard_types: List of hazard types to analyze
            scenario: Analysis scenario

        Returns:
            Dictionary with processing results and statistics
        """
        try:
            with batch_processing_lock:
                # Update asset status
                self.asset.granular_analysis_status = 'processing'
                self.asset.save()

                logger.info(f"Starting granular analysis for asset {self.asset.name} with {len(hazard_types)} hazard types")

                # Get all pending granular results
                pending_results = GranularAnalysisResult.objects.filter(
                    asset=self.asset,
                    processing_status='pending'
                ).order_by('hazard_type', 'grid_row', 'grid_col')

                total_points = pending_results.count()
                if total_points == 0:
                    logger.warning(f"No pending granular analysis results found for asset {self.asset.name}")
                    return {'success': False, 'error': 'No pending analysis results found'}

                logger.info(f"Processing {total_points} granular analysis points for asset {self.asset.name}")

                # Group results by hazard type for batch processing
                hazard_groups = {}
                for result in pending_results:
                    hazard_type = result.hazard_type
                    if hazard_type not in hazard_groups:
                        hazard_groups[hazard_type] = []
                    hazard_groups[hazard_type].append(result)

                # Process each hazard type
                processing_stats = {
                    'total_points': total_points,
                    'hazard_types': len(hazard_groups),
                    'processed_points': 0,
                    'failed_points': 0,
                    'start_time': timezone.now(),
                    'hazard_stats': {}
                }

                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = []

                    for hazard_type, results in hazard_groups.items():
                        if hazard_type not in hazard_types:
                            continue

                        # Process results in batches
                        for i in range(0, len(results), self.batch_size):
                            batch = results[i:i + self.batch_size]
                            future = executor.submit(
                                self._process_batch,
                                batch,
                                hazard_type,
                                scenario,
                                processing_stats
                            )
                            futures.append(future)

                    # Wait for all futures to complete
                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            logger.exception(f"Batch processing failed: {str(e)}")
                            processing_stats['failed_points'] += self.batch_size

                # Calculate final statistics
                processing_stats['end_time'] = timezone.now()
                processing_stats['duration'] = (processing_stats['end_time'] - processing_stats['start_time']).total_seconds()
                processing_stats['success_rate'] = (processing_stats['processed_points'] / processing_stats['total_points']) * 100

                # Update asset status
                if processing_stats['failed_points'] == 0:
                    self.asset.granular_analysis_status = 'completed'
                else:
                    self.asset.granular_analysis_status = 'completed_with_errors'

                self.asset.granular_analysis_progress = 100.0
                self.asset.save()

                # Generate aggregated hazard analysis results
                self._create_aggregated_results(hazard_types, scenario)

                # Generate heatmap data for each hazard type
                for hazard_type in hazard_types:
                    try:
                        create_heatmap_data(self.asset, hazard_type, scenario)
                        logger.info(f"Generated heatmap data for hazard {hazard_type}")
                    except Exception as e:
                        logger.exception(f"Failed to generate heatmap data for {hazard_type}: {str(e)}")

                logger.info(f"Completed granular analysis for asset {self.asset.name}")
                return {
                    'success': True,
                    'stats': processing_stats,
                    'message': f'Processed {processing_stats["processed_points"]} points successfully'
                }

        except Exception as e:
            logger.exception(f"Error processing granular analysis for asset {self.asset.name}: {str(e)}")
            self.asset.granular_analysis_status = 'failed'
            self.asset.save()
            return {'success': False, 'error': str(e)}

    def _process_batch(self, batch: List[GranularAnalysisResult], hazard_type: str,
                      scenario: str, processing_stats: Dict[str, Any]) -> None:
        """
        Process a batch of granular analysis results.

        Args:
            batch: List of GranularAnalysisResult objects to process
            hazard_type: Hazard type being processed
            scenario: Analysis scenario
            processing_stats: Dictionary to track processing statistics
        """
        try:
            # Create facility-like data for batch processing
            facility_data = []
            for result in batch:
                facility_data.append({
                    'Facility': f"Grid_{result.grid_row}_{result.grid_col}",
                    'Lat': float(result.latitude),
                    'Long': float(result.longitude),
                    'Archetype': self.asset.archetype
                })

            # Load hazard data for the batch
            try:
                hazard_data = load_cached_hazard_data(hazard_type)
                if not hazard_data:
                    raise ValueError(f"No hazard data available for {hazard_type}")

                # Combine facility data with hazard data
                combined_data = combine_facility_with_hazard_data(facility_data, hazard_data)

                # Update results with combined data
                with transaction.atomic():
                    for i, result in enumerate(batch):
                        if i < len(combined_data):
                            result_data = self._extract_hazard_values(combined_data[i], hazard_type)
                            result.result_data = result_data
                            result.processing_status = 'completed'
                            result.analysis_date = timezone.now()
                            result.save()

                            processing_stats['processed_points'] += 1
                        else:
                            result.processing_status = 'failed'
                            result.error_message = 'No hazard data returned'
                            result.save()

                            processing_stats['failed_points'] += 1

                # Update progress
                progress = (processing_stats['processed_points'] + processing_stats['failed_points']) / processing_stats['total_points'] * 100
                self.asset.granular_analysis_progress = progress
                self.asset.save()

            except Exception as e:
                logger.exception(f"Error processing batch for {hazard_type}: {str(e)}")
                # Mark all results in batch as failed
                with transaction.atomic():
                    for result in batch:
                        result.processing_status = 'failed'
                        result.error_message = str(e)
                        result.save()
                        processing_stats['failed_points'] += 1

        except Exception as e:
            logger.exception(f"Unexpected error in batch processing: {str(e)}")
            processing_stats['failed_points'] += len(batch)

    def _extract_hazard_values(self, facility_record: Dict[str, Any], hazard_type: str) -> Dict[str, Any]:
        """
        Extract relevant hazard values from a facility record.

        Args:
            facility_record: Combined facility and hazard data record
            hazard_type: Type of hazard being analyzed

        Returns:
            Dictionary with extracted hazard values and metadata
        """
        result_data = {
            'hazard_type': hazard_type,
            'facility_name': facility_record.get('Facility', 'Unknown'),
            'latitude': facility_record.get('Lat', 0),
            'longitude': facility_record.get('Long', 0),
            'archetype': facility_record.get('Archetype', 'default')
        }

        # Extract hazard-specific values
        hazard_value = None
        risk_level = 'unknown'

        # Common patterns for hazard exposure values
        possible_value_fields = [
            f'{hazard_type} Exposure (%)',
            f'{hazard_type} Exposure (%) - Moderate Case',
            f'{hazard_type} Exposure (%) - Worst Case',
            f'{hazard_type} Risk Score',
            f'{hazard_type} Severity',
            hazard_type
        ]

        for field in possible_value_fields:
            if field in facility_record and facility_record[field] is not None:
                try:
                    hazard_value = float(facility_record[field])
                    break
                except (ValueError, TypeError):
                    continue

        # Determine risk level based on value
        if hazard_value is not None:
            result_data['value'] = hazard_value

            # Risk level determination (simplified - can be customized per hazard type)
            if hazard_type == 'Heat':
                if hazard_value > 30:
                    risk_level = 'high'
                elif hazard_value > 20:
                    risk_level = 'medium'
                else:
                    risk_level = 'low'
            elif hazard_type in ['Flood', 'Sea Level Rise', 'Storm Surge']:
                if hazard_value > 50:
                    risk_level = 'high'
                elif hazard_value > 20:
                    risk_level = 'medium'
                else:
                    risk_level = 'low'
            elif hazard_type == 'Water Stress':
                if hazard_value > 40:
                    risk_level = 'high'
                elif hazard_value > 20:
                    risk_level = 'medium'
                else:
                    risk_level = 'low'
            else:
                # Generic risk assessment
                if hazard_value > 70:
                    risk_level = 'high'
                elif hazard_value > 30:
                    risk_level = 'medium'
                else:
                    risk_level = 'low'
        else:
            result_data['value'] = 0.0

        result_data['risk_level'] = risk_level

        # Include all available fields for comprehensive analysis
        for key, value in facility_record.items():
            if key not in ['Facility', 'Lat', 'Long', 'Archetype'] and not key.startswith('_'):
                result_data[key] = value

        return result_data

    def _create_aggregated_results(self, hazard_types: List[str], scenario: str) -> None:
        """
        Create aggregated hazard analysis results from granular data.

        Args:
            hazard_types: List of hazard types processed
            scenario: Analysis scenario
        """
        try:
            from .granular_utils import calculate_granular_statistics

            logger.info(f"Creating aggregated results for asset {self.asset.name}")

            for hazard_type in hazard_types:
                # Calculate statistics for this hazard type
                stats = calculate_granular_statistics(self.asset, hazard_type)

                if stats:
                    # Create or update aggregated HazardAnalysisResult
                    hazard_result, created = HazardAnalysisResult.objects.update_or_create(
                        asset=self.asset,
                        hazard_type=hazard_type,
                        scenario=scenario,
                        defaults={
                            'result_data': {
                                'granular_analysis': True,
                                'statistics': stats,
                                'asset_type': 'polygon',
                                'total_grid_points': stats.get('total_grid_points', 0),
                                'processed_points': stats.get('grid_points_processed', 0),
                                'analysis_date': timezone.now().isoformat()
                            }
                        }
                    )

                    if created:
                        logger.info(f"Created aggregated result for {hazard_type}")
                    else:
                        logger.info(f"Updated aggregated result for {hazard_type}")

        except Exception as e:
            logger.exception(f"Error creating aggregated results: {str(e)}")


def process_asset_granular_analysis(asset_id: int, hazard_types: List[str],
                                   scenario: str = 'current') -> Dict[str, Any]:
    """
    Convenience function to process granular analysis for an asset.

    Args:
        asset_id: ID of the asset to process
        hazard_types: List of hazard types to analyze
        scenario: Analysis scenario

    Returns:
        Dictionary with processing results
    """
    try:
        asset = Asset.objects.get(asset_id=asset_id)

        if not asset.has_granular_analysis:
            return {'success': False, 'error': 'Asset does not have granular analysis enabled'}

        processor = GranularAnalysisProcessor(asset)
        return processor.process_granular_analysis(hazard_types, scenario)

    except Asset.DoesNotExist:
        return {'success': False, 'error': 'Asset not found'}
    except Exception as e:
        logger.exception(f"Error in process_asset_granular_analysis: {str(e)}")
        return {'success': False, 'error': str(e)}


def get_granular_analysis_summary(asset_id: int) -> Dict[str, Any]:
    """
    Get a summary of granular analysis results for an asset.

    Args:
        asset_id: ID of the asset

    Returns:
        Dictionary with analysis summary
    """
    try:
        asset = Asset.objects.get(asset_id=asset_id)

        if not asset.has_granular_analysis:
            return {
                'success': False,
                'error': 'Asset does not have granular analysis enabled'
            }

        # Get granular results statistics
        granular_stats = {
            'total_results': GranularAnalysisResult.objects.filter(asset=asset).count(),
            'completed_results': GranularAnalysisResult.objects.filter(
                asset=asset, processing_status='completed'
            ).count(),
            'failed_results': GranularAnalysisResult.objects.filter(
                asset=asset, processing_status='failed'
            ).count(),
            'pending_results': GranularAnalysisResult.objects.filter(
                asset=asset, processing_status='pending'
            ).count()
        }

        # Get hazard type breakdown
        hazard_breakdown = {}
        hazard_types = GranularAnalysisResult.objects.filter(
            asset=asset
        ).values_list('hazard_type', flat=True).distinct()

        for hazard_type in hazard_types:
            hazard_stats = GranularAnalysisResult.objects.filter(
                asset=asset, hazard_type=hazard_type
            ).aggregate(
                total=models.Count('id'),
                completed=models.Count('id', filter=models.Q(processing_status='completed')),
                failed=models.Count('id', filter=models.Q(processing_status='failed'))
            )
            hazard_breakdown[hazard_type] = hazard_stats

        # Get heatmap data availability
        heatmap_availability = {}
        for hazard_type in hazard_types:
            heatmap_count = HeatmapData.objects.filter(
                asset=asset, hazard_type=hazard_type, processing_status='completed'
            ).count()
            heatmap_availability[hazard_type] = heatmap_count > 0

        return {
            'success': True,
            'asset_info': {
                'id': asset.id,
                'name': asset.name,
                'asset_type': asset.asset_type,
                'granular_analysis_status': asset.granular_analysis_status,
                'grid_spacing': asset.granular_grid_spacing,
                'total_grid_points': asset.granular_grid_points_count,
                'analysis_progress': asset.granular_analysis_progress
            },
            'granular_stats': granular_stats,
            'hazard_breakdown': hazard_breakdown,
            'heatmap_availability': heatmap_availability
        }

    except Asset.DoesNotExist:
        return {'success': False, 'error': 'Asset not found'}
    except Exception as e:
        logger.exception(f"Error getting granular analysis summary: {str(e)}")
        return {'success': False, 'error': str(e)}
