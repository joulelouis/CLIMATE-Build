from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('climate_hazards_analysis_v2', '0005_asset_has_session_independent_analysis_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='asset',
            name='session_key',
            field=models.CharField(blank=True, help_text='Session key used for upload/creation', max_length=255, null=True),
        ),
    ]
