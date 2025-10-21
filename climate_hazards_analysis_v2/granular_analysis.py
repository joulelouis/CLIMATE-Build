"""
Granular Risk Analysis Module
==============================
Implements point sampling grid strategy for polygon-based assets.
Provides finer resolution analysis within polygon boundaries instead of single centroid value.
"""

import numpy as np
import logging
import os
from collections import Counter
from shapely.geometry import shape, Point
from sklearn.cluster import DBSCAN

logger = logging.getLogger(__name__)


def generate_sample_grid(polygon_geometry, grid_spacing_meters=100):
    """
    Generate a grid of sample points within a polygon.

    This function creates a regular grid of points inside a polygon boundary,
    allowing for granular analysis instead of just using the centroid.

    Args:
        polygon_geometry: GeoJSON dict or Shapely polygon
        grid_spacing_meters: Distance between grid points in meters (10, 50, 100, 500, 1000)

    Returns:
        List of dictionaries with 'lat', 'lng' keys

    Example:
        >>> polygon = {'type': 'Polygon', 'coordinates': [...]}\
        >>> points = generate_sample_grid(polygon, grid_spacing_meters=100)
        >>> len(points)
        4200  # Approximately 4200 sample points for 42 km²
    """
    try:
        # Validate grid spacing
        valid_spacings = [10, 50, 100, 500, 1000]
        if grid_spacing_meters not in valid_spacings:
            logger.warning(f"Invalid grid spacing {grid_spacing_meters}m, using 100m default")
            grid_spacing_meters = 100

        # Convert GeoJSON to Shapely if needed
        if isinstance(polygon_geometry, dict):
            polygon = shape(polygon_geometry)
        else:
            polygon = polygon_geometry

        # Get bounding box
        minx, miny, maxx, maxy = polygon.bounds

        # Calculate grid spacing in degrees
        # Approximate conversion for Philippines (10-20°N latitude)
        # 1 degree ≈ 111km at equator, slightly less at higher latitudes
        degrees_per_meter = 1 / 111000
        grid_spacing_degrees = grid_spacing_meters * degrees_per_meter

        # Generate grid coordinates
        x_coords = np.arange(minx, maxx, grid_spacing_degrees)
        y_coords = np.arange(miny, maxy, grid_spacing_degrees)

        # Create points and filter to those inside polygon
        sample_points = []

        for x in x_coords:
            for y in y_coords:
                point = Point(x, y)

                # Only keep points inside polygon boundary
                if polygon.contains(point):
                    sample_points.append({
                        'lng': float(x),
                        'lat': float(y)
                    })

        logger.info(f"Generated {len(sample_points)} sample points with {grid_spacing_meters}m spacing")

        return sample_points

    except Exception as e:
        logger.error(f"Error generating sample grid: {e}")
        return []


def query_hazard_for_points(sample_points, hazard_raster_path, hazard_name='Unknown'):
    """
    Query hazard values for multiple points in batch.

    Uses rasterio to efficiently sample multiple points from a hazard raster file.

    Args:
        sample_points: List of point dictionaries with 'lat', 'lng' keys
        hazard_raster_path: Path to GeoTIFF hazard raster file
        hazard_name: Name of the hazard being queried

    Returns:
        List of dictionaries with coordinates and raw values

    Example:
        >>> points = [{'lat': 14.5, 'lng': 121.0}, ...]
        >>> results = query_hazard_for_points(points, 'flood_hazard.tif', 'Flood')
        >>> results[0]
        {'lat': 14.5, 'lng': 121.0, 'value': 0.85, 'hazard': 'Flood'}
    """
    try:
        import rasterio
        from rasterio.sample import sample_gen
        import os
    except ImportError:
        logger.error("rasterio not installed. Install with: pip install rasterio")
        return []

    results = []

    if not sample_points:
        logger.warning("No sample points provided for hazard query")
        return results

    if not os.path.exists(hazard_raster_path):
        logger.error(f"Hazard raster not found: {hazard_raster_path}")
        return results

    try:
        # Open raster file once for efficiency
        with rasterio.open(hazard_raster_path) as src:
            # Prepare coordinates for batch sampling (lng, lat order for rasterio)
            coords = [(pt['lng'], pt['lat']) for pt in sample_points]

            # Sample all points at once (much faster than one-by-one)
            sampled_values = list(sample_gen(src, coords))

            # Process results
            for i, point in enumerate(sample_points):
                try:
                    raster_value = sampled_values[i][0]  # First band

                    # Handle no-data values
                    if raster_value == src.nodata or np.isnan(raster_value):
                        raster_value = None

                    results.append({
                        'lat': point['lat'],
                        'lng': point['lng'],
                        'value': float(raster_value) if raster_value is not None else None,
                        'hazard': hazard_name
                    })

                except Exception as e:
                    logger.warning(f"Error processing point {i}: {e}")
                    results.append({
                        'lat': point['lat'],
                        'lng': point['lng'],
                        'value': None,
                        'hazard': hazard_name
                    })

        logger.info(f"Queried {len(results)} points from {hazard_name} raster")
        return results

    except Exception as e:
        logger.error(f"Error querying hazard raster: {e}")
        return []


def classify_hazard_risk(value, hazard_type):
    """
    Classify a hazard value into risk categories.

    Args:
        value: Numeric hazard value
        hazard_type: Type of hazard (Flood, Heat, etc.)

    Returns:
        Risk classification string (Low, Medium, High, Very High)
    """
    if value is None:
        return 'No Data'

    # Flood depth thresholds (meters)
    if hazard_type == 'Flood':
        if value < 0.5:
            return 'Low'
        elif value < 1.5:
            return 'Medium'
        elif value < 2.5:
            return 'High'
        else:
            return 'Very High'

    # Heat stress thresholds (days over 35°C)
    elif hazard_type == 'Heat':
        if value < 10:
            return 'Low'
        elif value < 45:
            return 'Medium'
        elif value < 90:
            return 'High'
        else:
            return 'Very High'

    # Water stress thresholds (%)
    elif hazard_type == 'Water Stress':
        if value < 10:
            return 'Low'
        elif value < 40:
            return 'Medium'
        elif value < 80:
            return 'High'
        else:
            return 'Very High'

    # Sea level rise thresholds (meters)
    elif hazard_type == 'Sea Level Rise':
        if value > 10:  # Reversed: higher elevation = lower risk
            return 'Low'
        elif value > 5:
            return 'Medium'
        elif value > 2:
            return 'High'
        else:
            return 'Very High'

    # Storm surge depth thresholds (meters)
    elif hazard_type == 'Storm Surge':
        if value < 0.5:
            return 'Low'
        elif value < 1.5:
            return 'Medium'
        elif value < 3.0:
            return 'High'
        else:
            return 'Very High'

    # Landslide factor of safety (reversed scale)
    elif hazard_type == 'Landslide':
        if value > 1.5:  # Reversed: higher FOS = lower risk
            return 'Low'
        elif value > 1.2:
            return 'Medium'
        elif value > 1.0:
            return 'High'
        else:
            return 'Very High'

    # Tropical cyclone windspeed (km/h)
    elif hazard_type == 'Tropical Cyclones':
        if value < 60:
            return 'Low'
        elif value < 120:
            return 'Medium'
        elif value < 180:
            return 'High'
        else:
            return 'Very High'

    # Default classification
    else:
        if value < 0.3:
            return 'Low'
        elif value < 0.6:
            return 'Medium'
        elif value < 0.9:
            return 'High'
        else:
            return 'Very High'


def consolidate_points_to_clusters(analyzed_points, grid_spacing_meters=100):
    """
    Consolidate sample points into risk clusters.

    Groups adjacent points with identical risk classifications across all hazards,
    reducing thousands of points into manageable clusters.

    Args:
        analyzed_points: List of dicts with 'lat', 'lng', and hazard risk classifications
        grid_spacing_meters: Grid spacing used (for cluster proximity calculation)

    Returns:
        Dictionary with consolidated clusters and statistics

    Example:
        >>> points = [
        ...     {'lat': 14.5, 'lng': 121.0, 'flood_risk': 'Medium', 'heat_risk': 'Low'},
        ...     {'lat': 14.501, 'lng': 121.0, 'flood_risk': 'Medium', 'heat_risk': 'Low'},
        ...     ...
        ... ]
        >>> result = consolidate_points_to_clusters(points, 100)
        >>> len(result['clusters'])
        47  # Reduced from 4200 points to 47 clusters
    """
    try:
        if not analyzed_points:
            return {'clusters': [], 'statistics': {}}

        # Step 1: Create risk profile strings for grouping
        for point in analyzed_points:
            # Combine all risk classifications into a single profile string
            risk_keys = [k for k in point.keys() if k.endswith('_risk')]
            profile = '|'.join([f"{k}:{point[k]}" for k in sorted(risk_keys)])
            point['risk_profile'] = profile

        # Step 2: Group points by identical risk profile
        profile_groups = {}
        for point in analyzed_points:
            profile = point['risk_profile']
            if profile not in profile_groups:
                profile_groups[profile] = []
            profile_groups[profile].append(point)

        logger.info(f"Found {len(profile_groups)} unique risk profiles")

        # Step 3: Apply spatial clustering within each profile group
        clusters = []
        cluster_id = 0

        # Convert grid spacing to degrees for DBSCAN epsilon
        degrees_per_meter = 1 / 111000
        eps_degrees = (grid_spacing_meters * 2) * degrees_per_meter  # 2x grid spacing for proximity

        for profile, points in profile_groups.items():
            # Extract coordinates for clustering
            coords = np.array([[p['lat'], p['lng']] for p in points])

            if len(points) == 1:
                # Single point - no clustering needed
                clusters.append({
                    'cluster_id': cluster_id,
                    'representative_point': {
                        'lat': points[0]['lat'],
                        'lng': points[0]['lng']
                    },
                    'risk_profile': profile,
                    'point_count': 1,
                    'all_points': points
                })
                cluster_id += 1
            else:
                # Apply DBSCAN clustering
                clustering = DBSCAN(eps=eps_degrees, min_samples=1).fit(coords)
                labels = clustering.labels_

                # Group by cluster labels
                for label in set(labels):
                    cluster_points = [points[i] for i in range(len(points)) if labels[i] == label]

                    # Calculate cluster centroid as representative point
                    centroid_lat = np.mean([p['lat'] for p in cluster_points])
                    centroid_lng = np.mean([p['lng'] for p in cluster_points])

                    clusters.append({
                        'cluster_id': cluster_id,
                        'representative_point': {
                            'lat': float(centroid_lat),
                            'lng': float(centroid_lng)
                        },
                        'risk_profile': profile,
                        'point_count': len(cluster_points),
                        'all_points': cluster_points
                    })
                    cluster_id += 1

        logger.info(f"Consolidated {len(analyzed_points)} points into {len(clusters)} clusters")

        # Step 4: Calculate statistics
        total_points = len(analyzed_points)

        # Get risk distribution for first hazard (for summary)
        first_risk_key = next((k for k in analyzed_points[0].keys() if k.endswith('_risk')), None)

        risk_distribution = {}
        if first_risk_key:
            risk_counter = Counter([p[first_risk_key] for p in analyzed_points])
            for risk_level in ['Low', 'Medium', 'High', 'Very High']:
                count = risk_counter.get(risk_level, 0)
                percentage = (count / total_points) * 100 if total_points > 0 else 0
                risk_distribution[risk_level] = {
                    'count': count,
                    'percentage': round(percentage, 1)
                }

        return {
            'clusters': clusters,
            'statistics': {
                'total_points': total_points,
                'cluster_count': len(clusters),
                'risk_distribution': risk_distribution
            }
        }

    except Exception as e:
        logger.error(f"Error consolidating points to clusters: {e}")
        return {'clusters': [], 'statistics': {}}


def calculate_polygon_area_km2(polygon_geometry):
    """
    Calculate polygon area in square kilometers.

    Args:
        polygon_geometry: GeoJSON dict or Shapely polygon

    Returns:
        Area in km²
    """
    try:
        if isinstance(polygon_geometry, dict):
            polygon = shape(polygon_geometry)
        else:
            polygon = polygon_geometry

        # Approximate conversion: degrees² to km² (111km per degree)
        area_km2 = polygon.area * 12321  # (111km)² ≈ 12321

        return area_km2

    except Exception as e:
        logger.error(f"Error calculating polygon area: {e}")
        return 0


def query_all_hazards_for_points(sample_points, selected_hazards, hazard_raster_config):
    """
    Query multiple hazards for all sample points.

    Args:
        sample_points: List of point dictionaries with 'lat', 'lng' keys
        selected_hazards: List of hazard names selected by user
        hazard_raster_config: Dictionary mapping hazard names to raster paths

    Returns:
        List of dictionaries with lat, lng, and all hazard values/classifications

    Example:
        >>> points = [{'lat': 14.5, 'lng': 121.0}, ...]
        >>> hazards = ['Flood', 'Heat']
        >>> config = {'Flood': '/path/to/flood.tif', 'Heat': '/path/to/heat.tif'}
        >>> results = query_all_hazards_for_points(points, hazards, config)
        >>> results[0]
        {
            'lat': 14.5,
            'lng': 121.0,
            'Flood_value': 0.85,
            'Flood_risk': 'Medium',
            'Heat_value': 45,
            'Heat_risk': 'Medium'
        }
    """
    try:
        if not sample_points:
            logger.warning("No sample points provided")
            return []

        # Initialize results with coordinates
        analyzed_points = []
        for point in sample_points:
            analyzed_points.append({
                'lat': point['lat'],
                'lng': point['lng']
            })

        # Query each hazard
        for hazard_name in selected_hazards:
            raster_path = hazard_raster_config.get(hazard_name)

            if not raster_path:
                logger.warning(f"No raster path configured for {hazard_name}")
                continue

            if not os.path.exists(raster_path):
                logger.warning(f"Raster file not found for {hazard_name}: {raster_path}")
                continue

            logger.info(f"Querying {hazard_name} for {len(sample_points)} points...")

            # Query hazard raster
            hazard_results = query_hazard_for_points(sample_points, raster_path, hazard_name)

            # Add hazard values and classifications to analyzed points
            for i, result in enumerate(hazard_results):
                if i < len(analyzed_points):
                    value = result.get('value')
                    analyzed_points[i][f'{hazard_name}_value'] = value
                    analyzed_points[i][f'{hazard_name}_risk'] = classify_hazard_risk(value, hazard_name)

        logger.info(f"Completed querying {len(selected_hazards)} hazards for {len(analyzed_points)} points")

        return analyzed_points

    except Exception as e:
        logger.error(f"Error querying all hazards for points: {e}")
        return []
