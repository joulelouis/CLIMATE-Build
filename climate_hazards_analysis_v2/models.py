from django.db import models
import json
from decimal import Decimal

class Asset(models.Model):
    """
    Model for storing both point-based facilities and polygon-based assets
    for climate hazards analysis.
    """
    name = models.CharField(max_length=255)
    archetype = models.CharField(max_length=255, default='default archetype')

    # Point location (for backward compatibility and as centroid for polygons)
    latitude = models.DecimalField(max_digits=10, decimal_places=6)
    longitude = models.DecimalField(max_digits=10, decimal_places=6)

    # Polygon geometry (optional - for polygon-based assets)
    # Stored as JSON for better compatibility
    polygon_geometry = models.JSONField(null=True, blank=True)

    # Asset type classification
    asset_type = models.CharField(
        max_length=20,
        choices=[
            ('point', 'Point Facility'),
            ('polygon', 'Polygon Asset'),
        ],
        default='point'
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    session_key = models.CharField(max_length=255, null=True, blank=True)

    # Additional properties stored as JSON
    properties = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['session_key']),
            models.Index(fields=['asset_type']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_asset_type_display()})"

    def save(self, *args, **kwargs):
        # Auto-detect asset type based on polygon geometry
        if self.polygon_geometry:
            self.asset_type = 'polygon'
            # Auto-update centroid from polygon centroid if not provided
            if not self.latitude or not self.longitude:
                centroid = self.calculate_polygon_centroid()
                if centroid:
                    self.latitude = Decimal(str(centroid[1]))
                    self.longitude = Decimal(str(centroid[0]))
        else:
            self.asset_type = 'point'
        super().save(*args, **kwargs)

    @property
    def coordinates(self):
        """Return coordinates as tuple (lat, lng)"""
        return (float(self.latitude), float(self.longitude))

    @property
    def geojson(self):
        """Return GeoJSON representation of the asset"""
        if self.asset_type == 'polygon' and self.polygon_geometry:
            return {
                'type': 'Feature',
                'geometry': self.polygon_geometry,
                'properties': {
                    'name': self.name,
                    'archetype': self.archetype,
                    'asset_type': self.asset_type,
                    'id': self.id
                }
            }
        else:
            return {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [float(self.longitude), float(self.latitude)]
                },
                'properties': {
                    'name': self.name,
                    'archetype': self.archetype,
                    'asset_type': self.asset_type,
                    'id': self.id
                }
            }

    def get_polygon_coordinates(self):
        """Return polygon coordinates in GeoJSON format"""
        return self.polygon_geometry

    def set_polygon_from_geojson(self, geojson_geometry):
        """Set polygon geometry from GeoJSON geometry object"""
        if geojson_geometry.get('type') == 'Polygon':
            self.polygon_geometry = geojson_geometry
            return True
        return False

    def calculate_polygon_centroid(self):
        """Calculate approximate centroid of polygon coordinates"""
        if not self.polygon_geometry or self.polygon_geometry.get('type') != 'Polygon':
            return None

        try:
            coords = self.polygon_geometry['coordinates'][0]  # Exterior ring
            if len(coords) < 3:
                return None

            # Calculate simple average of all points (not true centroid but close enough for our use)
            sum_x = sum(point[0] for point in coords[:-1])  # Exclude closing point
            sum_y = sum(point[1] for point in coords[:-1])
            n = len(coords) - 1  # Exclude closing point

            return [sum_x / n, sum_y / n]
        except (KeyError, IndexError, ZeroDivisionError):
            return None

    def get_polygon_area(self):
        """Calculate approximate area of polygon (in degrees squared)"""
        if not self.polygon_geometry or self.polygon_geometry.get('type') != 'Polygon':
            return None

        try:
            coords = self.polygon_geometry['coordinates'][0]
            if len(coords) < 4:  # Need at least 3 points plus closing point
                return None

            # Simple shoelace formula for area calculation
            area = 0
            n = len(coords) - 1  # Exclude closing point
            for i in range(n):
                j = (i + 1) % n
                area += coords[i][0] * coords[j][1]
                area -= coords[j][0] * coords[i][1]
            return abs(area / 2)
        except (KeyError, IndexError):
            return None

class HazardAnalysisResult(models.Model):
    """
    Model for storing climate hazard analysis results for assets.
    """
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='hazard_results')
    hazard_type = models.CharField(max_length=50)
    scenario = models.CharField(max_length=50, default='current')
    result_data = models.JSONField(default=dict)
    analysis_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['asset', 'hazard_type', 'scenario']),
        ]
        unique_together = ['asset', 'hazard_type', 'scenario']

    def __str__(self):
        return f"{self.asset.name} - {self.hazard_type} ({self.scenario})"
