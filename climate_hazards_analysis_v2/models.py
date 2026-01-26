from django.db import models


class HazardAnalysisResult(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    asset = models.ForeignKey(
        "climate_hazards_analysis.Asset",
        on_delete=models.CASCADE,
        related_name="hazard_results",
    )
    hazard_type = models.CharField(max_length=100)
    result_data = models.JSONField(null=True, blank=True)
    processing_status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class GranularAnalysisResult(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    asset = models.ForeignKey(
        "climate_hazards_analysis.Asset",
        on_delete=models.CASCADE,
        related_name="granular_results",
    )
    hazard_type = models.CharField(max_length=100)
    grid_row = models.IntegerField()
    grid_col = models.IntegerField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    result_data = models.JSONField(null=True, blank=True)
    processing_status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class HeatmapData(models.Model):
    asset = models.ForeignKey(
        "climate_hazards_analysis.Asset",
        on_delete=models.CASCADE,
        related_name="heatmap_data",
    )
    hazard_type = models.CharField(max_length=100)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OverrideValue(models.Model):
    asset = models.ForeignKey(
        "climate_hazards_analysis.Asset",
        on_delete=models.CASCADE,
        related_name="overrides",
    )
    column_name = models.CharField(max_length=255)
    override_value = models.TextField()
    original_value = models.TextField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    user_identifier = models.CharField(max_length=255, null=True, blank=True)
    session_key = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def create_or_update_override(
        cls,
        asset,
        column_name,
        override_value,
        original_value=None,
        reason=None,
        user_identifier=None,
        session_key=None,
    ):
        return cls.objects.update_or_create(
            asset=asset,
            column_name=column_name,
            defaults={
                "override_value": override_value,
                "original_value": original_value,
                "reason": reason,
                "user_identifier": user_identifier,
                "session_key": session_key,
            },
        )[0]

