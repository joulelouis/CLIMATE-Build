from django.db import models
import json
from decimal import Decimal
from typing import List, Dict, Any, Optional

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

    # Owner/organization tracking (replaces session dependencies)
    owner = models.CharField(max_length=255, null=True, blank=True,
                            help_text="Asset owner or organization identifier")
    source = models.CharField(max_length=100, null=True, blank=True,
                             help_text="Source system or upload identifier")
    batch_id = models.CharField(max_length=100, null=True, blank=True,
                               help_text="Batch identifier for bulk operations")

    # Additional properties stored as JSON
    properties = models.JSONField(default=dict, blank=True)

    # Granular analysis metadata
    has_granular_analysis = models.BooleanField(default=False)
    granular_grid_spacing = models.FloatField(null=True, blank=True)  # Grid spacing in degrees
    granular_analysis_status = models.CharField(
        max_length=20,
        choices=[
            ('none', 'No Granular Analysis'),
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='none'
    )
    granular_grid_points_count = models.IntegerField(default=0)  # Number of grid points processed
    granular_analysis_progress = models.FloatField(default=0.0)  # Progress 0-100%

    # Analysis workflow tracking
    last_analysis_date = models.DateTimeField(null=True, blank=True)
    analysis_version = models.CharField(max_length=20, default='v1.0')

    # Workflow state tracking
    workflow_state = models.CharField(
        max_length=20,
        choices=[
            ('uploaded', 'Data Uploaded'),
            ('hazards_selected', 'Hazards Selected'),
            ('analysis_complete', 'Analysis Complete'),
            ('overrides_applied', 'Overrides Applied'),
            ('finalized', 'Finalized'),
        ],
        default='uploaded',
        help_text="Current state in the analysis workflow"
    )

    # Session independence - allows overrides without session
    has_session_independent_analysis = models.BooleanField(
        default=False,
        help_text="Whether this asset has analysis results that can be overridden without session"
    )
    last_analysis_session_key = models.CharField(
        max_length=255, null=True, blank=True,
        help_text="Last session key that performed analysis on this asset"
    )
    session_key = models.CharField(max_length=255, null=True, blank=True,
                                   help_text="Session key used for upload/creation")

    # Quality and validation flags
    is_validated = models.BooleanField(default=False)
    validation_errors = models.JSONField(default=list, blank=True)
    quality_score = models.FloatField(null=True, blank=True,
                                    help_text="Overall data quality score 0-100")

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['asset_type']),
            models.Index(fields=['owner']),
            models.Index(fields=['source']),
            models.Index(fields=['batch_id']),
            models.Index(fields=['granular_analysis_status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['last_analysis_date']),
            models.Index(fields=['is_validated']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quality_score__isnull=True) | models.Q(quality_score__gte=0, quality_score__lte=100),
                name='valid_quality_score'
            ),
            models.CheckConstraint(
                check=models.Q(granular_analysis_progress__gte=0, granular_analysis_progress__lte=100),
                name='valid_progress_percentage'
            ),
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

    def update_analysis_status(self, status: str, progress: Optional[float] = None,
                             last_analysis_date: Optional[bool] = True):
        """
        Update granular analysis status and related fields.

        Args:
            status: New analysis status
            progress: Progress percentage (0-100)
            last_analysis_date: Whether to update last_analysis_date
        """
        self.granular_analysis_status = status
        if progress is not None:
            self.granular_analysis_progress = max(0, min(100, progress))
        if last_analysis_date:
            from django.utils import timezone
            self.last_analysis_date = timezone.now()
        self.save()

    def validate_asset(self) -> List[str]:
        """
        Validate asset data and return any errors.

        Returns:
            List of validation error messages
        """
        errors = []

        # Basic validation
        if not self.name or not self.name.strip():
            errors.append("Asset name is required")

        if self.asset_type == 'point':
            if not self.latitude or not self.longitude:
                errors.append("Point assets require both latitude and longitude")
            else:
                # Validate coordinate ranges
                if not (-90 <= float(self.latitude) <= 90):
                    errors.append("Latitude must be between -90 and 90")
                if not (-180 <= float(self.longitude) <= 180):
                    errors.append("Longitude must be between -180 and 180")

        elif self.asset_type == 'polygon':
            if not self.polygon_geometry:
                errors.append("Polygon assets require polygon geometry")
            else:
                # Validate GeoJSON structure
                if self.polygon_geometry.get('type') != 'Polygon':
                    errors.append("Invalid polygon geometry type")
                elif not self.polygon_geometry.get('coordinates'):
                    errors.append("Polygon coordinates are required")

        # Update validation status
        if errors:
            self.validation_errors = errors
            self.is_validated = False
        else:
            self.validation_errors = []
            self.is_validated = True

        self.save()
        return errors

    def calculate_quality_score(self) -> float:
        """
        Calculate data quality score for this asset.

        Returns:
            Quality score between 0 and 100
        """
        score = 0.0

        # Basic completeness (30 points)
        if self.name and self.name.strip():
            score += 10
        if self.archetype and self.archetype != 'default archetype':
            score += 10
        if self.properties:
            score += 10

        # Coordinate quality (40 points)
        if self.asset_type == 'point':
            if self.latitude and self.longitude:
                score += 20  # Coordinates present
                # Additional points for coordinate precision
                lat_prec = len(str(self.latitude).split('.')[-1].rstrip('0')) if '.' in str(self.latitude) else 0
                lng_prec = len(str(self.longitude).split('.')[-1].rstrip('0')) if '.' in str(self.longitude) else 0
                if lat_prec >= 6 and lng_prec >= 6:
                    score += 20  # High precision coordinates
                elif lat_prec >= 4 and lng_prec >= 4:
                    score += 10  # Medium precision

        elif self.asset_type == 'polygon':
            if self.polygon_geometry:
                score += 20  # Geometry present
                # Additional points for geometry complexity
                coords = self.polygon_geometry.get('coordinates', [[]])[0]
                if len(coords) > 10:
                    score += 20  # Complex polygon
                elif len(coords) > 4:
                    score += 10  # Simple polygon

        # Analysis completeness (30 points)
        if self.last_analysis_date:
            score += 10
        if self.granular_analysis_status == 'completed':
            score += 20
        elif self.granular_analysis_status in ['processing', 'pending']:
            score += 10

        self.quality_score = score
        self.save()
        return score

    def get_analysis_summary(self) -> Dict[str, Any]:
        """
        Get summary of analysis results for this asset.

        Returns:
            Dictionary with analysis summary
        """
        summary = {
            'asset_id': self.id,
            'asset_name': self.name,
            'asset_type': self.asset_type,
            'analysis_status': self.granular_analysis_status,
            'last_analysis': self.last_analysis_date.isoformat() if self.last_analysis_date else None,
            'hazard_types': [],
            'granular_data_available': self.has_granular_analysis,
            'grid_points_processed': self.granular_grid_points_count,
            'quality_score': self.quality_score,
            'is_validated': self.is_validated
        }

        # Get hazard types from analysis results
        hazard_types = self.hazard_results.values_list('hazard_type', flat=True).distinct()
        summary['hazard_types'] = list(hazard_types)

        return summary

    @classmethod
    def get_by_owner(cls, owner: str) -> 'QuerySet[Asset]':
        """Get assets by owner."""
        return cls.objects.filter(owner=owner)

    @classmethod
    def get_by_source(cls, source: str) -> 'QuerySet[Asset]':
        """Get assets by source."""
        return cls.objects.filter(source=source)

    @classmethod
    def get_by_batch(cls, batch_id: str) -> 'QuerySet[Asset]':
        """Get assets by batch ID."""
        return cls.objects.filter(batch_id=batch_id)

    @classmethod
    def get_assets_requiring_validation(cls) -> 'QuerySet[Asset]':
        """Get assets that have not been validated."""
        return cls.objects.filter(is_validated=False)

    @classmethod
    def get_assets_with_analysis(cls) -> 'QuerySet[Asset]':
        """Get assets that have analysis results."""
        return cls.objects.filter(
            models.Q(has_granular_analysis=True) |
            models.Q(hazard_results__isnull=False)
        ).distinct()

    def clone(self, new_name: str, owner: Optional[str] = None) -> 'Asset':
        """
        Create a clone of this asset with a new name.

        Args:
            new_name: Name for the cloned asset
            owner: Optional new owner

        Returns:
            New Asset instance
        """
        clone_data = {
            'name': new_name,
            'archetype': self.archetype,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'polygon_geometry': self.polygon_geometry,
            'asset_type': self.asset_type,
            'properties': self.properties.copy(),
            'owner': owner or self.owner,
            'source': self.source,
            'quality_score': None,  # Will be recalculated
            'is_validated': False,  # Will need revalidation
        }

        new_asset = Asset.objects.create(**clone_data)
        return new_asset

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


class GranularAnalysisResult(models.Model):
    """
    Model for storing granular grid point analysis results for polygon assets.
    Each grid point within a polygon has its own hazard analysis results.
    """
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='granular_results')
    # Grid point location
    latitude = models.DecimalField(max_digits=10, decimal_places=6)
    longitude = models.DecimalField(max_digits=10, decimal_places=6)
    # Grid metadata
    grid_row = models.IntegerField()  # Row index in the grid
    grid_col = models.IntegerField()  # Column index in the grid
    grid_spacing = models.FloatField()  # Spacing in degrees (or meters if projected)

    # Analysis results for this grid point
    hazard_type = models.CharField(max_length=50)
    scenario = models.CharField(max_length=50, default='current')
    result_data = models.JSONField(default=dict)

    # Analysis metadata
    analysis_date = models.DateTimeField(auto_now_add=True)
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['asset', 'hazard_type', 'scenario']),
            models.Index(fields=['asset', 'grid_row', 'grid_col']),
            models.Index(fields=['processing_status']),
            models.Index(fields=['latitude', 'longitude']),
        ]
        unique_together = ['asset', 'latitude', 'longitude', 'hazard_type', 'scenario']

    def __str__(self):
        return f"{self.asset.name} - Grid ({self.grid_row},{self.grid_col}) - {self.hazard_type}"

    @property
    def coordinates(self):
        """Return coordinates as tuple (lat, lng)"""
        return (float(self.latitude), float(self.longitude))


class HeatmapData(models.Model):
    """
    Model for storing pre-computed heatmap data for polygon assets.
    Used for efficient visualization of hazard exposure across polygon areas.
    """
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='heatmap_data')
    hazard_type = models.CharField(max_length=50)
    scenario = models.CharField(max_length=50, default='current')

    # Heatmap grid specifications
    grid_rows = models.IntegerField()
    grid_cols = models.IntegerField()
    grid_spacing = models.FloatField()

    # Bounding box for the heatmap
    min_lat = models.DecimalField(max_digits=10, decimal_places=6)
    max_lat = models.DecimalField(max_digits=10, decimal_places=6)
    min_lng = models.DecimalField(max_digits=10, decimal_places=6)
    max_lng = models.DecimalField(max_digits=10, decimal_places=6)

    # Heatmap values matrix (2D array stored as JSON)
    # Format: [[row1_val1, row1_val2, ...], [row2_val1, row2_val2, ...], ...]
    heatmap_values = models.JSONField(default=list)

    # Statistical summaries
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    mean_value = models.FloatField(null=True, blank=True)
    median_value = models.FloatField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )

    class Meta:
        indexes = [
            models.Index(fields=['asset', 'hazard_type', 'scenario']),
            models.Index(fields=['processing_status']),
            models.Index(fields=['hazard_type']),
        ]
        unique_together = ['asset', 'hazard_type', 'scenario']

    def __str__(self):
        return f"{self.asset.name} - Heatmap {self.hazard_type} ({self.scenario})"

    def get_heatmap_grid(self):
        """
        Return heatmap data as a 2D grid with coordinates.
        Returns list of dictionaries with lat, lng, and value for each grid point.
        """
        if not self.heatmap_values:
            return []

        grid_data = []
        lat_step = (float(self.max_lat) - float(self.min_lat)) / self.grid_rows
        lng_step = (float(self.max_lng) - float(self.min_lng)) / self.grid_cols

        for row_idx, row_values in enumerate(self.heatmap_values):
            for col_idx, value in enumerate(row_values):
                lat = float(self.min_lat) + (row_idx + 0.5) * lat_step
                lng = float(self.min_lng) + (col_idx + 0.5) * lng_step
                grid_data.append({
                    'lat': lat,
                    'lng': lng,
                    'value': value,
                    'row': row_idx,
                    'col': col_idx
                })

        return grid_data


class OverrideValue(models.Model):
    """
    Model for storing user override values for hazard analysis results.
    Provides database persistence for overrides, eliminating session dependency.
    """
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='overrides')

    # Override identification
    hazard_type = models.CharField(max_length=50, null=True, blank=True)
    column_name = models.CharField(max_length=255)

    # Override values
    original_value = models.TextField(null=True, blank=True)
    override_value = models.TextField()

    # Override metadata
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # User and session tracking
    user_identifier = models.CharField(max_length=255, null=True, blank=True,
                                     help_text="User session ID or identifier")
    session_key = models.CharField(max_length=255, null=True, blank=True,
                                  help_text="Session key for tracking")

    # Override status
    is_active = models.BooleanField(default=True,
                                   help_text="Whether this override is currently active")
    approval_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('auto_applied', 'Auto Applied'),
        ],
        default='auto_applied'
    )

    # Workflow context
    analysis_version = models.CharField(max_length=20, null=True, blank=True)
    scenario = models.CharField(max_length=50, default='current')

    class Meta:
        indexes = [
            models.Index(fields=['asset', 'column_name', 'is_active']),
            models.Index(fields=['asset', 'hazard_type']),
            models.Index(fields=['user_identifier']),
            models.Index(fields=['session_key']),
            models.Index(fields=['created_at']),
            models.Index(fields=['approval_status']),
        ]
        unique_together = ['asset', 'column_name', 'hazard_type', 'scenario', 'is_active']
        verbose_name = "Override Value"
        verbose_name_plural = "Override Values"

    def __str__(self):
        return f"{self.asset.name} - {self.column_name}: {self.override_value}"

    def apply_override(self, original_value):
        """
        Apply this override to a value.

        Args:
            original_value: The original analysis value

        Returns:
            The override value if active, otherwise the original value
        """
        if not self.is_active:
            return original_value
        return self.override_value

    def get_history(self):
        """
        Get override history for this asset and column.

        Returns:
            QuerySet of OverrideValue objects for this asset/column combination
        """
        return OverrideValue.objects.filter(
            asset=self.asset,
            column_name=self.column_name,
            hazard_type=self.hazard_type,
            scenario=self.scenario
        ).order_by('-created_at')

    @classmethod
    def get_active_override(cls, asset, column_name, hazard_type=None, scenario='current'):
        """
        Get the active override for a specific asset and column.

        Args:
            asset: Asset instance
            column_name: Name of the column to override
            hazard_type: Optional hazard type for specificity
            scenario: Analysis scenario

        Returns:
            OverrideValue instance or None
        """
        try:
            return cls.objects.get(
                asset=asset,
                column_name=column_name,
                hazard_type=hazard_type,
                scenario=scenario,
                is_active=True
            )
        except cls.DoesNotExist:
            return None

    @classmethod
    def create_or_update_override(cls, asset, column_name, override_value,
                                 original_value=None, reason=None, hazard_type=None,
                                 user_identifier=None, session_key=None, scenario='current'):
        """
        Create or update an override value.

        Args:
            asset: Asset instance
            column_name: Name of the column to override
            override_value: New override value
            original_value: Original analysis value
            reason: Reason for the override
            hazard_type: Optional hazard type
            user_identifier: User identifier
            session_key: Session key
            scenario: Analysis scenario

        Returns:
            OverrideValue instance
        """
        # Deactivate any existing active overrides for this column
        cls.objects.filter(
            asset=asset,
            column_name=column_name,
            hazard_type=hazard_type,
            scenario=scenario,
            is_active=True
        ).update(is_active=False)

        # Create new override
        return cls.objects.create(
            asset=asset,
            column_name=column_name,
            hazard_type=hazard_type,
            original_value=original_value,
            override_value=override_value,
            reason=reason,
            user_identifier=user_identifier,
            session_key=session_key,
            scenario=scenario
        )

    @classmethod
    def apply_overrides_to_data(cls, asset, data_dict, hazard_type=None, scenario='current'):
        """
        Apply all active overrides for an asset to a data dictionary.

        Args:
            asset: Asset instance
            data_dict: Dictionary of column_name -> value pairs
            hazard_type: Optional hazard type for specificity
            scenario: Analysis scenario

        Returns:
            Updated dictionary with overrides applied
        """
        active_overrides = cls.objects.filter(
            asset=asset,
            is_active=True,
            scenario=scenario
        )

        if hazard_type:
            active_overrides = active_overrides.filter(
                models.Q(hazard_type=hazard_type) | models.Q(hazard_type__isnull=True)
            )

        result = data_dict.copy()
        for override in active_overrides:
            if override.column_name in result:
                result[override.column_name] = override.apply_override(result[override.column_name])

        return result
