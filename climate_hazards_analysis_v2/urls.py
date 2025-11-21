from django.urls import path
from .views import (
    view_map, get_facility_data, add_facility, select_hazards, show_results,
    generate_report, sensitivity_parameters, sensitivity_results, save_table_changes,
    reset_table_data, preview_uploaded_file, preview_enhanced_facilities, export_hazard_data_to_excel,
    clear_site_data, refresh_csrf_token, get_polygon_assets, create_polygon_asset,
    update_polygon_asset, delete_polygon_asset, get_asset_analysis_results,
    get_heat_exposure_map_data, HeatExposureMapView, HazardExposureMapView,
    get_hazard_exposure_map_data, draw_polygon_complete, granular_analysis_grid,
    create_polygon_asset_with_granular, get_heatmap_data, get_granular_analysis_status,
    clear_granular_workflow, get_granular_workflow_state,
    execute_complete_granular_workflow, get_workflow_results_table,
    select_hazards_streamlined, hazard_exposure_results_streamlined, load_granular_data,
    EnhancedHazardExposureMapView, remove_file, clear_all_files, get_uploaded_files
)
from .api_views import (
    assets_api, asset_detail_api, asset_analysis_api, granular_analysis_api,
    heatmap_data_api, visualization_data_api,
    AssetListCreateView, AssetDetailView, AssetAnalysisView, GranularAnalysisView,
    GranularAnalysisPointView, HeatmapDataView, AssetVisualizationView,
    AssetStatisticsView, save_hazard_selection_json, run_json_analysis,
    get_json_analysis_results
)

app_name = "climate_hazards_analysis_v2"

urlpatterns = [
    path('', view_map, name='view_map'),
    path('select-hazards/', select_hazards, name='select_hazards'),
    path('results/', show_results, name='show_results'),
    path('heat-exposure-map/', HeatExposureMapView.as_view(), name='heat_exposure_map'),
    path('hazard-exposure-map/', HazardExposureMapView.as_view(), name='hazard_exposure_map'),
    path('api/hazard-exposure-map/', get_hazard_exposure_map_data, name='get_hazard_exposure_map_data'),
    path('sensitivity-parameters/', sensitivity_parameters, name='sensitivity_parameters'),
    path('sensitivity-results/', sensitivity_results, name='sensitivity_results'),
    path('generate-report/', generate_report, name='generate_report'),
    path('api/facility-data/', get_facility_data, name='get_facility_data'),
    path('api/add-facility/', add_facility, name='add_facility'),
    path('api/polygon-assets/', get_polygon_assets, name='get_polygon_assets'),
    path('api/polygon-assets/create/', create_polygon_asset, name='create_polygon_asset'),
    path('api/polygon-assets/<int:asset_id>/', update_polygon_asset, name='update_polygon_asset'),
    path('api/polygon-assets/<int:asset_id>/delete/', delete_polygon_asset, name='delete_polygon_asset'),
    path('api/assets/<int:asset_id>/analysis/', get_asset_analysis_results, name='get_asset_analysis_results'),
    path('save-table-changes/', save_table_changes, name='save_table_changes'),
    path('reset-table-data/', reset_table_data, name='reset_table_data'),
    path('export-to-excel/', export_hazard_data_to_excel, name='export_to_excel'),
    path('clear-site-data/', clear_site_data, name='clear_site_data'),
    path('refresh-csrf-token/', refresh_csrf_token, name='refresh_csrf_token'),
    path('api/preview-uploaded-file/', preview_uploaded_file, name='preview_uploaded_file'),
    path('api/preview-enhanced-facilities/', preview_enhanced_facilities, name='preview_enhanced_facilities'),
    path('api/heat-exposure-map/', get_heat_exposure_map_data, name='get_heat_exposure_map_data'),

    # Granular analysis endpoints
    path('api/polygon/complete/', draw_polygon_complete, name='draw_polygon_complete'),
    path('api/granular/analysis/', granular_analysis_grid, name='granular_analysis_grid'),
    path('api/assets/polygon/create/granular/', create_polygon_asset_with_granular, name='create_polygon_asset_with_granular'),
    path('api/heatmap/data/<int:asset_id>/', get_heatmap_data, name='get_heatmap_data'),
    path('api/granular/status/<int:asset_id>/', get_granular_analysis_status, name='get_granular_analysis_status'),
    path('api/granular/workflow/clear/', clear_granular_workflow, name='clear_granular_workflow'),
    path('api/granular/workflow/state/', get_granular_workflow_state, name='get_granular_workflow_state'),

    
    # Complete granular analysis workflow endpoints
    path('api/granular/workflow/execute/', execute_complete_granular_workflow, name='execute_complete_granular_workflow'),
    path('api/granular/workflow/results/<int:asset_id>/', get_workflow_results_table, name='get_workflow_results_table'),

    # New Stateless API Endpoints
    # Core asset management
    path('api/v2/assets/', assets_api, name='assets_api'),
    path('api/v2/assets/<int:asset_id>/', asset_detail_api, name='asset_detail_api'),
    path('api/v2/assets/<int:asset_id>/analysis/', asset_analysis_api, name='asset_analysis_api'),

    # Granular analysis
    path('api/v2/assets/<int:asset_id>/granular/', granular_analysis_api, name='granular_analysis_api'),
    path('api/v2/assets/<int:asset_id>/granular/points/', GranularAnalysisPointView.as_view(), name='granular_analysis_points_api'),

    # Heatmap data
    path('api/v2/assets/<int:asset_id>/heatmap/', heatmap_data_api, name='heatmap_data_api'),
    path('api/v2/heatmap/<int:asset_id>/', HeatmapDataView.as_view(), name='heatmap_view_api'),

    # Visualization data (compatible with existing HazardLayerManager)
    path('api/v2/visualization/', visualization_data_api, name='visualization_data_api'),
    path('api/v2/visualization/data/', AssetVisualizationView.as_view(), name='asset_visualization_api'),

    # Statistics and system info
    path('api/v2/statistics/', AssetStatisticsView.as_view(), name='asset_statistics_api'),

    # JSON Workflow Endpoints
    path('api/v2/json/save-hazard-selection/', save_hazard_selection_json, name='save_hazard_selection_json'),
    path('api/v2/json/run-analysis/', run_json_analysis, name='run_json_analysis'),
    path('api/v2/json/get-results/', get_json_analysis_results, name='get_json_analysis_results'),

    # Class-based view alternatives
    path('api/v2/assets/cbv/', AssetListCreateView.as_view(), name='asset_list_create_cbv'),
    path('api/v2/assets/<int:asset_id>/cbv/', AssetDetailView.as_view(), name='asset_detail_cbv'),
    path('api/v2/assets/<int:asset_id>/analysis/cbv/', AssetAnalysisView.as_view(), name='asset_analysis_cbv'),
    path('api/v2/assets/<int:asset_id>/granular/cbv/', GranularAnalysisView.as_view(), name='granular_analysis_cbv'),

    # Streamlined workflow for draw polygon assets
    path('select-hazards-streamlined/', select_hazards_streamlined, name='select_hazards_streamlined'),
    path('hazard-exposure-results-streamlined/', hazard_exposure_results_streamlined, name='hazard_exposure_results_streamlined'),

    # Granular data loading
    path('api/granular-data/load/', load_granular_data, name='load_granular_data'),

    # Enhanced hazard exposure map
    path('enhanced-hazard-exposure-map/', EnhancedHazardExposureMapView.as_view(), name='enhanced_hazard_exposure_map'),

    # File management endpoints
    path('api/files/remove/', remove_file, name='remove_file'),
    path('api/files/clear/', clear_all_files, name='clear_all_files'),
    path('api/files/', get_uploaded_files, name='get_uploaded_files'),
]