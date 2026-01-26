from django.db import models


class Asset(models.Model):
    GEOMETRY_HELP = "GeoJSON geometry or point coordinate payload for this asset."

    SOURCE_CHOICES = [
        ("upload", "Upload"),
        ("map_click", "Map Click"),
        ("draw_polygon", "Draw Polygon"),
        ("manual_point", "Manual Point"),
        ("manual_polygon", "Manual Polygon"),
        ("uploaded_file", "Uploaded File"),
        ("session_polygon_workflow", "Session Polygon Workflow"),
    ]
    ASSET_TYPE_CHOICES = [
        ("point", "Point"),
        ("polygon", "Polygon"),
        ("granular", "Granular Point"),
    ]
    GRANULAR_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    asset_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, db_column="asset_name")
    archetype = models.CharField(
        max_length=255,
        blank=True,
        default="default archetype",
        db_column="asset_archetype",
    )
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    geometry = models.JSONField(null=True, blank=True, help_text=GEOMETRY_HELP)
    polygon_geometry = models.JSONField(null=True, blank=True)
    asset_type = models.CharField(max_length=50, choices=ASSET_TYPE_CHOICES)
    source = models.CharField(max_length=255, null=True, blank=True)
    source_type = models.CharField(max_length=50, choices=SOURCE_CHOICES, blank=True, null=True)
    session_key = models.CharField(max_length=255, null=True, blank=True)
    properties = models.JSONField(null=True, blank=True)
    granular_analysis_enabled = models.BooleanField(default=False)
    has_granular_analysis = models.BooleanField(default=False)
    granular_analysis_status = models.CharField(
        max_length=50,
        choices=GRANULAR_STATUS_CHOICES,
        default="pending",
    )
    granular_grid_spacing = models.FloatField(null=True, blank=True)
    granular_analysis_progress = models.FloatField(default=0.0)
    granular_grid_points_count = models.IntegerField(default=0)
    has_session_independent_analysis = models.BooleanField(default=False)
    workflow_state = models.CharField(max_length=100, default="new")
    last_analysis_session_key = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def geojson(self):
        if self.polygon_geometry:
            return self.polygon_geometry
        if self.geometry:
            return self.geometry
        if self.latitude is not None and self.longitude is not None:
            return {"type": "Point", "coordinates": [self.longitude, self.latitude]}
        return None

    @property
    def id(self):
        return self.asset_id

    def get_polygon_coordinates(self):
        if isinstance(self.polygon_geometry, dict):
            return self.polygon_geometry.get("coordinates")
        return None

    def set_polygon_from_geojson(self, geojson):
        if not isinstance(geojson, dict):
            return False
        if geojson.get("type") not in {"Polygon", "MultiPolygon"}:
            return False
        self.polygon_geometry = geojson
        return True

    def __str__(self) -> str:
        return self.name

