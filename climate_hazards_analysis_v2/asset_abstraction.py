"""
Asset Abstraction Layer

This module provides a unified abstraction layer for handling both point and polygon assets
in the climate hazards analysis system. It abstracts away the implementation details
and provides a consistent interface regardless of the underlying asset type.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, Union
from decimal import Decimal
from dataclasses import dataclass, asdict

from .models import Asset, HazardAnalysisResult, GranularAnalysisResult, HeatmapData
from .asset_service import AssetService, AssetAnalysisService, AssetType, AnalysisStatus

logger = logging.getLogger(__name__)


@dataclass
class AssetCoordinates:
    """Unified coordinate representation for all asset types."""
    latitude: float
    longitude: float

    def as_tuple(self) -> Tuple[float, float]:
        return (self.latitude, self.longitude)


@dataclass
class AssetBounds:
    """Bounding box representation for assets."""
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float

    def contains(self, coordinates: AssetCoordinates) -> bool:
        return (self.min_lat <= coordinates.latitude <= self.max_lat and
                self.min_lng <= coordinates.longitude <= self.max_lng)

    def as_dict(self) -> Dict[str, float]:
        return {
            'min_lat': self.min_lat,
            'max_lat': self.max_lat,
            'min_lng': self.min_lng,
            'max_lng': self.max_lng
        }


@dataclass
class HazardExposureData:
    """Unified hazard exposure data structure."""
    hazard_type: str
    severity: str  # 'low', 'medium', 'high'
    value: float
    confidence: float
    metadata: Dict[str, Any]

    def get_color_code(self) -> str:
        """Get color code based on severity."""
        severity_colors = {
            'low': '#28a745',      # green
            'medium': '#ffc107',   # yellow
            'high': '#dc3545',     # red
            'extreme': '#6f42c1'   # purple
        }
        return severity_colors.get(self.severity.lower(), '#6c757d')


@dataclass
class AssetVisualizationData:
    """Unified visualization data structure for assets."""
    id: int
    name: str
    asset_type: str
    coordinates: AssetCoordinates
    bounds: Optional[AssetBounds]
    geojson: Dict[str, Any]
    hazard_exposures: List[HazardExposureData]
    properties: Dict[str, Any]
    has_granular_data: bool
    analysis_status: str

    def to_leaflet_format(self) -> Dict[str, Any]:
        """Convert to Leaflet-compatible format."""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.asset_type,
            'lat': self.coordinates.latitude,
            'lng': self.coordinates.longitude,
            'geojson': self.geojson,
            'properties': self.properties,
            'hazard_data': {
                exposure.hazard_type: asdict(exposure)
                for exposure in self.hazard_exposures
            },
            'has_granular': self.has_granular_data,
            'status': self.analysis_status
        }


class BaseAsset(ABC):
    """Abstract base class for all asset types."""

    def __init__(self, asset_model: Asset):
        self._model = asset_model
        self._coordinates = AssetCoordinates(
            latitude=float(asset_model.latitude),
            longitude=float(asset_model.longitude)
        )

    @property
    def model(self) -> Asset:
        """Get the underlying Django model instance."""
        return self._model

    @property
    def id(self) -> int:
        return self._model.id

    @property
    def name(self) -> str:
        return self._model.name

    @property
    def archetype(self) -> str:
        return self._model.archetype

    @property
    def coordinates(self) -> AssetCoordinates:
        return self._coordinates

    @property
    def asset_type(self) -> str:
        return self._model.asset_type

    @property
    def properties(self) -> Dict[str, Any]:
        return self._model.properties or {}

    @property
    def geojson(self) -> Dict[str, Any]:
        return self._model.geojson

    @abstractmethod
    def get_bounds(self) -> Optional[AssetBounds]:
        """Get the bounding box for this asset."""
        pass

    @abstractmethod
    def contains_point(self, coordinates: AssetCoordinates) -> bool:
        """Check if this asset contains the given point."""
        pass

    @abstractmethod
    def get_area(self) -> Optional[float]:
        """Get the area of this asset (if applicable)."""
        pass

    def get_hazard_exposures(self, hazard_types: Optional[List[str]] = None,
                           scenario: str = 'current') -> List[HazardExposureData]:
        """Get hazard exposure data for this asset."""
        exposures = []

        results_query = self._model.hazard_results.filter(scenario=scenario)
        if hazard_types:
            results_query = results_query.filter(hazard_type__in=hazard_types)

        for result in results_query:
            result_data = result.result_data
            exposures.append(HazardExposureData(
                hazard_type=result.hazard_type,
                severity=result_data.get('severity', 'unknown'),
                value=result_data.get('value', 0.0),
                confidence=result_data.get('confidence', 0.0),
                metadata=result_data.get('metadata', {})
            ))

        return exposures

    def has_granular_analysis(self) -> bool:
        """Check if this asset has granular analysis data."""
        return self._model.has_granular_analysis

    def get_analysis_status(self) -> str:
        """Get the current analysis status."""
        return self._model.granular_analysis_status

    def to_visualization_data(self, hazard_types: Optional[List[str]] = None,
                            scenario: str = 'current') -> AssetVisualizationData:
        """Convert to visualization data format."""
        return AssetVisualizationData(
            id=self.id,
            name=self.name,
            asset_type=self.asset_type,
            coordinates=self.coordinates,
            bounds=self.get_bounds(),
            geojson=self.geojson,
            hazard_exposures=self.get_hazard_exposures(hazard_types, scenario),
            properties=self.properties,
            has_granular_data=self.has_granular_analysis(),
            analysis_status=self.get_analysis_status()
        )


class PointAsset(BaseAsset):
    """Point-based asset implementation."""

    def __init__(self, asset_model: Asset):
        if asset_model.asset_type != AssetType.POINT:
            raise ValueError("Asset model must be of type 'point'")
        super().__init__(asset_model)

    def get_bounds(self) -> Optional[AssetBounds]:
        """Point assets have minimal bounds around the point."""
        # Create a small buffer around the point (approximately 100m)
        buffer_degrees = 0.001  # Roughly 100m at most latitudes
        return AssetBounds(
            min_lat=self.coordinates.latitude - buffer_degrees,
            max_lat=self.coordinates.latitude + buffer_degrees,
            min_lng=self.coordinates.longitude - buffer_degrees,
            max_lng=self.coordinates.longitude + buffer_degrees
        )

    def contains_point(self, coordinates: AssetCoordinates) -> bool:
        """Check if point is within the small buffer around this point."""
        bounds = self.get_bounds()
        return bounds.contains(coordinates) if bounds else False

    def get_area(self) -> Optional[float]:
        """Point assets have no area."""
        return 0.0

    def distance_to_km(self, other_asset: BaseAsset) -> float:
        """Calculate distance to another asset in kilometers using Haversine formula."""
        from math import radians, cos, sin, asin, sqrt

        lat1, lng1 = self.coordinates.as_tuple()
        lat2, lng2 = other_asset.coordinates.as_tuple()

        # Convert to radians
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])

        # Haversine formula
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Earth's radius in kilometers

        return c * r


class PolygonAsset(BaseAsset):
    """Polygon-based asset implementation."""

    def __init__(self, asset_model: Asset):
        if asset_model.asset_type != AssetType.POLYGON:
            raise ValueError("Asset model must be of type 'polygon'")
        if not asset_model.polygon_geometry:
            raise ValueError("Polygon asset must have geometry data")
        super().__init__(asset_model)

    @property
    def polygon_geometry(self) -> Dict[str, Any]:
        return self._model.polygon_geometry

    def _get_polygon_coordinates(self) -> List[Tuple[float, float]]:
        """Get polygon coordinates as list of (longitude, latitude) tuples."""
        coords = self.polygon_geometry['coordinates'][0]  # Exterior ring
        return [(lng, lat) for lng, lat in coords]

    def get_bounds(self) -> Optional[AssetBounds]:
        """Get the bounding box of the polygon."""
        if not self.polygon_geometry:
            return None

        coords = self.polygon_geometry['coordinates'][0]
        lngs = [point[0] for point in coords]
        lats = [point[1] for point in coords]

        return AssetBounds(
            min_lat=min(lats),
            max_lat=max(lats),
            min_lng=min(lngs),
            max_lng=max(lngs)
        )

    def contains_point(self, coordinates: AssetCoordinates) -> bool:
        """Check if the polygon contains the given point using ray casting algorithm."""
        try:
            if not self.polygon_geometry:
                return False

            x, y = coordinates.longitude, coordinates.latitude
            coords = self._get_polygon_coordinates()

            # Ray casting algorithm
            n = len(coords) - 1  # Exclude closing point
            inside = False

            p1x, p1y = coords[0]
            for i in range(1, n + 1):
                p2x, p2y = coords[i % n]
                if y > min(p1y, p2y):
                    if y <= max(p1y, p2y):
                        if x <= max(p1x, p2x):
                            if p1y != p2y:
                                xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                            if p1x == p2x or x <= xinters:
                                inside = not inside
                p1x, p1y = p2x, p2y

            return inside
        except Exception as e:
            logger.error(f"Error checking point containment: {str(e)}")
            return False

    def get_area(self) -> Optional[float]:
        """Get the area of the polygon."""
        try:
            return self._model.get_polygon_area()
        except Exception as e:
            logger.error(f"Error calculating polygon area: {str(e)}")
            return None

    def get_centroid(self) -> AssetCoordinates:
        """Get the centroid of the polygon."""
        try:
            centroid_coords = self._model.calculate_polygon_centroid()
            if centroid_coords:
                return AssetCoordinates(
                    latitude=centroid_coords[1],
                    longitude=centroid_coords[0]
                )
            # Fall back to model coordinates
            return self.coordinates
        except Exception as e:
            logger.error(f"Error calculating centroid: {str(e)}")
            return self.coordinates

    def intersects_with(self, other_asset: BaseAsset) -> bool:
        """Check if this polygon intersects with another asset."""
        if other_asset.asset_type == AssetType.POINT:
            return self.contains_point(other_asset.coordinates)
        elif other_asset.asset_type == AssetType.POLYGON:
            try:
                # Check if any vertex of this polygon is inside the other polygon
                coords1 = self._get_polygon_coordinates()
                for coord in coords1[:-1]:  # Exclude closing point
                    test_point = AssetCoordinates(latitude=coord[1], longitude=coord[0])
                    if other_asset.contains_point(test_point):
                        return True

                # Check if any vertex of other polygon is inside this polygon
                coords2 = other_asset._get_polygon_coordinates()
                for coord in coords2[:-1]:  # Exclude closing point
                    test_point = AssetCoordinates(latitude=coord[1], longitude=coord[0])
                    if self.contains_point(test_point):
                        return True

                # Simple bounding box intersection check
                bounds1 = self.get_bounds()
                bounds2 = other_asset.get_bounds()
                if bounds1 and bounds2:
                    return not (bounds1.max_lat < bounds2.min_lat or
                               bounds1.min_lat > bounds2.max_lat or
                               bounds1.max_lng < bounds2.min_lng or
                               bounds1.min_lng > bounds2.max_lng)

                return False
            except Exception as e:
                logger.error(f"Error checking polygon intersection: {str(e)}")
                return False
        return False


class AssetFactory:
    """Factory class for creating asset objects."""

    @staticmethod
    def create_asset(asset_model: Asset) -> BaseAsset:
        """Create appropriate asset object based on model type."""
        if asset_model.asset_type == AssetType.POINT:
            return PointAsset(asset_model)
        elif asset_model.asset_type == AssetType.POLYGON:
            return PolygonAsset(asset_model)
        else:
            raise ValueError(f"Unknown asset type: {asset_model.asset_type}")

    @staticmethod
    def create_point_asset(name: str, latitude: float, longitude: float,
                         archetype: str = 'default archetype',
                         properties: Optional[Dict[str, Any]] = None) -> PointAsset:
        """Create a new point asset."""
        model = AssetService.create_point_asset(name, latitude, longitude, archetype, properties)
        return PointAsset(model)

    @staticmethod
    def create_polygon_asset(name: str, polygon_geometry: Dict[str, Any],
                           archetype: str = 'default archetype',
                           properties: Optional[Dict[str, Any]] = None) -> PolygonAsset:
        """Create a new polygon asset."""
        model = AssetService.create_polygon_asset(name, polygon_geometry, archetype, properties)
        return PolygonAsset(model)


class AssetCollection:
    """Collection class for managing multiple assets."""

    def __init__(self, assets: Optional[List[BaseAsset]] = None):
        self._assets = assets or []

    def add_asset(self, asset: BaseAsset) -> None:
        """Add an asset to the collection."""
        self._assets.append(asset)

    def remove_asset(self, asset_id: int) -> bool:
        """Remove an asset by ID."""
        for i, asset in enumerate(self._assets):
            if asset.id == asset_id:
                del self._assets[i]
                return True
        return False

    def get_asset(self, asset_id: int) -> Optional[BaseAsset]:
        """Get an asset by ID."""
        for asset in self._assets:
            if asset.id == asset_id:
                return asset
        return None

    def filter_by_type(self, asset_type: str) -> 'AssetCollection':
        """Filter assets by type."""
        filtered = [asset for asset in self._assets if asset.asset_type == asset_type]
        return AssetCollection(filtered)

    def filter_by_bounds(self, bounds: AssetBounds) -> 'AssetCollection':
        """Filter assets within given bounds."""
        filtered = []
        for asset in self._assets:
            asset_bounds = asset.get_bounds()
            if asset_bounds and self._bounds_overlap(bounds, asset_bounds):
                filtered.append(asset)
        return AssetCollection(filtered)

    def filter_by_hazard(self, hazard_types: List[str],
                        severity_threshold: Optional[str] = None,
                        scenario: str = 'current') -> 'AssetCollection':
        """Filter assets by hazard exposure."""
        filtered = []
        for asset in self._assets:
            exposures = asset.get_hazard_exposures(hazard_types, scenario)
            if not exposures:
                continue

            if severity_threshold:
                # Check if any exposure meets the threshold
                severity_levels = {'low': 1, 'medium': 2, 'high': 3, 'extreme': 4}
                threshold_level = severity_levels.get(severity_threshold.lower(), 0)

                for exposure in exposures:
                    exposure_level = severity_levels.get(exposure.severity.lower(), 0)
                    if exposure_level >= threshold_level:
                        filtered.append(asset)
                        break
            else:
                filtered.append(asset)

        return AssetCollection(filtered)

    def find_nearby_assets(self, center: AssetCoordinates,
                          radius_km: float) -> 'AssetCollection':
        """Find assets within a given radius of a center point."""
        from math import radians, cos, sin, asin, sqrt

        def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            """Calculate distance between two points in kilometers."""
            R = 6371  # Earth radius in kilometers

            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1

            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            return R * c

        nearby = []
        for asset in self._assets:
            distance = haversine_distance(
                center.latitude, center.longitude,
                asset.coordinates.latitude, asset.coordinates.longitude
            )
            if distance <= radius_km:
                nearby.append(asset)

        return AssetCollection(nearby)

    def get_all_bounds(self) -> Optional[AssetBounds]:
        """Get bounds that encompass all assets in the collection."""
        if not self._assets:
            return None

        all_bounds = []
        for asset in self._assets:
            bounds = asset.get_bounds()
            if bounds:
                all_bounds.append(bounds)

        if not all_bounds:
            return None

        return AssetBounds(
            min_lat=min(bounds.min_lat for bounds in all_bounds),
            max_lat=max(bounds.max_lat for bounds in all_bounds),
            min_lng=min(bounds.min_lng for bounds in all_bounds),
            max_lng=max(bounds.max_lng for bounds in all_bounds)
        )

    def to_visualization_data(self, hazard_types: Optional[List[str]] = None,
                            scenario: str = 'current') -> List[AssetVisualizationData]:
        """Convert all assets to visualization data."""
        return [
            asset.to_visualization_data(hazard_types, scenario)
            for asset in self._assets
        ]

    def __len__(self) -> int:
        return len(self._assets)

    def __iter__(self):
        return iter(self._assets)

    def __getitem__(self, index):
        return self._assets[index]

    @staticmethod
    def _bounds_overlap(bounds1: AssetBounds, bounds2: AssetBounds) -> bool:
        """Check if two bounds overlap."""
        return not (bounds1.max_lat < bounds2.min_lat or
                   bounds1.min_lat > bounds2.max_lat or
                   bounds1.max_lng < bounds2.min_lng or
                   bounds1.min_lng > bounds2.max_lng)


class AssetRepository:
    """Repository class for asset data access using the abstraction layer."""

    @staticmethod
    def get_all_assets(asset_type: Optional[str] = None) -> AssetCollection:
        """Get all assets as a collection."""
        assets = AssetService.get_all_assets(asset_type)
        asset_objects = [AssetFactory.create_asset(model) for model in assets]
        return AssetCollection(asset_objects)

    @staticmethod
    def get_asset_by_id(asset_id: int) -> Optional[BaseAsset]:
        """Get a single asset by ID."""
        model = AssetService.get_asset_by_id(asset_id)
        if model:
            return AssetFactory.create_asset(model)
        return None

    @staticmethod
    def get_assets_within_bounds(min_lat: float, max_lat: float,
                               min_lng: float, max_lng: float,
                               asset_type: Optional[str] = None) -> AssetCollection:
        """Get assets within specified bounds."""
        bounds = AssetBounds(min_lat, max_lat, min_lng, max_lng)
        models = AssetService.get_assets_within_bounds(
            min_lat, max_lat, min_lng, max_lng, asset_type
        )
        asset_objects = [AssetFactory.create_asset(model) for model in models]
        collection = AssetCollection(asset_objects)
        return collection.filter_by_bounds(bounds)

    @staticmethod
    def create_asset(name: str, coordinates_or_geometry: Union[Tuple[float, float], Dict[str, Any]],
                    asset_type: str = AssetType.POINT, **kwargs) -> BaseAsset:
        """Create a new asset using the factory."""
        if asset_type == AssetType.POLYGON:
            return AssetFactory.create_polygon_asset(name, coordinates_or_geometry, **kwargs)
        else:
            lat, lng = coordinates_or_geometry
            return AssetFactory.create_point_asset(name, lat, lng, **kwargs)

    @staticmethod
    def delete_asset(asset_id: int) -> bool:
        """Delete an asset."""
        return AssetService.delete_asset(asset_id)

    @staticmethod
    def get_assets_for_visualization(hazard_types: Optional[List[str]] = None,
                                   bounds: Optional[AssetBounds] = None,
                                   scenario: str = 'current') -> List[Dict[str, Any]]:
        """Get assets formatted for visualization."""
        if bounds:
            collection = AssetRepository.get_assets_within_bounds(**bounds.as_dict())
        else:
            collection = AssetRepository.get_all_assets()

        if hazard_types:
            collection = collection.filter_by_hazard(hazard_types, scenario=scenario)

        viz_data = collection.to_visualization_data(hazard_types, scenario)
        return [data.to_leaflet_format() for data in viz_data]


# Convenience functions for backward compatibility
def get_asset_collection(asset_type: Optional[str] = None) -> AssetCollection:
    """Get all assets as a collection."""
    return AssetRepository.get_all_assets(asset_type)


def create_asset_from_data(name: str, asset_data: Dict[str, Any]) -> BaseAsset:
    """Create asset from data dictionary."""
    asset_type = asset_data.get('asset_type', AssetType.POINT)

    if asset_type == AssetType.POLYGON:
        polygon_geometry = asset_data.get('polygon_geometry')
        if not polygon_geometry:
            raise ValueError("Polygon geometry required for polygon assets")
        return AssetRepository.create_asset(
            name, polygon_geometry, asset_type,
            archetype=asset_data.get('archetype', 'default archetype'),
            properties=asset_data.get('properties', {})
        )
    else:
        lat = asset_data.get('latitude')
        lng = asset_data.get('longitude')
        if lat is None or lng is None:
            raise ValueError("Latitude and longitude required for point assets")
        return AssetRepository.create_asset(
            name, (float(lat), float(lng)), asset_type,
            archetype=asset_data.get('archetype', 'default archetype'),
            properties=asset_data.get('properties', {})
        )