from django.core.management.base import BaseCommand
from climate_hazards_analysis_v2.models import Asset, GranularAnalysisResult
from climate_hazards_analysis_v2.granular_utils import prepare_hierarchical_exposure_data


class Command(BaseCommand):
    help = 'Test the hierarchical polygon exposure data structure'

    def handle(self, *args, **options):
        self.stdout.write("Testing hierarchical polygon exposure data structure...")

        try:
            # Find a polygon asset with granular analysis
            asset = Asset.objects.filter(
                asset_type='polygon',
                has_granular_analysis=True
            ).first()

            if not asset:
                self.stdout.write(self.style.WARNING("No polygon assets with granular analysis found."))
                self.stdout.write("Creating a test asset...")

                # Create a test polygon asset
                asset = Asset.objects.create(
                    name='Test Polygon Asset',
                    archetype='test archetype',
                    latitude=40.7128,
                    longitude=-74.0060,
                    asset_type='polygon',
                    polygon_geometry={
                        'type': 'Polygon',
                        'coordinates': [[
                            [-74.01, 40.71],
                            [-74.00, 40.71],
                            [-74.00, 40.72],
                            [-74.01, 40.72],
                            [-74.01, 40.71]
                        ]]
                    },
                    has_granular_analysis=True,
                    granular_analysis_status='completed',
                    granular_grid_spacing=0.001,
                    granular_grid_points_count=4
                )

                # Create some test granular results
                hazards = ['Heat', 'Flood']
                grid_points = [
                    (40.710, -74.010, 0, 0),
                    (40.710, -74.000, 0, 1),
                    (40.720, -74.000, 1, 1),
                    (40.720, -74.010, 1, 0)
                ]

                for lat, lng, row, col in grid_points:
                    for hazard in hazards:
                        GranularAnalysisResult.objects.create(
                            asset=asset,
                            latitude=lat,
                            longitude=lng,
                            grid_row=row,
                            grid_col=col,
                            grid_spacing=0.001,
                            hazard_type=hazard,
                            scenario='current',
                            result_data={
                                'value': 25.5 + row * 5 + col * 2,
                                'risk_level': 'medium' if row == 0 else 'high',
                                'unit': 'celsius' if hazard == 'Heat' else 'meters'
                            },
                            processing_status='completed'
                        )

                selected_hazards = hazards
            else:
                # Get some sample hazards for this asset
                asset_hazards = GranularAnalysisResult.objects.filter(
                    asset=asset,
                    processing_status='completed'
                ).values_list('hazard_type', flat=True).distinct()
                selected_hazards = list(asset_hazards[:2])  # Test with first 2 hazards

            self.stdout.write(self.style.SUCCESS(f"Found asset: {asset.name}"))
            self.stdout.write(self.style.SUCCESS(f"Selected hazards: {selected_hazards}"))

            # Test the hierarchical data preparation
            result = prepare_hierarchical_exposure_data(asset, selected_hazards)

            if result.get('success'):
                self.stdout.write(self.style.SUCCESS("Hierarchical data preparation successful!"))
                self.stdout.write(self.style.SUCCESS(f"Total rows: {len(result['data'])}"))
                self.stdout.write(self.style.SUCCESS(f"Columns: {result['columns']}"))
                self.stdout.write(self.style.SUCCESS(f"Grid points count: {result['grid_points_count']}"))

                # Verify structure
                data = result['data']
                if len(data) > 0:
                    parent_row = data[0]
                    self.stdout.write(self.style.SUCCESS(f"Parent row: {parent_row['name']} (type: {parent_row['type']})"))
                    self.stdout.write(self.style.SUCCESS(f"Parent has children: {parent_row.get('children_count', 0)}"))

                    if len(data) > 1:
                        child_rows = data[1:]
                        self.stdout.write(self.style.SUCCESS(f"Number of child rows: {len(child_rows)}"))

                        # Check first child row structure
                        first_child = child_rows[0]
                        self.stdout.write(self.style.SUCCESS(f"First child: {first_child['name']}"))
                        self.stdout.write(self.style.SUCCESS(f"Child hazards: {list(first_child['hazards'].keys())}"))

                        # Verify hazard data structure
                        for hazard in selected_hazards:
                            if hazard in first_child['hazards']:
                                hazard_data = first_child['hazards'][hazard]
                                self.stdout.write(
                                    self.style.SUCCESS(f"{hazard} data - Value: {hazard_data.get('value')}, "
                                                     f"Risk: {hazard_data.get('risk_level')}")
                                )

                self.stdout.write(self.style.SUCCESS("\nHierarchical data structure test PASSED!"))
            else:
                self.stdout.write(self.style.ERROR(f"Hierarchical data preparation failed: {result.get('error')}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Test failed with error: {str(e)}"))
            import traceback
            self.stdout.write(traceback.format_exc())