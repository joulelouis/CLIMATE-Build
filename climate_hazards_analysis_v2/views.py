from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
import os
import uuid
from io import BytesIO
import pandas as pd
import geopandas as gpd
import json
from django.conf import settings
from pathlib import Path
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.utils.decorators import method_decorator
from django.middleware.csrf import get_token
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.core.exceptions import ValidationError
from .utils import standardize_facility_dataframe, load_cached_hazard_data, combine_facility_with_hazard_data, validate_shapefile
from .error_utils import handle_sensitivity_param_error
from .models import Asset, HazardAnalysisResult, GranularAnalysisResult, HeatmapData, OverrideValue
from .granular_analysis import generate_sample_grid, calculate_polygon_area_km2
from .granular_utils import (
    generate_grid_points_from_polygon, create_granular_analysis_results,
    calculate_granular_statistics, create_heatmap_data, get_granular_analysis_progress,
    calculate_polygon_bounding_box, is_point_in_polygon
)
from .session_utils import GranularAnalysisSessionManager
from .granular_workflow_service import (
    GranularAnalysisWorkflowService, execute_granular_analysis_workflow
)
import logging
import copy
import zipfile
import tempfile
import glob
from typing import List, Dict, Any, Optional
import mimetypes

# Import from climate_hazards_analysis module
from climate_hazards_analysis.utils.climate_hazards_analysis import generate_climate_hazards_analysis
from climate_hazards_analysis.utils.generate_report import generate_climate_hazards_report_pdf
from tropical_cyclone_analysis.utils.tropical_cyclone_analysis import generate_tropical_cyclone_analysis

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join(settings.BASE_DIR, 'climate_hazards_analysis_v2', 'static', 'input_files')
ALLOWED_UPLOAD_EXTENSIONS = {'.csv', '.xlsx', '.xls', '.zip', '.gpkg', '.shp'}
MAX_UPLOAD_TOTAL_BYTES = 5 * 1024 * 1024  # 5 MB across all uploaded files
MAX_PREVIEW_BYTES = 100_000  # cap preview responses


def _sanitize_upload_filename(filename: str) -> str:
    """Return a filesystem-safe name (no path segments, bounded length)."""
    base = os.path.basename(filename or '').strip()
    base = base.replace('\\', '_').replace('/', '_')
    if not base:
        raise ValueError("Invalid file name")
    if len(base) > 150:
        stem, ext = os.path.splitext(base)
        base = f"{stem[:100]}{ext}"
    return base


def _get_current_upload_usage(request) -> int:
    """Sum sizes of files tracked in session metadata."""
    uploaded_files = request.session.get('climate_hazards_v2_uploaded_files', {})
    return sum(int(meta.get('size', 0) or 0) for meta in uploaded_files.values())


def _enforce_upload_quota(request, incoming_bytes: int):
    """Raise if adding the incoming payload would exceed the 5 MB cap."""
    current = _get_current_upload_usage(request)
    if current + incoming_bytes > MAX_UPLOAD_TOTAL_BYTES:
        raise ValueError("Total upload size exceeds 5 MB limit across all files")


def _validate_zip_file(zip_ref: zipfile.ZipFile, current_usage: int):
    """Validate zip contents for traversal and size limits."""
    total_uncompressed = 0
    for info in zip_ref.infolist():
        member_path = Path(info.filename)
        if member_path.is_absolute() or '..' in member_path.parts:
            raise ValueError("Zip file contains unsafe paths")
        total_uncompressed += info.file_size
        if current_usage + total_uncompressed > MAX_UPLOAD_TOTAL_BYTES:
            raise ValueError("Uncompressed zip content exceeds 5 MB upload limit")


def _assert_within_upload_dir(file_path: str):
    """Ensure the resolved path stays inside the configured upload directory."""
    upload_root = Path(UPLOAD_DIR).resolve()
    resolved = Path(file_path).resolve()
    if not resolved.is_relative_to(upload_root):
        raise ValueError("Requested file is outside the upload directory")


def order_selected_hazards(selected_hazards):
    """
    Reorder selected hazards to match the desired display order.

    Args:
        selected_hazards (list): List of selected hazard names

    Returns:
        list: Reordered list of hazard names
    """
    desired_order = [
        'Flood',
        'Water Stress',
        'Sea Level Rise',
        'Tropical Cyclones',
        'Heat',
        'Storm Surge',
        'Rainfall-Induced Landslide'
    ]

    # Create ordered list maintaining only selected hazards
    ordered_hazards = []
    for hazard in desired_order:
        if hazard in selected_hazards:
            ordered_hazards.append(hazard)

    # Add any additional hazards not in our desired order at the end
    for hazard in selected_hazards:
        if hazard not in ordered_hazards:
            ordered_hazards.append(hazard)

    return ordered_hazards

def parse_numeric(value, default=0):
    """Convert POST parameter to int or float.

    Returns ``default`` if conversion fails.
    """
    try:
        float_val = float(value)
        return int(float_val) if float_val.is_integer() else float_val
    except (TypeError, ValueError):
        raise ValueError(f"Invalid numeric value: {value}")

def view_map(request):
    """
    Main view for the Climate Hazards Analysis V2 module that displays the map interface
    with upload functionality.
    """
    context = {
        'error': None,
        'success_message': None,
        'uploaded_file_name': request.session.get('climate_hazards_v2_uploaded_filename')
    }
    
    # If facility files have been uploaded through the form (support multiple files)
    if request.method == 'POST' and request.FILES.getlist('facility_csv'):
        files = request.FILES.getlist('facility_csv')
        total_new_facilities = 0
        try:
            for file in files:
                ext = os.path.splitext(file.name)[1].lower()

                # Guardrails: allowlist and size limit
                if ext not in ALLOWED_UPLOAD_EXTENSIONS:
                    raise ValueError(f"Unsupported file type '{ext or 'unknown'}'. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}")
                _enforce_upload_quota(request, int(file.size or 0))

                os.makedirs(UPLOAD_DIR, exist_ok=True)
                safe_name = _sanitize_upload_filename(file.name)
                file_path = os.path.join(UPLOAD_DIR, safe_name)

                # Check for duplicate file names (case-insensitive)
                uploaded_files = request.session.get('climate_hazards_v2_uploaded_files', {})
                for existing_file_id, existing_file_metadata in uploaded_files.items():
                    if existing_file_metadata.get('name', '').lower() == file.name.lower():
                        context['error'] = f"File '{file.name}' has already been uploaded. Please choose a different file."
                        return render(request, 'climate_hazards_analysis_v2/main.html', context)
                
                with open(file_path, 'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)
                
                # Process the uploaded file to get facility data
                if ext in ['.xls', '.xlsx']:
                    df = pd.read_excel(file_path)

                elif ext in ['.zip', '.gpkg', '.shp']:
                    # Initialize zip_file_count for zip files
                    zip_file_count = 0

                    if ext == '.zip':
                        with tempfile.TemporaryDirectory() as tmpdir:
                            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                                _validate_zip_file(zip_ref, _get_current_upload_usage(request) + int(file.size or 0))
                                zip_ref.extractall(tmpdir)
                                # Count actual files in zip for accurate record count
                                zip_file_count = len(zip_ref.namelist())

                            # Validate that required shapefile files are present
                            extracted_files = [f.lower() for f in os.listdir(tmpdir)]
                            shp_files = [f for f in extracted_files if f.endswith('.shp')]
                            shx_files = [f for f in extracted_files if f.endswith('.shx')]
                            dbf_files = [f for f in extracted_files if f.endswith('.dbf')]

                            if not shp_files:
                                raise ValueError('The shapefile(.zip) is missing the (.shp) file')
                            if not shx_files:
                                raise ValueError('The shapefile(.zip) is missing the (.shx) file')
                            if not dbf_files:
                                raise ValueError('The shapefile(.zip) is missing the (.dbf) file')

                            # Use the first .shp file found
                            shp_file = shp_files[0]
                            shp_path = os.path.join(tmpdir, shp_file)
                            gdf = gpd.read_file(shp_path)
                    elif ext == '.gpkg':
                        # Read GeoPackage file (reads first layer by default)
                        gdf = gpd.read_file(file_path)
                    elif ext == '.shp':
                        gdf = gpd.read_file(file_path)

                    # Validate geospatial file structure before processing
                    attribute_columns = validate_shapefile(gdf)
                    logger.info(f"Geospatial file attribute columns: {attribute_columns}")

                    gdf = gdf.to_crs('EPSG:4326')

                    # Enhanced centroid calculation with robust error handling
                    try:
                        geom_count = len(gdf)
                    except TypeError:
                        geom_count = 0
                    logger.info(f"[SHAPEFILE_DEBUG] Calculating centroids for {geom_count} geometries")

                    # Check for empty or invalid geometries before calculating centroids
                    invalid_geoms = gdf.geometry.isna() | gdf.geometry.is_empty
                    invalid_count = getattr(invalid_geoms, "sum", lambda: 0)()
                    try:
                        has_invalid = bool(invalid_count)
                    except Exception:
                        has_invalid = False
                    if has_invalid:
                        logger.warning(f"[SHAPEFILE_DEBUG] Found {invalid_count} empty/invalid geometries")
                        gdf = gdf[~invalid_geoms]
                        try:
                            remaining = len(gdf)
                        except Exception:
                            remaining = 'unknown'
                        logger.info(f"[SHAPEFILE_DEBUG] Removed invalid geometries, remaining: {remaining}")

                    # Calculate centroids with error handling
                    try:
                        gdf['Lat'] = gdf.geometry.centroid.y
                        gdf['Long'] = gdf.geometry.centroid.x
                    except Exception as e:
                        logger.error(f"[SHAPEFILE_DEBUG] Error calculating centroids: {e}")
                        # Fallback: use representative point instead of centroid
                        try:
                            gdf['Lat'] = gdf.geometry.representative_point().y
                            gdf['Long'] = gdf.geometry.representative_point().x
                            logger.info(f"[SHAPEFILE_DEBUG] Used representative points as fallback")
                        except Exception as e2:
                            logger.error(f"[SHAPEFILE_DEBUG] Error with representative points: {e2}")
                            raise ValueError(f"Failed to extract coordinates from shapefile: {e2}")

                    # Filter out any rows with NaN coordinates before creating DataFrame
                    try:
                        valid_coords = ~(gdf['Lat'].isna() | gdf['Long'].isna())
                        nan_count = (~valid_coords).sum()
                        if nan_count > 0:
                            logger.warning(f"[SHAPEFILE_DEBUG] Filtering out {nan_count} rows with NaN coordinates")
                            gdf = gdf[valid_coords]
                    except Exception:
                        pass

                    if hasattr(gdf, "empty") and not gdf.empty:
                        try:
                            logger.info(f"[SHAPEFILE_DEBUG] Final Lat range: {gdf['Lat'].min():.6f} to {gdf['Lat'].max():.6f}")
                            logger.info(f"[SHAPEFILE_DEBUG] Final Long range: {gdf['Long'].min():.6f} to {gdf['Long'].max():.6f}")
                        except Exception:
                            pass
                    else:
                        logger.error(f"[SHAPEFILE_DEBUG] ERROR: No valid coordinates found in shapefile!")
                        raise ValueError("No valid coordinates could be extracted from shapefile")

                    df = pd.DataFrame(gdf.drop(columns='geometry'))

                else:
                    df = pd.read_csv(file_path)

                # Standardize column names and validate data before saving
                df = standardize_facility_dataframe(df)

                # Store facility data in session for map display
                if ext in ['.zip', '.gpkg', '.shp']:
                    uploaded_facilities = []
                    for i, row in df.iterrows():
                        record = row.to_dict()
                        geom = gdf.geometry.iloc[i]
                        if getattr(geom, "geom_type", None) == 'MultiPoint':
                            record['geometry'] = geom.convex_hull.__geo_interface__
                        elif getattr(geom, "geom_type", None) in ['Polygon', 'MultiPolygon']:
                            record['geometry'] = geom.__geo_interface__

                        # Mark shapefile/geopackage records as polygon assets to prevent double counting
                        record['AssetType'] = 'polygon'

                        uploaded_facilities.append(record)
                else:
                    uploaded_facilities = df.to_dict(orient='records')

                # Debug: Log the uploaded facility data
                logger.info(f"Processed {len(uploaded_facilities)} facilities from file: {str(uploaded_facilities)[:200]}...")

                # Get existing drawn polygon assets (not from uploaded files)
                existing_facility_data = request.session.get('climate_hazards_v2_facility_data', [])
                drawn_polygon_assets = [f for f in existing_facility_data if f.get('source') == 'drawn_polygon']
                legacy_facilities = [
                    f for f in existing_facility_data
                    if f.get('source') != 'drawn_polygon' and not f.get('_file_id')
                ]
                logger.info(f"Found {len(drawn_polygon_assets)} drawn polygon assets in session")
                logger.info(f"Found {len(legacy_facilities)} legacy session facilities")

                # Combine drawn polygon assets with uploaded facilities for display/CSV
                combined_facility_data = legacy_facilities + drawn_polygon_assets + uploaded_facilities
                logger.info(f"Combined total: {len(combined_facility_data)} facilities")

                # Save facility data to CSV (creates standardized CSV file)
                csv_path = _save_facility_data_to_csv(request, combined_facility_data)

                # Generate unique file ID and track file in session
                file_id = str(uuid.uuid4())

                # Get file type from MIME type or extension
                file_type = mimetypes.guess_type(file.name)[0] or 'unknown'
                if file_type == 'unknown':
                    ext_for_type = os.path.splitext(file.name)[1].lower()
                    type_map = {
                        '.csv': 'text/csv',
                        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        '.xls': 'application/vnd.ms-excel',
                        '.shp': 'application/octet-stream',
                        '.zip': 'application/zip',
                        '.gpkg': 'application/geopackage+sqlite3'
                    }
                    file_type = type_map.get(ext_for_type, 'unknown')

                # Prepare file metadata
                file_metadata = {
                    'id': file_id,
                    'name': file.name,
                    'size': file.size,
                    'type': file_type,
                    'record_count': zip_file_count if ext == '.zip' else len(uploaded_facilities),
                    'upload_time': timezone.now().isoformat(),
                    'file_path': file_path,
                    'csv_path': csv_path,
                    'extension': ext,
                    'facility_data': uploaded_facilities  # Store facility data specific to this file
                }

                # Add file to session tracking (store facility_data per file)
                _add_file_to_session(request, file_id, file_metadata)

                # Update combined facility data and session CSV for compatibility
                _rebuild_combined_facility_data(request)

                # Store assets in database for JSON workflow (NEW)
                session_key = request.session.session_key or 'anonymous'
                created_asset_ids = _store_uploaded_assets_as_json(uploaded_facilities, file.name, file_id, session_key=session_key)

                # Log JSON workflow data to console
                from .json_console_simple import simple_json_console
                from .models import Asset
                created_assets = Asset.objects.filter(id__in=created_asset_ids) if created_asset_ids else []

                if created_asset_ids:
                    # Store asset IDs in session for JSON workflow access (accumulate unique IDs across uploads)
                    existing_asset_ids = request.session.get('climate_hazards_v2_uploaded_asset_ids', [])
                    updated_ids = list({*existing_asset_ids, *created_asset_ids})
                    request.session['climate_hazards_v2_uploaded_asset_ids'] = updated_ids
                    logger.info(f"Updated session with {len(updated_ids)} total asset IDs after upload (added {len(created_asset_ids)})")

                # Create unified JSON for all uploaded assets (after session IDs are updated)
                _create_unified_assets_json(request)

                # Get all uploaded assets for unified logging (now includes latest upload)
                all_uploaded_assets = _get_all_uploaded_assets_json(request)
                simple_json_console.log_upload_step(combined_facility_data, file_metadata, created_assets, all_uploaded_assets)

                # Store uploaded filename in session for display (backward compatibility)
                request.session['climate_hazards_v2_uploaded_filename'] = file.name
                request.session.modified = True

                total_new_facilities += len(uploaded_facilities)

            # Add success message to context (aggregate across files)
            combined_total = len(request.session.get('climate_hazards_v2_facility_data', []))
            context['success_message'] = f"Successfully loaded {total_new_facilities} facilities from {len(files)} file(s). Total in session: {combined_total}."
            
        except Exception as e:
            logger.exception(f"Error processing file: {str(e)}")
            context['error'] = f"Error processing file: {str(e)}"
    else:
        # Ensure facility data is properly initialized when page loads without file upload
        _rebuild_combined_facility_data(request)

    # Return the template with context
    return render(request, 'climate_hazards_analysis_v2/main.html', context)

def get_facility_data(request):
    """
    API endpoint to retrieve facility data for the map.
    Returns JSON with facility data including coordinates and available hazard data.
    Enhanced to include polygon assets from the database.
    """
    # Ensure facility data is up to date with the latest file structure
    _rebuild_combined_facility_data(request)

    # Get base facility data from session
    facility_data = request.session.get('climate_hazards_v2_facility_data', [])

    # Get polygon assets from database for current session
    try:
        session_key = request.session.session_key or 'anonymous'
        polygon_assets = Asset.objects.filter(
            asset_type='polygon',
            source=session_key
        ).order_by('-created_at')

        # Convert database assets to facility data format
        for asset in polygon_assets:
            facility_asset = {
                'Facility': asset.name,
                'Lat': float(asset.latitude),
                'Long': float(asset.longitude),
                'Archetype': asset.archetype,
                'AssetType': 'polygon',
                'AssetId': asset.id,
                'CreatedAt': asset.created_at.isoformat()
            }

            # Include polygon geometry
            polygon_coords = asset.get_polygon_coordinates()
            if polygon_coords:
                facility_asset['geometry'] = polygon_coords

            facility_data.append(facility_asset)

    except Exception as db_error:
        logger.warning(f"Error retrieving polygon assets from database: {str(db_error)}")
        # Continue with session data only

    if not facility_data:
        return JsonResponse({
            'facilities': []
        })

    try:
        # Load cached hazard data
        hazard_data = [
            load_cached_hazard_data('flood'),
            load_cached_hazard_data('water_stress'),
            load_cached_hazard_data('heat')
        ]

        # Combine facility data with hazard data
        enriched_facilities = combine_facility_with_hazard_data(facility_data, hazard_data)

        return JsonResponse({
            'facilities': enriched_facilities
        })
    except Exception as e:
        logger.exception(f"Error enriching facility data: {e}")
        return JsonResponse({
            'facilities': facility_data,
            'error': str(e)
        })
    

@require_GET
def preview_uploaded_file(request):
    """Return the most recently uploaded facility file for preview."""
    file_path = request.session.get('climate_hazards_v2_facility_csv_path')
    if not file_path or not os.path.exists(file_path):
        return JsonResponse({'error': 'No uploaded file found'}, status=404)

    try:
        with open(file_path, 'rb') as f:
            content = f.read(MAX_PREVIEW_BYTES)
    except (UnicodeDecodeError, ValueError, OSError):
        return JsonResponse({'error': 'Invalid or unreadable file'}, status=400)

    return HttpResponse(content, content_type='text/csv')


@require_GET
def preview_enhanced_facilities(request):
    """
    Enhanced preview endpoint that returns facility data with hierarchical structure
    including polygon assets and their granular analysis points.
    """
    try:
        # Get regular facility data from session
        facility_data = request.session.get('climate_hazards_v2_facility_data', [])

        # Initialize enhanced data structure
        enhanced_data = {
            'regular_facilities': [],
            'polygon_assets': [],
            'summary': {
                'total_facilities': 0,
                'total_polygons': 0,
                'total_granular_points': 0
            }
        }

        # Process regular facilities (point assets)
        for facility in facility_data:
            if facility.get('AssetType') != 'polygon':
                enhanced_data['regular_facilities'].append(facility)

        # Session-only approach: Get polygon assets from session facility_data
        polygon_assets = [f for f in facility_data if f.get('AssetType') == 'polygon' or f.get('geometry')]

        # Process polygon assets
        for asset in polygon_assets:
            polygon_data = {
                'id': asset.get('AssetId'),
                'name': asset['Facility'],
                'archetype': asset.get('Archetype', 'default archetype'),
                'latitude': float(asset['Lat']),
                'longitude': float(asset['Long']),
                'area_km2': asset.get('polygon_area_km2'),
                'has_granular_analysis': asset.get('granular_analysis_enabled', False),
                'granular_grid_spacing': asset.get('granular_grid_spacing'),
                'granular_points_count': asset.get('granular_points_count', 0),
                'created_at': None,  # Session assets don't have DB timestamps
                'granular_points': asset.get('granular-points', []),
                'centroid': {
                    'lat': float(asset['Lat']),
                    'lng': float(asset['Long'])
                }
            }

            # Calculate polygon area if geometry is available
            if asset.get('geometry'):
                try:
                    import json
                    from shapely.geometry import shape
                    geometry = shape(asset['geometry'])
                    # Convert from square meters to square kilometers
                    polygon_data['area_km2'] = geometry.area / 1000000
                except Exception as e:
                    logger.warning(f"Could not calculate area for asset {asset.get('AssetId')}: {e}")
                    polygon_data['area_km2'] = 0

            # Get granular points from session asset data
            if asset.get('granular_analysis_enabled') and asset.get('granular-points'):
                granular_points = asset['granular-points']
                if granular_points:
                    polygon_data['granular_points'] = granular_points
                    enhanced_data['summary']['total_granular_points'] += len(granular_points)

            enhanced_data['polygon_assets'].append(polygon_data)
            enhanced_data['summary']['total_polygons'] += 1

        # Update summary counts
        enhanced_data['summary']['total_facilities'] = len(enhanced_data['regular_facilities'])

        return JsonResponse({
            'success': True,
            'data': enhanced_data
        })

    except Exception as e:
        logger.exception(f"Error in enhanced facility preview: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to load enhanced facility preview'
        }, status=500)


# Test data injection endpoint for heat exposure map
@csrf_exempt
@require_http_methods(["GET"])
def inject_test_heat_data(request):
    """Inject test data for heat exposure map testing."""
    try:
        # Create test facilities with heat exposure data
        test_facilities = [
            {
                'Facility': 'Test Facility 1',
                'Lat': 14.5992,
                'Long': 120.9842,
                'Archetype': 'Commercial',
                'Heat Exposure (%)': 15.2,
                'geometry': None
            },
            {
                'Facility': 'Test Facility 2',
                'Lat': 14.5993,
                'Long': 120.9851,
                'Archetype': 'Industrial',
                'Heat Exposure (%)': 45.8,
                'geometry': None
            },
            {
                'Facility': 'Test Facility 3',
                'Lat': 14.5994,
                'Long': 120.9853,
                'Archetype': 'Residential',
                'Heat Exposure (%)': 85.3,
                'geometry': None
            }
        ]

        # Populate session with test data
        request.session['climate_hazards_v2_facility_data'] = test_facilities
        request.session['climate_hazards_v2_selected_hazards'] = ['Heat']

        logger.info(f"Test heat data injected: {len(test_facilities)} facilities")

        return JsonResponse({
            'success': True,
            'message': f'Test data injected successfully. {len(test_facilities)} facilities with heat exposure data.'
        })

    except Exception as e:
        logger.exception(f"Error injecting test heat data: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to inject test data'
        }, status=500)

@csrf_exempt
def add_facility(request):
    """
    API endpoint to add a new facility from coordinates clicked on the map.
    Supports both point-based facilities and polygon-based assets.
    Enhanced to save both to session and database.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lat = data.get('lat')
            lng = data.get('lng')
            name = data.get('name')
            archetype = data.get('archetype', 'default archetype')
            geometry = data.get('geometry')  # Polygon geometry if provided
            grid_spacing = data.get('gridSpacing')  # Grid spacing from frontend modal
            area_km2 = data.get('areaKm2')  # Polygon area from frontend

            # Basic validation
            if lat is None or lng is None:
                return JsonResponse({
                    'success': False,
                    'error': 'Latitude and longitude are required'
                }, status=400)

            try:
                lat_val = float(lat)
                lng_val = float(lng)
            except (TypeError, ValueError):
                return JsonResponse({
                    'success': False,
                    'error': 'Latitude and longitude must be numeric'
                }, status=400)

            if not (-90 <= lat_val <= 90 and -180 <= lng_val <= 180):
                return JsonResponse({
                    'success': False,
                    'error': 'Latitude/Longitude out of bounds'
                }, status=400)

            auto_named = False
            name_provided = 'name' in data
            name_clean = (name or '').strip() if name is not None else ''
            archetype_provided = 'archetype' in data

            # Reject explicitly provided empty names
            if name_provided and not name_clean:
                return JsonResponse({
                    'success': False,
                    'error': 'Name cannot be empty'
                }, status=400)

            # If archetype explicitly provided but name missing, require a name
            if archetype_provided and not name_provided:
                return JsonResponse({
                    'success': False,
                    'error': 'Name is required when archetype is provided'
                }, status=400)

            # Auto-generate a name if missing entirely
            if not name_clean:
                name_clean = f"New Facility at {lat_val:.4f}, {lng_val:.4f}"
                auto_named = True

            # Create database asset record (simplified)
            try:
                session_key = request.session.session_key or 'anonymous'
                asset = Asset(
                    name=name_clean,
                    archetype=archetype.strip() if archetype else 'default archetype',
                    latitude=lat_val,
                    longitude=lng_val,
                    source=session_key,
                    session_key=session_key
                )

                # Set polygon geometry if provided
                if geometry and asset.set_polygon_from_geojson(geometry):
                    pass  # Geometry set successfully

                # Store additional properties (area, grid spacing) in properties JSON field
                properties = {}
                if area_km2:
                    properties['area_km2'] = area_km2
                if grid_spacing:
                    properties['grid_spacing'] = grid_spacing
                if properties:
                    asset.properties = properties

                asset.save()

            except Exception:
                # Continue with session-based storage if database fails
                pass

            # Get existing facility data or initialize empty list
            facility_data = request.session.get('climate_hazards_v2_facility_data', [])

            # Add new facility with optional archetype and geometry
            new_facility = {
                'Facility': name_clean,
                'Lat': lat,
                'Long': lng,
                'Archetype': archetype,
                'source': 'drawn_polygon'  # treat as user-created to persist through rebuilds
            }

            # Add polygon geometry if provided
            if geometry:
                new_facility['geometry'] = geometry

                # Calculate area if not provided
                if area_km2 is None:
                    area_km2 = calculate_polygon_area_km2(geometry)

                new_facility['polygon_area_km2'] = area_km2

                # Store grid spacing for later hazard analysis
                if grid_spacing:
                    new_facility['grid_spacing_meters'] = grid_spacing

                logger.info(f"Polygon asset '{name}' created with area {area_km2:.2f} km². "
                          f"Hazard analysis will be performed in step 6 of the workflow.")

            facility_data.append(new_facility)

            # Update session
            request.session['climate_hazards_v2_facility_data'] = facility_data
            request.session.modified = True

            # Clear uploaded filename when adding drawn facilities
            if 'climate_hazards_v2_uploaded_filename' in request.session:
                del request.session['climate_hazards_v2_uploaded_filename']

            # Create/update CSV file from facility data
            try:
                _save_facility_data_to_csv(request, facility_data)
            except Exception:
                pass  # Continue even if CSV save fails

            return JsonResponse({
                'success': True,
                'facility': new_facility,
                'asset_id': asset.id if 'asset' in locals() else None,
                'message': f"New Facility at {lat_val:.4f}, {lng_val:.4f}" if auto_named else "Facility added successfully"
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data provided'
            }, status=400)
        except Exception as e:
            logger.exception(f"Error adding facility: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

    return JsonResponse({
        'success': False,
        'error': 'Only POST method is allowed'
    }, status=405)


def _save_facility_data_to_csv(request, facility_data):
    """
    Helper function to save facility data from session to a CSV file.
    This ensures compatibility with the analysis functions that expect a CSV file path.

    Note: Only saves regular point facilities (AssetType != 'polygon') for climate analysis.
    Polygon assets are handled separately via the unified CSV approach.
    """
    if not facility_data:
        return None

    # Include both point and polygon (using centroid) facilities; drop ones without coordinates
    regular_facilities = []
    for f in facility_data:
        if f.get('Lat') is None or f.get('Long') is None:
            continue
        regular_facilities.append(f)

    if not regular_facilities:
        logger.warning("No regular facilities found for CSV creation (only polygon assets detected)")
        return None

    # Generate a filename (use session key for uniqueness)
    csv_filename = f"facility_data_{request.session.session_key or 'default'}.csv"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    csv_path = os.path.join(UPLOAD_DIR, csv_filename)

    # Convert facility data to DataFrame (excluding geometry for CSV)
    df_data = []
    for facility in regular_facilities:
        row = {
            'Facility': facility.get('Facility'),
            'Lat': facility.get('Lat'),
            'Long': facility.get('Long'),
            'Archetype': facility.get('Archetype', 'default archetype')
        }
        df_data.append(row)

    df = pd.DataFrame(df_data)

    # Save to CSV
    df.to_csv(csv_path, index=False)

    # Update session with CSV path
    request.session['climate_hazards_v2_facility_csv_path'] = csv_path
    request.session.modified = True

    logger.info(f"Saved {len(regular_facilities)} regular facilities to CSV: {csv_path}")

    return csv_path

def select_hazards(request):
    """
    View for selecting climate/weather hazards for analysis.
    This is the second step in the climate hazard analysis workflow.
    """
    # Get facility data from session
    facility_data = request.session.get('climate_hazards_v2_facility_data', [])

    # Ensure CSV file exists for facility data (important for polygon/point-drawn assets)
    facility_csv_path = request.session.get('climate_hazards_v2_facility_csv_path')
    if facility_data and (not facility_csv_path or not os.path.exists(facility_csv_path)):
        logger.info("CSV file not found, creating from session data...")
        _save_facility_data_to_csv(request, facility_data)

    # Define available hazard types
    hazard_types = [
        'Flood',
        'Water Stress',
        'Heat',
        'Sea Level Rise',
        'Tropical Cyclones',
        'Storm Surge',
        'Rainfall Induced Landslide'
    ]

    # Count regular assets (excluding polygons)
    regular_assets_count = len([f for f in facility_data if f.get('AssetType') != 'polygon'])

    # Count polygon assets and granular points from session (session-only)
    polygon_assets_count = 0
    granular_points_count = 0

    # Get polygon assets from session facility_data
    polygon_assets = [f for f in facility_data if f.get('AssetType') == 'polygon' or f.get('geometry')]
    polygon_assets_count = len(polygon_assets)

    # Count granular points from session data
    for asset in polygon_assets:
        if asset.get('granular_analysis_enabled') and asset.get('granular-points'):
            granular_points = asset['granular-points']
            if granular_points:
                granular_points_count += len(granular_points)

    context = {
        'facility_count': regular_assets_count,
        'polygon_assets_count': polygon_assets_count,
        'granular_points_count': granular_points_count,
        'hazard_types': hazard_types,
        'selected_hazards': request.session.get('climate_hazards_v2_selected_hazards', []),
    }

    # Handle form submission
    if request.method == 'POST':
        selected_hazards = request.POST.getlist('hazards')
        ordered_hazards = order_selected_hazards(selected_hazards)
        request.session['climate_hazards_v2_selected_hazards'] = ordered_hazards

        # Store hazard selections in unified JSON
        _store_hazard_selections_in_unified_json(request, ordered_hazards)

        # Log JSON workflow data to console
        from .json_console_simple import simple_json_console
        asset_ids = request.session.get('climate_hazards_v2_uploaded_asset_ids', [])

        # Get unified assets for enhanced logging
        unified_assets = _get_all_uploaded_assets_json(request)

        parameters = {
            'source': 'hazard_selection_form',
            'total_hazards_available': len(hazard_types),
            'session_updated': True,
            'selected_hazards_count': len(ordered_hazards)
        }
        simple_json_console.log_hazard_selection_step(asset_ids, ordered_hazards, parameters, unified_assets)

        # Capture parent_facility information from form data
        parent_facilities = {}

        # Debug: Log all POST keys to understand the data structure
        logger.info(f"[DEBUG] All POST keys: {list(request.POST.keys())}")
        for key, value in request.POST.items():
            logger.info(f"[DEBUG] POST data: {key} = {value}")

        # Method 1: Look for parent_facility_* fields
        for key in request.POST:
            if key.startswith('parent_facility_'):
                facility_id = key.replace('parent_facility_', '')
                parent_facilities[facility_id] = request.POST[key]
                logger.info(f"Captured parent_facility mapping: {facility_id} -> {request.POST[key]}")

        # Method 2: Look for single parent_facility field
        if 'parent_facility' in request.POST:
            # If it's a single value, we need to map it to the correct archetype
            parent_facility_value = request.POST['parent_facility']
            logger.info(f"Found single parent_facility field: {parent_facility_value}")

            # We'll need to determine the archetype from the facility data
            # For now, store it as a default mapping
            parent_facilities['default'] = parent_facility_value
            parent_facilities['residential'] = parent_facility_value  # Default assumption

        # Store parent facility mappings in session for processing
        if parent_facilities:
            request.session['climate_hazards_v2_parent_facilities'] = parent_facilities
            request.session.modified = True
            logger.info(f"Stored {len(parent_facilities)} parent facility mappings in session")
            for fid, name in parent_facilities.items():
                logger.info(f"  - {fid} -> {name}")

        # Prepare unified asset inventory for processing
        asset_inventory = _prepare_unified_asset_inventory(facility_data, request)

        # Store asset inventory in session for processing in show_results
        request.session['climate_hazards_v2_asset_inventory'] = asset_inventory

        logger.info(f"Prepared unified asset inventory: {asset_inventory['summary']}")

        # Check if this is granular analysis workflow (for backward compatibility)
        granular_workflow = GranularAnalysisSessionManager.is_granular_workflow(request)
        polygon_asset_id = GranularAnalysisSessionManager.get_asset_id(request)

        if granular_workflow and polygon_asset_id:
            # For granular analysis, trigger the analysis processing
            try:
                asset = Asset.objects.get(id=polygon_asset_id)
                if asset.has_granular_analysis and asset.granular_analysis_status == 'pending':
                    from .granular_processor import process_asset_granular_analysis
                    processing_result = process_asset_granular_analysis(
                        asset.id, selected_hazards, scenario='current'
                    )

                    if processing_result.get('success'):
                        logger.info(f"Started granular analysis processing for asset {asset.name}")
                    else:
                        logger.error(f"Failed to start granular analysis: {processing_result.get('error')}")

                # Redirect to results page for granular assets
                return redirect('climate_hazards_analysis_v2:show_results')

            except Asset.DoesNotExist:
                logger.error(f"Polygon asset {polygon_asset_id} not found")
            except Exception as e:
                logger.exception(f"Error processing granular analysis: {str(e)}")

        # Redirect to results page for unified workflow
        return redirect('climate_hazards_analysis_v2:show_results')

    # For GET requests, just display the hazard selection form
    return render(request, 'climate_hazards_analysis_v2/select_hazards.html', context)


def _prepare_unified_asset_inventory(facility_data, request):
    """
    Prepare a unified inventory of all assets (regular facilities + polygon assets)
    for processing in the main workflow.

    Args:
        facility_data: List of facility data from session
        request: Django request object

    Returns:
        dict: Unified asset inventory with metadata
    """
    logger.info("Preparing unified asset inventory for mixed asset types")

    # Initialize inventory structure
    inventory = {
        'regular_facilities': [],
        'polygon_assets': [],
        'summary': {
            'total_regular_facilities': 0,
            'total_polygon_assets': 0,
            'total_granular_points': 0,
            'has_mixed_assets': False
        },
        'processing_plan': {
            'regular_facilities_count': 0,
            'polygon_assets_count': 0,
            'requires_hierarchical_display': False
        }
    }

    # Separate regular facilities from polygon assets
    logger.info(f"[DEBUG] Processing {len(facility_data)} facility records for asset inventory")
    for facility in facility_data:
        if facility.get('AssetType') == 'polygon' or facility.get('geometry'):
            # This is a polygon asset
            logger.info(f"[DEBUG] Found polygon asset: {facility.get('Facility', facility.get('Name', 'Unknown'))}")
            polygon_info = {
                'id': facility.get('id'),
                'name': facility.get('Facility', facility.get('Name', 'Unknown Polygon')),
                'archetype': facility.get('Archetype', 'default archetype'),
                'geometry': facility.get('geometry'),
                'asset_type': 'polygon',
                'granular_analysis_enabled': facility.get('granular_analysis_enabled', False),
                'granular_points': facility.get('granular-points', []),
                'centroid_lat': facility.get('Latitude'),
                'centroid_lng': facility.get('Longitude'),
                'properties': facility
            }
            inventory['polygon_assets'].append(polygon_info)

            # Count granular points
            if polygon_info['granular_analysis_enabled'] and polygon_info['granular_points']:
                inventory['summary']['total_granular_points'] += len(polygon_info['granular_points'])
                inventory['processing_plan']['requires_hierarchical_display'] = True

        else:
            # This is a regular facility
            regular_info = {
                'id': facility.get('id'),
                'name': facility.get('Facility', facility.get('Name', 'Unknown Facility')),
                'archetype': facility.get('Archetype', 'default archetype'),
                'latitude': facility.get('Latitude'),
                'longitude': facility.get('Longitude'),
                'asset_type': 'point',
                'properties': facility
            }
            inventory['regular_facilities'].append(regular_info)

    # Update summary counts
    inventory['summary']['total_regular_facilities'] = len(inventory['regular_facilities'])
    inventory['summary']['total_polygon_assets'] = len(inventory['polygon_assets'])
    inventory['summary']['has_mixed_assets'] = (
        inventory['summary']['total_regular_facilities'] > 0 and
        inventory['summary']['total_polygon_assets'] > 0
    )

    # Update processing plan
    inventory['processing_plan']['regular_facilities_count'] = inventory['summary']['total_regular_facilities']
    inventory['processing_plan']['polygon_assets_count'] = inventory['summary']['total_polygon_assets']

    logger.info(f"Asset inventory prepared: {inventory['summary']}")
    logger.info(f"[DEBUG] Final inventory - Regular facilities: {inventory['summary']['total_regular_facilities']}, "
                f"Polygon assets: {inventory['summary']['total_polygon_assets']}, "
                f"Has mixed assets: {inventory['summary']['has_mixed_assets']}")

    return inventory


def _validate_and_prepare_session_data(request):
    """
    Validate and prepare session data for climate hazard analysis.

    Returns:
        tuple: (facility_data, selected_hazards, facility_csv_path) or redirect response if validation fails
    """
    facility_data = request.session.get('climate_hazards_v2_facility_data', [])
    selected_hazards = request.session.get('climate_hazards_v2_selected_hazards', [])
    facility_csv_path = request.session.get('climate_hazards_v2_facility_csv_path')

    # Debug logging
    logger.info(f"[DEBUG] Session data validation:")
    logger.info(f"[DEBUG] facility_data count: {len(facility_data)}")
    logger.info(f"[DEBUG] selected_hazards: {selected_hazards}")
    logger.info(f"[DEBUG] facility_csv_path: {facility_csv_path}")
    logger.info(f"[DEBUG] Session keys: {list(request.session.keys())}")

    # Check if we have the necessary data
    if not facility_data or not selected_hazards:
        logger.warning(f"[DEBUG] Missing data - facility_data: {len(facility_data)}, selected_hazards: {len(selected_hazards) if selected_hazards else 0}")
        return None, None, None, redirect('climate_hazards_analysis_v2:select_hazards')

    logger.info(f"Starting results processing for {len(facility_data)} facilities")
    logger.info(f"Selected hazards: {selected_hazards}")

    return facility_data, selected_hazards, facility_csv_path, None


def _ensure_facility_csv_exists(request, facility_data, facility_csv_path, selected_hazards):
    """
    Ensure facility CSV file exists, create from session data if needed.

    Args:
        request: Django request object
        facility_data: Facility data from session
        facility_csv_path: Current CSV file path
        selected_hazards: List of selected hazards

    Returns:
        str: Valid CSV file path or None if failed
    """
    if facility_csv_path and os.path.exists(facility_csv_path):
        return facility_csv_path

    logger.warning(f"Facility CSV file not found: {facility_csv_path}, creating from session data...")

    if not facility_data:
        logger.error("No facility data in session")
        return None

    new_csv_path = _save_facility_data_to_csv(request, facility_data)
    if not new_csv_path or not os.path.exists(new_csv_path):
        logger.error("Failed to create CSV file from facility data")
        return None

    return new_csv_path


def _get_hazard_types():
    """
    Get the list of available hazard types.

    Returns:
        list: List of available hazard types
    """
    return [
        'Flood', 'Water Stress', 'Heat', 'Sea Level Rise',
        'Tropical Cyclones', 'Storm Surge', 'Rainfall Induced Landslide'
    ]


def _render_error_page(request, error_message, facility_data, selected_hazards):
    """
    Render error page with consistent context.

    Args:
        request: Django request object
        error_message: Error message to display
        facility_data: Facility data (for count)
        selected_hazards: Selected hazards list

    Returns:
        HttpResponse: Rendered error page
    """
    return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
        'error': error_message,
        'facility_count': len(facility_data) if facility_data else 0,
        'hazard_types': _get_hazard_types(),
        'selected_hazards': selected_hazards or []
    })


def _build_fallback_analysis_json(facility_data, selected_hazards, session_key=None):
    """
    Create a minimal JSON analysis output when the primary analysis pipeline fails.
    Ensures downstream JSON loader can render tables with uploaded facilities.
    """
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        safe_session = (session_key or 'anonymous').replace('/', '_')
        json_path = os.path.join(UPLOAD_DIR, f'fallback_analysis_{safe_session}.json')

        records = []
        hazard_columns = selected_hazards or _get_hazard_types()
        for fac in facility_data or []:
            record = dict(fac)
            for hazard in hazard_columns:
                if hazard not in record:
                    record[hazard] = 'Not calculated'
            records.append(record)

        payload = {
            "data": records,
            "metadata": {
                "source": "fallback",
                "total_facilities": len(records),
                "selected_hazards": hazard_columns
            }
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

        logger.warning(f"[FALLBACK_ANALYSIS] Generated fallback JSON at {json_path} with {len(records)} records")
        return json_path
    except Exception as e:
        logger.error(f"[FALLBACK_ANALYSIS] Failed to build fallback JSON: {e}")
        return None


def show_results(request):
    """
    View to display climate hazard analysis results.
    Updated to work with unified JSON processing for assets and hazards.
    """
    logger.info("SHOW_RESULTS function called - starting unified climate hazard analysis")

    # === PRIORITY: Check for Unified JSON Analysis (New Approach) ===
    unified_analysis_data = _get_unified_json_for_analysis(request)
    if unified_analysis_data:
        logger.info("Using unified JSON analysis workflow")
        return _handle_unified_json_analysis_results(request, unified_analysis_data)

    # Validate and prepare session data (legacy fallback)
    facility_data, selected_hazards, facility_csv_path, redirect_response = _validate_and_prepare_session_data(request)
    if redirect_response:
        return redirect_response

    try:
        logger.info(f"Facility CSV path: {facility_csv_path}")

        # Check for unified asset inventory (new approach) or legacy granular workflow
        asset_inventory = request.session.get('climate_hazards_v2_asset_inventory')
        granular_workflow = GranularAnalysisSessionManager.is_granular_workflow(request)
        polygon_asset_id = GranularAnalysisSessionManager.get_asset_id(request)

        # Debug logging for asset inventory detection
        if asset_inventory:
            logger.info(f"[DEBUG] Asset inventory found: {asset_inventory.get('summary', {})}")
            logger.info(f"[DEBUG] Has mixed assets: {asset_inventory.get('summary', {}).get('has_mixed_assets')}")
            logger.info(f"[DEBUG] Total polygon assets: {asset_inventory.get('summary', {}).get('total_polygon_assets', 0)}")
        else:
            logger.warning("[DEBUG] No asset inventory found in session")

        if asset_inventory and (
            asset_inventory.get('summary', {}).get('has_mixed_assets') or
            asset_inventory.get('summary', {}).get('total_polygon_assets', 0) > 0
        ):
            logger.info("Processing unified asset inventory with mixed asset types or polygon-only assets")
            return _handle_unified_mixed_assets_results(request, asset_inventory, selected_hazards, facility_data, facility_csv_path)

        elif granular_workflow and polygon_asset_id:
            logger.info(f"Processing legacy granular analysis results for polygon asset {polygon_asset_id}")
            return _handle_granular_polygon_results(request, polygon_asset_id, selected_hazards)

  
        # Verify facility CSV file exists, create if needed (for polygon/point-drawn assets)
        if not facility_csv_path or not os.path.exists(facility_csv_path):
            logger.warning(f"Facility CSV file not found: {facility_csv_path}, creating from session data...")
            if facility_data:
                facility_csv_path = _save_facility_data_to_csv(request, facility_data)
                if not facility_csv_path or not os.path.exists(facility_csv_path):
                    logger.error(f"Failed to create CSV file from facility data")
                    return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
                        'error': 'Failed to create facility data file. Please try uploading your data again.',
                        'facility_count': len(facility_data),
                        'hazard_types': [
                            'Flood', 'Water Stress', 'Heat', 'Sea Level Rise',
                            'Tropical Cyclones', 'Storm Surge', 'Rainfall Induced Landslide'
                        ],
                        'selected_hazards': selected_hazards
                    })
            else:
                logger.error(f"No facility data in session")
                return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
                    'error': 'Facility data not found. Please upload your facility data again.',
                    'facility_count': 0,
                    'hazard_types': [
                        'Flood', 'Water Stress', 'Heat', 'Sea Level Rise',
                        'Tropical Cyclones', 'Storm Surge', 'Rainfall Induced Landslide'
                    ],
                    'selected_hazards': selected_hazards
                })

        # ===== UNIFIED GRANULAR ANALYSIS APPROACH =====
        # Check if any facilities have sample points - if yes, create expanded CSV
        has_sample_points = any('sample_points' in fac for fac in facility_data)
        granular_facility_mapping = {}  # Maps original facility names to their sample point count

        if has_sample_points:
            logger.info("🔍 Detected facilities with sample points - creating expanded CSV for unified analysis")

            # Create expanded CSV with both centroids and sample points
            expanded_rows = []

            for facility in facility_data:
                facility_name = facility.get('Facility')
                lat = facility.get('Lat')
                lng = facility.get('Long')
                archetype = facility.get('Archetype', 'default archetype')

                # Debug logging for unified CSV creation
                logger.info(f"[UNIFIED_CSV_DEBUG] Processing facility: {facility_name}")
                logger.info(f"[UNIFIED_CSV_DEBUG] Coordinates - Lat: {lat}, Long: {lng}")
                logger.info(f"[UNIFIED_CSV_DEBUG] Coordinate types - Lat: {type(lat)}, Long: {type(lng)}")

                # Validate coordinates before adding to expanded rows
                if lat is not None and lng is not None and str(lat).strip() != '' and str(lng).strip() != '':
                    try:
                        # Convert to float to ensure they're numeric
                        lat_float = float(lat)
                        lng_float = float(lng)

                        # Check for reasonable coordinate ranges
                        if -90 <= lat_float <= 90 and -180 <= lng_float <= 180:
                            # Add the main facility row (centroid)
                            expanded_rows.append({
                                'Facility': facility_name,
                                'Lat': lat_float,
                                'Long': lng_float,
                                'Archetype': archetype
                            })
                        else:
                            logger.warning(f"[UNIFIED_CSV_DEBUG] Skipping facility {facility_name} with out-of-bounds coordinates: Lat={lat_float}, Long={lng_float}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"[UNIFIED_CSV_DEBUG] Skipping facility {facility_name} with invalid coordinates: Lat={lat}, Long={lng}, Error={e}")
                else:
                    logger.warning(f"[UNIFIED_CSV_DEBUG] Skipping facility {facility_name} with missing coordinates: Lat={lat}, Long={lng}")

                # If this facility has sample points, add them as separate rows
                if 'sample_points' in facility:
                    sample_points = facility['sample_points']
                    logger.info(f"Adding {len(sample_points)} sample points for {facility_name}")

                    # Track this facility for later result parsing
                    granular_facility_mapping[facility_name] = {
                        'sample_point_count': len(sample_points),
                        'grid_spacing': facility.get('grid_spacing_meters', 100),
                        'polygon_area_km2': facility.get('polygon_area_km2', 0)
                    }

                    for idx, point in enumerate(sample_points, start=1):
                        expanded_rows.append({
                            'Facility': f"{facility_name}_Point_{idx}",
                            'Lat': point['lat'],
                            'Long': point['lng'],
                            'Archetype': archetype
                        })

            # Create expanded CSV
            expanded_df = pd.DataFrame(expanded_rows)

            # Enhanced logging for expanded CSV
            logger.info(f"[UNIFIED_CSV_DEBUG] Created expanded DataFrame with {len(expanded_rows)} rows")
            if not expanded_df.empty:
                logger.info(f"[UNIFIED_CSV_DEBUG] Expanded DataFrame columns: {expanded_df.columns.tolist()}")
                logger.info(f"[UNIFIED_CSV_DEBUG] Coordinate columns sample:")
                logger.info(f"[UNIFIED_CSV_DEBUG] Lat values: {expanded_df['Lat'].head().tolist()}")
                logger.info(f"[UNIFIED_CSV_DEBUG] Long values: {expanded_df['Long'].head().tolist()}")
                logger.info(f"[UNIFIED_CSV_DEBUG] Lat NaN count: {expanded_df['Lat'].isna().sum()}")
                logger.info(f"[UNIFIED_CSV_DEBUG] Long NaN count: {expanded_df['Long'].isna().sum()}")
            else:
                logger.error(f"[UNIFIED_CSV_DEBUG] ERROR: Expanded DataFrame is empty!")

            upload_dir = os.path.join(settings.BASE_DIR, 'climate_hazards_analysis_v2', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)

            expanded_csv_filename = f"facility_data_expanded_{request.session.session_key or 'default'}.csv"
            expanded_csv_path = os.path.join(upload_dir, expanded_csv_filename)
            expanded_df.to_csv(expanded_csv_path, index=False)

            logger.info(f"Created expanded CSV with {len(expanded_rows)} rows (including sample points)")
            logger.info(f"Expanded CSV saved to: {expanded_csv_path}")

            # Use expanded CSV for analysis
            analysis_csv_path = expanded_csv_path
        else:
            logger.info("No sample points detected - using standard centroid-only analysis")
            analysis_csv_path = facility_csv_path

        # Re-use the generate_climate_hazards_analysis function from the original module
        logger.info(f"Calling generate_climate_hazards_analysis with: {analysis_csv_path}")
        result = generate_climate_hazards_analysis(
            facility_csv_path=analysis_csv_path,
            selected_fields=selected_hazards,
            flood_scenarios=['current', 'moderate', 'worst']
        )
        
        # Check for errors in the result; if failed, create fallback JSON
        if result is None or 'error' in result:
            error_message = result.get('error', 'Unknown error') if result else 'Analysis failed.'
            logger.error(f"Climate hazards analysis error: {error_message}")
            fallback_json = _build_fallback_analysis_json(facility_data, selected_hazards, request.session.session_key)
            if fallback_json:
                result = {'combined_json_path': fallback_json}
            else:
                return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
                    'error': error_message,
                    'facility_count': len(facility_data),
                    'hazard_types': _get_hazard_types(),
                    'selected_hazards': selected_hazards
                })
        
        # === JSON-ONLY LOADING (Migrated from Parallel CSV/JSON) ===
        # Get JSON path from the analysis result
        from .json_csv_loader import json_csv_loader
        file_paths = json_csv_loader.get_analysis_file_paths(result)

        combined_json_path = file_paths['json_path']

        logger.info("=== JSON-ONLY LOADING ===")
        json_csv_loader.log_file_status(combined_json_path)

        # Check if JSON file exists
        if not combined_json_path:
            logger.error("JSON file not found - using fallback JSON output")
            combined_json_path = _build_fallback_analysis_json(facility_data, selected_hazards, request.session.session_key)
            if not combined_json_path:
                return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
                    'error': 'Analysis output JSON file not found.',
                    'facility_count': len(facility_data),
                    'hazard_types': _get_hazard_types(),
                    'selected_hazards': selected_hazards
                })

        # Load data from JSON file
        try:
            data, columns = json_csv_loader.load_analysis_results(combined_json_path)

            # Convert back to DataFrame for compatibility with existing code
            df = pd.DataFrame(data)
            logger.info(f"Successfully loaded {len(data)} records from JSON")

        except Exception as e:
            logger.error(f"JSON loading failed: {str(e)}")
            return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
                'error': f'Failed to load analysis results: {str(e)}',
                'facility_count': len(facility_data),
                'hazard_types': [
                    'Flood', 'Water Stress', 'Heat', 'Sea Level Rise',
                    'Tropical Cyclones', 'Storm Surge', 'Rainfall Induced Landslide'
                ],
                'selected_hazards': selected_hazards
            })

        # === END JSON-ONLY LOADING ===

        # Log JSON-only workflow data to console
        from .json_console_simple import simple_json_console
        results_data = df.to_dict(orient="records")
        simple_json_console.log_results_step(results_data, df.columns.tolist(), {}, len(facility_data))

        # Ensure facility CSV file exists
        validated_csv_path = _ensure_facility_csv_exists(request, facility_data, facility_csv_path, selected_hazards)
        if not validated_csv_path:
            return _render_error_page(
                request,
                'Failed to create facility data file. Please try uploading your data again.',
                facility_data,
                selected_hazards
            )
  
        # Execute climate analysis
        result = _execute_climate_analysis(validated_csv_path, selected_hazards)
        if not result:
            return _render_error_page(
                request,
                'Climate hazards analysis failed. Please try again.',
                facility_data,
                selected_hazards
            )

        # Load and process the combined CSV data
        df, error = _load_and_process_combined_json(result.get('combined_json_path'))
        if error:
            return _render_error_page(request, error, facility_data, selected_hazards)

        logger.info(f"Loaded CSV with shape: {df.shape}")
        logger.info(f"CSV columns: {df.columns.tolist()}")

        # Handle data validation and missing columns
        df = _validate_and_fix_data_columns(df, selected_hazards)

        # Process tropical cyclone data if selected
        if 'Tropical Cyclones' in selected_hazards:
            df = _process_tropical_cyclone_data(df, validated_csv_path)

        # Add asset archetype information
        df = _add_asset_archetype_info(df, validated_csv_path)

        # Clean up potential merge suffixes like _x or _y that may appear
        rename_map = {c: c[:-2] for c in df.columns if c.endswith('_x') or c.endswith('_y')}
        if rename_map:
            logger.info(f"Renaming columns to remove merge suffixes: {rename_map}")
            df.rename(columns=rename_map, inplace=True)
            # Drop any duplicate columns that may remain after renaming
            df = df.loc[:, ~df.columns.duplicated()]

        

        # Add Asset Archetype information from facility CSV
        try:
            # Load facility CSV to get Asset Archetype information
            facility_df = pd.read_csv(facility_csv_path, encoding='utf-8')
        except UnicodeDecodeError:
            try:
                facility_df = pd.read_csv(facility_csv_path, encoding='latin-1')
            except UnicodeDecodeError:
                facility_df = pd.read_csv(facility_csv_path, encoding='cp1252')

        # Find Asset Archetype column with various naming conventions
        archetype_column = None
        possible_names = [
            'Asset Archetype', 'asset archetype', 'AssetArchetype', 'assetarchetype',
            'Archetype', 'archetype', 'Asset Type', 'asset type', 'AssetType', 'assettype',
            'Type', 'type', 'Category', 'category', 'Asset Category', 'asset category'
        ]

        for possible_name in possible_names:
            if possible_name in facility_df.columns:
                archetype_column = possible_name
                logger.info(f"Found Asset Archetype column: '{archetype_column}'")
                break

        if archetype_column:
            # Create a mapping from Facility name to Asset Archetype
            archetype_mapping = dict(zip(facility_df['Facility'], facility_df[archetype_column]))

            # Add Asset Archetype column to the combined data
            df['Asset Archetype'] = df['Facility'].map(archetype_mapping)

            # Fill any missing archetypes with 'Unknown'
            df['Asset Archetype'] = df['Asset Archetype'].fillna('Unknown')

            # Reorder columns to put Asset Archetype as 2nd column (after Facility)
            columns_list = df.columns.tolist()
            if 'Asset Archetype' in columns_list and 'Facility' in columns_list:
                # Remove Asset Archetype from its current position
                columns_list.remove('Asset Archetype')
                # Find Facility index and insert Asset Archetype after it
                facility_index = columns_list.index('Facility')
                columns_list.insert(facility_index + 1, 'Asset Archetype')
                # Reorder the DataFrame
                df = df[columns_list]
                logger.info("Added Asset Archetype column as 2nd column")

        else:
            logger.warning("No Asset Archetype column found in facility CSV, using default 'Unknown'")
            df['Asset Archetype'] = 'Unknown'
            # Still reorder to put it as 2nd column
            columns_list = df.columns.tolist()
            if 'Facility' in columns_list:
                columns_list.remove('Asset Archetype')
                facility_index = columns_list.index('Facility')
                columns_list.insert(facility_index + 1, 'Asset Archetype')
                df = df[columns_list]

        # Convert to dict for template
        data = df.to_dict(orient="records")
        columns = df.columns.tolist()

        logger.info(f"Final data has {len(data)} rows and {len(columns)} columns")
        logger.info(f"Final columns: {columns}")

        # ===== PARSE GRANULAR ANALYSIS RESULTS =====
        if granular_facility_mapping:
            logger.info("🔍 Parsing granular analysis results from unified analysis")

            from .granular_analysis import consolidate_points_to_clusters, classify_hazard_risk

            # Mapping from CSV column names to hazard types
            column_to_hazard_map = {
                'Flood Depth (meters)': 'Flood',
                'Water Stress Exposure (%)': 'Water Stress',
                'Days over 35° Celsius': 'Heat',
                'Extreme Windspeed 100 year Return Period (km/h)': 'Tropical Cyclones',
                'Storm Surge Flood Depth (meters)': 'Storm Surge',
                'Rainfall-Induced Landslide (factor of safety)': 'Landslide'
            }

            # Separate centroid rows from sample point rows
            centroid_rows = []
            sample_point_rows = {}  # Maps facility name to list of sample point results

            for row in data:
                facility_name = row.get('Facility', '')

                if '_Point_' in facility_name:
                    # This is a sample point row - extract base facility name
                    base_facility_name = facility_name.split('_Point_')[0]

                    if base_facility_name not in sample_point_rows:
                        sample_point_rows[base_facility_name] = []

                    # Convert row to sample point format for consolidation
                    # Extract lat/lng and transform hazard data
                    point_data = {
                        'lat': row.get('Lat'),
                        'lng': row.get('Long')
                    }

                    # Transform CSV columns to expected format with _value and _risk suffixes
                    for csv_col, hazard_type in column_to_hazard_map.items():
                        if csv_col in row and row[csv_col] is not None:
                            value = row[csv_col]

                            # Try to convert to float for classification
                            try:
                                if isinstance(value, str):
                                    # Handle categorical values
                                    if value == 'Little to none':
                                        numeric_value = 0.0
                                    elif value == 'N/A' or value == 'Data not available':
                                        continue
                                    else:
                                        # Try to extract numeric value from ranges like "0.1 to 0.5"
                                        numeric_value = float(value.split()[0])
                                else:
                                    numeric_value = float(value)

                                # Store value and classify risk
                                hazard_key = hazard_type.replace(' ', '_')
                                point_data[f'{hazard_key}_value'] = numeric_value
                                point_data[f'{hazard_key}_risk'] = classify_hazard_risk(numeric_value, hazard_type)

                            except (ValueError, AttributeError, IndexError) as e:
                                logger.warning(f"Could not convert {csv_col} value '{value}' to numeric: {e}")
                                continue

                    # Also preserve original column names for display
                    for col, value in row.items():
                        if col not in ['Facility', 'Lat', 'Long', 'Archetype', 'Asset Archetype']:
                            point_data[col] = value

                    sample_point_rows[base_facility_name].append(point_data)
                else:
                    # This is a centroid row - keep it
                    centroid_rows.append(row)

            logger.info(f"Separated into {len(centroid_rows)} centroid rows and {len(sample_point_rows)} facilities with sample points")

            # Process granular analysis for each facility with sample points
            for facility_name, sample_points in sample_point_rows.items():
                logger.info(f"Processing granular analysis for {facility_name}: {len(sample_points)} sample points")

                # Find the corresponding centroid row
                centroid_row = None
                for row in centroid_rows:
                    if row.get('Facility') == facility_name:
                        centroid_row = row
                        break

                if centroid_row and len(sample_points) > 0:
                    # Get facility metadata
                    facility_meta = granular_facility_mapping.get(facility_name, {})
                    grid_spacing = facility_meta.get('grid_spacing', 100)
                    polygon_area_km2 = facility_meta.get('polygon_area_km2', 0)

                    # Apply consolidation
                    try:
                        consolidated = consolidate_points_to_clusters(sample_points, grid_spacing)

                        # Add granular analysis data to the centroid row (for modal/summary)
                        centroid_row['granular_analysis'] = {
                            'analyzed_points': sample_points,
                            'clusters': consolidated.get('clusters', []),
                            'statistics': consolidated.get('statistics', {}),
                            'grid_spacing': grid_spacing,
                            'polygon_area_km2': polygon_area_km2
                        }
                        centroid_row['has_granular_analysis'] = True
                        centroid_row['sample_point_count'] = len(sample_points)

                        logger.info(f"Granular analysis completed for {facility_name}: "
                                  f"{len(sample_points)} points, {len(consolidated.get('clusters', []))} clusters")
                    except Exception as e:
                        logger.error(f"Error consolidating points for {facility_name}: {e}")
                        centroid_row['has_granular_analysis'] = False

            # Reconstruct data with centroids AND sample points (for table display)
            # Order: Parent facility row, followed by its sample point rows
            reconstructed_data = []

            for row in centroid_rows:
                facility_name = row.get('Facility')

                # Add the parent facility row (centroid)
                row['is_parent_facility'] = True
                row['is_sample_point'] = False
                reconstructed_data.append(row)

                # Add sample point rows if this facility has them
                if facility_name in sample_point_rows:
                    for idx, point_data in enumerate(sample_point_rows[facility_name], start=1):
                        # Create a full row for this sample point with all columns
                        point_row = {}

                        # Copy all centroid columns as base
                        for col in columns:
                            point_row[col] = point_data.get(col, 'N/A')

                        # Set facility name to show it's a sample point
                        point_row['Facility'] = f"└─ Point {idx}"
                        point_row['Lat'] = point_data.get('lat')
                        point_row['Long'] = point_data.get('lng')

                        # Mark as sample point row
                        point_row['is_sample_point'] = True
                        point_row['is_parent_facility'] = False
                        point_row['parent_facility'] = facility_name

                        reconstructed_data.append(point_row)

            # Replace data with reconstructed data (includes both centroids and sample points)
            data = reconstructed_data
            logger.info(f"Final data after granular parsing: {len(data)} rows (including sample points)")

        # Debug info will be handled in the hazard-specific sections below
        
        # Create detailed column groups for the table header
        groups = {}
        # Base group - Facility Information
        facility_cols = ['Facility', 'Asset Archetype']
        facility_count = sum(1 for col in facility_cols if col in columns)
        if facility_count > 0:
            groups['Facility Information'] = facility_count
        
        # Create a mapping for each hazard type and its columns
        hazard_columns = {
            'Flood': ['Flood Depth (meters)'],
            'Water Stress': [
                'Water Stress Exposure (%)',
                'Water Stress Exposure 2030 (%) - Moderate Case',
                'Water Stress Exposure 2050 (%) - Moderate Case',
                'Water Stress Exposure 2030 (%) - Worst Case',
                'Water Stress Exposure 2050 (%) - Worst Case'
            ],
            'Sea Level Rise': [
                '2030 Sea Level Rise (meters) - Moderate Case',
                '2040 Sea Level Rise (meters) - Moderate Case',
                '2050 Sea Level Rise (meters) - Moderate Case',
                '2030 Sea Level Rise (meters) - Worst Case',
                '2040 Sea Level Rise (meters) - Worst Case',
                '2050 Sea Level Rise (meters) - Worst Case'
            ],
            'Tropical Cyclones': ['Extreme Windspeed 10 year Return Period (km/h)',
                                'Extreme Windspeed 20 year Return Period (km/h)',
                                'Extreme Windspeed 50 year Return Period (km/h)',
                                'Extreme Windspeed 100 year Return Period (km/h)'],
            'Heat': [
                'Days over 30° Celsius', 'Days over 33° Celsius', 'Days over 35° Celsius',
                'Days over 35° Celsius (2026 - 2030) - Moderate Case',
                'Days over 35° Celsius (2031 - 2040) - Moderate Case',
                'Days over 35° Celsius (2041 - 2050) - Moderate Case',
                'Days over 35° Celsius (2026 - 2030) - Worst Case',
                'Days over 35° Celsius (2031 - 2040) - Worst Case',
                'Days over 35° Celsius (2041 - 2050) - Worst Case'
            ],
            'Storm Surge': [
                'Storm Surge Flood Depth (meters)',
                'Storm Surge Flood Depth (meters) - Worst Case'
            ],
            'Rainfall-Induced Landslide': [
                'Rainfall-Induced Landslide (factor of safety)',
                'Rainfall-Induced Landslide (factor of safety) - Moderate Case',
                'Rainfall-Induced Landslide (factor of safety) - Worst Case'
            ]
        }
        
        # Add column groups for each hazard type that has columns in the data
        for hazard, cols in hazard_columns.items():
            count = sum(1 for col in cols if col in columns)
            logger.info(f"🔍 Group Creation - Checking {hazard}: found {count} columns out of {len(cols)} expected")
            if hazard == 'Tropical Cyclones':
                logger.info(f"🌀 TC specific check: {[col for col in cols if col in columns]}")
            if count > 0:
                groups[hazard] = count
                logger.info(f"✅ Added {hazard} group with {count} columns")
            else:
                logger.warning(f"❌ No columns found for {hazard} group")

        logger.info("=== DEBUG: Column Detection ===")
        logger.info(f"Final columns list: {columns}")
        logger.info(f"Groups created: {groups}")

        # Only count heat-related future scenario columns that start with
        # "Days over 35 Celsius" for Moderate and Worst Case scenarios
        heat_basecase_count = sum(
            1
            for c in columns
            if c.startswith('Days over 35° Celsius') and c.endswith(' - Moderate Case')
        )
        heat_worstcase_count = sum(
            1
            for c in columns
            if c.startswith('Days over 35° Celsius') and c.endswith(' - Worst Case')
        )
        
        heat_baseline_cols = ['Days over 30° Celsius', 'Days over 33° Celsius', 'Days over 35° Celsius']
        heat_baseline_count = sum(1 for c in heat_baseline_cols if c in columns)

        if 'Heat' in groups:
            groups['Heat'] = heat_baseline_count + heat_basecase_count + heat_worstcase_count

        ws_moderatecase_count = sum(
            1 for c in columns
            if c.startswith('Water Stress Exposure') and c.endswith(' - Moderate Case')
        )
        ws_worstcase_count = sum(
            1 for c in columns
            if c.startswith('Water Stress Exposure') and c.endswith(' - Worst Case')
        )
        ws_baseline_cols = ['Water Stress Exposure (%)']
        ws_baseline_count = sum(1 for c in ws_baseline_cols if c in columns)

        if 'Water Stress' in groups:
            groups['Water Stress'] = ws_baseline_count + ws_moderatecase_count + ws_worstcase_count

        # Flood column counts
        flood_current_count = sum(1 for c in columns if c == 'Flood Depth (meters)')
        flood_moderate_count = sum(1 for c in columns if c == 'Flood Depth (meters) - Moderate Case')
        flood_worst_count = sum(1 for c in columns if c == 'Flood Depth (meters) - Worst Case')

        if 'Flood' in groups:
            groups['Flood'] = flood_current_count + flood_moderate_count + flood_worst_count

        # Tropical Cyclone column counts
        tc_basecase_count = sum(
            1 for c in columns
            if c.endswith(' - Moderate Case') and 'Windspeed' in c
        )
        tc_worstcase_count = sum(
            1 for c in columns
            if c.endswith(' - Worst Case') and 'Windspeed' in c
        )
        tc_baseline_cols = [
            'Extreme Windspeed 10 year Return Period (km/h)',
            'Extreme Windspeed 20 year Return Period (km/h)',
            'Extreme Windspeed 50 year Return Period (km/h)',
            'Extreme Windspeed 100 year Return Period (km/h)'
        ]
        tc_baseline_count = sum(1 for c in tc_baseline_cols if c in columns)

        if 'Tropical Cyclones' in groups:
            groups['Tropical Cyclones'] = (
                tc_baseline_count + tc_basecase_count + tc_worstcase_count
            )

        # Storm Surge column counts
        ss_worstcase_count = sum(
            1 for c in columns
            if c.endswith(' - Worst Case') and 'Storm Surge Flood Depth' in c
        )
        ss_baseline_cols = ['Storm Surge Flood Depth (meters)']
        ss_baseline_count = sum(1 for c in ss_baseline_cols if c in columns)

        if 'Storm Surge' in groups:
            groups['Storm Surge'] = ss_baseline_count + ss_worstcase_count
        slr_moderatecase_count = sum(1 for c in columns if c.endswith(" - Moderate Case") and "Sea Level Rise" in c)
        slr_worstcase_count = sum(1 for c in columns if c.endswith(" - Worst Case") and "Sea Level Rise" in c)
        if "Sea Level Rise" in groups:
            groups["Sea Level Rise"] = slr_moderatecase_count + slr_worstcase_count
        # Rainfall-Induced Landslide column counts
        ls_moderatecase_count = sum(
            1 for c in columns
            if c.endswith(' - Moderate Case') and 'Landslide' in c
        )
        ls_worstcase_count = sum(
            1 for c in columns
            if c.endswith(' - Worst Case') and 'Landslide' in c
        )
        ls_baseline_cols = ['Rainfall-Induced Landslide (factor of safety)']
        ls_baseline_count = sum(1 for c in ls_baseline_cols if c in columns)

        if 'Rainfall-Induced Landslide' in groups:
            groups['Rainfall-Induced Landslide'] = (
                ls_baseline_count + ls_moderatecase_count + ls_worstcase_count
            )


        
        if 'Flood' in selected_hazards:
            flood_col_exists = 'Flood Depth (meters)' in columns
            logger.info(f"'Flood Depth (meters)' in columns: {flood_col_exists}")
        
        # Enhanced TC Debug
        if 'Tropical Cyclones' in selected_hazards:
            tc_expected = ['Extreme Windspeed 10 year Return Period (km/h)',
                          'Extreme Windspeed 20 year Return Period (km/h)',
                          'Extreme Windspeed 50 year Return Period (km/h)',
                          'Extreme Windspeed 100 year Return Period (km/h)']
            tc_found = [col for col in tc_expected if col in columns]
            logger.info(f"'Tropical Cyclones' expected columns: {tc_expected}")
            logger.info(f"'Tropical Cyclones' found columns: {tc_found}")
            logger.info(f"'Tropical Cyclones' found count: {len(tc_found)}")

            # 🚨 EMERGENCY TC DEBUG - Final check before group creation
            logger.info("🚨 EMERGENCY TC DEBUG - PRE GROUP CREATION 🚨")
            tc_final_check = [col for col in tc_expected if col in columns]
            logger.info(f"TC columns in final data: {tc_final_check}")
            logger.info(f"TC column count in final data: {len(tc_final_check)}")
            logger.info("🚨 END EMERGENCY DEBUG - PRE GROUP CREATION 🚨")
        
        # Verify specific hazard groups were added if selected
        if 'Flood' in selected_hazards:
            if 'Flood' in groups:
                logger.info(f"✓ Flood group successfully added to table headers")
            else:
                logger.error("✗ Flood group missing from table headers!")
                        
        if 'Tropical Cyclones' in selected_hazards:
            if 'Tropical Cyclones' in groups:  # ← Correct key name!
                logger.info(f"✅ Tropical Cyclones group successfully added to table headers")
            else:
                logger.error("❌ Tropical Cyclones group missing from table headers!")
                # Additional detailed debug
                logger.error(f"❌ Groups dict: {groups}")
                logger.error(f"❌ Selected hazards: {selected_hazards}")
                logger.error(f"❌ TC columns expected: {hazard_columns['Tropical Cyclones']}")
                tc_debug_found = [col for col in hazard_columns['Tropical Cyclones'] if col in columns]
                logger.error(f"❌ TC columns actually found: {tc_debug_found}")
        
        # Get the paths to any generated plots
        plot_path = result.get('plot_path')
        all_plots = result.get('all_plots', [])

        # Store analysis results in session for potential reuse
        request.session['climate_hazards_v2_results'] = {
            'data': df.to_dict(orient="records"),
            'columns': df.columns.tolist(),
            'plot_path': plot_path if plot_path else None,
            'all_plots': all_plots
        }
        request.session.modified = True

        # Preserve a baseline copy of the results the first time they are
        # generated so we can restore them later if needed
        if 'climate_hazards_v2_baseline_results' not in request.session:
            request.session['climate_hazards_v2_baseline_results'] = copy.deepcopy(
                request.session['climate_hazards_v2_results']
            )

        # Build comprehensive column groups for hazard exposure table
        groups = _build_column_groups(df.columns.tolist(), selected_hazards)

        # Get uploaded asset IDs for JSON workflow
        uploaded_asset_ids = request.session.get('climate_hazards_v2_uploaded_asset_ids', [])

        # Log JSON workflow data to console
        from .json_console_simple import simple_json_console
        results_data = df.to_dict(orient="records")
        simple_json_console.log_results_step(results_data, df.columns.tolist(), groups, len(uploaded_asset_ids))

        # Prepare context for the template
        context = {
            'data': results_data,
            'columns': df.columns.tolist(),
            'groups': groups,  # Now properly populated with column group data
            'plot_path': plot_path,
            'all_plots': all_plots,
            'selected_hazards': selected_hazards,
            'uploaded_asset_ids': uploaded_asset_ids,  # For JSON workflow JavaScript
            'success_message': f"Successfully analyzed {len(df)} facilities for {len(selected_hazards)} hazard types."
        }

        logger.info("Rendering results template...")
        return render(request, 'climate_hazards_analysis_v2/results.html', context)

    except Exception as e:
        logger.exception(f"Error in climate hazards analysis: {str(e)}")

        return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
            'error': f"Error in climate hazards analysis: {str(e)}",
            'facility_count': len(facility_data),
            'hazard_types': [
                'Flood', 'Water Stress', 'Heat', 'Sea Level Rise',
                'Tropical Cyclones', 'Storm Surge', 'Rainfall Induced Landslide'
            ],
            'selected_hazards': selected_hazards
        })


def _handle_unified_mixed_assets_results(request, asset_inventory, selected_hazards, facility_data, facility_csv_path):
    """
    Handle results display for mixed asset types (regular facilities + polygon assets).
    Processes both asset types in parallel and merges results into hierarchical format.

    Args:
        request: Django request object
        asset_inventory: Unified asset inventory from select_hazards
        selected_hazards: List of selected hazard types
        facility_data: Original facility data from session
        facility_csv_path: Path to facility CSV file

    Returns:
        HttpResponse: Rendered results page with hierarchical table
    """
    try:
        logger.info(f"Processing unified mixed assets results via CSV approach: {asset_inventory['summary']}")
        logger.info(f"[DEBUG] Asset inventory summary details:")
        logger.info(f"[DEBUG] - Regular facilities: {asset_inventory['summary']['total_regular_facilities']}")
        logger.info(f"[DEBUG] - Polygon assets: {asset_inventory['summary']['total_polygon_assets']}")
        logger.info(f"[DEBUG] - Granular points: {asset_inventory['summary']['total_granular_points']}")
        logger.info(f"[DEBUG] - Has mixed assets: {asset_inventory['summary']['has_mixed_assets']}")

        # Process mixed assets using unified CSV approach
        logger.info("=== USING UNIFIED CSV APPROACH FOR MIXED ASSETS ===")
        mixed_results = _process_mixed_assets_via_unified_csv(asset_inventory, selected_hazards, request)

        if not mixed_results.get('success'):
            logger.error(f"Unified CSV processing failed: {mixed_results.get('error')}")
            return _render_error_page(request, f"Mixed asset processing failed: {mixed_results.get('error')}", facility_data, selected_hazards)

        hierarchical_data = mixed_results.get('data', [])
        logger.info(f"Successfully processed {len(hierarchical_data)} hierarchical rows via unified CSV")

        # Extract columns from hierarchical data
        if hierarchical_data:
            sample_row = hierarchical_data[0]
            columns = list(sample_row.keys())
            # Filter out internal metadata columns
            display_columns = [col for col in columns if not col.startswith('_') and col not in ['row_type', 'parent_id', 'level', 'parent_facility', 'original_asset_name']]
        else:
            display_columns = ['Facility', 'Asset Archetype'] + selected_hazards

        # Prepare context for template
        context = {
            'data': hierarchical_data,  # Hierarchical data directly for template
            'columns': display_columns,
            'selected_hazards': selected_hazards,
            'facility_count': asset_inventory['summary']['total_regular_facilities'],
            'polygon_assets_count': asset_inventory['summary']['total_polygon_assets'],
            'granular_points_count': asset_inventory['summary']['total_granular_points'],
            'has_mixed_assets': asset_inventory['summary']['has_mixed_assets'],
            'requires_hierarchical_display': True,  # Always hierarchical for mixed assets
            'groups': _build_column_groups(display_columns, selected_hazards),  # Fixed: use 'groups' instead of 'column_groups'
            'processing_method': 'unified_csv',  # Indicate unified CSV approach
        }

        logger.info(f"Successfully processed mixed assets via unified CSV: {len(hierarchical_data)} total rows")

        return render(request, 'climate_hazards_analysis_v2/results.html', context)

    except Exception as e:
        logger.exception(f"Error handling unified mixed assets results: {str(e)}")
        return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
            'error': f'Error processing mixed asset analysis: {str(e)}',
            'facility_count': len(facility_data),
            'hazard_types': _get_hazard_types(),
            'selected_hazards': selected_hazards
        })


def _process_regular_facilities_unified(facility_data, selected_hazards, facility_csv_path, asset_inventory):
    """
    Process regular facilities using the existing climate hazards analysis pipeline.

    Args:
        facility_data: List of regular facility data
        selected_hazards: List of selected hazard types
        facility_csv_path: Path to facility CSV file
        asset_inventory: Asset inventory containing metadata

    Returns:
        dict: Processing results with success status and data
    """
    try:
        logger.info(f"Processing {len(facility_data)} regular facilities through existing pipeline")

        # Filter regular facilities from facility_data
        regular_facilities = [f for f in facility_data if f.get('AssetType') != 'polygon' and not f.get('geometry')]

        if not regular_facilities:
            return {'success': True, 'data': []}

        # Create temporary CSV with only regular facilities
        regular_csv_path = _create_temporary_regular_facilities_csv(regular_facilities)
        if not regular_csv_path:
            return {'success': False, 'error': 'Failed to create temporary CSV for regular facilities'}

        # Execute climate analysis using existing function
        result = _execute_climate_analysis(regular_csv_path, selected_hazards)
        if not result:
            return {'success': False, 'error': 'Climate analysis failed for regular facilities'}

        # Load and process results
        df, error = _load_and_process_combined_json(result.get('combined_json_path'))
        if error:
            return {'success': False, 'error': error}

        # Process tropical cyclone data if selected
        if 'Tropical Cyclones' in selected_hazards:
            df = _process_tropical_cyclone_data(df, regular_csv_path)

        # Add asset archetype information
        df = _add_asset_archetype_info(df, regular_csv_path)

        # Clean up merge suffixes
        rename_map = {c: c[:-2] for c in df.columns if c.endswith('_x') or c.endswith('_y')}
        if rename_map:
            df.rename(columns=rename_map, inplace=True)
            df = df.loc[:, ~df.columns.duplicated()]

        # Convert to dict format
        data = df.to_dict(orient="records")

        # Clean up temporary file
        try:
            os.remove(regular_csv_path)
        except:
            pass

        logger.info(f"Successfully processed {len(data)} regular facility results")
        return {'success': True, 'data': data}

    except Exception as e:
        logger.exception(f"Error processing regular facilities: {str(e)}")
        return {'success': False, 'error': str(e)}


def _create_unified_mixed_assets_csv(asset_inventory, selected_hazards):
    """
    Create a unified CSV containing both regular facilities and polygon granular points.
    This enables using the existing climate_hazards_analysis pipeline for mixed asset processing.

    Args:
        asset_inventory: Unified asset inventory from select_hazards
        selected_hazards: List of selected hazard types

    Returns:
        str: Path to the unified CSV file, or None if failed
    """
    try:
        logger.info("Creating unified CSV for mixed asset processing")

        import tempfile
        import csv
        from datetime import datetime

        # Create temporary CSV file
        temp_dir = tempfile.mkdtemp()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unified_csv_path = os.path.join(temp_dir, f'unified_mixed_assets_{timestamp}.csv')

        unified_rows = []

        # Process regular facilities
        regular_facilities = asset_inventory.get('regular_facilities', [])
        logger.info(f"Adding {len(regular_facilities)} regular facilities to unified CSV")

        for facility in regular_facilities:
            row = {
                'Facility': facility.get('Facility', ''),
                'Lat': facility.get('Lat', ''),
                'Long': facility.get('Long', ''),
                'Asset Archetype': facility.get('Asset Archetype', 'default archetype'),
                'AssetType': 'regular',
                'Asset_ID': facility.get('id', ''),
                'Parent_Facility': '',  # Regular facilities have no parent
                'Point_Type': 'facility'  # For identification
            }
            unified_rows.append(row)

        # Process polygon assets and their granular points
        polygon_assets = asset_inventory.get('polygon_assets', [])
        logger.info(f"Processing {len(polygon_assets)} polygon assets for unified CSV")

        for polygon_asset in polygon_assets:
            asset_name = polygon_asset.get('name', polygon_asset.get('Facility', 'Unknown Polygon'))
            asset_archetype = polygon_asset.get('archetype', 'default archetype')
            polygon_id = polygon_asset.get('id', '')

            # Get polygon geometry and granular points
            geometry = polygon_asset.get('geometry')
            if not geometry:
                logger.warning(f"No geometry found for polygon asset: {asset_name}")
                continue

            # Use stored granular points from session data instead of generating new ones
            grid_points = polygon_asset.get('granular_points', [])

            if not grid_points:
                logger.warning(f"No granular points found for polygon: {asset_name}")
                # Don't skip the polygon - still add the centroid even without granular points
                logger.info(f"Will still process polygon centroid even without granular points: {asset_name}")
            else:
                logger.info(f"Using {len(grid_points)} stored granular points for polygon: {asset_name}")

            # Add centroid as parent row - ALWAYS attempt to add centroid
            centroid_lat = polygon_asset.get('centroid_lat') or polygon_asset.get('latitude') or polygon_asset.get('Lat')
            centroid_lng = polygon_asset.get('centroid_lng') or polygon_asset.get('longitude') or polygon_asset.get('Long')

            # Debug logging to understand centroid data
            logger.info(f"Centroid data for {asset_name}: lat={centroid_lat}, lng={centroid_lng}")
            logger.info(f"Available polygon asset keys: {list(polygon_asset.keys())}")

            if centroid_lat and centroid_lng:
                # Convert to float if string
                try:
                    centroid_lat = float(centroid_lat)
                    centroid_lng = float(centroid_lng)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid centroid coordinates format for {asset_name}: lat={centroid_lat}, lng={centroid_lng}")
                    # Calculate centroid from geometry as fallback
                    geometry = polygon_asset.get('geometry')
                    if geometry and geometry.get('type') == 'Polygon':
                        coordinates = geometry['coordinates'][0]  # Exterior ring
                        if len(coordinates) >= 4:
                            lats = [coord[1] for coord in coordinates[:-1]]  # Exclude closing point
                            lngs = [coord[0] for coord in coordinates[:-1]]
                            centroid_lat = sum(lats) / len(lats)
                            centroid_lng = sum(lngs) / len(lngs)
                            logger.info(f"Calculated centroid from geometry: {centroid_lat}, {centroid_lng}")
                        else:
                            logger.warning(f"Invalid polygon geometry for centroid calculation: {asset_name}")
                            continue
                    else:
                        logger.warning(f"No valid geometry for centroid calculation: {asset_name}")
                        continue

                centroid_row = {
                    'Facility': f"🟢 {asset_name} (Centroid)",
                    'Lat': centroid_lat,
                    'Long': centroid_lng,
                    'Asset Archetype': f"{asset_archetype} - Polygon Centroid",
                    'AssetType': 'polygon_centroid',
                    'Asset_ID': polygon_id,
                    'Parent_Facility': '',
                    'Point_Type': 'centroid'
                }
                unified_rows.append(centroid_row)
                logger.info(f"Added centroid row for polygon: {asset_name} at ({centroid_lat}, {centroid_lng})")
            else:
                logger.warning(f"No centroid coordinates found for polygon: {asset_name}")
                logger.warning(f"  Available keys: centroid_lat={polygon_asset.get('centroid_lat')}, latitude={polygon_asset.get('latitude')}")
                logger.warning(f"  Available keys: centroid_lng={polygon_asset.get('centroid_lng')}, longitude={polygon_asset.get('longitude')}")

            # Add granular points as child rows (only if granular points exist)
            if grid_points:
                logger.info(f"Adding {len(grid_points)} granular points for polygon: {asset_name}")
                for i, point in enumerate(grid_points):
                    # Handle tuple format: (latitude, longitude, grid_row, grid_col)
                    if isinstance(point, tuple) and len(point) >= 2:
                        lat, lon = point[0], point[1]
                    elif isinstance(point, dict):
                        lat = point.get('lat', point.get('latitude'))
                        lon = point.get('lon', point.get('longitude'))
                    else:
                        logger.warning(f"Invalid point format at index {i}: {point}")
                        continue

                    child_row = {
                        'Facility': f"└── Granular Point {i+1}",
                        'Lat': lat,
                        'Long': lon,
                        'Asset Archetype': f"{asset_archetype} - Granular Point",
                        'AssetType': 'polygon_granular',
                        'Asset_ID': f"{polygon_id}_point_{i}",
                        'Parent_Facility': asset_name,
                        'Point_Type': 'granular'
                    }
                    unified_rows.append(child_row)

        # Write unified CSV
        logger.info(f"Writing {len(unified_rows)} total rows to unified CSV: {unified_csv_path}")

        # Debug: Log what we're about to write
        logger.info(f"[UNIFIED_CSV_DEBUG] Unified rows summary:")
        for i, row in enumerate(unified_rows[:5]):  # Log first 5 rows for debugging
            logger.info(f"[UNIFIED_CSV_DEBUG] Row {i+1}: {row}")
        if len(unified_rows) > 5:
            logger.info(f"[UNIFIED_CSV_DEBUG] ... and {len(unified_rows) - 5} more rows")

        if not unified_rows:
            logger.error("[UNIFIED_CSV_DEBUG] No rows to write to unified CSV!")
            return None

        with open(unified_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Facility', 'Lat', 'Long', 'Asset Archetype', 'AssetType', 'Asset_ID', 'Parent_Facility', 'Point_Type']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(unified_rows)

        logger.info(f"Successfully created unified CSV with {len(unified_rows)} rows")

        # Verify the file was created and has content
        if os.path.exists(unified_csv_path):
            with open(unified_csv_path, 'r', encoding='utf-8') as verify_file:
                first_line = verify_file.readline().strip()
                logger.info(f"[UNIFIED_CSV_DEBUG] CSV header: {first_line}")

                # Count actual data rows (excluding header)
                data_lines = sum(1 for _ in verify_file) - 1  # Subtract header
                logger.info(f"[UNIFIED_CSV_DEBUG] Actual data rows in file: {data_lines}")

                if data_lines == 0:
                    logger.error("[UNIFIED_CSV_DEBUG] CSV file contains no data rows!")
                    return None
        else:
            logger.error(f"[UNIFIED_CSV_DEBUG] CSV file was not created: {unified_csv_path}")
            return None

        return unified_csv_path

    except Exception as e:
        logger.exception(f"Error creating unified mixed assets CSV: {str(e)}")
        return None


def _execute_climate_analysis_unified_csv(unified_csv_path, selected_hazards):
    """
    Execute climate analysis on unified CSV with non-strict mode for polygon centroids.

    This function creates a modified version of the climate analysis that can handle
    unified CSV files containing polygon centroids with strict_mode=False.

    Args:
        unified_csv_path: Path to the unified CSV file
        selected_hazards: List of selected hazard types

    Returns:
        dict: Analysis result or None if failed
    """
    try:
        logger.info("Executing climate analysis on unified CSV with non-strict mode")

        # Import the required modules
        import pandas as pd
        import os
        from climate_hazards_analysis.utils.climate_hazards_analysis import (
            process_flood_exposure_analysis,
            process_sea_level_rise_analysis,
            process_water_stress_analysis,
            process_heat_exposure_analysis,
            process_tropical_cyclone_analysis
        )
        from climate_hazards_analysis.utils.common_utils import (
            standardize_facility_dataframe,
            merge_dataframes_safely
        )
        from django.conf import settings

        # Load and standardize facility dataframe with non-strict mode
        try:
            df_fac = pd.read_csv(unified_csv_path, encoding='utf-8')
        except UnicodeDecodeError:
            try:
                df_fac = pd.read_csv(unified_csv_path, encoding='latin-1')
                logger.warning(f"Unified CSV read with latin-1 encoding")
            except UnicodeDecodeError:
                df_fac = pd.read_csv(unified_csv_path, encoding='cp1252')
                logger.warning(f"Unified CSV read with cp1252 encoding")

        logger.info(f"[UNIFIED_CSV_DEBUG] Before standardization:")
        logger.info(f"[UNIFIED_CSV_DEBUG] Original DataFrame shape: {df_fac.shape}")
        logger.info(f"[UNIFIED_CSV_DEBUG] Original columns: {df_fac.columns.tolist()}")

        # Use non-strict mode for unified CSV to handle polygon centroids
        df_fac = standardize_facility_dataframe(df_fac, strict_mode=False)
        logger.info(f"Loaded unified CSV data with {len(df_fac)} facilities")

        if df_fac.empty:
            logger.error("Unified CSV resulted in empty DataFrame after standardization")
            return None

        # Initialize combined DataFrame
        base_columns = ['Facility', 'Lat', 'Long']
        if 'Asset Archetype' in df_fac.columns:
            base_columns.append('Asset Archetype')

        # Add AssetType and Parent_Facility if they exist
        if 'AssetType' in df_fac.columns:
            base_columns.append('AssetType')
        if 'Parent_Facility' in df_fac.columns:
            base_columns.append('Parent_Facility')

        combined_df = df_fac[base_columns].copy()

        # Process each selected hazard with error handling for polygon-only scenarios
        if 'Flood Exposure' in selected_hazards:
            logger.info("Processing flood exposure analysis for unified CSV...")
            try:
                flood_result = process_flood_exposure_analysis(
                    unified_csv_path,
                    selected_fields=['Flood Exposure'],
                    scenarios=['current', 'moderate', 'worst']
                )
                if flood_result and len(flood_result) > 0:
                    flood_df = flood_result[0]  # First element is the DataFrame
                    combined_df = merge_dataframes_safely(combined_df, flood_df, on=['Facility', 'Lat', 'Long'])
                    logger.info(f"Successfully merged flood exposure data: {len(flood_df)} rows")
                else:
                    logger.warning("Flood exposure analysis returned no data")
            except Exception as e:
                logger.warning(f"Flood exposure analysis failed for unified CSV: {str(e)}")
                # Add default flood exposure values
                combined_df['Flood Depth (meters)'] = '0.1 to 0.5'  # Default to lowest risk

        if 'Sea Level Rise' in selected_hazards:
            logger.info("Processing sea level rise analysis for unified CSV...")
            try:
                slr_result = process_sea_level_rise_analysis(unified_csv_path, ['Sea Level Rise'])
                if slr_result and 'combined_csv_path' in slr_result:
                    slr_df = pd.read_csv(slr_result['combined_csv_path'])
                    combined_df = merge_dataframes_safely(combined_df, slr_df, on=['Facility', 'Lat', 'Long'])
                    logger.info(f"Successfully merged sea level rise data: {len(slr_df)} rows")
                else:
                    logger.warning("Sea level rise analysis returned no data")
            except Exception as e:
                logger.warning(f"Sea level rise analysis failed for unified CSV: {str(e)}")
                # Add default sea level rise values
                combined_df['Sea Level Rise (meters)'] = '0.0 to 0.5'  # Default to lowest risk

        if 'Water Stress' in selected_hazards:
            logger.info("Processing water stress analysis for unified CSV...")
            try:
                ws_result = process_water_stress_analysis(unified_csv_path, ['Water Stress'])
                if ws_result and 'combined_csv_path' in ws_result:
                    ws_df = pd.read_csv(ws_result['combined_csv_path'])
                    combined_df = merge_dataframes_safely(combined_df, ws_df, on=['Facility', 'Lat', 'Long'])
                    logger.info(f"Successfully merged water stress data: {len(ws_df)} rows")
                else:
                    logger.warning("Water stress analysis returned no data")
            except Exception as e:
                logger.warning(f"Water stress analysis failed for unified CSV: {str(e)}")
                # Add default water stress values
                combined_df['Water Stress'] = 'Low'  # Default to lowest risk

        if 'Heat Exposure' in selected_hazards:
            logger.info("Processing heat exposure analysis for unified CSV...")
            try:
                heat_result = process_heat_exposure_analysis(unified_csv_path, ['Heat Exposure'])
                if heat_result and 'combined_csv_path' in heat_result:
                    heat_df = pd.read_csv(heat_result['combined_csv_path'])
                    combined_df = merge_dataframes_safely(combined_df, heat_df, on=['Facility', 'Lat', 'Long'])
                    logger.info(f"Successfully merged heat exposure data: {len(heat_df)} rows")
                else:
                    logger.warning("Heat exposure analysis returned no data")
            except Exception as e:
                logger.warning(f"Heat exposure analysis failed for unified CSV: {str(e)}")
                # Add default heat exposure values
                combined_df['Heat Exposure'] = 'Low'  # Default to lowest risk

        if 'Tropical Cyclones' in selected_hazards:
            logger.info("Processing tropical cyclone analysis for unified CSV...")
            try:
                tc_result = process_tropical_cyclone_analysis(unified_csv_path, ['Tropical Cyclones'])
                if tc_result and 'combined_csv_path' in tc_result:
                    tc_df = pd.read_csv(tc_result['combined_csv_path'])
                    combined_df = merge_dataframes_safely(combined_df, tc_df, on=['Facility', 'Lat', 'Long'])
                    logger.info(f"Successfully merged tropical cyclone data: {len(tc_df)} rows")
                else:
                    logger.warning("Tropical cyclone analysis returned no data")
            except Exception as e:
                logger.warning(f"Tropical cyclone analysis failed for unified CSV: {str(e)}")
                # Add default tropical cyclone values
                combined_df['Tropical Cyclones'] = 'Low'  # Default to lowest risk

        # Save combined result
        import tempfile
        from datetime import datetime
        temp_dir = tempfile.mkdtemp()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        combined_csv_path = os.path.join(temp_dir, f'unified_analysis_result_{timestamp}.csv')

        combined_df.to_csv(combined_csv_path, index=False)
        logger.info(f"Unified analysis result saved to: {combined_csv_path}")

        return {
            'combined_csv_path': combined_csv_path,
            'total_facilities': len(combined_df),
            'analysis_type': 'unified_csv'
        }

    except Exception as e:
        logger.exception(f"Error in unified CSV climate analysis: {str(e)}")
        return None


def _process_mixed_assets_via_unified_csv(asset_inventory, selected_hazards, request=None):
    """
    Process mixed assets using the unified CSV approach with existing climate_hazards_analysis pipeline.

    Args:
        asset_inventory: Unified asset inventory from select_hazards
        selected_hazards: List of selected hazard types
        request: Django request object (optional, for accessing session data)

    Returns:
        dict: Processing results with success status and data
    """
    try:
        logger.info("=== PROCESSING MIXED ASSETS VIA UNIFIED CSV APPROACH ===")
        logger.info(f"Asset inventory summary: {asset_inventory.get('summary', {})}")
        logger.info(f"Selected hazards: {selected_hazards}")

        # Validate inputs
        if not asset_inventory:
            return {'success': False, 'error': 'No asset inventory provided'}

        if not selected_hazards:
            return {'success': False, 'error': 'No hazards selected'}

        # Create unified CSV containing all assets
        logger.info("Step 1: Creating unified CSV...")
        unified_csv_path = _create_unified_mixed_assets_csv(asset_inventory, selected_hazards)
        if not unified_csv_path:
            return {'success': False, 'error': 'Failed to create unified CSV'}

        logger.info(f"Step 1 Complete: Unified CSV created at {unified_csv_path}")

        try:
            # Step 2: Execute climate analysis using existing pipeline
            logger.info("Step 2: Executing climate hazards analysis on unified CSV...")

            # Validate CSV file exists before processing
            if not os.path.exists(unified_csv_path):
                return {'success': False, 'error': f'Unified CSV file not found: {unified_csv_path}'}

            # Use the unified CSV climate analysis function with non-strict mode
            result = _execute_climate_analysis_unified_csv(unified_csv_path, selected_hazards)

            if result is None:
                return {'success': False, 'error': 'Climate analysis returned None result'}

            if 'error' in result:
                error_msg = result.get('error', 'Unknown climate analysis error')
                logger.error(f"Climate analysis failed: {error_msg}")
                return {'success': False, 'error': f'Climate analysis failed: {error_msg}'}

            logger.info(f"Step 2 Complete: Climate analysis successful")
            logger.info(f"Analysis result keys: {list(result.keys())}")

            # Step 3: Load and process results
            logger.info("Step 3: Loading and processing JSON results...")
            combined_json_path = result.get('combined_json_path')

            if not combined_json_path:
                return {'success': False, 'error': 'No JSON path in analysis result'}

            if not os.path.exists(combined_json_path):
                return {'success': False, 'error': f'JSON file not found: {combined_json_path}'}

            df, error = _load_and_process_combined_json(combined_json_path)
            if error:
                return {'success': False, 'error': f'Failed to load JSON: {error}'}

            if df is None or df.empty:
                return {'success': False, 'error': 'Combined CSV resulted in empty DataFrame'}

            logger.info(f"Step 3 Complete: Loaded DataFrame with shape {df.shape}")
            logger.info(f"DataFrame columns: {df.columns.tolist()}")

            # Step 4: Convert to hierarchical structure
            logger.info("Step 4: Converting to hierarchical structure...")
            hierarchical_data = _convert_unified_csv_to_hierarchical(df, asset_inventory, request)

            if not hierarchical_data:
                logger.warning("Hierarchical conversion resulted in empty data")
                # Return success but with empty data - this might be valid for some cases
                return {'success': True, 'data': [], 'warning': 'No hierarchical data generated'}

            logger.info(f"Step 4 Complete: Hierarchical structure created with {len(hierarchical_data)} rows")

            logger.info(f"=== UNIFIED CSV PROCESSING SUCCESSFUL ===")
            return {'success': True, 'data': hierarchical_data}

        except Exception as inner_e:
            logger.exception(f"Error in climate analysis phase: {str(inner_e)}")
            return {'success': False, 'error': f'Climate analysis error: {str(inner_e)}'}

        finally:
            # Clean up temporary unified CSV
            try:
                if os.path.exists(unified_csv_path):
                    os.remove(unified_csv_path)
                    logger.info(f"Cleaned up temporary unified CSV: {unified_csv_path}")

                temp_dir = os.path.dirname(unified_csv_path)
                if temp_dir and os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
                    logger.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as cleanup_e:
                logger.warning(f"Error cleaning up temporary files: {str(cleanup_e)}")

    except Exception as e:
        logger.exception(f"Critical error in _process_mixed_assets_via_unified_csv: {str(e)}")
        return {'success': False, 'error': f'Processing failed: {str(e)}'}


def _convert_unified_csv_to_hierarchical(df, asset_inventory, request=None):
    """
    Convert unified CSV results back to hierarchical structure for template display.

    Args:
        df: DataFrame with processed results from unified CSV
        asset_inventory: Original asset inventory for reference
        request: Django request object (optional, for accessing session data)

    Returns:
        list: Hierarchical data structure for template
    """
    try:
        hierarchical_data = []

        # Validate DataFrame
        if df is None or df.empty:
            logger.warning("Empty DataFrame received in _convert_unified_csv_to_hierarchical")
            return []

        logger.info(f"Converting unified CSV with {len(df)} rows and columns: {df.columns.tolist()}")

        # Check if this is unified CSV data (has AssetType) or regular combined output
        if 'AssetType' in df.columns:
            logger.info("Processing unified CSV with AssetType column")
            return _process_unified_csv_with_assettype(df)
        else:
            logger.info("Processing regular combined output CSV")
            return _process_combined_output_csv(df, asset_inventory, request)

    except Exception as e:
        logger.exception(f"Critical error in _convert_unified_csv_to_hierarchical: {str(e)}")
        return []


def _process_unified_csv_with_assettype(df):
    """
    Process unified CSV that contains AssetType column.
    """
    try:
        hierarchical_data = []

        # Group by asset type with error handling
        try:
            polygon_centroids = df[df['AssetType'] == 'polygon_centroid'] if 'AssetType' in df.columns else pd.DataFrame()
            granular_points = df[df['AssetType'] == 'polygon_granular'] if 'AssetType' in df.columns else pd.DataFrame()
            regular_facilities = df[df['AssetType'] == 'regular'] if 'AssetType' in df.columns else pd.DataFrame()
        except Exception as e:
            logger.error(f"Error grouping DataFrame by AssetType: {str(e)}")
            return []

        logger.info(f"Data groups - Regular: {len(regular_facilities)}, Centroids: {len(polygon_centroids)}, Granular: {len(granular_points)}")

        # Process regular facilities (as top-level rows)
        for _, facility_row in regular_facilities.iterrows():
            try:
                row_data = facility_row.to_dict()
                row_data['row_type'] = 'facility'
                row_data['parent_id'] = None
                row_data['level'] = 0
                hierarchical_data.append(row_data)
            except Exception as e:
                logger.error(f"Error processing facility row: {str(e)}")
                continue

        # Process polygon centroids and their granular points
        for _, centroid_row in polygon_centroids.iterrows():
            try:
                centroid_data = centroid_row.to_dict()
                centroid_data['row_type'] = 'polygon_parent'
                centroid_data['parent_id'] = None
                centroid_data['level'] = 0
                centroid_data['has_granular_analysis'] = True

                # Add hierarchical metadata with safe string operations
                facility_name = centroid_data.get('Facility', '')
                asset_name = centroid_data.get('Parent_Facility', facility_name.replace('🟢 ', '').replace(' (Centroid)', '') if facility_name else '')
                centroid_data['original_asset_name'] = asset_name

                hierarchical_data.append(centroid_data)

                # Find and add child granular points with error handling
                try:
                    parent_facility = facility_name.replace('🟢 ', '').replace(' (Centroid)', '') if facility_name else ''
                    if 'Parent_Facility' in granular_points.columns and not granular_points.empty:
                        child_points = granular_points[granular_points['Parent_Facility'] == parent_facility]

                        for _, child_row in child_points.iterrows():
                            try:
                                child_data = child_row.to_dict()
                                child_data['row_type'] = 'polygon_child'
                                child_data['parent_id'] = facility_name
                                child_data['level'] = 1
                                child_data['parent_facility'] = facility_name
                                child_data['has_granular_analysis'] = False  # Child rows don't have their own granular analysis
                                hierarchical_data.append(child_data)
                            except Exception as e:
                                logger.error(f"Error processing child granular point: {str(e)}")
                                continue
                except Exception as e:
                    logger.error(f"Error finding child granular points for {parent_facility}: {str(e)}")

            except Exception as e:
                logger.error(f"Error processing polygon centroid: {str(e)}")
                continue

        logger.info(f"Successfully converted unified CSV to hierarchical structure: {len(hierarchical_data)} rows")
        return hierarchical_data

    except Exception as e:
        logger.exception(f"Error in _process_unified_csv_with_assettype: {str(e)}")
        return []


def _process_combined_output_csv(df, asset_inventory=None, request=None):
    """
    Process regular combined output CSV that doesn't have AssetType column.
    Detects hierarchical structure based on facility names and asset archetypes.

    Args:
        df: DataFrame with combined output data
        asset_inventory: Asset inventory containing polygon asset information
        request: Django request object (optional, for accessing session data)
    """
    try:
        hierarchical_data = []

        logger.info(f"=== PROCESSING COMBINED OUTPUT CSV ===")
        logger.info(f"Processing combined output CSV with {len(df)} rows")
        logger.info(f"Asset inventory provided: {asset_inventory is not None}")
        if asset_inventory:
            logger.info(f"Asset inventory keys: {list(asset_inventory.keys())}")
            if 'polygon_assets' in asset_inventory:
                logger.info(f"Polygon assets count: {len(asset_inventory['polygon_assets'])}")

        # Get parent facility mappings from session
        parent_facilities = {}
        if request:
            parent_facilities = request.session.get('climate_hazards_v2_parent_facilities', {})
            logger.info(f"Retrieved {len(parent_facilities)} parent facility mappings from session")
            for facility_id, parent_name in parent_facilities.items():
                logger.info(f"  - {facility_id} -> {parent_name}")

        # Identify parent and child rows based on facility naming patterns
        parent_rows = []
        child_rows = []

        for _, row in df.iterrows():
            facility_name = row.get('Facility', '')
            asset_archetype = row.get('Asset Archetype', '')

            # Detect parent rows (polygon centroids)
            if ('Centroid' in facility_name or
                '🟢' in facility_name or
                'Polygon Centroid' in asset_archetype):

                row_data = row.to_dict()
                row_data['row_type'] = 'polygon_parent'
                row_data['parent_id'] = None
                row_data['level'] = 0
                row_data['has_granular_analysis'] = True
                row_data['original_asset_name'] = facility_name.replace('🟢 ', '').replace(' (Centroid)', '')
                parent_rows.append(row_data)

            # Detect child rows (granular points)
            elif ('└──' in facility_name or
                  'Granular Point' in facility_name or
                  'Granular Point' in asset_archetype):

                row_data = row.to_dict()
                row_data['row_type'] = 'polygon_child'
                row_data['level'] = 1
                row_data['has_granular_analysis'] = False  # Child rows don't have their own granular analysis
                child_rows.append(row_data)

            # Regular facilities
            else:
                row_data = row.to_dict()
                row_data['row_type'] = 'facility'
                row_data['parent_id'] = None
                row_data['level'] = 0
                hierarchical_data.append(row_data)

        # Don't process children here - wait for synthetic parent creation
        # Children will be processed and linked after synthetic parents are created
        logger.info(f"Deferring child row processing for {len(child_rows)} children until synthetic parents are created")

        # Add parent rows or create synthetic parents if none exist
        if not parent_rows:
            logger.info("No parent rows found in CSV, creating synthetic parent rows")

            # Get polygon asset names from asset inventory if available
            polygon_asset_names = {}
            if asset_inventory and 'polygon_assets' in asset_inventory:
                for polygon_asset in asset_inventory['polygon_assets']:
                    asset_name = polygon_asset.get('name', polygon_asset.get('Facility', 'Unknown Polygon'))
                    asset_archetype = polygon_asset.get('archetype', 'default archetype')
                    # Map archetype to actual asset name
                    polygon_asset_names[asset_archetype] = asset_name
                    logger.info(f"Mapped polygon asset: {asset_archetype} -> {asset_name}")

            logger.info(f"Available polygon asset mappings: {polygon_asset_names}")
            logger.info(f"Available parent facility mappings from form: {parent_facilities}")

            # Group child rows by base archetype
            base_archetypes = {}
            for child_row in child_rows:
                child_archetype = child_row.get('Asset Archetype', '')
                if ' - Granular Point' in child_archetype:
                    base_archetype = child_archetype.replace(' - Granular Point', '')
                    if base_archetype not in base_archetypes:
                        base_archetypes[base_archetype] = []
                    base_archetypes[base_archetype].append(child_row)

            # Create synthetic parent rows for each base archetype
            for base_archetype, children in base_archetypes.items():
                if children:
                    # Use the first child's data to create parent row
                    first_child = children[0]

                    # PRIORITY 1: Try to get parent name from form data first (most accurate)
                    actual_asset_name = None
                    if parent_facilities:
                        # The parent facility mapping should match our base archetype
                        actual_asset_name = parent_facilities.get(base_archetype)
                        if actual_asset_name:
                            logger.info(f"✓ FOUND parent name from form data: {base_archetype} -> {actual_asset_name}")

                    # PRIORITY 2: Fallback to asset inventory mapping
                    if not actual_asset_name:
                        actual_asset_name = polygon_asset_names.get(base_archetype)
                        if actual_asset_name:
                            logger.info(f"Using parent name from asset inventory: {base_archetype} -> {actual_asset_name}")

                    # PRIORITY 3: Final fallback to archetype name
                    if not actual_asset_name:
                        actual_asset_name = base_archetype
                        logger.info(f"Using fallback parent name (archetype): {base_archetype} -> {actual_asset_name}")

                    logger.info(f"Creating synthetic parent for {base_archetype} using final name: {actual_asset_name}")

                    parent_row = {
                        'Facility': actual_asset_name,  # Use actual asset name, no emoji or suffix
                        'Asset Archetype': f"{base_archetype} - Polygon Centroid",
                        'Lat': first_child.get('Lat', ''),
                        'Long': first_child.get('Long', ''),
                        'row_type': 'polygon_parent',
                        'parent_id': None,
                        'level': 0,
                        'has_granular_analysis': True,
                        'original_asset_name': actual_asset_name
                    }

                    logger.info(f"Created parent row with Facility: '{parent_row['Facility']}'")

                    # Copy all the hazard analysis data from first child
                    for key, value in first_child.items():
                        if key not in ['Facility', 'Asset Archetype', 'row_type', 'parent_id', 'level', 'has_granular_analysis', 'original_asset_name']:
                            parent_row[key] = value

                    logger.info(f"Created synthetic parent row: {parent_row['Facility']}")
                    parent_rows.append(parent_row)

                    # Update all children to point to this parent
                    for child_row in children:
                        child_row['parent_id'] = parent_row['Facility']
                        child_row['parent_facility'] = parent_row['Facility']
                        logger.info(f"Linked child to parent: child_facility={child_row.get('Facility', 'Unknown')} -> parent_id='{parent_row['Facility']}'")

                    # Add the linked children to hierarchical data
                    for child_row in children:
                        hierarchical_data.append(child_row)

        hierarchical_data.extend(parent_rows)

        # Process any children that weren't part of synthetic parent groups
        # These are children that don't match any base_archetype
        linked_child_ids = set()
        for base_archetype, children in base_archetypes.items():
            linked_child_ids.update(id(child) for child in children)

        remaining_children = [child for child in child_rows if id(child) not in linked_child_ids]
        if remaining_children:
            logger.warning(f"Found {len(remaining_children)} remaining children not linked to synthetic parents")
            for child_row in remaining_children:
                hierarchical_data.append(child_row)

        logger.info(f"Successfully processed combined output CSV: {len(hierarchical_data)} total rows")
        logger.info(f"  - Regular facilities: {len([r for r in hierarchical_data if r['row_type'] == 'facility'])}")
        logger.info(f"  - Polygon parents: {len([r for r in hierarchical_data if r['row_type'] == 'polygon_parent'])}")
        logger.info(f"  - Polygon children: {len([r for r in hierarchical_data if r['row_type'] == 'polygon_child'])}")

        # Debug: Ensure all hierarchical rows have required fields
        for i, row in enumerate(hierarchical_data):
            if row['row_type'] in ['polygon_parent', 'polygon_child']:
                missing_fields = []
                if 'parent_id' not in row:
                    missing_fields.append('parent_id')
                if 'parent_facility' not in row:
                    missing_fields.append('parent_facility')
                if 'has_granular_analysis' not in row:
                    missing_fields.append('has_granular_analysis')

                if missing_fields:
                    logger.warning(f"Row {i} (type: {row['row_type']}) missing required fields: {missing_fields}")
                    # Add missing fields
                    for field in missing_fields:
                        if field == 'parent_id':
                            row['parent_id'] = row.get('parent_id', None)
                        elif field == 'parent_facility':
                            row['parent_facility'] = row.get('parent_facility', row.get('parent_id', None))
                        elif field == 'has_granular_analysis':
                            row['has_granular_analysis'] = row['row_type'] == 'polygon_parent'

        return hierarchical_data

    except Exception as e:
        logger.exception(f"Error in _process_combined_output_csv: {str(e)}")
        return []


def _process_polygon_assets_unified(polygon_assets, selected_hazards):
    """
    Process polygon assets using granular analysis workflow.

    Args:
        polygon_assets: List of polygon asset data
        selected_hazards: List of selected hazard types

    Returns:
        dict: Processing results with success status and data
    """
    try:
        logger.info(f"Processing {len(polygon_assets)} polygon assets through granular workflow")

        polygon_results = []

        for polygon_asset in polygon_assets:
            try:
                # Get or create Asset model instance
                asset_id = polygon_asset.get('id')
                asset = None

                if asset_id:
                    try:
                        # Try to get asset by database ID (integer)
                        if isinstance(asset_id, int) or (isinstance(asset_id, str) and asset_id.isdigit()):
                            asset = Asset.objects.get(id=int(asset_id))
                        else:
                            # Check if this is a session-based polygon asset (string ID like "polygon_b480aff8")
                            # For session-based assets, we need to create the database record first
                            logger.info(f"Session-based polygon asset detected: {asset_id}, creating database record")
                            asset = _create_asset_from_polygon_data(polygon_asset)
                    except (ValueError, Asset.DoesNotExist):
                        # If ID lookup fails, try to create from session data
                        logger.warning(f"Could not find asset with ID {asset_id}, creating from session data")
                        asset = _create_asset_from_polygon_data(polygon_asset)
                else:
                    # Create Asset from session data
                    asset = _create_asset_from_polygon_data(polygon_asset)

                if not asset:
                    logger.warning(f"Could not create/find asset for polygon: {polygon_asset.get('name') or polygon_asset.get('Facility')}")
                    continue

                # Use the actual geometry from the Asset model if available, fallback to session data
                geometry = asset.polygon_geometry or polygon_asset.get('geometry')
                if not geometry:
                    logger.error(f"No polygon geometry found for asset {asset.name}")
                    continue

                # Execute granular analysis workflow
                from .granular_workflow_service import execute_granular_analysis_workflow
                workflow_result = execute_granular_analysis_workflow(
                    polygon_geometry=geometry,
                    asset_name=asset.name,
                    selected_hazards=selected_hazards,
                    archetype=asset.archetype,
                    scenario='current'
                )

                if workflow_result.get('success'):
                    # Convert workflow results to table format
                    table_results = workflow_result.get('table_results', [])
                    polygon_results.extend(table_results)
                    logger.info(f"Successfully processed polygon {asset.name} with {len(table_results)} result rows")
                else:
                    logger.error(f"Failed to process polygon {asset.name}: {workflow_result.get('error')}")

            except Exception as e:
                logger.exception(f"Error processing polygon asset {polygon_asset.get('name') or polygon_asset.get('Facility')}: {str(e)}")

        logger.info(f"Successfully processed {len(polygon_results)} polygon result rows")
        return {'success': True, 'data': polygon_results}

    except Exception as e:
        logger.exception(f"Error processing polygon assets: {str(e)}")
        return {'success': False, 'error': str(e)}


def _create_hierarchical_results_structure(unified_results, selected_hazards):
    """
    Create hierarchical data structure for displaying mixed asset results.

    Args:
        unified_results: Results from processing regular facilities and polygon assets
        selected_hazards: List of selected hazard types

    Returns:
        dict: Hierarchical data structure with flat_data, hierarchical, and columns
    """
    try:
        logger.info("Creating hierarchical results structure for mixed assets")

        hierarchical_data = []
        flat_data = []

        # Add regular facility results (as top-level rows)
        for facility_result in unified_results['regular_facilities']:
            row_data = facility_result.copy()
            row_data['row_type'] = 'facility'
            row_data['parent_id'] = None
            row_data['level'] = 0
            row_data['is_expandable'] = False
            hierarchical_data.append(row_data)
            flat_data.append(row_data)

        # Add polygon asset results (as parent rows with granular children)
        for polygon_result in unified_results['polygon_assets']:
            # Create parent row for polygon centroid
            parent_row = polygon_result.copy()
            parent_row['row_type'] = 'polygon_parent'
            parent_row['parent_id'] = None
            parent_row['parent_facility'] = parent_row.get('Facility', '')  # Add missing parent_facility field
            parent_row['level'] = 0
            parent_row['is_expandable'] = True
            parent_row['children_count'] = parent_row.get('Grid Points Processed', 0)
            parent_row['has_granular_analysis'] = True  # Add missing has_granular_analysis field
            hierarchical_data.append(parent_row)
            flat_data.append(parent_row)

            # Get granular results for this polygon
            asset_name = parent_row.get('Facility')
            granular_children = _get_granular_children_for_polygon(asset_name, selected_hazards)

            # Add child rows for granular points
            for child_idx, child_result in enumerate(granular_children):
                child_row = child_result.copy()
                child_row['row_type'] = 'polygon_child'
                child_row['parent_id'] = asset_name
                child_row['parent_facility'] = asset_name  # Add missing parent_facility field
                child_row['level'] = 1
                child_row['is_expandable'] = False
                child_row['child_index'] = child_idx + 1
                child_row['has_granular_analysis'] = False  # Add missing has_granular_analysis field
                hierarchical_data.append(child_row)
                flat_data.append(child_row)

        # Extract columns from the data
        if flat_data:
            columns = list(flat_data[0].keys())
        else:
            columns = []

        logger.info(f"Created hierarchical structure: {len(hierarchical_data)} total rows")
        return {
            'hierarchical': hierarchical_data,
            'flat_data': flat_data,
            'columns': columns
        }

    except Exception as e:
        logger.exception(f"Error creating hierarchical results structure: {str(e)}")
        return {
            'hierarchical': [],
            'flat_data': [],
            'columns': []
        }


def _create_temporary_regular_facilities_csv(regular_facilities):
    """
    Create a temporary CSV file containing only regular facilities.

    Args:
        regular_facilities: List of regular facility data

    Returns:
        str: Path to temporary CSV file or None if failed
    """
    try:
        if not regular_facilities:
            return None

        import tempfile
        import csv

        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8')
        temp_path = temp_file.name

        # Write regular facilities to CSV
        fieldnames = ['Facility', 'Lat', 'Long', 'Archetype']
        writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
        writer.writeheader()

        for facility in regular_facilities:
            writer.writerow({
                'Facility': facility.get('Facility', facility.get('Name', 'Unknown')),
                'Lat': facility.get('Lat', facility.get('Latitude')),
                'Long': facility.get('Long', facility.get('Longitude')),
                'Archetype': facility.get('Archetype', 'default archetype')
            })

        temp_file.close()
        logger.info(f"Created temporary regular facilities CSV: {temp_path}")
        return temp_path

    except Exception as e:
        logger.exception(f"Error creating temporary regular facilities CSV: {str(e)}")
        return None


def _create_asset_from_polygon_data(polygon_data):
    """
    Create an Asset model instance from polygon session data.

    Args:
        polygon_data: Polygon asset data from session

    Returns:
        Asset: Created asset instance or None if failed
    """
    try:
        # Handle multiple possible field names for compatibility
        name = polygon_data.get('name') or polygon_data.get('Facility') or 'Unknown Polygon'
        archetype = polygon_data.get('archetype') or polygon_data.get('Archetype', 'default archetype')
        centroid_lat = polygon_data.get('centroid_lat') or polygon_data.get('Lat')
        centroid_lng = polygon_data.get('centroid_lng') or polygon_data.get('Long')
        geometry = polygon_data.get('geometry') or polygon_data.get('polygon_geometry')

        if not centroid_lat or not centroid_lng:
            logger.warning(f"No centroid coordinates for polygon {name}")
            return None

        if not geometry:
            logger.warning(f"No polygon geometry for {name}")
            return None

        # Check if an asset with the same name and coordinates already exists
        # This prevents creating duplicates when processing the same polygon multiple times
        existing_assets = Asset.objects.filter(
            name=name,
            latitude=Decimal(str(centroid_lat)),
            longitude=Decimal(str(centroid_lng)),
            asset_type='polygon'
        ).first()

        if existing_assets:
            logger.info(f"Found existing asset for polygon {name} (ID: {existing_assets.id})")
            return existing_assets

        # Create new asset
        asset = Asset.objects.create(
            name=name,
            archetype=archetype,
            latitude=Decimal(str(centroid_lat)),
            longitude=Decimal(str(centroid_lng)),
            polygon_geometry=geometry,
            asset_type='polygon',
            has_granular_analysis=True,
            granular_analysis_status='pending',
            # Set owner/source to track session-based assets
            source='session_polygon_workflow',
            owner=polygon_data.get('session_key', 'session')
        )

        logger.info(f"Created asset from polygon data: {asset.name} (ID: {asset.id})")
        return asset

    except Exception as e:
        logger.exception(f"Error creating asset from polygon data: {str(e)}")
        return None


def _get_granular_children_for_polygon(asset_name, selected_hazards):
    """
    Get granular analysis results for a polygon asset to display as children.

    Args:
        asset_name: Name of the polygon asset
        selected_hazards: List of selected hazard types

    Returns:
        list: List of child row data for granular points
    """
    try:
        # Try to get granular results from database
        try:
            asset = Asset.objects.get(name=asset_name)
            granular_results = GranularAnalysisResult.objects.filter(
                asset=asset,
                hazard_type__in=selected_hazards,
                processing_status='completed'
            ).order_by('grid_row', 'grid_col')

            if granular_results.exists():
                children = []
                for result in granular_results:
                    child_data = {
                        'Facility': f"{asset_name}_Point_{result.grid_row}_{result.grid_col}",
                        'Lat': float(result.latitude),
                        'Long': float(result.longitude),
                        'Archetype': asset.archetype,
                        'Asset Type': 'Granular Point',
                        'Grid Row': result.grid_row,
                        'Grid Col': result.grid_col,
                    }

                    # Add hazard-specific data
                    if result.result_data:
                        for key, value in result.result_data.items():
                            child_data[key] = value

                    children.append(child_data)

                return children

        except Asset.DoesNotExist:
            logger.warning(f"Asset {asset_name} not found for granular children")

        # Fallback: return empty list if no granular results found
        logger.info(f"No granular results found for {asset_name}, returning empty children list")
        return []

    except Exception as e:
        logger.exception(f"Error getting granular children for {asset_name}: {str(e)}")
        return []


def _build_column_groups(columns, selected_hazards):
    """
    Build comprehensive column groups for the hazard exposure table.

    Args:
        columns (list): List of column names from the analysis results
        selected_hazards (list): List of selected hazard types

    Returns:
        dict: Dictionary mapping group names to column counts
    """
    logger.info(f"Building column groups for {len(columns)} columns and selected hazards: {selected_hazards}")
    logger.info(f"Available columns: {columns}")

    groups = {}

    # Comprehensive column mappings for all hazard types
    column_mappings = {
        'Facility Information': [
            'Facility',
            'Asset Archetype',
            'Lat',
            'Long'
        ],
        'Flood': [
            'Flood Depth (meters)',
            'Flood Depth (meters) - Moderate Case',
            'Flood Depth (meters) - Worst Case'
        ],
        'Water Stress': [
            'Water Stress Exposure (%)',
            'Water Stress Exposure 2030 (%) - Moderate Case',
            'Water Stress Exposure 2050 (%) - Moderate Case',
            'Water Stress Exposure 2030 (%) - Worst Case',
            'Water Stress Exposure 2050 (%) - Worst Case'
        ],
        'Heat': [
            'Days over 30° Celsius',
            'Days over 33° Celsius',
            'Days over 35° Celsius',
            'Days over 35° Celsius (2026 - 2030) - Moderate Case',
            'Days over 35° Celsius (2031 - 2040) - Moderate Case',
            'Days over 35° Celsius (2041 - 2050) - Moderate Case',
            'Days over 35° Celsius (2026 - 2030) - Worst Case',
            'Days over 35° Celsius (2031 - 2040) - Worst Case',
            'Days over 35° Celsius (2041 - 2050) - Worst Case'
        ],
        'Sea Level Rise': [
            '2030 Sea Level Rise (meters) - Moderate Case',
            '2040 Sea Level Rise (meters) - Moderate Case',
            '2050 Sea Level Rise (meters) - Moderate Case',
            '2030 Sea Level Rise (meters) - Worst Case',
            '2040 Sea Level Rise (meters) - Worst Case',
            '2050 Sea Level Rise (meters) - Worst Case'
        ],
        'Tropical Cyclones': [
            'Extreme Windspeed 10 year Return Period (km/h)',
            'Extreme Windspeed 20 year Return Period (km/h)',
            'Extreme Windspeed 50 year Return Period (km/h)',
            'Extreme Windspeed 100 year Return Period (km/h)',
            'Extreme Windspeed 10 year Return Period (km/h) - Moderate Case',
            'Extreme Windspeed 20 year Return Period (km/h) - Moderate Case',
            'Extreme Windspeed 50 year Return Period (km/h) - Moderate Case',
            'Extreme Windspeed 100 year Return Period (km/h) - Moderate Case',
            'Extreme Windspeed 10 year Return Period (km/h) - Worst Case',
            'Extreme Windspeed 20 year Return Period (km/h) - Worst Case',
            'Extreme Windspeed 50 year Return Period (km/h) - Worst Case',
            'Extreme Windspeed 100 year Return Period (km/h) - Worst Case'
        ],
        'Storm Surge': [
            'Storm Surge Flood Depth (meters)',
            'Storm Surge Flood Depth (meters) - Worst Case'
        ],
        'Rainfall-Induced Landslide': [
            'Rainfall-Induced Landslide (factor of safety)',
            'Rainfall-Induced Landslide (factor of safety) - Moderate Case',
            'Rainfall-Induced Landslide (factor of safety) - Worst Case'
        ]
    }

    # Map hazard type variations to standard names
    hazard_name_mapping = {
        'Sea Level Rise': 'Sea Level Rise',
        'Tropical Cyclones': 'Tropical Cyclones',
        'Storm Surge': 'Storm Surge',
        'Rainfall Induced Landslide': 'Rainfall-Induced Landslide',
        'Rainfall-Induced Landslide': 'Rainfall-Induced Landslide',
        'Water Stress': 'Water Stress'
    }

    # Always include Facility Information if we have basic columns
    facility_cols = [col for col in column_mappings['Facility Information'] if col in columns]
    if facility_cols:
        groups['Facility Information'] = len(facility_cols)
        logger.info(f"Added Facility Information group with {len(facility_cols)} columns: {facility_cols}")

    # Define the desired order for hazard groups
    desired_hazard_order = [
        'Flood',
        'Water Stress',
        'Sea Level Rise',
        'Tropical Cyclones',
        'Heat',
        'Storm Surge',
        'Rainfall-Induced Landslide'
    ]

    # Add groups for selected hazards based on actual column presence in correct order
    for hazard in desired_hazard_order:
        # Skip if this hazard wasn't selected
        if hazard not in selected_hazards:
            continue
        # Normalize hazard name
        normalized_hazard = hazard_name_mapping.get(hazard, hazard)

        if normalized_hazard in column_mappings:
            # Count actual columns present for this hazard
            hazard_columns = [col for col in column_mappings[normalized_hazard] if col in columns]

            if hazard_columns:
                groups[normalized_hazard] = len(hazard_columns)
                logger.info(f"Added {normalized_hazard} group with {len(hazard_columns)} columns: {hazard_columns}")
            else:
                logger.info(f"No columns found for hazard type: {normalized_hazard}")
        else:
            logger.warning(f"Unknown hazard type: {normalized_hazard}")

    # Special handling for cases where hazard might be selected but no data is available
    # Check for any columns that contain hazard-related terms but weren't in our mapping
    additional_hazards = set()
    for column in columns:
        column_lower = column.lower()

        # Detect additional hazard columns that might not be in our mapping
        if any(term in column_lower for term in ['flood', 'water stress', 'heat', 'temperature',
                                                'sea level', 'cyclone', 'wind', 'storm surge',
                                                'landslide', 'rainfall']):

            # Try to categorize the column
            if 'flood' in column_lower and 'Flood' not in groups:
                additional_hazards.add('Flood')
            elif 'water stress' in column_lower and 'Water Stress' not in groups:
                additional_hazards.add('Water Stress')
            elif any(term in column_lower for term in ['heat', 'temperature', 'celsius']) and 'Heat' not in groups:
                additional_hazards.add('Heat')
            elif 'sea level' in column_lower and 'Sea Level Rise' not in groups:
                additional_hazards.add('Sea Level Rise')
            elif any(term in column_lower for term in ['cyclone', 'wind']) and 'Tropical Cyclones' not in groups:
                additional_hazards.add('Tropical Cyclones')
            elif 'storm surge' in column_lower and 'Storm Surge' not in groups:
                additional_hazards.add('Storm Surge')
            elif any(term in column_lower for term in ['landslide', 'rainfall']) and 'Rainfall-Induced Landslide' not in groups:
                additional_hazards.add('Rainfall-Induced Landslide')

    # Add any additional hazard groups found
    for hazard in additional_hazards:
        hazard_columns = [col for col in columns if hazard.lower() in col.lower()]
        if hazard_columns:
            groups[hazard] = len(hazard_columns)
            logger.info(f"Added additional {hazard} group with {len(hazard_columns)} columns: {hazard_columns}")

    logger.info(f"Final groups dictionary: {groups}")

    # Ensure we have at least some groups for the template to work
    if not groups:
        logger.warning("No groups were created, creating minimal group structure")
        groups = {
            'Facility Information': len([col for col in columns if col in ['Facility', 'Asset Archetype', 'Lat', 'Long']]),
            'Analysis Results': len([col for col in columns if col not in ['Facility', 'Asset Archetype', 'Lat', 'Long']])
        }
        logger.info(f"Created minimal groups: {groups}")

    return groups


def _execute_climate_analysis(facility_csv_path, selected_hazards):
    """
    Execute the climate hazards analysis.

    Args:
        facility_csv_path: Path to facility CSV file
        selected_hazards: List of selected hazard types

    Returns:
        dict: Analysis result or None if failed
    """
    logger.info("Calling generate_climate_hazards_analysis...")
    result = generate_climate_hazards_analysis(
        facility_csv_path=facility_csv_path,
        selected_fields=selected_hazards,
        flood_scenarios=['current', 'moderate', 'worst']
    )

    # Check for errors in the result
    if result is None or 'error' in result:
        error_message = result.get('error', 'Unknown error') if result else 'Analysis failed.'
        logger.error(f"Climate hazards analysis error: {error_message}")
        return None

    return result


def _load_and_process_combined_csv(combined_csv_path):
    """
    Load and process the combined CSV file with proper encoding handling.

    Args:
        combined_csv_path: Path to the combined CSV file

    Returns:
        tuple: (DataFrame, error_message) or (DataFrame, None) if successful
    """
    if not combined_csv_path or not os.path.exists(combined_csv_path):
        error_msg = f"Combined CSV not found: {combined_csv_path}"
        logger.error(error_msg)
        return None, 'Combined analysis output not found.'

    # Load the combined CSV file with encoding handling
    logger.info(f"Loading combined CSV from: {combined_csv_path}")

    encodings = ['utf-8', 'latin-1', 'cp1252']
    df = None

    for encoding in encodings:
        try:
            df = pd.read_csv(combined_csv_path, encoding=encoding)
            if encoding != 'utf-8':
                logger.warning(f"CSV file {combined_csv_path} read with {encoding} encoding")
            break
        except UnicodeDecodeError:
            continue

    if df is None:
        error_msg = f"Could not read CSV file {combined_csv_path} with any encoding"
        logger.error(error_msg)
        return None, error_msg

    # Normalize column names
    df.columns = df.columns.str.strip()

    return df, None


def _load_and_process_combined_json(combined_json_path):
    """
    Load and process the combined JSON file with proper error handling.

    Args:
        combined_json_path: Path to the combined JSON file

    Returns:
        tuple: (DataFrame, error_message) or (DataFrame, None) if successful
    """
    if not combined_json_path or not os.path.exists(combined_json_path):
        error_msg = f"Combined JSON not found: {combined_json_path}"
        logger.error(error_msg)
        return None, 'Combined analysis output file not found.'

    # Load the combined JSON file
    logger.info(f"Loading combined JSON from: {combined_json_path}")

    try:
        # Use the JSON loader to read the file
        from .json_csv_loader import json_csv_loader
        data, columns = json_csv_loader.load_analysis_results(json_path=combined_json_path)

        # Convert to DataFrame for compatibility with existing code
        df = pd.DataFrame(data)

        if df.empty:
            error_msg = f"JSON file loaded but resulted in empty DataFrame: {combined_json_path}"
            logger.warning(error_msg)
            return df, error_msg

        logger.info(f"Successfully loaded JSON with {len(df)} records and {len(df.columns)} columns")
        return df, None

    except Exception as e:
        error_msg = f"Error loading JSON file {combined_json_path}: {str(e)}"
        logger.error(error_msg)
        return None, error_msg


def _validate_and_fix_data_columns(df, selected_hazards):
    """
    Validate and fix data columns for the analysis results.

    Args:
        df: DataFrame with analysis results
        selected_hazards: List of selected hazard types

    Returns:
        DataFrame: Validated and fixed DataFrame
    """
    # This is a placeholder function - implement as needed
    return df


def _process_tropical_cyclone_data(df, facility_csv_path):
    """
    Process tropical cyclone data for the analysis results.

    Args:
        df: DataFrame with analysis results
        facility_csv_path: Path to facility CSV file

    Returns:
        DataFrame: DataFrame with tropical cyclone data processed
    """
    # This is a placeholder function - implement as needed
    return df


def _add_asset_archetype_info(df, facility_csv_path):
    """
    Add asset archetype information to the analysis results.

    Args:
        df: DataFrame with analysis results
        facility_csv_path: Path to facility CSV file

    Returns:
        DataFrame: DataFrame with asset archetype information added
    """
    try:
        # Read the facility CSV to get archetype information
        if facility_csv_path and os.path.exists(facility_csv_path):
            try:
                facility_df = pd.read_csv(facility_csv_path, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    facility_df = pd.read_csv(facility_csv_path, encoding='latin-1')
                except UnicodeDecodeError:
                    facility_df = pd.read_csv(facility_csv_path, encoding='cp1252')

            # Look for Asset Archetype column with various naming conventions
            archetype_column = None
            possible_names = [
                'Asset Archetype', 'asset archetype', 'AssetArchetype', 'assetarchetype',
                'Archetype', 'archetype', 'Asset Type', 'asset type', 'AssetType', 'assettype',
                'Type', 'type', 'Category', 'category', 'Asset Category', 'asset category'
            ]

            for col_name in possible_names:
                if col_name in facility_df.columns:
                    archetype_column = col_name
                    break

            if archetype_column:
                logger.info(f"Found Asset Archetype column: '{archetype_column}'")

                # Create mapping from facility name to archetype
                archetype_mapping = {}
                for _, row in facility_df.iterrows():
                    # Try multiple facility name columns
                    facility_name = None
                    for name_col in ['Facility', 'Site', 'Name', 'Asset Name']:
                        if name_col in facility_df.columns and pd.notna(row.get(name_col)):
                            facility_name = str(row.get(name_col)).strip()
                            break

                    archetype = str(row.get(archetype_column, '')).strip()
                    if facility_name and archetype and archetype.lower() not in ['', 'nan', 'none']:
                        archetype_mapping[facility_name] = archetype

                logger.info(f"Created archetype mapping for {len(archetype_mapping)} facilities")

                # Add Asset Archetype column to the results DataFrame
                df['Asset Archetype'] = df['Facility'].map(archetype_mapping)

                # Fill missing values with 'Default'
                df['Asset Archetype'] = df['Asset Archetype'].fillna('Default')

                # Reorder columns to put Asset Archetype as the 2nd column (after Facility)
                if 'Asset Archetype' in df.columns and 'Facility' in df.columns:
                    cols = df.columns.tolist()
                    facility_idx = cols.index('Facility')

                    # Remove Asset Archetype from its current position
                    if 'Asset Archetype' in cols:
                        cols.remove('Asset Archetype')

                    # Insert Asset Archetype after Facility
                    cols.insert(facility_idx + 1, 'Asset Archetype')
                    df = df[cols]

                logger.info(f"Successfully added Asset Archetype column to results")
                logger.info(f"Asset Archetype value counts: {df['Asset Archetype'].value_counts()}")

            else:
                logger.warning(f"No Asset Archetype column found in facility CSV. Available columns: {facility_df.columns.tolist()}")
                # Add default Asset Archetype column
                df['Asset Archetype'] = 'Default'

                # Reorder columns to put Asset Archetype as the 2nd column
                if 'Asset Archetype' in df.columns and 'Facility' in df.columns:
                    cols = df.columns.tolist()
                    facility_idx = cols.index('Facility')

                    # Remove Asset Archetype from its current position
                    if 'Asset Archetype' in cols:
                        cols.remove('Asset Archetype')

                    # Insert Asset Archetype after Facility
                    cols.insert(facility_idx + 1, 'Asset Archetype')
                    df = df[cols]
        else:
            logger.warning("Facility CSV file not found or doesn't exist")
            # Add default Asset Archetype column
            df['Asset Archetype'] = 'Default'

            # Reorder columns to put Asset Archetype as the 2nd column
            if 'Asset Archetype' in df.columns and 'Facility' in df.columns:
                cols = df.columns.tolist()
                facility_idx = cols.index('Facility')

                # Remove Asset Archetype from its current position
                if 'Asset Archetype' in cols:
                    cols.remove('Asset Archetype')

                # Insert Asset Archetype after Facility
                cols.insert(facility_idx + 1, 'Asset Archetype')
                df = df[cols]

    except Exception as e:
        logger.exception(f"Error adding asset archetype information: {e}")
        # Add default Asset Archetype column even on error
        df['Asset Archetype'] = 'Default'

        # Reorder columns to put Asset Archetype as the 2nd column
        if 'Asset Archetype' in df.columns and 'Facility' in df.columns:
            cols = df.columns.tolist()
            facility_idx = cols.index('Facility')

            # Remove Asset Archetype from its current position
            if 'Asset Archetype' in cols:
                cols.remove('Asset Archetype')

            # Insert Asset Archetype after Facility
            cols.insert(facility_idx + 1, 'Asset Archetype')
            df = df[cols]

    return df


def generate_report(request):
    """
    Django view that generates the PDF report and returns it as an HTTP response.
    Updated to handle simplified flood categories.
    """
    # Get selected hazards and facility data
    selected_fields = request.session.get('climate_hazards_v2_selected_hazards', [])
    facility_data = request.session.get('climate_hazards_v2_facility_data', [])
    
    # Try to get results data if available
    results_data = request.session.get('climate_hazards_v2_results', {})
    if not selected_fields and results_data:
        selected_fields = results_data.get('selected_hazards', [])
    
    # Get the analysis data needed for high-risk asset identification
    analysis_data = []
    if results_data and 'data' in results_data:
        analysis_data = results_data.get('data', [])
    elif 'combined_csv_path' in request.session:
        # Load from CSV if available
        csv_path = request.session.get('combined_csv_path')
        if csv_path and os.path.exists(csv_path):
            try:
                import pandas as pd
                df = pd.read_csv(csv_path)
                analysis_data = df.to_dict(orient='records')
            except Exception as e:
                print(f"Error loading data for report: {e}")
    
    # Identify high-risk assets for each hazard type
    high_risk_assets = identify_high_risk_assets(analysis_data, selected_fields)

    # Get high-risk counts from sensitivity results
    sensitivity_results = request.session.get('climate_hazards_v2_sensitivity_results')
    risk_counts = compute_sensitivity_high_risk_counts(sensitivity_results, selected_fields) if sensitivity_results else {}
    
    # Initialize a BytesIO buffer for the PDF
    buffer = BytesIO()
    
    # Generate the PDF report with dynamic high-risk assets
    generate_climate_hazards_report_pdf(
        buffer,
        selected_fields,
        high_risk_assets=high_risk_assets,
        risk_counts=risk_counts,
    )
    
    # Get the PDF content
    pdf = buffer.getvalue()
    buffer.close()
    
    # Create and return the HTTP response with the PDF
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="Climate_Hazard_Exposure_Report_V2.pdf"'
    return response

def identify_high_risk_assets(data, selected_hazards):
    """
    Identify assets with high risk ratings for each hazard type.
    Updated to handle simplified flood categories.
    
    Args:
        data (list): List of dictionaries containing facility data with hazard ratings
        selected_hazards (list): List of selected hazard types
        
    Returns:
        dict: Dictionary mapping hazard types to lists of high-risk assets
    """
    high_risk_assets = {}
    
    # Define thresholds for high risk by hazard type (updated for simplified flood categories)
    thresholds = {
        'Flood': {
            'column': 'Flood Depth (meters)',
            'criteria': lambda v: v in ['Greater than 1.5', 'High Risk']  # Support both old and new categories
        },
        'Water Stress': {
            'column': 'Water Stress Exposure (%)',
            'criteria': lambda v: isinstance(v, (int, float)) and v > 30
        },
        'Heat': {
            'columns': {
                'Days over 30° Celsius': lambda v: isinstance(v, (int, float)) and v >= 300,
                'Days over 33° Celsius': lambda v: isinstance(v, (int, float)) and v >= 100,
                'Days over 35° Celsius': lambda v: isinstance(v, (int, float)) and v >= 30
            },
            'criteria': lambda row, cols: any(cols[col](row.get(col)) for col in cols if col in row)
        },
        'Sea Level Rise': {
            'column': '2050 Sea Level Rise (meters) - Worst Case',
            'criteria': lambda v: v != 'Little to none' and isinstance(v, (int, float)) and v > 0.5
        },
        'Tropical Cyclones': {
            'column': 'Extreme Windspeed 100 year Return Period (km/h)',
            'criteria': lambda v: v != 'Data not available' and isinstance(v, (int, float)) and v >= 178
        },
        'Storm Surge': {
            'column': 'Storm Surge Flood Depth (meters)',
            'criteria': lambda v: isinstance(v, (int, float)) and v >= 1.5
        },
        'Rainfall Induced Landslide': {
            'column': 'Rainfall-Induced Landslide (factor of safety)',
            'criteria': lambda v: isinstance(v, (int, float)) and v < 1
        }
    }
    
    # Process each selected hazard
    for hazard in selected_hazards:
        if hazard not in thresholds:
            continue
        
        high_risk_assets[hazard] = []
        threshold = thresholds[hazard]
        
        for asset in data:
            facility_name = asset.get('Facility', 'Unknown')
            
            # Special case for Heat which has multiple columns
            if hazard == 'Heat' and 'columns' in threshold:
                if threshold['criteria'](asset, threshold['columns']):
                    high_risk_assets[hazard].append({
                        'name': facility_name,
                        'lat': asset.get('Lat'),
                        'lng': asset.get('Long')
                    })
                continue
            
            # Standard case with single column
            column = threshold.get('column')
            if column in asset:
                value = asset[column]
                try:
                    # Try to convert string values to numbers if possible
                    if isinstance(value, str) and value not in ['N/A', 'Little to none', 'Data not available',
                                                               '0.1 to 0.5', '0.5 to 1.5', 'Greater than 1.5', 'Unknown']:
                        try:
                            value = float(value)
                        except ValueError:
                            pass
                    
                    if threshold['criteria'](value):
                        high_risk_assets[hazard].append({
                            'name': facility_name,
                            'lat': asset.get('Lat'),
                            'lng': asset.get('Long')
                        })
                except (TypeError, ValueError):
                    continue
    
    return high_risk_assets

def compute_sensitivity_high_risk_counts(sensitivity_results, selected_hazards):
    """Compute high-risk asset counts for current and future scenarios."""
    if not sensitivity_results:
        return {}

    data = sensitivity_results.get('data', [])
    counts = {h: {'current': 0, 'future_moderate': 0, 'future_worst': 0} for h in selected_hazards}

    hazard_thresholds = {
        'Water Stress': {
            'current': [('Water Stress Exposure (%)', lambda v: isinstance(v, (int, float)) and v > 30)],
            'future_moderate': [
                ('Water Stress Exposure 2030 (%) - Moderate Case', lambda v: isinstance(v, (int, float)) and v > 30),
                ('Water Stress Exposure 2050 (%) - Moderate Case', lambda v: isinstance(v, (int, float)) and v > 30),
            ],
            'future_worst': [
                ('Water Stress Exposure 2030 (%) - Worst Case', lambda v: isinstance(v, (int, float)) and v > 30),
                ('Water Stress Exposure 2050 (%) - Worst Case', lambda v: isinstance(v, (int, float)) and v > 30),
            ],
        },
        'Heat': {
            'current': [
                ('Days over 30° Celsius', lambda v: isinstance(v, (int, float)) and v >= 300),
                ('Days over 33° Celsius', lambda v: isinstance(v, (int, float)) and v >= 100),
                ('Days over 35° Celsius', lambda v: isinstance(v, (int, float)) and v >= 30),
            ],
            'future_moderate': [
                ('Days over 35° Celsius (2026 - 2030) - Moderate Case', lambda v: isinstance(v, (int, float)) and v >= 30),
                ('Days over 35° Celsius (2031 - 2040) - Moderate Case', lambda v: isinstance(v, (int, float)) and v >= 30),
                ('Days over 35° Celsius (2041 - 2050) - Moderate Case', lambda v: isinstance(v, (int, float)) and v >= 30),
            ],
            'future_worst': [
                ('Days over 35° Celsius (2026 - 2030) - Worst Case', lambda v: isinstance(v, (int, float)) and v >= 30),
                ('Days over 35° Celsius (2031 - 2040) - Worst Case', lambda v: isinstance(v, (int, float)) and v >= 30),
                ('Days over 35° Celsius (2041 - 2050) - Worst Case', lambda v: isinstance(v, (int, float)) and v >= 30),
            ],
        },
        'Flood': {
            'current': [('Flood Depth (meters)', lambda v: v in ['Greater than 1.5', 'High Risk'])],
            'future_moderate': [],
            'future_worst': [],
        },
        'Sea Level Rise': {
            'current': [],
            'future_moderate': [('2050 Sea Level Rise (meters) - Moderate Case', lambda v: isinstance(v, (int, float)) and v > 0.5)],
            'future_worst': [('2050 Sea Level Rise (meters) - Worst Case', lambda v: isinstance(v, (int, float)) and v > 0.5)],
        },
        'Tropical Cyclones': {
            'current': [('Extreme Windspeed 100 year Return Period (km/h)', lambda v: isinstance(v, (int, float)) and v >= 178)],
            'future_moderate': [],
            'future_worst': [],
        },
        'Storm Surge': {
            'current': [('Storm Surge Flood Depth (meters)', lambda v: isinstance(v, (int, float)) and v >= 1.5)],
            'future_moderate': [],
            'future_worst': [('Storm Surge Flood Depth (meters) - Worst Case', lambda v: isinstance(v, (int, float)) and v >= 1.5)],
        },
        'Rainfall Induced Landslide': {
            'current': [('Rainfall-Induced Landslide (factor of safety)', lambda v: isinstance(v, (int, float)) and v < 1)],
            'future_moderate': [('Rainfall-Induced Landslide (factor of safety) - Moderate Case', lambda v: isinstance(v, (int, float)) and v < 1)],
            'future_worst': [('Rainfall-Induced Landslide (factor of safety) - Worst Case', lambda v: isinstance(v, (int, float)) and v < 1)],
        },
    }

    for row in data:
        for hazard in selected_hazards:
            thresholds = hazard_thresholds.get(hazard, {})
            for scenario in ['current', 'future_moderate', 'future_worst']:
                for col_name, criterion in thresholds.get(scenario, []):
                    if col_name in row:
                        value = row[col_name]
                        try:
                            if isinstance(value, str) and value not in ['N/A', 'Little to none', 'Data not available',
                                                                       'Not material', '0.1 to 0.5', '0.5 to 1.5',
                                                                       'Greater than 1.5', 'Unknown']:
                                value = float(value)
                        except ValueError:
                            pass
                        try:
                            if criterion(value):
                                counts[hazard][scenario] += 1
                                break
                        except Exception:
                            continue

    return counts

def sensitivity_parameters(request):
    """
    View for setting sensitivity parameters for climate hazard analysis.
    This is the fourth step in the climate hazard analysis workflow.
    """
    # Get facility data and selected hazards from session
    facility_data = request.session.get('climate_hazards_v2_facility_data', [])
    selected_hazards = request.session.get('climate_hazards_v2_selected_hazards', [])

    # Check if we have the necessary data from previous steps
    if not facility_data or not selected_hazards:
        return redirect('climate_hazards_analysis_v2:select_hazards')

    # Extract Asset Archetypes from the facility data
    asset_archetypes = []
    facility_csv_path = request.session.get('climate_hazards_v2_facility_csv_path')

    if facility_csv_path and os.path.exists(facility_csv_path):
        try:
            # Read the CSV file to get asset archetypes
            try:
                df = pd.read_csv(facility_csv_path, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(facility_csv_path, encoding='latin-1')
                except UnicodeDecodeError:
                    df = pd.read_csv(facility_csv_path, encoding='cp1252')
            
            # Look for Asset Archetype column with various naming conventions
            archetype_column = None
            possible_names = [
                'Asset Archetype', 'asset archetype', 'AssetArchetype', 'assetarchetype',
                'Archetype', 'archetype', 'Asset Type', 'asset type', 'AssetType', 'assettype',
                'Type', 'type', 'Category', 'category', 'Asset Category', 'asset category'
            ]
            
            for col_name in possible_names:
                if col_name in df.columns:
                    archetype_column = col_name
                    break
            
            if archetype_column:
                # Get unique asset archetypes, removing NaN values and sorting
                unique_archetypes = df[archetype_column].dropna().unique()
                unique_archetypes = sorted([str(arch).strip() for arch in unique_archetypes if str(arch).strip()])
                
                # Create numbered list
                asset_archetypes = [
                    {'number': i + 1, 'name': archetype} 
                    for i, archetype in enumerate(unique_archetypes)
                ]
                
                logger.info(f"Found {len(asset_archetypes)} asset archetypes in column '{archetype_column}'")
            else:
                logger.warning("No Asset Archetype column found in the facility CSV")
                asset_archetypes = [{'number': 1, 'name': 'Default Archetype'}]
                
        except Exception as e:
            logger.exception(f"Error reading asset archetypes from CSV: {e}")
            asset_archetypes = [{'number': 1, 'name': 'Default Archetype'}]
    else:
        asset_archetypes = [{'number': 1, 'name': 'Default Archetype'}]

    # Get existing archetype parameters from session to restore checkbox states
    archetype_params = request.session.get('climate_hazards_v2_archetype_params', {})
    # Convert to JSON string for JavaScript consumption
    import json
    archetype_params_json = json.dumps(archetype_params)

    context = {
        'facility_count': len(facility_data),
        'selected_hazards': selected_hazards,
        'asset_archetypes': asset_archetypes,
        'archetype_params': archetype_params,
        'archetype_params_json': archetype_params_json,
    }

    # Handle form submission
    if request.method == 'POST':
        try:
            # Get the selected archetype
            selected_archetype = request.POST.get('selected_archetype', '').strip()
            
            # Extract Water Stress sensitivity parameters from the form
            water_stress_params = {
                'water_stress_low': parse_numeric(request.POST.get('water_stress_low', 10)),
                'water_stress_high': parse_numeric(request.POST.get('water_stress_high', 31)),
                'water_stress_not_material': int(request.POST.get('water_stress_not_material', 0)),
            }

            # Extract Heat sensitivity parameters from the form
            heat_params = {
                'heat_low': parse_numeric(request.POST.get('heat_low', 10)),
                'heat_high': parse_numeric(request.POST.get('heat_high', 45)),
                'heat_not_material': int(request.POST.get('heat_not_material', 0)),
            }

            # Extract Flood sensitivity parameters from the form
            flood_params = {
                'flood_low': parse_numeric(request.POST.get('flood_low', 0.5)),
                'flood_high': parse_numeric(request.POST.get('flood_high', 1.5)),
                'flood_not_material': int(request.POST.get('flood_not_material', 0)),
            }

            # Extract Tropical Cyclone sensitivity parameters from the form
            tropical_cyclone_params = {
                'tropical_cyclone_low': parse_numeric(request.POST.get('tropical_cyclone_low', 119)),
                'tropical_cyclone_high': parse_numeric(request.POST.get('tropical_cyclone_high', 178)),
                'tropical_cyclone_not_material': int(request.POST.get('tropical_cyclone_not_material', 0)),
            }

            # Extract Storm Surge sensitivity parameters from the form
            storm_surge_params = {
                'storm_surge_low': parse_numeric(request.POST.get('storm_surge_low', 0.5)),
                'storm_surge_high': parse_numeric(request.POST.get('storm_surge_high', 1.5)),
                'storm_surge_not_material': int(request.POST.get('storm_surge_not_material', 0)),
            }

            # Extract Rainfall-Induced Landslide sensitivity parameters from the form
            landslide_params = {
                'landslide_low': parse_numeric(request.POST.get('landslide_low', 1)),
                'landslide_high': parse_numeric(request.POST.get('landslide_high', 1.5)),
                'landslide_not_material': int(request.POST.get('landslide_not_material', 0)),
            }
            
            logger.info(f"Water Stress parameters received: {water_stress_params}")
            logger.info(f"Heat parameters received: {heat_params}")
            
            # Get existing archetype parameters from session
            archetype_params = request.session.get('climate_hazards_v2_archetype_params', {})
            old_archetype_params = copy.deepcopy(archetype_params)
            
            # Check if archetype parameters were submitted through the form
            collected_archetype_params = {}
            for key in request.POST.keys():
                if key.startswith('archetype_params['):
                    # Parse the archetype_params[archetype_name][param_name] format
                    import re
                    match = re.match(r'archetype_params\[([^\]]+)\]\[([^\]]+)\]', key)
                    if match:
                        archetype_name, param_name = match.groups()
                        if archetype_name not in collected_archetype_params:
                            collected_archetype_params[archetype_name] = {}
                        collected_archetype_params[archetype_name][param_name] = parse_numeric(request.POST.get(key))

            # Combine parameters
            combined_params = {
                **water_stress_params,
                **heat_params,
                **flood_params,
                **tropical_cyclone_params,
                **storm_surge_params,
                **landslide_params,
            }
            
            # Use collected parameters if they exist, otherwise use current form values
            if collected_archetype_params:
                archetype_params.update(collected_archetype_params)
                logger.info(f"Updated archetype parameters from form submission: {collected_archetype_params}")
            elif selected_archetype:
                archetype_params[selected_archetype] = combined_params
                logger.info(f"Saved parameters for archetype '{selected_archetype}': {combined_params}")
            else:
                archetype_params['_default'] = combined_params
                logger.info(f"Saved default parameters: {combined_params}")
            
            # Update session with archetype parameters
            request.session['climate_hazards_v2_archetype_params'] = archetype_params

            # Determine which archetypes had revised parameters compared to previous values
            hazard_keys = ['water_stress', 'heat', 'flood',
                           'tropical_cyclone', 'storm_surge', 'landslide']
            revised_params = {}
            for arch, params in archetype_params.items():
                changed_hazards = {}
                old_params = old_archetype_params.get(arch, {})
                for key in hazard_keys:
                    low_key = f"{key}_low"
                    high_key = f"{key}_high"
                    if params.get(low_key) != old_params.get(low_key) or params.get(high_key) != old_params.get(high_key):
                        changed_hazards[key] = {
                            'low': params.get(low_key),
                            'high': params.get(high_key),
                        }
                if changed_hazards:
                    revised_params[arch] = changed_hazards

            request.session['climate_hazards_v2_revised_params'] = revised_params

            request.session.modified = True
            
            # Check if Apply Parameters button was clicked (default to apply)
            submit_type = request.POST.get('submit_type', 'apply-parameters-btn')
            if submit_type == 'apply-parameters-btn':
                logger.info("Redirecting to sensitivity results")
                return redirect('climate_hazards_analysis_v2:sensitivity_results')
            else:
                context['success_message'] = "Sensitivity parameters saved!"
            
        except (ValueError, TypeError) as e:
            handle_sensitivity_param_error(context, e)
        except Exception as e:
            logger.exception(f"Unexpected error in sensitivity parameter processing: {e}")
            context['error'] = "An unexpected error occurred while processing parameters."

    # For GET requests or if there was an error, show the form
    return render(request, 'climate_hazards_analysis_v2/sensitivity_parameters.html', context)


def sensitivity_results(request):
    """
    View to display climate hazard analysis results with archetype-specific sensitivity parameters.
    This is step 5 in the climate hazard analysis workflow.
    """
    # Get facility data and selected hazards from session
    facility_data = request.session.get('climate_hazards_v2_facility_data', [])
    selected_hazards = request.session.get('climate_hazards_v2_selected_hazards', [])
    facility_csv_path = request.session.get('climate_hazards_v2_facility_csv_path')
    archetype_params = request.session.get('climate_hazards_v2_archetype_params', {})
    
    # Ensure we have analysis results; if not, try to build a fallback from uploaded assets
    original_results = request.session.get('climate_hazards_v2_results')
    if not original_results:
        unified_assets = _get_all_uploaded_assets_json(request)
        if unified_assets and unified_assets.get('data'):
            fallback_data = unified_assets['data']
            first_row = fallback_data[0] if fallback_data else {}
            fallback_columns = list(first_row.keys()) if isinstance(first_row, dict) else []
            original_results = {
                'data': fallback_data,
                'columns': fallback_columns
            }
            request.session['climate_hazards_v2_results'] = original_results
            if 'climate_hazards_v2_baseline_results' not in request.session:
                request.session['climate_hazards_v2_baseline_results'] = copy.deepcopy(original_results)
            request.session.modified = True

    # Check if we have the necessary data
    if not facility_data or not selected_hazards:
        return redirect('climate_hazards_analysis_v2:select_hazards')
    
    if not archetype_params:
        return render(request, 'climate_hazards_analysis_v2/sensitivity_parameters.html', {
            'error': 'No sensitivity parameters found. Please set sensitivity parameters first.',
            'facility_count': len(facility_data),
            'selected_hazards': selected_hazards,
            'asset_archetypes': []
        })
    
    try:
        logger.info(f"Starting sensitivity results processing for {len(facility_data)} facilities")
        logger.info(f"Selected hazards: {selected_hazards}")
        logger.info(f"Archetype parameters: {archetype_params}")
        
        # Get the original analysis results from step 3
        original_results = request.session.get('climate_hazards_v2_results')
        if not original_results:
            logger.error("Original analysis results not found in session")
            return redirect('climate_hazards_analysis_v2:show_results')
        
        # Create a copy of the original data for sensitivity analysis
        sensitivity_data = copy.deepcopy(original_results['data'])
        columns = original_results['columns'].copy()
        
        # Remove Lat and Long columns from the sensitivity results
        columns_to_remove = ['Lat', 'Long']
        for col_to_remove in columns_to_remove:
            if col_to_remove in columns:
                columns.remove(col_to_remove)
        
        # Remove Lat and Long from each data row
        for row in sensitivity_data:
            for col_to_remove in columns_to_remove:
                if col_to_remove in row:
                    del row[col_to_remove]
        
        logger.info(f"Removed Lat/Long columns. Remaining columns: {columns}")
        logger.info(f"Loaded original data with {len(sensitivity_data)} rows")
        
        # Load the facility CSV to get archetype information
        archetype_mapping = {}
        if facility_csv_path and os.path.exists(facility_csv_path):
            try:
                df = pd.read_csv(facility_csv_path, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(facility_csv_path, encoding='latin-1')
                except UnicodeDecodeError:
                    df = pd.read_csv(facility_csv_path, encoding='cp1252')
            
            logger.info(f"Loaded CSV with columns: {df.columns.tolist()}")
            
            # Find archetype column
            archetype_column = None
            possible_names = [
                'Asset Archetype', 'asset archetype', 'AssetArchetype', 'assetarchetype',
                'Archetype', 'archetype', 'Asset Type', 'asset type', 'AssetType', 'assettype',
                'Type', 'type', 'Category', 'category', 'Asset Category', 'asset category'
            ]
            
            for col_name in possible_names:
                if col_name in df.columns:
                    archetype_column = col_name
                    break
            
            if archetype_column:
                logger.info(f"Found archetype column: '{archetype_column}'")
                # Create mapping from facility name to archetype
                for _, row in df.iterrows():
                    # Try multiple facility name columns
                    facility_name = None
                    for name_col in ['Facility', 'Site', 'Name', 'Asset Name']:
                        if name_col in df.columns and pd.notna(row.get(name_col)):
                            facility_name = str(row.get(name_col)).strip()
                            break
                    
                    archetype = str(row.get(archetype_column, '')).strip()
                    if facility_name and archetype and archetype.lower() not in ['', 'nan', 'none']:
                        archetype_mapping[facility_name] = archetype
                        logger.info(f"Mapped '{facility_name}' → '{archetype}'")
                
                logger.info(f"Created archetype mapping for {len(archetype_mapping)} facilities")
                logger.info(f"Archetype mapping: {archetype_mapping}")
            else:
                logger.warning(f"No archetype column found. Available columns: {df.columns.tolist()}")
        else:
            logger.warning("Facility CSV file not found or doesn't exist")

        # Mapping of not-material flags to their corresponding result columns
        hazard_to_columns = {
            'water_stress_not_material': ['Water Stress Exposure (%)',
                'Water Stress Exposure 2030 (%) - Moderate Case',
                'Water Stress Exposure 2050 (%) - Moderate Case',
                'Water Stress Exposure 2030 (%) - Worst Case',
                'Water Stress Exposure 2050 (%) - Worst Case'],
            'flood_not_material': ['Flood Depth (meters)'],
            'heat_not_material': [
                'Days over 30° Celsius',
                'Days over 33° Celsius',
                'Days over 35° Celsius',
                'Days over 35° Celsius (2026 - 2030) - Moderate Case',
                'Days over 35° Celsius (2031 - 2040) - Moderate Case',
                'Days over 35° Celsius (2041 - 2050) - Moderate Case',
                'Days over 35° Celsius (2026 - 2030) - Worst Case',
                'Days over 35° Celsius (2031 - 2040) - Worst Case',
                'Days over 35° Celsius (2041 - 2050) - Worst Case',
            ],
            'tropical_cyclone_not_material': [
                'Extreme Windspeed 10 year Return Period (km/h)',
                'Extreme Windspeed 20 year Return Period (km/h)',
                'Extreme Windspeed 50 year Return Period (km/h)',
                'Extreme Windspeed 100 year Return Period (km/h)',
                'Extreme Windspeed 10 year Return Period (km/h) - Moderate Case',
                'Extreme Windspeed 20 year Return Period (km/h) - Moderate Case',
                'Extreme Windspeed 50 year Return Period (km/h) - Moderate Case',
                'Extreme Windspeed 100 year Return Period (km/h) - Moderate Case',
                'Extreme Windspeed 10 year Return Period (km/h) - Worst Case',
                'Extreme Windspeed 20 year Return Period (km/h) - Worst Case',
                'Extreme Windspeed 50 year Return Period (km/h) - Worst Case',
                'Extreme Windspeed 100 year Return Period (km/h) - Worst Case',
            ],
            'storm_surge_not_material': [
                'Storm Surge Flood Depth (meters)',
                'Storm Surge Flood Depth (meters) - Worst Case',
            ],
            'landslide_not_material': [
                'Rainfall-Induced Landslide (factor of safety)',
                'Rainfall-Induced Landslide (factor of safety) - Moderate Case',
                'Rainfall-Induced Landslide (factor of safety) - Worst Case',
            ],
        }

        # Apply archetype-specific Water Stress sensitivity parameters
        if 'Water Stress' in selected_hazards and 'Water Stress Exposure (%)' in columns:
            # Debug: log all facility names from sensitivity data
            sensitivity_facility_names = [row.get('Facility', '') for row in sensitivity_data]
            logger.info(f"Facility names in sensitivity data: {sensitivity_facility_names}")
            logger.info(f"Facility names in archetype mapping: {list(archetype_mapping.keys())}")
            
            for row in sensitivity_data:
                facility_name = row.get('Facility', '').strip()
                archetype = archetype_mapping.get(facility_name)
                
                if not archetype:
                    # If no exact match, try to find a partial match
                    for mapped_name, mapped_archetype in archetype_mapping.items():
                        # Try different matching strategies
                        if (facility_name.lower() in mapped_name.lower() or 
                            mapped_name.lower() in facility_name.lower() or
                            facility_name.lower().replace(' ', '') == mapped_name.lower().replace(' ', '')):
                            archetype = mapped_archetype
                            logger.info(f"Used partial match: '{facility_name}' → '{mapped_name}' → '{archetype}'")
                            break
                
                if not archetype:
                    # Try removing common prefixes/suffixes and matching
                    clean_facility_name = facility_name.lower().strip()
                    for mapped_name, mapped_archetype in archetype_mapping.items():
                        clean_mapped_name = mapped_name.lower().strip()
                        # Check if core facility names match (ignoring common words)
                        facility_words = set(clean_facility_name.split())
                        mapped_words = set(clean_mapped_name.split())
                        # If they share at least 2 words, consider it a match
                        if len(facility_words.intersection(mapped_words)) >= 2:
                            archetype = mapped_archetype
                            logger.info(f"Used word-based match: '{facility_name}' → '{mapped_name}' → '{archetype}'")
                            break
                
                if not archetype:
                    archetype = 'Default'
                    logger.warning(f"No archetype found for facility '{facility_name}', using 'Default'")
                else:
                    logger.info(f"Assigned archetype '{archetype}' to facility '{facility_name}'")
                
                # Get parameters for this archetype (or default)
                params = archetype_params.get(archetype, archetype_params.get('_default', {
                    'water_stress_low': 10,
                    'water_stress_high': 31,
                    'storm_surge_low': 0.5,
                    'storm_surge_high': 1.5,
                    'landslide_low': 1,
                    'landslide_high': 1.5,
                }))
                
                # Store the archetype and parameters used for this facility (for template access)
                row['Asset Archetype'] = archetype
                row['WS_Low_Threshold'] = params['water_stress_low']
                row['WS_High_Threshold'] = params['water_stress_high']
                row['SS_Low_Threshold'] = params.get('storm_surge_low', 0.5)
                row['SS_High_Threshold'] = params.get('storm_surge_high', 1.5)
                row['TC_Low_Threshold'] = params.get('tropical_cyclone_low', 119)
                row['TC_High_Threshold'] = params.get('tropical_cyclone_high', 178)
                row['Heat_Low_Threshold'] = params.get('heat_low', 10)
                row['Heat_High_Threshold'] = params.get('heat_high', 45)
                
                # Overwrite hazard values with "Not material" when flagged
                for nm_key, cols in hazard_to_columns.items():
                    if params.get(nm_key):
                        for col in cols:
                            if col in row:
                                row[col] = 'Not material'

                logger.info(
                    f"Applied thresholds for '{facility_name}' ({archetype}): "
                    f"Low<{params['water_stress_low']}%, High>{params['water_stress_high']}%"
                )
        
        # Add new columns to the columns list and reorder to put Asset Archetype as 2nd column
        new_columns = ['Asset Archetype']
        
        # Reorder columns to put Asset Archetype as 2nd column
        if 'Asset Archetype' not in columns:
            # Create new ordered columns list
            ordered_columns = []
            
            # Add Facility first
            if 'Facility' in columns:
                ordered_columns.append('Facility')
            
            # Add Asset Archetype second
            ordered_columns.append('Asset Archetype')
            
            # Add remaining columns (excluding the ones we're repositioning)
            for col in columns:
                if col not in ['Facility', 'Asset Archetype']:
                    ordered_columns.append(col)
            
            # Update the columns list
            columns = ordered_columns
            
            logger.info(f"Reordered columns for sensitivity results: {columns}")
        
        # CRITICAL: Reorder the actual row data to match the column order
        # This ensures that when the template iterates through row.items(), 
        # the values appear in the correct column positions
        reordered_data = []
        for row in sensitivity_data:
            ordered_row = {}
            for column in columns:
                if column in row:
                    ordered_row[column] = row[column]
                else:
                    ordered_row[column] = 'N/A'  # Default for missing columns

            # Preserve threshold values for template logic without displaying them
            for thresh in ['WS_Low_Threshold', 'WS_High_Threshold', 'SS_Low_Threshold', 'SS_High_Threshold',
                          'TC_Low_Threshold', 'TC_High_Threshold', 'Heat_Low_Threshold', 'Heat_High_Threshold']:
                if thresh in row:
                    ordered_row[thresh] = row[thresh]
            reordered_data.append(ordered_row)
        
        sensitivity_data = reordered_data
        logger.info(f"Reordered row data to match column order. Sample row keys: {list(sensitivity_data[0].keys()) if sensitivity_data else 'No data'}")
        
        logger.info(f"Applied sensitivity parameters to {len(sensitivity_data)} facilities")
        
        # Create detailed column groups for the table header (same as original but with new columns)
        groups = {}
        # Base group - Facility Information
        facility_cols = [
            'Facility',
            'Lat',
            'Long',
            'Asset Archetype'
        ]
        facility_count = sum(1 for col in facility_cols if col in columns)
        if facility_count > 0:
            groups['Facility Information'] = facility_count
        
        # Create a mapping for each hazard type and its columns (excluding separate risk level column)
        hazard_columns = {
            'Flood': ['Flood Depth (meters)'],
            'Water Stress': [
                'Water Stress Exposure (%)',
                'Water Stress Exposure 2030 (%) - Moderate Case',
                'Water Stress Exposure 2050 (%) - Moderate Case',
                'Water Stress Exposure 2030 (%) - Worst Case',
                'Water Stress Exposure 2050 (%) - Worst Case'
            ],
            'Sea Level Rise': [
                '2030 Sea Level Rise (meters) - Moderate Case',
                '2040 Sea Level Rise (meters) - Moderate Case',
                '2050 Sea Level Rise (meters) - Moderate Case',
                '2030 Sea Level Rise (meters) - Worst Case',
                '2040 Sea Level Rise (meters) - Worst Case',
                '2050 Sea Level Rise (meters) - Worst Case'
            ],
            'Tropical Cyclones': [
                'Extreme Windspeed 10 year Return Period (km/h)',
                'Extreme Windspeed 20 year Return Period (km/h)',
                'Extreme Windspeed 50 year Return Period (km/h)',
                'Extreme Windspeed 100 year Return Period (km/h)',
                'Extreme Windspeed 10 year Return Period (km/h) - Moderate Case',
                'Extreme Windspeed 20 year Return Period (km/h) - Moderate Case',
                'Extreme Windspeed 50 year Return Period (km/h) - Moderate Case',
                'Extreme Windspeed 100 year Return Period (km/h) - Moderate Case',
                'Extreme Windspeed 10 year Return Period (km/h) - Worst Case',
                'Extreme Windspeed 20 year Return Period (km/h) - Worst Case',
                'Extreme Windspeed 50 year Return Period (km/h) - Worst Case',
                'Extreme Windspeed 100 year Return Period (km/h) - Worst Case'
            ],
            'Heat': [
                'Days over 30° Celsius',
                'Days over 33° Celsius',
                'Days over 35° Celsius',
                'Days over 35° Celsius (2026 - 2030) - Moderate Case',
                'Days over 35° Celsius (2031 - 2040) - Moderate Case',
                'Days over 35° Celsius (2041 - 2050) - Moderate Case',
                'Days over 35° Celsius (2026 - 2030) - Worst Case',
                'Days over 35° Celsius (2031 - 2040) - Worst Case',
                'Days over 35° Celsius (2041 - 2050) - Worst Case'
            ],
            'Storm Surge': [
                'Storm Surge Flood Depth (meters)',
                'Storm Surge Flood Depth (meters) - Worst Case'
            ],
            'Rainfall-Induced Landslide': [
                'Rainfall-Induced Landslide (factor of safety)',
                'Rainfall-Induced Landslide (factor of safety) - Moderate Case',
                'Rainfall-Induced Landslide (factor of safety) - Worst Case'
            ]
        }
        
        # Add column groups for each hazard type that has columns in the data
        for hazard, cols in hazard_columns.items():
            count = sum(1 for col in cols if col in columns)
            if count > 0:
                groups[hazard] = count
                logger.info(f"Added {hazard} group with {count} columns")
        
        # Calculate sub-group column counts for header alignment
        heat_basecase_count = sum(
            1 for c in columns
            if c.startswith('Days over 35° Celsius') and c.endswith(' - Moderate Case')
        )
        heat_worstcase_count = sum(
            1 for c in columns
            if c.startswith('Days over 35° Celsius') and c.endswith(' - Worst Case')
        )
        heat_baseline_cols = [
            'Days over 30° Celsius',
            'Days over 33° Celsius',
            'Days over 35° Celsius'
        ]
        heat_baseline_count = sum(1 for c in heat_baseline_cols if c in columns)

        if 'Heat' in groups:
            groups['Heat'] = heat_baseline_count + heat_basecase_count + heat_worstcase_count

        ws_moderatecase_count = sum(
            1 for c in columns
            if c.startswith('Water Stress Exposure') and c.endswith(' - Moderate Case')
        )
        ws_worstcase_count = sum(
            1 for c in columns
            if c.startswith('Water Stress Exposure') and c.endswith(' - Worst Case')
        )
        ws_baseline_cols = ['Water Stress Exposure (%)']
        ws_baseline_count = sum(1 for c in ws_baseline_cols if c in columns)

        if 'Water Stress' in groups:
            groups['Water Stress'] = ws_baseline_count + ws_moderatecase_count + ws_worstcase_count

        tc_basecase_count = sum(
            1 for c in columns if c.endswith(' - Moderate Case') and 'Windspeed' in c
        )
        tc_worstcase_count = sum(
            1 for c in columns if c.endswith(' - Worst Case') and 'Windspeed' in c
        )
        tc_baseline_cols = [
            'Extreme Windspeed 10 year Return Period (km/h)',
            'Extreme Windspeed 20 year Return Period (km/h)',
            'Extreme Windspeed 50 year Return Period (km/h)',
            'Extreme Windspeed 100 year Return Period (km/h)'
        ]
        tc_baseline_count = sum(1 for c in tc_baseline_cols if c in columns)

        if 'Tropical Cyclones' in groups:
            groups['Tropical Cyclones'] = (
                tc_baseline_count + tc_basecase_count + tc_worstcase_count
            )

        ss_worstcase_count = sum(
            1 for c in columns if c.endswith(' - Worst Case') and 'Storm Surge Flood Depth' in c
        )
        ss_baseline_cols = ['Storm Surge Flood Depth (meters)']
        ss_baseline_count = sum(1 for c in ss_baseline_cols if c in columns)

        if 'Storm Surge' in groups:
            groups['Storm Surge'] = ss_baseline_count + ss_worstcase_count
        slr_moderatecase_count = sum(1 for c in columns if c.endswith(" - Moderate Case") and "Sea Level Rise" in c)
        slr_worstcase_count = sum(1 for c in columns if c.endswith(" - Worst Case") and "Sea Level Rise" in c)
        if "Sea Level Rise" in groups:
            groups["Sea Level Rise"] = slr_moderatecase_count + slr_worstcase_count

        ls_moderatecase_count = sum(
            1 for c in columns if c.endswith(' - Moderate Case') and 'Landslide' in c
        )
        ls_worstcase_count = sum(
            1 for c in columns if c.endswith(' - Worst Case') and 'Landslide' in c
        )
        ls_baseline_cols = ['Rainfall-Induced Landslide (factor of safety)']
        ls_baseline_count = sum(1 for c in ls_baseline_cols if c in columns)

        if 'Rainfall-Induced Landslide' in groups:
            groups['Rainfall-Induced Landslide'] = (
                ls_baseline_count + ls_moderatecase_count + ls_worstcase_count
            )
        
        # Store sensitivity results in session
        request.session['climate_hazards_v2_sensitivity_results'] = {
            'data': sensitivity_data,
            'columns': columns,
            'archetype_params': archetype_params
        }

        revised_params = request.session.get('climate_hazards_v2_revised_params', {})

        # Convert revised_params into a display friendly structure that lists
        # thresholds per hazard for each archetype
        hazard_labels = {
            'water_stress': 'Water Stress',
            'heat': 'Heat',
            'flood': 'Flood',
            'tropical_cyclone': 'Tropical Cyclone',
            'storm_surge': 'Storm Surge',
            'landslide': 'Rainfall-Induced Landslide',
        }
        revised_thresholds = {}
        for arch, hazards in revised_params.items():
            hazard_list = []
            for key, values in hazards.items():
                label = hazard_labels.get(key, key)
                hazard_list.append({
                    'name': label,
                    'low': values.get('low'),
                    'high': values.get('high'),
                })
            if hazard_list:
                revised_thresholds[arch] = hazard_list
        
        # Prepare context for the template
        context = {
            'data': sensitivity_data,
            'columns': columns,
            'groups': groups,
            'selected_hazards': selected_hazards,
            'archetype_params': archetype_params,
            'revised_thresholds': revised_thresholds,
            'heat_basecase_count': heat_basecase_count,
            'heat_worstcase_count': heat_worstcase_count,
            'heat_baseline_count': heat_baseline_count,
            'tc_basecase_count': tc_basecase_count,
            'tc_worstcase_count': tc_worstcase_count,
            'tc_baseline_count': tc_baseline_count,
            'ss_baseline_count': ss_baseline_count,
            'ss_worstcase_count': ss_worstcase_count,
            'ls_baseline_count': ls_baseline_count,
            'ls_moderatecase_count': ls_moderatecase_count,
            'ls_worstcase_count': ls_worstcase_count,
            'slr_moderatecase_count': slr_moderatecase_count,
            'slr_worstcase_count': slr_worstcase_count,
            'is_sensitivity_results': True,  # Flag to indicate this is sensitivity results
            'success_message': f"Successfully applied sensitivity parameters to {len(sensitivity_data)} facilities. Results now use archetype-specific color coding."
        }
        
        logger.info("Rendering sensitivity results template...")
        return render(request, 'climate_hazards_analysis_v2/sensitivity_results.html', context)
        
    except Exception as e:
        logger.exception(f"Error in sensitivity results: {str(e)}")
        
        return render(request, 'climate_hazards_analysis_v2/sensitivity_parameters.html', {
            'error': f"Error generating sensitivity results: {str(e)}",
            'facility_count': len(facility_data),
            'selected_hazards': selected_hazards,
            'asset_archetypes': []
        })
    
@require_http_methods(["POST"])
def save_table_changes(request):
    """
    Handle AJAX requests to save changes made to the Adjust Magnitude with Local Conditions table.
    Updates session data and persists overrides to database for session independence.
    """
    try:
        # Parse the JSON data from the request
        data = json.loads(request.body)
        changes = data.get('changes', [])

        if not changes:
            return JsonResponse({'success': False, 'error': 'No changes provided'})

        logger.info(f"Processing {len(changes)} table changes")

        # Get current asset exposure results data from session
        results_data = request.session.get('climate_hazards_v2_results')
        session_has_data = results_data and 'data' in results_data and results_data['data']

        # Enhanced fallback: If no session data, check if assets exist for database fallback
        if not session_has_data:
            logger.warning("No analysis results found in session - attempting database fallback")

            # Check if we have uploaded assets to work with
            uploaded_asset_ids = request.session.get('climate_hazards_v2_uploaded_asset_ids', [])
            if not uploaded_asset_ids:
                return JsonResponse({
                    'success': False,
                    'error': 'No analysis results found. Please run the climate analysis first.',
                    'redirect_url': '/climate-hazards-analysis-v2/select-hazards/',
                    'requires_analysis': True
                })

            # Create fallback data structure
            assets = Asset.objects.filter(id__in=uploaded_asset_ids)
            if not assets.exists():
                return JsonResponse({
                    'success': False,
                    'error': 'No assets found. Please upload facility data first.',
                    'redirect_url': '/climate-hazards-analysis-v2/'
                })

            logger.info(f"Using database fallback with {assets.count()} assets")

            # Process changes directly to database without session dependency
            successful_overrides = 0
            failed_overrides = []

            for change in changes:
                facility_name = change['facilityName']
                column_name = change['column']
                new_value = change['newValue']
                reason = change.get('reason', '')

                try:
                    # Find the asset
                    asset = assets.get(name=facility_name)

                    # Convert value to appropriate type
                    converted_value = convert_table_value(new_value, column_name)

                    # Create database override
                    override = OverrideValue.create_or_update_override(
                        asset=asset,
                        column_name=column_name,
                        override_value=str(converted_value),
                        original_value=None,  # We don't have the original value in fallback mode
                        reason=reason,
                        user_identifier=request.session.session_key,
                        session_key=request.session.session_key
                    )

                    # Update asset workflow state
                    asset.workflow_state = 'overrides_applied'
                    asset.has_session_independent_analysis = True
                    asset.save()

                    successful_overrides += 1
                    logger.info(f"Created database override for {facility_name} - {column_name}: {converted_value}")

                except Asset.DoesNotExist:
                    failed_overrides.append(f"Asset '{facility_name}' not found")
                    logger.warning(f"Asset not found for facility: {facility_name}")
                except Exception as e:
                    failed_overrides.append(f"Error processing {facility_name}: {str(e)}")
                    logger.error(f"Error creating override for {facility_name}: {e}")

            return JsonResponse({
                'success': successful_overrides > 0,
                'message': f'Successfully saved {successful_overrides} override(s) to database',
                'successful_overrides': successful_overrides,
                'failed_overrides': failed_overrides,
                'database_mode': True,
                'requires_analysis': False
            })

        # Normal session-based processing
        table_data = results_data['data']

        # Apply changes to both session data and database
        for change in changes:
            row_index = change['rowIndex']
            column_name = change['column']
            new_value = change['newValue']
            facility_name = change['facilityName']
            reason = change.get('reason', '')

            # Find the correct row in the data (match by facility name for safety)
            target_row = None
            for i, row in enumerate(table_data):
                if i == row_index and row.get('Facility') == facility_name:
                    target_row = row
                    break

            if target_row is None:
                logger.warning(f"Could not find row {row_index} for facility {facility_name}")
                continue

            # Get original value before override
            original_value = target_row.get(column_name)

            # Convert value to appropriate type
            converted_value = convert_table_value(new_value, column_name)

            # Update session data
            target_row[column_name] = converted_value

            # Try to find and update the corresponding asset in database
            try:
                # Find the asset by name (assuming facility name matches asset name)
                asset = Asset.objects.get(name=facility_name)

                # Create or update database override
                override = OverrideValue.create_or_update_override(
                    asset=asset,
                    column_name=column_name,
                    override_value=str(converted_value),
                    original_value=str(original_value) if original_value is not None else None,
                    reason=reason,
                    user_identifier=request.session.session_key,
                    session_key=request.session.session_key
                )

                # Mark asset as having session-independent analysis
                asset.has_session_independent_analysis = True
                asset.workflow_state = 'overrides_applied'
                asset.last_analysis_session_key = request.session.session_key
                asset.save()

                logger.info(f"Updated {facility_name} - {column_name}: {converted_value} (session + database)")

            except Asset.DoesNotExist:
                logger.warning(f"Asset not found in database for facility: {facility_name}")
                # Continue with session-only update
            except Exception as db_error:
                logger.error(f"Database error for {facility_name}: {db_error}")
                # Continue with session-only update

        # Update session data for asset exposure results
        results_data['data'] = table_data
        request.session['climate_hazards_v2_results'] = results_data
        request.session.modified = True

        # Optionally save to CSV file for persistence
        try:
            save_updated_data_to_csv(table_data, request)
        except Exception as csv_error:
            logger.warning(f"Failed to save to CSV: {csv_error}")
            # Don't fail the request if CSV save fails

        return JsonResponse({
            'success': True,
            'message': f'Successfully updated {len(changes)} values (session + database)',
            'changes_applied': len(changes),
            'database_mode': False
        })

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in request: {e}")
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})

    except Exception as e:
        logger.exception(f"Error saving table changes: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@require_GET
def check_analysis_context(request):
    """
    Check if analysis context exists for making overrides.
    Returns JSON response indicating whether assets exist and analysis has been run.
    """
    try:
        # Check if we have uploaded assets in session
        uploaded_asset_ids = request.session.get('climate_hazards_v2_uploaded_asset_ids', [])

        if not uploaded_asset_ids:
            return JsonResponse({
                'has_context': False,
                'message': 'No assets found. Please upload facility data first.',
                'requires_upload': True,
                'redirect_url': '/climate-hazards-analysis-v2/'
            })

        # Check if assets exist in database
        assets = Asset.objects.filter(id__in=uploaded_asset_ids)
        if not assets.exists():
            return JsonResponse({
                'has_context': False,
                'message': 'No assets found in database. Please upload facility data first.',
                'requires_upload': True,
                'redirect_url': '/climate-hazards-analysis-v2/'
            })

        # Check if any assets have session-independent analysis
        assets_with_overrides = assets.filter(has_session_independent_analysis=True)
        if assets_with_overrides.exists():
            return JsonResponse({
                'has_context': True,
                'message': 'Assets have database-stored analysis results. Overrides are available.',
                'database_mode': True,
                'asset_count': assets_with_overrides.count()
            })

        # Check if we have session-based analysis results
        results_data = request.session.get('climate_hazards_v2_results')
        if results_data and 'data' in results_data and results_data['data']:
            return JsonResponse({
                'has_context': True,
                'message': 'Session-based analysis results found. Overrides are available.',
                'database_mode': False
            })

        # We have assets but no analysis results
        return JsonResponse({
            'has_context': False,
            'message': 'Assets found but no analysis results exist. Please run the climate analysis first.',
            'requires_analysis': True,
            'redirect_url': '/climate-hazards-analysis-v2/select-hazards/',
            'asset_count': assets.count()
        })

    except Exception as e:
        logger.exception(f"Error checking analysis context: {e}")
        return JsonResponse({
            'has_context': False,
            'message': 'Error checking analysis context. Please try again.',
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
def reset_table_data(request):
    """Restore the asset exposure results to the original baseline."""
    baseline = request.session.get('climate_hazards_v2_baseline_results')
    if not baseline:
        return JsonResponse({'success': False, 'error': 'No baseline data available'})

    request.session['climate_hazards_v2_results'] = copy.deepcopy(baseline)
    return JsonResponse({'success': True})

def convert_table_value(value, column_name):
    """
    Convert string value to appropriate type based on column name.
    """
    if value in ['', 'N/A', 'Data not available']:
        return value
    
    # Numeric columns
    numeric_columns = [
        'Flood Depth (meters)',
        'Water Stress Exposure (%)',
        'Days over 30° Celsius',
        'Days over 33° Celsius',
        'Days over 35° Celsius',
        '2030 Sea Level Rise (meters) - Moderate Case',
        '2040 Sea Level Rise (meters) - Moderate Case',
        '2050 Sea Level Rise (meters) - Moderate Case',
        '2030 Sea Level Rise (meters) - Worst Case',
        '2040 Sea Level Rise (meters) - Worst Case',
        '2050 Sea Level Rise (meters) - Worst Case',
        'Extreme Windspeed 10 year Return Period (km/h)',
        'Extreme Windspeed 20 year Return Period (km/h)',
        'Extreme Windspeed 50 year Return Period (km/h)',
        'Extreme Windspeed 100 year Return Period (km/h)',
        'Storm Surge Flood Depth (meters)',
        'Storm Surge Flood Depth (meters) - Worst Case',
        'Rainfall-Induced Landslide (factor of safety)',
        'Elevation (meter above sea level)'
    ]
    
    if column_name in numeric_columns:
        try:
            # Convert to float, then to int if it's a whole number
            float_val = float(value)
            if float_val.is_integer():
                return int(float_val)
            return float_val
        except (ValueError, TypeError):
            logger.warning(f"Could not convert '{value}' to number for column '{column_name}'")
            return value
    
    return str(value)


def save_updated_data_to_csv(table_data, request):
    """
    Save the updated table data to a CSV file for persistence.
    """
    try:
        # Create DataFrame from the updated data
        df = pd.DataFrame(table_data)

        # Generate filename with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"asset_exposure_updated_{timestamp}.csv"

        # Save to a designated directory (adjust path as needed)
        output_dir = os.path.join('media', 'climate_hazards_v2', 'updated_data')
        os.makedirs(output_dir, exist_ok=True)

        file_path = os.path.join(output_dir, filename)
        df.to_csv(file_path, index=False)

        # Store the updated file path in session for reference
        request.session['climate_hazards_v2_asset_exposure_updated_csv_path'] = file_path

        logger.info(f"Updated data saved to: {file_path}")

    except Exception as e:
        logger.error(f"Error saving updated data to CSV: {e}")
        raise

def export_hazard_data_to_excel(request):
    """
    Export hazard exposure data to Excel format.
    This endpoint can be used for both regular and sensitivity results.
    """
    try:
        # Check if this is for sensitivity results
        is_sensitivity = request.GET.get('sensitivity', 'false').lower() == 'true'

        if is_sensitivity:
            # Get sensitivity results data
            results_data = request.session.get('climate_hazards_v2_sensitivity_results')
            if not results_data or 'data' not in results_data:
                return JsonResponse({
                    'success': False,
                    'error': 'No sensitivity results data found'
                }, status=404)

            data = results_data['data']
            columns = results_data['columns']
            filename_prefix = 'climate_hazard_sensitivity_results'
        else:
            # Get regular results data
            results_data = request.session.get('climate_hazards_v2_results')
            if not results_data or 'data' not in results_data:
                return JsonResponse({
                    'success': False,
                    'error': 'No hazard analysis results found'
                }, status=404)

            data = results_data['data']
            columns = results_data['columns']
            filename_prefix = 'climate_hazard_exposure_results'

        if not data:
            return JsonResponse({
                'success': False,
                'error': 'No data available for export'
            }, status=404)

        # Create DataFrame
        df = pd.DataFrame(data)

        # Ensure columns are in the correct order
        if columns:
            # Only include columns that exist in the data
            available_columns = [col for col in columns if col in df.columns]
            df = df[available_columns]

        # Create output buffer
        output = BytesIO()

        # Generate filename with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{timestamp}.xlsx"

        # Create Excel writer with formatting
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Hazard Analysis Results')

            # Get the workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['Hazard Analysis Results']

            # Add formatting
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#F1D500',  # SGV yellow color
                'border': 1,
                'text_wrap': True,
                'valign': 'top'
            })

            # Apply header formatting
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Auto-adjust column widths
            for i, col in enumerate(df.columns):
                # Get the maximum length of data in this column
                max_len = max(
                    df[col].astype(str).map(len).max(),
                    len(str(col))
                ) + 2  # Add some padding

                # Set column width (with a maximum to prevent too wide columns)
                worksheet.set_column(i, i, min(max_len, 50))

        # Prepare response
        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        logger.info(f"Successfully exported {len(df)} rows to Excel: {filename}")

        return response

    except Exception as e:
        logger.exception(f"Error exporting to Excel: {e}")
        return JsonResponse({
            'success': False,
            'error': f'Export failed: {str(e)}'
        }, status=500)


@require_http_methods(["POST"])
def clear_site_data(request):
    """
    Clear all session data related to climate hazards analysis.
    This includes facility data, selected hazards, analysis results,
    and temporary files.
    """
    try:
        logger.info("Starting to clear site data for session")

        # Validate request
        if not request.session.exists(request.session.session_key):
            logger.warning("Attempted to clear data for non-existent session")
            return JsonResponse({
                'success': True,
                'message': 'No active session data found to clear.'
            })

        # List of session keys to clear
        session_keys_to_clear = [
            'climate_hazards_v2_facility_data',
            'climate_hazards_v2_facility_csv_path',
            'climate_hazards_v2_uploaded_filename',
            'climate_hazards_v2_selected_hazards',
            'climate_hazards_v2_results',
            'climate_hazards_v2_baseline_results',
            'climate_hazards_v2_sensitivity_results',
            'climate_hazards_v2_archetype_params',
            'climate_hazards_v2_revised_params',
            'climate_hazards_v2_asset_exposure_updated_csv_path',
            'polygon_asset_ids',  # Clear session asset IDs for enhanced preview
            # Clear any additional analysis-related session variables
            'combined_csv_path',  # Used in report generation
        ]

        # Clear session data
        cleared_count = 0
        for key in session_keys_to_clear:
            if key in request.session:
                del request.session[key]
                cleared_count += 1
                logger.info(f"Cleared session key: {key}")

        # Clean up temporary files
        temp_files_removed = 0
        try:
            # Define paths for temporary files
            temp_dir = UPLOAD_DIR

            if os.path.exists(temp_dir):
                # Remove facility CSV files created for this session
                session_pattern = f"facility_data_{request.session.session_key or '*'}*.csv"
                for file_path in glob.glob(os.path.join(temp_dir, session_pattern)):
                    try:
                        os.remove(file_path)
                        temp_files_removed += 1
                        logger.info(f"Removed temporary file: {file_path}")
                    except OSError as e:
                        logger.warning(f"Could not remove file {file_path}: {e}")

                # Also remove old files (older than 24 hours) to prevent buildup
                import time
                current_time = time.time()
                for file_path in glob.glob(os.path.join(temp_dir, "facility_data_*.csv")):
                    try:
                        file_age = current_time - os.path.getctime(file_path)
                        if file_age > 24 * 3600:  # 24 hours in seconds
                            os.remove(file_path)
                            temp_files_removed += 1
                            logger.info(f"Removed old temporary file: {file_path}")
                    except OSError as e:
                        logger.warning(f"Could not remove old file {file_path}: {e}")

        except Exception as e:
            logger.warning(f"Error cleaning up temporary files: {e}")

        # Mark session as modified
        request.session.modified = True

        logger.info(f"Successfully cleared {cleared_count} session keys and {temp_files_removed} temporary files")

        return JsonResponse({
            'success': True,
            'message': f'Successfully cleared all site data! Removed {cleared_count} data items and {temp_files_removed} temporary files.'
        })

    except Exception as e:
        logger.exception(f"Error clearing site data: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Failed to clear site data: {str(e)}'
        }, status=500)


@ensure_csrf_cookie
@require_GET
def refresh_csrf_token(request):
    """
    Refresh CSRF token for AJAX requests.
    This endpoint ensures a valid CSRF token is available for clients
    that may have lost their token due to storage clearing.
    """
    try:
        # Get current CSRF token
        token = get_token(request)

        return JsonResponse({
            'success': True,
            'csrf_token': token,
            'message': 'CSRF token refreshed successfully'
        })

    except Exception as e:
        logger.error(f"Error refreshing CSRF token: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to refresh CSRF token'
        }, status=500)


# Polygon Asset Management Views

@require_GET
def get_polygon_assets(request):
    """
    API endpoint to retrieve all polygon assets for the current session.
    Returns assets in GeoJSON format for map display.
    """
    try:
        # Session-only approach: Get polygon assets from session facility_data
        facility_data = request.session.get('climate_hazards_v2_facility_data', [])

        # Filter only polygon assets
        polygon_assets = [f for f in facility_data if f.get('AssetType') == 'polygon' or f.get('geometry')]

        # Convert to GeoJSON FeatureCollection
        features = []
        for asset in polygon_assets:
            feature = {
                'type': 'Feature',
                'properties': {
                    'name': asset['Facility'],
                    'archetype': asset.get('Archetype', 'default archetype'),
                    'id': asset['AssetId'],
                    'AssetType': 'polygon'
                },
                'geometry': asset['geometry']
            }
            features.append(feature)

        geojson_data = {
            'type': 'FeatureCollection',
            'features': features
        }

        logger.info(f"Retrieved {len(features)} polygon assets from session")

        return JsonResponse({
            'success': True,
            'assets': geojson_data,
            'count': len(features)
        })

    except Exception as e:
        logger.exception(f"Error retrieving polygon assets: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to retrieve polygon assets'
        }, status=500)


@require_http_methods(["PUT"])
def update_polygon_asset(request, asset_id):
    """
    API endpoint to update an existing polygon asset.
    """
    try:
        data = json.loads(request.body)

        # Session-only approach: Update in session facility_data
        facility_data = request.session.get('climate_hazards_v2_facility_data', [])
        asset_updated = False
        updated_asset = None

        for facility in facility_data:
            if facility.get('AssetId') == asset_id and facility.get('AssetType') == 'polygon':
                # Update basic fields
                if 'name' in data and data['name'].strip():
                    facility['Facility'] = data['name'].strip()

                if 'archetype' in data:
                    facility['Archetype'] = data['archetype'].strip() if data['archetype'] else 'default archetype'

                # Update polygon geometry if provided
                if 'geometry' in data and data['geometry']:
                    facility['geometry'] = data['geometry']
                    # Recalculate centroid if geometry changed
                    geometry = data['geometry']
                    if geometry.get('type') == 'Polygon':
                        coords = geometry['coordinates'][0]  # Exterior ring
                        if len(coords) >= 3:
                            sum_lng = sum(point[0] for point in coords[:-1])
                            sum_lat = sum(point[1] for point in coords[:-1])
                            n = len(coords) - 1
                            facility['Lat'] = sum_lng / n
                            facility['Long'] = sum_lat / n

                # Create GeoJSON response
                updated_asset = {
                    'type': 'Feature',
                    'properties': {
                        'name': facility['Facility'],
                        'archetype': facility['Archetype'],
                        'id': facility['AssetId'],
                        'AssetType': 'polygon'
                    },
                    'geometry': facility['geometry']
                }

                asset_updated = True
                logger.info(f"Updated session-only polygon asset: {facility['Facility']} (ID: {asset_id})")
                break

        if not asset_updated:
            return JsonResponse({
                'success': False,
                'error': 'Polygon asset not found'
            }, status=404)

        # Update session
        request.session['climate_hazards_v2_facility_data'] = facility_data
        request.session.save()

        return JsonResponse({
            'success': True,
            'asset': updated_asset,
            'message': 'Polygon asset updated successfully'
        })

    except Exception as e:
        logger.exception(f"Error updating polygon asset: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to update polygon asset'
        }, status=500)


@require_http_methods(["DELETE"])
def delete_polygon_asset(request, asset_id):
    """
    API endpoint to delete a polygon asset.
    """
    try:
        # Session-only approach: Remove from session facility_data
        facility_data = request.session.get('climate_hazards_v2_facility_data', [])
        asset_deleted = False
        asset_name = None

        # Find and remove the asset
        new_facility_data = []
        for facility in facility_data:
            if facility.get('AssetId') == asset_id and facility.get('AssetType') == 'polygon':
                asset_name = facility['Facility']
                asset_deleted = True
                logger.info(f"Deleted session-only polygon asset: {asset_name} (ID: {asset_id})")
                # Don't add this asset to the new list (effectively deleting it)
            else:
                new_facility_data.append(facility)

        if not asset_deleted:
            return JsonResponse({
                'success': False,
                'error': 'Polygon asset not found'
            }, status=404)

        # Update session with filtered data
        request.session['climate_hazards_v2_facility_data'] = new_facility_data
        request.session.save()

        return JsonResponse({
            'success': True,
            'message': f'Polygon asset "{asset_name}" deleted successfully'
        })

    except Exception as e:
        logger.exception(f"Error deleting polygon asset: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to delete polygon asset'
        }, status=500)


@require_http_methods(["POST"])
def create_polygon_asset(request):
    """
    API endpoint to create a new polygon asset from the drawing workflow.
    Handles the polygon creation workflow: draw polygon -> modal -> save.
    """
    try:
        data = json.loads(request.body)

        # Validate required fields
        if not data.get('geometry'):
            return JsonResponse({
                'success': False,
                'error': 'Polygon geometry is required'
            }, status=400)

        if not data.get('name', '').strip():
            return JsonResponse({
                'success': False,
                'error': 'Asset name is required'
            }, status=400)

        # Calculate centroid from polygon geometry
        geometry = data['geometry']
        if geometry.get('type') != 'Polygon':
            return JsonResponse({
                'success': False,
                'error': 'Invalid polygon geometry type'
            }, status=400)

        # Calculate centroid coordinates
        coords = geometry['coordinates'][0]  # Exterior ring
        if len(coords) < 3:
            return JsonResponse({
                'success': False,
                'error': 'Polygon must have at least 3 points'
            }, status=400)

        # Simple centroid calculation (average of coordinates)
        sum_lng = sum(point[0] for point in coords[:-1])  # Exclude closing point
        sum_lat = sum(point[1] for point in coords[:-1])
        n = len(coords) - 1  # Exclude closing point
        centroid_lng = sum_lng / n
        centroid_lat = sum_lat / n

        # Extract granular analysis settings
        grid_spacing = data.get('gridSpacing')  # Grid spacing from frontend modal
        area_km2 = data.get('areaKm2')  # Polygon area from frontend
        enable_granular = data.get('enableGranular', False)  # Whether granular analysis is enabled
        granular_points = data.get('granular-points')  # Grid points for granular analysis

        # Session-only approach: Generate unique ID and store entirely in session
        import uuid
        unique_id = str(uuid.uuid4())[:8]  # Short unique ID

        # Store in session facility_data (session-only storage)
        facility_data = request.session.get('climate_hazards_v2_facility_data', [])

        # Create facility data entry (session-only)
        new_facility = {
            'id': unique_id,  # Session-generated unique ID
            'Facility': data['name'].strip(),
            'Lat': centroid_lat,
            'Long': centroid_lng,
            'Archetype': data.get('archetype', 'default archetype').strip() or 'default archetype',
            'AssetType': 'polygon',
            'AssetId': unique_id,
            'geometry': geometry,
            'polygon_area_km2': area_km2,
            'source': request.session.session_key or 'anonymous'
        }

        # Add granular analysis settings if enabled
        if enable_granular:
            new_facility['granular_grid_spacing'] = grid_spacing
            new_facility['granular_points_count'] = len(granular_points) if granular_points else 0
            new_facility['granular_analysis_enabled'] = True
            if granular_points:
                new_facility['granular-points'] = granular_points

        facility_data.append(new_facility)

        # Update session
        request.session['climate_hazards_v2_facility_data'] = facility_data
        request.session.save()

        logger.info(f"Created session-only polygon asset: {data['name'].strip()} (ID: {unique_id})")

        # Return GeoJSON-like response for frontend compatibility
        geojson_asset = {
            'type': 'Feature',
            'properties': {
                'name': data['name'].strip(),
                'archetype': data.get('archetype', 'default archetype').strip() or 'default archetype',
                'id': unique_id,
                'AssetType': 'polygon'
            },
            'geometry': geometry
        }

        return JsonResponse({
            'success': True,
            'asset': geojson_asset,
            'message': 'Polygon asset created successfully'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data provided'
        }, status=400)
    except Exception as e:
        logger.exception(f"Error creating polygon asset: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to create polygon asset'
        }, status=500)


@require_GET
def get_asset_analysis_results(request, asset_id):
    """
    API endpoint to retrieve climate hazard analysis results for a specific asset.
    """
    try:
        asset = Asset.objects.get(id=asset_id)

        # Get all analysis results for this asset
        results = HazardAnalysisResult.objects.filter(asset=asset).order_by(
            'hazard_type', 'scenario'
        )

        # Format results
        results_data = {}
        for result in results:
            if result.hazard_type not in results_data:
                results_data[result.hazard_type] = {}
            results_data[result.hazard_type][result.scenario] = result.result_data

        return JsonResponse({
            'success': True,
            'asset': asset.geojson,
            'results': results_data,
            'has_results': len(results) > 0
        })

    except Asset.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Asset not found'
        }, status=404)
    except Exception as e:
        logger.exception(f"Error retrieving asset analysis results: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to retrieve analysis results'
        }, status=500)


class HeatExposureMapView(TemplateView):
    """
    Dedicated view for displaying the Heat Exposure Map with full functionality.

    This view provides a focused experience for visualizing heat exposure data
    across facilities, with all the interactive features previously available
    in the results page tab.
    """
    template_name = 'climate_hazards_analysis_v2/heat_exposure_map.html'

    def dispatch(self, request, *args, **kwargs):
        """
        Validate session data before processing the request.
        """
        # Validate that we have the necessary session data
        facility_data = request.session.get('climate_hazards_v2_facility_data', [])
        selected_hazards = request.session.get('climate_hazards_v2_selected_hazards', [])

        if not facility_data:
            logger.warning("Heat Exposure Map accessed without facility data")
            return redirect('climate_hazards_analysis_v2:select_hazards')

        if not selected_hazards or 'Heat' not in selected_hazards:
            logger.warning("Heat Exposure Map accessed without heat hazard selected")
            return redirect('climate_hazards_analysis_v2:select_hazards')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """
        Build context data for the heat exposure map template.
        """
        context = super().get_context_data(**kwargs)

        # Get session data with safety checks
        if not hasattr(self, 'request') or not self.request:
            logger.error("HeatExposureMapView: No request available in get_context_data")
            return context

        facility_data = self.request.session.get('climate_hazards_v2_facility_data', [])
        selected_hazards = self.request.session.get('climate_hazards_v2_selected_hazards', [])
        facility_csv_path = self.request.session.get('climate_hazards_v2_facility_csv_path')

        # Get analysis results if available
        results_data = self.request.session.get('climate_hazards_v2_results', {})

        # Build facility summary for context
        facility_count = len(facility_data)
        polygon_asset_count = sum(1 for fac in facility_data if fac.get('asset_type') == 'polygon')
        point_asset_count = sum(1 for fac in facility_data if fac.get('asset_type') == 'point')

        context.update({
            'facility_count': facility_count,
            'polygon_asset_count': polygon_asset_count,
            'point_asset_count': point_asset_count,
            'selected_hazards': selected_hazards,
            'has_analysis_results': bool(results_data),
            'heat_exposure_api_url': reverse_lazy('climate_hazards_analysis_v2:get_heat_exposure_map_data'),
            'results_url': reverse_lazy('climate_hazards_analysis_v2:show_results'),
            'select_hazards_url': reverse_lazy('climate_hazards_analysis_v2:select_hazards'),
        })

        # Add CSRF token safely
        try:
            context['csrf_token'] = get_token(self.request)
        except Exception as e:
            logger.warning(f"Could not generate CSRF token for heat exposure map: {e}")
            context['csrf_token'] = ''

        # Add sample facility info for debugging/display purposes
        if facility_data:
            sample_facilities = [
                {
                    'name': fac.get('name', 'Unknown'),
                    'lat': fac.get('lat', 0),
                    'long': fac.get('long', 0),
                    'asset_type': fac.get('asset_type', 'unknown')
                }
                for fac in facility_data[:3]  # Show first 3 facilities as examples
            ]
            context['sample_facilities'] = sample_facilities

        logger.info(f"Heat Exposure Map context prepared for {facility_count} facilities")
        return context


class HazardExposureMapView(TemplateView):
    """
    Dedicated view for displaying the Hazard Exposure Map with full functionality.

    This view provides a focused experience for visualizing all selected climate hazards
    across facilities, with interactive hazard selection and asset markers.
    """
    template_name = 'climate_hazards_analysis_v2/hazard_exposure_map.html'

    def dispatch(self, request, *args, **kwargs):
        """
        Validate session data before processing the request.
        Handles both regular workflow and granular polygon analysis.
        """
        # Check for regular workflow data
        facility_data = request.session.get('climate_hazards_v2_facility_data', [])
        selected_hazards = request.session.get('climate_hazards_v2_selected_hazards', [])

        # Check for granular workflow data
        from .session_utils import GranularAnalysisSessionManager
        is_granular = GranularAnalysisSessionManager.is_granular_workflow(request)
        granular_asset_id = GranularAnalysisSessionManager.get_asset_id(request)

        # Validate that we have data from either workflow
        has_regular_data = facility_data and selected_hazards
        has_granular_data = is_granular and granular_asset_id

        if not has_regular_data and not has_granular_data:
            logger.warning("Hazard Exposure Map accessed without valid session data")
            return redirect('climate_hazards_analysis_v2:select_hazards')

        # For granular workflow, get hazards from the asset
        if has_granular_data and not selected_hazards:
            try:
                from .models import Asset, GranularAnalysisResult
                asset = Asset.objects.get(id=granular_asset_id)
                granular_hazards = list(GranularAnalysisResult.objects.filter(
                    asset=asset,
                    processing_status='completed'
                ).values_list('hazard_type', flat=True).distinct())

                if granular_hazards:
                    selected_hazards = granular_hazards
                    # Store in session for template access
                    request.session['climate_hazards_v2_selected_hazards'] = selected_hazards
                else:
                    logger.warning(f"No completed analysis found for granular asset {granular_asset_id}")
                    return redirect('climate_hazards_analysis_v2:select_hazards')

            except Exception as e:
                logger.error(f"Error getting hazards for granular asset {granular_asset_id}: {e}")
                return redirect('climate_hazards_analysis_v2:select_hazards')

        # Store workflow type in context
        request.session['_hazard_map_workflow_type'] = 'granular' if has_granular_data else 'regular'
        request.session.save()

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """
        Build context data for the hazard exposure map template.
        Handles both regular workflow and granular polygon analysis.
        """
        context = super().get_context_data(**kwargs)

        # Get session data with safety checks
        if not hasattr(self, 'request') or not self.request:
            logger.error("HazardExposureMapView: No request available in get_context_data")
            return context

        # Check workflow type
        workflow_type = self.request.session.get('_hazard_map_workflow_type', 'regular')
        is_granular = workflow_type == 'granular'

        if is_granular:
            # Handle granular workflow data
            from .session_utils import GranularAnalysisSessionManager
            granular_asset_id = GranularAnalysisSessionManager.get_asset_id(self.request)
            selected_hazards = self.request.session.get('climate_hazards_v2_selected_hazards', [])

            try:
                from .models import Asset
                asset = Asset.objects.get(id=granular_asset_id)

                # Create facility data from granular asset
                facility_data = [{
                    'name': asset.name,
                    'latitude': float(asset.latitude),
                    'longitude': float(asset.longitude),
                    'asset_type': 'polygon',
                    'archetype': asset.archetype or 'Unknown',
                    'id': asset.id
                }]

                facility_count = 1
                polygon_asset_count = 1
                point_asset_count = 0

                # Get granular results for context
                from .models import GranularAnalysisResult
                granular_results = GranularAnalysisResult.objects.filter(
                    asset=asset,
                    processing_status='completed',
                    hazard_type__in=selected_hazards
                )

                # Create mock results_data for granular workflow
                results_data = {
                    'status': 'completed',
                    'hazard_types': selected_hazards,
                    'analysis_summary': {
                        'total_facilities': 1,
                        'processed_facilities': 1,
                        'failed_facilities': 0
                    }
                }

            except Exception as e:
                logger.error(f"Error processing granular data for hazard map: {e}")
                # Fallback to empty data
                facility_data = []
                selected_hazards = []
                facility_count = 0
                polygon_asset_count = 0
                point_asset_count = 0
                results_data = {}

        else:
            # Handle regular workflow data
            facility_data = self.request.session.get('climate_hazards_v2_facility_data', [])
            selected_hazards = self.request.session.get('climate_hazards_v2_selected_hazards', [])
            facility_csv_path = self.request.session.get('climate_hazards_v2_facility_csv_path')

            # Get analysis results if available
            results_data = self.request.session.get('climate_hazards_v2_results', {})

            # Build facility summary for context
            facility_count = len(facility_data)
            polygon_asset_count = sum(1 for fac in facility_data if fac.get('asset_type') == 'polygon')
            point_asset_count = sum(1 for fac in facility_data if fac.get('asset_type') == 'point')

        # Define hazard configurations
        hazard_configs = {
            'Heat': {'icon': 'fas fa-temperature-high', 'color': '#dc3545'},
            'Cold': {'icon': 'fas fa-snowflake', 'color': '#17a2b8'},
            'Wind': {'icon': 'fas fa-wind', 'color': '#28a745'},
            'Coastal': {'icon': 'fas fa-water', 'color': '#007bff'},
            'Flooding': {'icon': 'fas fa-tint', 'color': '#6f42c1'},
            'Drought': {'icon': 'fas fa-sun', 'color': '#fd7e14'},
            'Landslide': {'icon': 'fas fa-mountain', 'color': '#6c757d'}
        }

        # Filter hazard configs for selected hazards
        selected_hazard_configs = {hazard: hazard_configs.get(hazard, {}) for hazard in selected_hazards}

        context.update({
            'facility_count': facility_count,
            'polygon_asset_count': polygon_asset_count,
            'point_asset_count': point_asset_count,
            'selected_hazards': selected_hazards,
            'selected_hazard_configs': selected_hazard_configs,
            'has_analysis_results': bool(results_data),
            'hazard_exposure_api_url': reverse_lazy('climate_hazards_analysis_v2:visualization_data_api'),
            'results_url': reverse_lazy('climate_hazards_analysis_v2:show_results'),
            'select_hazards_url': reverse_lazy('climate_hazards_analysis_v2:select_hazards'),
        })

        # Add CSRF token safely
        try:
            context['csrf_token'] = get_token(self.request)
        except Exception as e:
            logger.warning(f"Could not generate CSRF token for hazard exposure map: {e}")
            context['csrf_token'] = ''

        # Add workflow type to context for template
        context['workflow_type'] = workflow_type
        context['is_granular_workflow'] = is_granular

        # Add sample facility info for debugging/display purposes
        if facility_data:
            sample_facilities = [
                {
                    'name': fac.get('name', 'Unknown'),
                    'lat': fac.get('lat', fac.get('latitude', 0)),
                    'long': fac.get('long', fac.get('longitude', 0)),
                    'asset_type': fac.get('asset_type', 'unknown')
                }
                for fac in facility_data[:3]  # Show first 3 facilities as examples
            ]
            context['sample_facilities'] = sample_facilities

        logger.info(f"Hazard Exposure Map context prepared for {facility_count} facilities with {len(selected_hazards)} hazards (workflow: {workflow_type})")
        return context


@csrf_exempt
@require_http_methods(["GET"])
def get_heat_exposure_map_data(request):
    """
    API endpoint to retrieve heat exposure data for map visualization.
    Returns spatial heat data that can be rendered as a map layer.
    """
    try:
        # Get facility data from session
        facility_data = request.session.get('climate_hazards_v2_facility_data', [])

        if not facility_data:
            return JsonResponse({
                'success': False,
                'error': 'No facility data found'
            }, status=404)

        # Get selected hazards and archetype parameters
        selected_hazards = request.session.get('climate_hazards_v2_selected_hazards', [])
        archetype_params = request.session.get('climate_hazards_v2_archetype_params', {})

        # Check if heat hazard is selected
        if 'Heat' not in selected_hazards:
            return JsonResponse({
                'success': False,
                'error': 'Heat hazard not selected'
            }, status=400)

        logger.info(f"Processing heat exposure map data for {len(facility_data)} facilities")

        # Process heat exposure for each facility
        heat_exposure_data = []
        for facility in facility_data:
            try:
                lat = facility.get('Lat', 0)
                lng = facility.get('Long', 0)
                facility_name = facility.get('Facility', 'Unknown')
                archetype = facility.get('Archetype', 'default')

                # Get heat exposure value from processed data
                # Using same logic as main results processing
                heat_value = 0
                heat_category = 'Unknown'

                # Try to extract from existing heat columns in data
                possible_heat_columns = [
                    'Heat Exposure (%)',
                    'Heat Exposure (%) - Moderate Case',
                    'Heat Exposure (%) - Worst Case'
                ]

                for col in possible_heat_columns:
                    if col in facility and facility[col] is not None:
                        heat_value = float(facility[col])
                        break

                # Categorize heat exposure
                if heat_value > 0:
                    if heat_value <= 25:
                        heat_category = 'Low'
                    elif heat_value <= 50:
                        heat_category = 'Medium'
                    else:
                        heat_category = 'High'
                else:
                    heat_category = 'No Data'

                # Create point feature for map
                feature = {
                    'type': 'Feature',
                    'properties': {
                        'name': facility_name,
                        'archetype': archetype,
                        'heat_exposure': round(heat_value, 2) if heat_value > 0 else 0,
                        'heat_category': heat_category,
                        'latitude': lat,
                        'longitude': lng
                    },
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [lng, lat]
                    }
                }
                heat_exposure_data.append(feature)

            except Exception as facility_error:
                logger.warning(f"Error processing facility {facility.get('Facility', 'Unknown')}: {facility_error}")
                continue

        # Create GeoJSON response
        heat_geojson = {
            'type': 'FeatureCollection',
            'features': heat_exposure_data
        }

        # Add metadata
        response_data = {
            'success': True,
            'data': heat_geojson,
            'metadata': {
                'total_facilities': len(heat_exposure_data),
                'selected_hazards': selected_hazards,
                'heat_categories': ['No Data', 'Low', 'Medium', 'High'],
                'heat_colors': {
                    'No Data': '#CCCCCC',
                    'Low': '#2ECC71',      # Green
                    'Medium': '#F1D4D3',   # Orange
                    'High': '#E74C3C'       # Red
                }
            }
        }

        logger.info(f"Generated heat exposure map with {len(heat_exposure_data)} facilities")

        return JsonResponse(response_data)

    except Exception as e:
        logger.exception(f"Error generating heat exposure map data: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to generate heat exposure map data'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_hazard_exposure_map_data(request):
    """
    API endpoint to retrieve hazard exposure data for map visualization.
    Returns spatial hazard data for all selected hazards that can be rendered as map layers.
    """
    try:
        # Check for granular analysis workflow
        granular_workflow = GranularAnalysisSessionManager.is_granular_workflow(request)
        polygon_asset_id = GranularAnalysisSessionManager.get_asset_id(request)

        logger.info(f"Granular workflow check: granular_workflow={granular_workflow}, polygon_asset_id={polygon_asset_id}")

        if granular_workflow and polygon_asset_id:
            logger.info(f"Generating hazard exposure map for granular asset {polygon_asset_id}")
            return _generate_granular_hazard_exposure_map(request, polygon_asset_id)

        # Get facility data from session
        facility_data = request.session.get('climate_hazards_v2_facility_data', [])

        if not facility_data:
            # Check if there are any polygon assets as fallback (even without granular analysis)
            polygon_assets = Asset.objects.filter(
                asset_type='polygon'
            ).order_by('-created_at')[:5]  # Get up to 5 most recent polygon assets

            if polygon_assets.exists():
                logger.info(f"No facility data found, but found {polygon_assets.count()} polygon assets. Using the most recent one.")
                return _generate_basic_polygon_hazard_exposure_map(request, polygon_assets.first().id)

            return JsonResponse({
                'success': False,
                'error': 'No facility data found'
            }, status=404)

        # Get selected hazards
        selected_hazards = request.session.get('climate_hazards_v2_selected_hazards', [])

        if not selected_hazards:
            return JsonResponse({
                'success': False,
                'error': 'No hazards selected'
            }, status=400)

        logger.info(f"Processing hazard exposure map data for {len(facility_data)} facilities with hazards: {selected_hazards}")

        # Process hazard exposure for each facility
        hazard_exposure_data = []
        for facility in facility_data:
            try:
                lat = float(facility.get('Lat', 0))
                lng = float(facility.get('Long', 0))
                facility_name = facility.get('Facility', 'Unknown')
                archetype = facility.get('Archetype', 'default')

                # Extract hazard values for all selected hazards
                hazard_values = {}
                for hazard in selected_hazards:
                    # Try different column name patterns for each hazard
                    possible_columns = [
                        f'{hazard} Exposure (%)',
                        f'{hazard} Exposure (%) - Moderate Case',
                        f'{hazard} Exposure (%) - Worst Case',
                        f'{hazard} Risk Score',
                        f'{hazard} Severity',
                        hazard  # Try just the hazard name
                    ]

                    hazard_value = 0
                    for col in possible_columns:
                        if col in facility and facility[col] is not None:
                            try:
                                hazard_value = float(facility[col])
                                break
                            except (ValueError, TypeError):
                                continue

                    hazard_values[hazard] = round(hazard_value, 2) if hazard_value > 0 else 0

                # Create point feature for map
                feature = {
                    'type': 'Feature',
                    'properties': {
                        'name': facility_name,
                        'archetype': archetype,
                        'hazard_values': hazard_values,
                        'selected_hazards': selected_hazards,
                        'latitude': lat,
                        'longitude': lng
                    },
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [lng, lat]
                    }
                }
                hazard_exposure_data.append(feature)

            except Exception as facility_error:
                logger.warning(f"Error processing facility {facility.get('Facility', 'Unknown')}: {facility_error}")
                continue

        # Create GeoJSON response
        hazard_geojson = {
            'type': 'FeatureCollection',
            'features': hazard_exposure_data
        }

        # Add metadata
        response_data = {
            'success': True,
            'data': hazard_geojson,
            'metadata': {
                'total_facilities': len(hazard_exposure_data),
                'selected_hazards': selected_hazards,
                'hazard_configs': {
                    'Heat': {'icon': 'fas fa-temperature-high', 'color': '#dc3545'},
                    'Cold': {'icon': 'fas fa-snowflake', 'color': '#17a2b8'},
                    'Wind': {'icon': 'fas fa-wind', 'color': '#28a745'},
                    'Coastal': {'icon': 'fas fa-water', 'color': '#007bff'},
                    'Flooding': {'icon': 'fas fa-tint', 'color': '#6f42c1'},
                    'Drought': {'icon': 'fas fa-sun', 'color': '#fd7e14'},
                    'Landslide': {'icon': 'fas fa-mountain', 'color': '#6c757d'}
                }
            }
        }

        return JsonResponse(response_data)

    except Exception as e:
        logger.exception(f"Error generating hazard exposure map data: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to generate hazard exposure map data'
        }, status=500)


# Granular Analysis Views

@csrf_exempt
@require_http_methods(["POST"])
def draw_polygon_complete(request):
    """
    API endpoint to handle completion of polygon drawing and trigger granular analysis.
    This endpoint is called when user finishes drawing a polygon on the map.
    """
    try:
        # Ensure session exists
        if not request.session.session_key:
            request.session.create()
            logger.info("Created new session for polygon drawing")

        data = json.loads(request.body)

        # Validate required fields
        if not data.get('geometry'):
            return JsonResponse({
                'success': False,
                'error': 'Polygon geometry is required'
            }, status=400)

        geometry = data['geometry']
        if geometry.get('type') != 'Polygon':
            return JsonResponse({
                'success': False,
                'error': 'Invalid polygon geometry type'
            }, status=400)

        # Extract asset data
        asset_name = data.get('name', 'Unnamed Asset')
        asset_archetype = data.get('archetype', 'default archetype')
        centroid_lat = data.get('lat')
        centroid_lng = data.get('lng')
        area_km2 = data.get('areaKm2', 0)
        grid_spacing = None  # Granular analysis disabled; keep placeholder
        granular_points = []

        # Initialize streamlined workflow
        GranularAnalysisSessionManager.initialize_granular_workflow(request)

        # Store polygon geometry for streamlined workflow
        GranularAnalysisSessionManager.store_polygon_geometry(request, geometry)

        # Store complete polygon asset in session for streamlined workflow
        polygon_asset = {
            'id': f"polygon_{uuid.uuid4().hex[:8]}",  # Generate unique ID
            'Facility': asset_name,
            'Archetype': asset_archetype,
            'Lat': centroid_lat,
            'Long': centroid_lng,
            'geometry': geometry,
            'polygon_area_km2': area_km2,
            'grid_spacing_meters': grid_spacing,
            'granular-points': granular_points,
            'AssetType': 'polygon',
            'streamlined': True  # Mark as streamlined workflow asset
        }

        # Store in session facility data
        facility_data = request.session.get('climate_hazards_v2_facility_data', [])
        facility_data.append(polygon_asset)
        request.session['climate_hazards_v2_facility_data'] = facility_data

        # Set streamlined workflow flag
        request.session['streamlined_workflow'] = True
        request.session.modified = True

        logger.info(f"Streamlined polygon asset created: {asset_name} (centroid-only analysis)")

        return JsonResponse({
            'success': True,
            'message': f'Polygon asset "{asset_name}" created successfully. You can now proceed to hazard analysis.',
            'next_step': 'manual_hazard_selection',
            'asset_id': polygon_asset['id']
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data provided'
        }, status=400)
    except Exception as e:
        logger.exception(f"Error completing polygon drawing: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to complete polygon drawing'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def granular_analysis_grid(request):
    """
    API endpoint to process grid spacing for granular analysis and generate grid points.
    This endpoint creates the granular analysis framework for the polygon asset.
    """
    return JsonResponse({
        'success': False,
        'disabled': True,
        'error': 'Granular analysis is temporarily disabled. Centroid-only hazard exposure is available.'
    })


@csrf_exempt
@require_http_methods(["POST"])
def create_polygon_asset_with_granular(request):
    """
    API endpoint to create a polygon asset with granular analysis data.
    This creates both the asset record and initiates granular analysis processing.
    """
    return JsonResponse({
        'success': False,
        'disabled': True,
        'error': 'Granular analysis is temporarily disabled. Centroid-only hazard exposure is available.'
    })


@require_GET
def get_heatmap_data(request, asset_id):
    """
    API endpoint to retrieve heatmap data for a polygon asset.
    Returns pre-computed heatmap data for visualization.
    """
    return JsonResponse({
        'success': False,
        'disabled': True,
        'error': 'Granular heatmap data is temporarily disabled. Centroid-only hazard exposure is available.'
    })


@require_GET
def get_granular_analysis_status(request, asset_id):
    """
    API endpoint to get the status and progress of granular analysis for an asset.
    """
    return JsonResponse({
        'success': False,
        'disabled': True,
        'error': 'Granular analysis is temporarily disabled. Centroid-only hazard exposure is available.'
    })


def _convert_hierarchical_to_original_format(hierarchical_data: Dict[str, Any], selected_hazards: List[str]) -> List[Dict[str, Any]]:
    """
    Convert hierarchical data structure to original template format.

    Args:
        hierarchical_data: Hierarchical data from prepare_hierarchical_exposure_data
        selected_hazards: List of selected hazard types

    Returns:
        List of formatted rows compatible with original template
    """
    try:
        data = hierarchical_data['data']
        parent_row = data[0]
        child_rows = data[1:]

        formatted_rows = []

        # Format parent row (polygon centroid)
        parent_formatted = {
            'Facility': parent_row['name'],
            'Asset Archetype': parent_row.get('archetype', 'N/A'),
            'Latitude': parent_row['latitude'],
            'Longitude': parent_row['longitude'],
            'is_parent_facility': True,
            'has_granular_analysis': True,
            'sample_point_count': len(child_rows),
            'is_sample_point': False,
            'granular_analysis': {
                'dominant_risk': _calculate_dominant_risk(parent_row['hazards'], selected_hazards),
                'status': 'completed'
            }
        }

        # Add hazard data for parent row (aggregated statistics)
        for hazard in selected_hazards:
            if hazard in parent_row['hazards']:
                hazard_stats = parent_row['hazards'][hazard]
                parent_formatted[f'{hazard} Value'] = f"{hazard_stats.get('mean_value', 0):.2f}"
                parent_formatted[f'{hazard} Risk'] = _calculate_risk_level(hazard_stats.get('mean_value', 0), hazard)
            else:
                parent_formatted[f'{hazard} Value'] = 'N/A'
                parent_formatted[f'{hazard} Risk'] = 'No Data'

        formatted_rows.append(parent_formatted)

        # Format child rows (grid points)
        for i, child in enumerate(child_rows):
            child_formatted = {
                'Facility': f"{parent_row['name']} - Point {i+1}",
                'Asset Archetype': child.get('archetype', 'N/A'),
                'Latitude': child['latitude'],
                'Longitude': child['longitude'],
                'is_parent_facility': False,
                'has_granular_analysis': False,
                'is_sample_point': True,
                'parent_facility': parent_row['name'],
                'granular_analysis': {
                    'dominant_risk': _calculate_dominant_risk(child['hazards'], selected_hazards),
                    'status': 'completed'
                }
            }

            # Add hazard data for child row (individual values)
            for hazard in selected_hazards:
                if hazard in child['hazards']:
                    hazard_data = child['hazards'][hazard]
                    value = hazard_data.get('value')
                    risk = hazard_data.get('risk_level', 'unknown')

                    if value is not None:
                        child_formatted[f'{hazard} Value'] = f"{value:.2f}"
                        child_formatted[f'{hazard} Risk'] = risk.title()
                    else:
                        child_formatted[f'{hazard} Value'] = 'N/A'
                        child_formatted[f'{hazard} Risk'] = 'No Data'
                else:
                    child_formatted[f'{hazard} Value'] = 'N/A'
                    child_formatted[f'{hazard} Risk'] = 'No Data'

            formatted_rows.append(child_formatted)

        return formatted_rows

    except Exception as e:
        logger.exception(f"Error converting hierarchical data to original format: {str(e)}")
        return []


def _calculate_dominant_risk(hazards: Dict[str, Any], selected_hazards: List[str]) -> str:
    """Calculate dominant risk level from multiple hazards."""
    risk_scores = {'low': 1, 'medium': 2, 'high': 3, 'very high': 4}
    max_score = 0
    dominant_risk = 'medium'

    for hazard in selected_hazards:
        if hazard in hazards:
            hazard_stats = hazards[hazard]
            # For parent row, calculate risk from mean value
            mean_value = hazard_stats.get('mean_value', 0)
            risk_level = _calculate_risk_level(mean_value, hazard)

            score = risk_scores.get(risk_level.lower(), 2)
            if score > max_score:
                max_score = score
                dominant_risk = risk_level

    return dominant_risk


def _calculate_risk_level(value: float, hazard_type: str) -> str:
    """Calculate risk level based on hazard type and value."""
    if hazard_type == 'Heat':
        if value < 25:
            return 'Low'
        elif value < 30:
            return 'Medium'
        elif value < 35:
            return 'High'
        else:
            return 'Very High'
    elif hazard_type == 'Flood':
        if value < 0.1:
            return 'Low'
        elif value < 0.5:
            return 'Medium'
        elif value < 1.5:
            return 'High'
        else:
            return 'Very High'
    else:
        # Default risk calculation
        if value < 10:
            return 'Low'
        elif value < 30:
            return 'Medium'
        elif value < 50:
            return 'High'
        else:
            return 'Very High'


def _get_original_template_columns(selected_hazards: List[str]) -> List[str]:
    """Get column names in original template format."""
    columns = ['Facility', 'Asset Archetype', 'Latitude', 'Longitude']

    for hazard in selected_hazards:
        columns.extend([f'{hazard} Value', f'{hazard} Risk'])

    return columns


def _get_column_descriptions(selected_hazards: List[str]) -> Dict[str, str]:
    """Get column descriptions for tooltips."""
    descriptions = {
        'Facility': 'Asset name or identifier',
        'Asset Archetype': 'Asset category or type',
        'Latitude': 'Geographic latitude',
        'Longitude': 'Geographic longitude'
    }

    for hazard in selected_hazards:
        descriptions[f'{hazard} Value'] = f'{hazard} exposure value'
        descriptions[f'{hazard} Risk'] = f'{hazard} risk level'

    return descriptions


def _get_column_groups(selected_hazards: List[str]) -> Dict[str, int]:
    """Get column groups for header grouping."""
    groups = {
        'Asset Information': 4,  # Facility, Asset Archetype, Latitude, Longitude
    }

    for hazard in selected_hazards:
        groups[hazard] = 2  # Value and Risk columns

    return groups


def _handle_granular_polygon_results(request, asset_id: int, selected_hazards: List[str]):
    """
    Handle results display for polygon assets with granular analysis.
    Uses hierarchical data structure with centroid as parent and grid points as children.

    Args:
        request: Django request object
        asset_id: ID of the polygon asset
        selected_hazards: List of selected hazard types

    Returns:
        HttpResponse: Rendered results page with hierarchical table
    """
    try:
        from .granular_utils import prepare_hierarchical_exposure_data
        from .granular_processor import get_granular_analysis_summary

        asset = Asset.objects.get(id=asset_id)

        if not asset.has_granular_analysis:
            return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
                'error': 'Asset does not have granular analysis enabled.',
                'facility_count': 0,
                'hazard_types': _get_hazard_types(),
                'selected_hazards': selected_hazards
            })

        # Get analysis summary
        summary = get_granular_analysis_summary(asset_id)
        if not summary.get('success'):
            return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
                'error': f'Failed to get analysis summary: {summary.get("error")}',
                'facility_count': 0,
                'hazard_types': _get_hazard_types(),
                'selected_hazards': selected_hazards
            })

        # Prepare hierarchical exposure data
        hierarchical_data = prepare_hierarchical_exposure_data(asset, selected_hazards)

        if not hierarchical_data.get('success'):
            return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
                'error': f'Failed to prepare hierarchical data: {hierarchical_data.get("error")}',
                'facility_count': 0,
                'hazard_types': _get_hazard_types(),
                'selected_hazards': selected_hazards
            })

        # Convert hierarchical data to original template format
        formatted_data = _convert_hierarchical_to_original_format(hierarchical_data, selected_hazards)

        # Prepare context for template
        context = {
            # Original template format data
            'data': formatted_data,
            'columns': _get_original_template_columns(selected_hazards),
            'column_descriptions': _get_column_descriptions(selected_hazards),
            'groups': _get_column_groups(selected_hazards),

            # Metadata
            'facility_count': 1,  # Single asset
            'selected_hazards': selected_hazards,
            'asset': asset,
            'analysis_summary': summary,
            'is_granular_analysis': True,
            'analysis_status': asset.granular_analysis_status,
            'grid_points_count': hierarchical_data['grid_points_count'],
            'grid_spacing': asset.granular_grid_spacing,
            'analysis_progress': asset.granular_analysis_progress,
        }

        logger.info(f"Rendering hierarchical granular results for asset {asset.name} "
                   f"with {hierarchical_data['grid_points_count']} grid points "
                   f"and {len(selected_hazards)} hazards")
        return render(request, 'climate_hazards_analysis_v2/results.html', context)

    except Asset.DoesNotExist:
        logger.error(f"Asset {asset_id} not found")
        return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
            'error': 'Asset not found.',
            'facility_count': 0,
            'hazard_types': _get_hazard_types(),
            'selected_hazards': selected_hazards
        })
    except Exception as e:
        logger.exception(f"Error handling granular polygon results: {str(e)}")
        return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
            'error': f'Error processing granular analysis results: {str(e)}',
            'facility_count': 0,
            'hazard_types': _get_hazard_types(),
            'selected_hazards': selected_hazards
        })


def _generate_basic_polygon_hazard_exposure_map(request, asset_id: int):
    """
    Generate basic hazard exposure map data for polygon assets without granular analysis.
    Returns polygon geometry with placeholder hazard values.

    Args:
        request: Django request object
        asset_id: ID of the polygon asset

    Returns:
        JsonResponse: Map data with polygon boundary
    """
    try:
        asset = Asset.objects.get(id=asset_id)

        logger.info(f"Generating basic polygon hazard exposure map for asset {asset.name}")

        # Get selected hazards
        selected_hazards = request.session.get('climate_hazards_v2_selected_hazards', [])
        if not selected_hazards:
            # Default to all hazard types
            selected_hazards = ['Flood', 'Water Stress', 'Heat', 'Sea Level Rise', 'Tropical Cyclones', 'Storm Surge', 'Rainfall Induced Landslide']

        # Create GeoJSON feature collection
        features = []

        # Add the polygon boundary as a feature
        polygon_feature = {
            'type': 'Feature',
            'geometry': asset.polygon_geometry,
            'properties': {
                'id': asset.id,
                'name': asset.name,
                'asset_type': 'polygon',
                'feature_type': 'boundary',
                'hazard_values': {hazard: 0 for hazard in selected_hazards},  # Default to 0 for now
                'selected_hazards': selected_hazards,
                'granular_analysis_available': asset.has_granular_analysis
            }
        }
        features.append(polygon_feature)

        # Create the GeoJSON data structure
        geojson_data = {
            'type': 'FeatureCollection',
            'features': features
        }

        logger.info(f"Generated basic polygon map data for asset {asset.name} with {len(features)} features")

        return JsonResponse({
            'success': True,
            'data': geojson_data,
            'metadata': {
                'asset_name': asset.name,
                'asset_type': 'polygon',
                'selected_hazards': selected_hazards,
                'granular_analysis_available': asset.has_granular_analysis,
                'note': 'Basic polygon visualization - granular analysis not completed'
            }
        })

    except Asset.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Asset with ID {asset_id} not found'
        }, status=404)

    except Exception as e:
        logger.exception(f"Error generating basic polygon hazard exposure map: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Error generating polygon map data: {str(e)}'
        }, status=500)


def _generate_granular_hazard_exposure_map(request, asset_id: int):
    """
    Generate hazard exposure map data for polygon assets with granular analysis.
    Uses heatmap data for visualization of hazard exposure across the polygon area.

    Args:
        request: Django request object
        asset_id: ID of the polygon asset

    Returns:
        JsonResponse: Map data with heatmap layers for each hazard
    """
    try:
        asset = Asset.objects.get(id=asset_id)

        if not asset.has_granular_analysis:
            return JsonResponse({
                'success': False,
                'error': 'Asset does not have granular analysis enabled'
            }, status=400)

        # Get selected hazards
        selected_hazards = request.session.get('climate_hazards_v2_selected_hazards', [])
        if not selected_hazards:
            # Get hazard types from granular results if not in session
            selected_hazards = GranularAnalysisResult.objects.filter(
                asset=asset
            ).values_list('hazard_type', flat=True).distinct()

        logger.info(f"Generating hazard exposure map for asset {asset.name} with hazards: {selected_hazards}")

        # Create GeoJSON feature collection
        features = []

        # Add the polygon boundary as a feature
        polygon_feature = {
            'type': 'Feature',
            'geometry': asset.polygon_geometry,
            'properties': {
                'id': asset.id,
                'name': asset.name,
                'asset_type': 'polygon',
                'feature_type': 'boundary',
                'analysis_status': asset.granular_analysis_status,
                'grid_points_count': asset.granular_grid_points_count
            }
        }
        features.append(polygon_feature)

        # Generate heatmap data for each hazard type
        heatmap_layers = {}
        for hazard_type in selected_hazards:
            try:
                # Get or create heatmap data
                heatmap_data = HeatmapData.objects.filter(
                    asset=asset,
                    hazard_type=hazard_type,
                    processing_status='completed'
                ).first()

                if not heatmap_data:
                    logger.info(f"Generating heatmap data for hazard {hazard_type}")
                    from .granular_utils import create_heatmap_data
                    heatmap_data = create_heatmap_data(asset, hazard_type, 'current')

                if heatmap_data:
                    # Get heatmap grid points
                    grid_points = heatmap_data.get_heatmap_grid()

                    # Create heatmap layer
                    heatmap_layer = {
                        'type': 'heatmap',
                        'hazard_type': hazard_type,
                        'grid_points': grid_points,
                        'metadata': {
                            'min_value': heatmap_data.min_value,
                            'max_value': heatmap_data.max_value,
                            'mean_value': heatmap_data.mean_value,
                            'median_value': heatmap_data.median_value,
                            'grid_rows': heatmap_data.grid_rows,
                            'grid_cols': heatmap_data.grid_cols,
                            'bounding_box': {
                                'min_lat': float(heatmap_data.min_lat),
                                'max_lat': float(heatmap_data.max_lat),
                                'min_lng': float(heatmap_data.min_lng),
                                'max_lng': float(heatmap_data.max_lng)
                            }
                        }
                    }
                    heatmap_layers[hazard_type] = heatmap_layer

                    # Also add individual grid points as features for detailed visualization
                    for point in grid_points:
                        point_feature = {
                            'type': 'Feature',
                            'geometry': {
                                'type': 'Point',
                                'coordinates': [point['lng'], point['lat']]
                            },
                            'properties': {
                                'hazard_type': hazard_type,
                                'value': point['value'],
                                'row': point['row'],
                                'col': point['col'],
                                'feature_type': 'grid_point',
                                'asset_id': asset.id
                            }
                        }
                        features.append(point_feature)

            except Exception as e:
                logger.exception(f"Error generating heatmap for hazard {hazard_type}: {str(e)}")
                continue

        # Add aggregated point feature at centroid
        centroid_feature = {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [float(asset.longitude), float(asset.latitude)]
            },
            'properties': {
                'id': asset.id,
                'name': asset.name,
                'archetype': asset.archetype,
                'asset_type': 'polygon',
                'feature_type': 'centroid',
                'analysis_status': asset.granular_analysis_status,
                'grid_points_count': asset.granular_grid_points_count,
                'analysis_progress': asset.granular_analysis_progress
            }
        }
        features.append(centroid_feature)

        # Create final GeoJSON
        geojson_data = {
            'type': 'FeatureCollection',
            'features': features
        }

        # Prepare response data
        response_data = {
            'success': True,
            'data': geojson_data,
            'metadata': {
                'asset': {
                    'id': asset.id,
                    'name': asset.name,
                    'asset_type': 'polygon',
                    'analysis_status': asset.granular_analysis_status,
                    'grid_points_count': asset.granular_grid_points_count,
                    'analysis_progress': asset.granular_analysis_progress
                },
                'selected_hazards': selected_hazards,
                'heatmap_layers': heatmap_layers,
                'total_features': len(features),
                'hazard_configs': {
                    'Heat': {'icon': 'fas fa-temperature-high', 'color': '#dc3545'},
                    'Cold': {'icon': 'fas fa-snowflake', 'color': '#17a2b8'},
                    'Wind': {'icon': 'fas fa-wind', 'color': '#28a745'},
                    'Coastal': {'icon': 'fas fa-water', 'color': '#007bff'},
                    'Flooding': {'icon': 'fas fa-tint', 'color': '#6f42c1'},
                    'Drought': {'icon': 'fas fa-sun', 'color': '#fd7e14'},
                    'Landslide': {'icon': 'fas fa-mountain', 'color': '#6c757d'},
                    'Water Stress': {'icon': 'fas fa-tint-slash', 'color': '#20c997'},
                    'Sea Level Rise': {'icon': 'fas fa-water', 'color': '#0d6efd'},
                    'Tropical Cyclones': {'icon': 'fas fa-hurricane', 'color': '#fd7e14'},
                    'Storm Surge': {'icon': 'fas fa-water', 'color': '#0891b2'},
                    'Rainfall Induced Landslide': {'icon': 'fas fa-mountain', 'color': '#059669'}
                }
            }
        }

        logger.info(f"Generated granular hazard exposure map for asset {asset.name} with {len(features)} features")
        return JsonResponse(response_data)

    except Asset.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Asset not found'
        }, status=404)
    except Exception as e:
        logger.exception(f"Error generating granular hazard exposure map: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to generate granular hazard exposure map'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def clear_granular_workflow(request):
    """
    API endpoint to clear granular analysis workflow data from session.
    Used to reset the workflow and start over.
    """
    try:
        if not request.session.session_key:
            return JsonResponse({
                'success': False,
                'error': 'No active session'
            }, status=401)

        # Clear granular workflow data
        GranularAnalysisSessionManager.clear_granular_workflow(request)

        logger.info(f"Cleared granular workflow data from session {request.session.session_key}")

        return JsonResponse({
            'success': True,
            'message': 'Granular analysis workflow cleared successfully'
        })

    except Exception as e:
        logger.exception(f"Error clearing granular workflow: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to clear granular workflow'
        }, status=500)


@require_GET
def get_granular_workflow_state(request):
    """
    API endpoint to get current granular workflow state.
    Returns validation and status information about the current workflow.
    """
    try:
        if not request.session.session_key:
            return JsonResponse({
                'success': False,
                'error': 'No active session'
            }, status=401)

        # Get workflow state and validation
        workflow_summary = GranularAnalysisSessionManager.create_workflow_summary(request)
        validation_result = GranularAnalysisSessionManager.validate_workflow_state(request)

        response_data = {
            'success': True,
            'workflow_summary': workflow_summary,
            'validation': validation_result
        }

        return JsonResponse(response_data)

    except Exception as e:
        logger.exception(f"Error getting granular workflow state: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to get workflow state'
        }, status=500)


@require_POST
def generate_asset_exposure_analysis(request):
    """
    6-Step Workflow functionality has been removed.
    This endpoint is no longer available.
    """
    return JsonResponse({
        'success': False,
        'error': 'The 6-Step Workflow functionality has been removed. Please use the streamlined polygon workflow instead.'
    }, status=410)  # 410 Gone

# Original function removed - 6-Step Workflow functionality removed
# def generate_asset_exposure_analysis(request):
    """
    New endpoint for 6-step workflow: Generate real hazard analysis for polygon assets.
    This replaces the premature hazard analysis that was happening during asset creation.

    This endpoint:
    1. Processes selected hazards for existing polygon assets
    2. Performs real hazard data analysis (not fake/random data)
    3. Generates proper heatmaps with actual hazard values
    4. Returns aggregated results per polygon
    """
    try:
        if not request.session.session_key:
            request.session.create()

        data = json.loads(request.body)
        selected_hazards = data.get('selected_hazards', [])
        asset_ids = data.get('asset_ids', [])  # Optional: specific assets to analyze

        if not selected_hazards:
            return JsonResponse({
                'success': False,
                'error': 'No hazards selected for analysis'
            }, status=400)

        # Get facility data from session (now contains both uploaded and drawn assets)
        facility_data = request.session.get('climate_hazards_v2_facility_data', [])

        # Separate regular assets and polygon assets
        regular_assets = [f for f in facility_data if not f.get('geometry') and f.get('AssetType') != 'polygon']
        polygon_assets = [f for f in facility_data if f.get('geometry') or f.get('AssetType') == 'polygon']

        logger.info(f"Found {len(regular_assets)} regular assets and {len(polygon_assets)} polygon assets in session")

        if not regular_assets and not polygon_assets:
            return JsonResponse({
                'success': False,
                'error': 'No assets found. Please upload facility data or draw polygon assets first.'
            }, status=400)

        logger.info(f"Starting hazard analysis for {len(regular_assets)} regular assets and {len(polygon_assets)} polygon assets with hazards: {selected_hazards}")

        # Process regular assets (existing logic)
        regular_analysis_results = []
        for asset in regular_assets:
            try:
                # Create a simple result structure for regular assets
                asset_result = {
                    'asset_id': asset.get('id'),
                    'asset_name': asset.get('Facility'),
                    'asset_archetype': asset.get('Archetype', 'default archetype'),
                    'asset_type': 'regular',
                    'latitude': asset.get('Lat'),
                    'longitude': asset.get('Long'),
                    'hazard_analysis': {
                        'selected_hazards': selected_hazards,
                        'hazards': {hazard: None for hazard in selected_hazards}  # Placeholder
                    }
                }
                regular_analysis_results.append(asset_result)
            except Exception as e:
                logger.error(f"Error analyzing regular asset {asset.get('Facility', 'Unknown')}: {str(e)}")
                continue

        # Process polygon assets with granular analysis
        polygon_analysis_results = []
        for asset in polygon_assets:
            try:
                asset_result = _analyze_polygon_asset_hazards(
                    asset, selected_hazards, request.session.session_key
                )
                if asset_result:
                    polygon_analysis_results.append(asset_result)
            except Exception as e:
                logger.error(f"Error analyzing polygon asset {asset.get('Facility', 'Unknown')}: {str(e)}")
                continue

        # Combine all results for the results table
        combined_results = []

        # Add regular assets
        combined_results.extend(regular_analysis_results)

        # Add polygon centroids and granular points
        for polygon_result in polygon_analysis_results:
            combined_results.append(polygon_result['centroid_result'])
            combined_results.extend(polygon_result['granular_results'])

        if not combined_results:
            return JsonResponse({
                'success': False,
                'error': 'Failed to analyze any assets'
            }, status=500)

        # Store analysis results in session for results page
        request.session['climate_hazards_v2_analysis_results'] = combined_results
        request.session['climate_hazards_v2_selected_hazards'] = selected_hazards
        request.session.modified = True

        total_centroids = len(polygon_analysis_results)
        total_granular_points = sum(r['total_granular_points'] for r in polygon_analysis_results)

        logger.info(f"Successfully completed hazard analysis for {len(regular_analysis_results)} regular assets, {total_centroids} polygon centroids, and {total_granular_points} granular points")

        return JsonResponse({
            'success': True,
            'results': combined_results,
            'summary': {
                'regular_assets': len(regular_analysis_results),
                'polygon_centroids': total_centroids,
                'granular_points': total_granular_points,
                'total_rows': len(combined_results)
            },
            'hazards_analyzed': selected_hazards
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data provided'
        }, status=400)
    except Exception as e:
        logger.exception(f"Error in generate_asset_exposure_analysis: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Analysis failed: {str(e)}'
        }, status=500)


def _analyze_polygon_asset_hazards(asset, selected_hazards, session_key):
    """
    Analyze real hazard data for a single polygon asset.
    Returns aggregated hazard results for the polygon.
    """
    try:
        geometry = asset.get('geometry')
        if not geometry:
            logger.warning(f"Asset {asset.get('Facility')} has no geometry")
            return None

        # Get grid spacing if available, otherwise determine based on area
        grid_spacing = asset.get('grid_spacing_meters')
        area_km2 = asset.get('polygon_area_km2')

        if not grid_spacing and area_km2:
            # Determine appropriate grid spacing based on area
            if area_km2 >= 50:
                grid_spacing = 500  # Large areas
            elif area_km2 >= 10:
                grid_spacing = 200  # Medium areas
            else:
                grid_spacing = 100  # Small areas

        if not grid_spacing:
            grid_spacing = 100  # Default

        # Check if asset has granular analysis points stored
        granular_points = asset.get('granular-points', [])
        sample_points = []

        if granular_points:
            # Use existing granular points
            sample_points = granular_points
            logger.info(f"Using {len(granular_points)} stored granular points for {asset.get('Facility')}")
        else:
            # Generate sample points within the polygon (fallback)
            sample_points = generate_sample_grid(geometry, grid_spacing_meters=grid_spacing)
            logger.info(f"Generated {len(sample_points)} sample points for {asset.get('Facility')}")

        if not sample_points:
            logger.warning(f"No sample points available for asset {asset.get('Facility')}")
            return None

        # Analyze hazards for each sample point
        hazard_results = []
        for point in sample_points:
            point_result = {
                'latitude': point['latitude'],
                'longitude': point['longitude'],
                'hazards': {}
            }

            # Analyze each selected hazard
            for hazard in selected_hazards:
                try:
                    hazard_value = _get_hazard_value_at_point(
                        point['latitude'], point['longitude'], hazard
                    )
                    point_result['hazards'][hazard] = hazard_value
                except Exception as e:
                    logger.warning(f"Error getting {hazard} value at point {point['latitude']}, {point['longitude']}: {str(e)}")
                    point_result['hazards'][hazard] = None

            hazard_results.append(point_result)

        # Aggregate results for the polygon
        aggregated_results = _aggregate_hazard_results(hazard_results, selected_hazards)

        # Create centroid hazard analysis (parent row)
        centroid_hazards = {}
        for hazard in selected_hazards:
            # Calculate centroid hazard value as average of all points
            point_values = [point['hazards'].get(hazard) for point in hazard_results if point['hazards'].get(hazard) is not None]

            if point_values:
                centroid_hazards[hazard] = sum(point_values) / len(point_values)
            else:
                centroid_hazards[hazard] = None

        # Create parent-child structure for results table
        centroid_result = {
            'asset_id': asset.get('id'),
            'asset_name': asset.get('Facility'),
            'asset_archetype': asset.get('Archetype', 'default archetype'),
            'asset_type': 'polygon_centroid',  # Parent row
            'geometry': geometry,
            'latitude': asset.get('Lat'),
            'longitude': asset.get('Long'),
            'area_km2': area_km2,
            'grid_spacing_meters': grid_spacing,
            'sample_points_count': len(sample_points),
            'hazard_analysis': {
                'selected_hazards': selected_hazards,
                'hazards': centroid_hazards,
                'aggregated_results': aggregated_results
            }
        }

        # Create granular point results (child rows)
        granular_results = []
        for i, point in enumerate(sample_points):
            # Generate hazard analysis for this granular point
            point_hazards = {}
            for hazard in selected_hazards:
                hazard_value = _get_hazard_value_at_point(point['latitude'], point['longitude'], hazard)
                point_hazards[hazard] = hazard_value

            granular_result = {
                'asset_id': asset.get('id'),
                'asset_name': asset.get('Facility'),
                'parent_asset_id': asset.get('id'),  # Link to parent
                'asset_type': 'polygon_granular',  # Child row
                'point_number': i + 1,
                'geometry': None,  # Individual points don't have geometry
                'latitude': point['latitude'],
                'longitude': point['longitude'],
                'grid_position': point.get('grid_position', f"Point {i + 1}"),
                'hazard_analysis': {
                    'selected_hazards': selected_hazards,
                    'hazards': point_hazards
                }
            }
            granular_results.append(granular_result)

        return {
            'centroid_result': centroid_result,
            'granular_results': granular_results,
            'total_granular_points': len(granular_results)
        }

    except Exception as e:
        logger.exception(f"Error analyzing polygon asset hazards for {asset.get('Facility')}: {str(e)}")
        return None


def _get_hazard_value_at_point(latitude, longitude, hazard_type):
    """
    Get real hazard data value at a specific point.
    This replaces the fake/random data generation with actual hazard analysis.
    Fixed parameter order: (latitude, longitude, hazard_type)
    """
    try:
        # Hazard name mapping to handle variations
        hazard_name_mapping = {
            'Flood': 'flood',
            'Heat': 'heat',
            'Sea Level Rise': 'sea level rise',
            'Tropical Cyclones': 'tropical cyclones',
            'Storm Surge': 'storm surge',
            'Rainfall Induced Landslide': 'landslide',
            'Rainfall-Induced Landslide': 'landslide',
            'Water Stress': 'water stress'
        }

        # Normalize hazard type
        normalized_hazard = hazard_name_mapping.get(hazard_type, hazard_type.lower())

        # Implementation depends on your hazard data sources
        # This is a placeholder that should be replaced with actual hazard data retrieval

        if normalized_hazard == 'flood':
            # Example: Get flood depth from flood maps or API
            # This would integrate with real flood hazard data
            flood_depth = _get_flood_depth_at_point(latitude, longitude)
            return flood_depth

        elif normalized_hazard == 'heat':
            # Example: Get heat exposure from climate data
            # This would integrate with real heat hazard data
            temperature_increase = _get_temperature_increase_at_point(latitude, longitude)
            return temperature_increase

        elif normalized_hazard == 'tropical cyclones':
            # Example: Get wind speed from typhoon/climate data
            # This would integrate with real wind hazard data
            wind_speed = _get_wind_speed_at_point(latitude, longitude)
            return wind_speed

        elif normalized_hazard == 'storm surge':
            # Example: Get storm surge depth from coastal data
            # This would integrate with real storm surge data
            surge_depth = _get_storm_surge_at_point(latitude, longitude)
            return surge_depth

        elif normalized_hazard == 'landslide':
            # Example: Get landslide susceptibility from geological data
            # This would integrate with real landslide hazard data
            susceptibility = _get_landslide_susceptibility_at_point(latitude, longitude)
            return susceptibility

        elif normalized_hazard == 'sea level rise':
            # Example: Get sea level rise projection
            # This would integrate with real SLR data
            slr_value = _get_sea_level_rise_at_point(latitude, longitude)
            return slr_value

        elif normalized_hazard == 'water stress':
            # Example: Get water stress level from hydrological data
            # This would integrate with real water stress data
            stress_level = _get_water_stress_at_point(latitude, longitude)
            return stress_level

        else:
            logger.warning(f"Unknown hazard type: {hazard_type} (normalized: {normalized_hazard})")
            return None

    except Exception as e:
        logger.error(f"Error getting hazard value for {hazard_type} at {latitude}, {longitude}: {str(e)}")
        return None


def _get_flood_depth_at_point(latitude, longitude):
    """
    Get flood depth at a specific point from flood hazard data.
    Mock implementation for development - generates realistic flood depth values.
    """
    import random
    import math

    # Create realistic flood depth patterns based on location
    # Higher flood risk near water bodies (simplified model for Philippines)

    # Normalize coordinates for consistent results
    lat_norm = (latitude - 12.0) / 2.0  # Normalize around Philippines center
    lng_norm = (longitude - 121.0) / 2.0

    # Create distance from water bodies (simplified model)
    # Areas near coasts have higher flood risk
    water_proximity = math.sqrt(lat_norm**2 + lng_norm**2)

    # Base flood depth calculation
    base_depth = 0.5 + (1.0 - water_proximity) * 2.0  # 0.5-2.5m range
    random_factor = random.uniform(0.8, 1.2)  # Random variation

    flood_depth = max(0, base_depth * random_factor)

    # Return simple numeric value
    return flood_depth


def _get_risk_level_from_flood_depth(depth):
    """Calculate risk level based on flood depth."""
    if depth < 0.5:
        return 'Low'
    elif depth < 1.0:
        return 'Medium'
    elif depth < 2.0:
        return 'High'
    else:
        return 'Very High'


def _get_risk_level_from_temperature(increase):
    """Calculate risk level based on temperature increase."""
    if increase < 1.0:
        return 'Low'
    elif increase < 2.0:
        return 'Medium'
    elif increase < 3.0:
        return 'High'
    else:
        return 'Very High'


def _get_risk_level_from_wind_speed(speed):
    """Calculate risk level based on wind speed."""
    if speed < 50:
        return 'Low'
    elif speed < 80:
        return 'Medium'
    elif speed < 120:
        return 'High'
    else:
        return 'Very High'


def _get_risk_level_from_surge_height(height):
    """Calculate risk level based on storm surge height."""
    if height < 1.0:
        return 'Low'
    elif height < 2.0:
        return 'Medium'
    elif height < 3.0:
        return 'High'
    else:
        return 'Very High'


def _get_risk_level_from_landslide_fos(fos):
    """Calculate risk level based on landslide factor of safety."""
    if fos > 1.5:
        return 'Low'
    elif fos > 1.0:
        return 'Medium'
    elif fos > 0.7:
        return 'High'
    else:
        return 'Very High'


def _get_risk_level_from_sea_level_rise(slr):
    """Calculate risk level based on sea level rise."""
    if slr < 0.5:
        return 'Low'
    elif slr < 1.0:
        return 'Medium'
    elif slr < 2.0:
        return 'High'
    else:
        return 'Very High'


def _get_risk_level_from_water_stress(stress):
    """Calculate risk level based on water stress percentage."""
    if stress < 20:
        return 'Low'
    elif stress < 40:
        return 'Medium'
    elif stress < 60:
        return 'High'
    else:
        return 'Very High'


def _get_temperature_increase_at_point(latitude, longitude):
    """
    Get temperature increase at a specific point from climate data.
    Mock implementation for development - generates realistic temperature values.
    """
    import random
    import math

    # Create realistic temperature increase patterns
    # Urban areas have higher temperature increases (heat island effect)
    # Higher latitudes may have different warming patterns

    # Normalize coordinates for consistent results
    lat_norm = (latitude - 12.0) / 5.0
    lng_norm = (longitude - 121.0) / 5.0

    # Urban heat island effect simulation (simplified)
    urban_factor = 1.0 + 0.3 * (1.0 - math.sqrt(lat_norm**2 + lng_norm**2))

    # Base temperature increase (climate change projection)
    base_increase = 1.2 + 0.8 * abs(lat_norm)  # 1.2-2.0°C range
    random_factor = random.uniform(0.9, 1.1)

    temp_increase = base_increase * urban_factor * random_factor

    # Return simple numeric value
    return temp_increase


def _get_wind_speed_at_point(latitude, longitude):
    """
    Get wind speed at a specific point from wind hazard data.
    Mock implementation for development - generates realistic wind speed values.
    """
    import random
    import math

    # Create realistic wind speed patterns
    # Coastal areas have higher wind speeds

    # Normalize coordinates for consistent results
    lat_norm = (latitude - 12.0) / 5.0
    lng_norm = (longitude - 121.0) / 5.0

    # Coastal exposure simulation
    coastal_factor = 1.0 + 0.5 * (1.0 - math.sqrt(lat_norm**2 + lng_norm**2))

    # Base wind speed calculation
    base_speed = 60 + 40 * coastal_factor  # 60-100 km/h range
    random_factor = random.uniform(0.8, 1.2)

    wind_speed = base_speed * random_factor

    # Return simple numeric value
    return wind_speed


def _get_landslide_susceptibility_at_point(latitude, longitude):
    """
    Get landslide susceptibility at a specific point from landslide hazard data.
    Mock implementation for development - generates realistic landslide susceptibility values.
    """
    import random
    import math

    # Create realistic landslide susceptibility patterns
    # Higher susceptibility in areas with elevation changes and steep slopes

    # Normalize coordinates for consistent results
    lat_norm = (latitude - 12.0) / 5.0
    lng_norm = (longitude - 121.0) / 5.0

    # Simulate topographic variation (simplified model)
    # Areas with higher coordinate variation represent steeper terrain
    elevation_variation = math.sin(lat_norm * 3) * math.cos(lng_norm * 3)

    # Base susceptibility calculation (Factor of Safety)
    # Lower FoS = Higher susceptibility
    base_fos = 1.5 - abs(elevation_variation) * 0.8  # 0.7-1.5 range
    random_factor = random.uniform(0.9, 1.1)

    factor_of_safety = max(0.3, base_fos * random_factor)

    # Return simple numeric value
    return factor_of_safety


def _get_sea_level_rise_at_point(latitude, longitude):
    """
    Get sea level rise projection at a specific point from SLR data.
    Mock implementation for development - generates realistic SLR values.
    """
    import random
    import math

    # Create realistic sea level rise patterns
    # Coastal areas have higher SLR impact

    # Normalize coordinates for consistent results
    lat_norm = (latitude - 12.0) / 5.0
    lng_norm = (longitude - 121.0) / 5.0

    # Calculate distance from coast (simplified model)
    # Areas closer to "coast" (lower coordinate values) have higher impact
    coastal_proximity = math.sqrt(lat_norm**2 + lng_norm**2)

    # Base sea level rise calculation (for 2050 projection)
    # Higher values for coastal areas
    base_slr = 0.3 + (1.0 - coastal_proximity) * 0.7  # 0.3-1.0m range
    random_factor = random.uniform(0.9, 1.1)

    sea_level_rise = base_slr * random_factor

    # Return simple numeric value
    return sea_level_rise


def _get_storm_surge_at_point(latitude, longitude):
    """
    Get storm surge depth at a specific point from storm surge data.
    Mock implementation for development - generates realistic storm surge values.
    """
    import random
    import math

    # Create realistic storm surge patterns
    # Higher surge risk in coastal areas and low-lying regions

    # Normalize coordinates for consistent results
    lat_norm = (latitude - 12.0) / 5.0
    lng_norm = (longitude - 121.0) / 5.0

    # Calculate coastal exposure
    coastal_proximity = math.sqrt(lat_norm**2 + lng_norm**2)

    # Base storm surge calculation
    # Higher values for coastal areas
    base_surge = 1.0 + (1.0 - coastal_proximity) * 2.5  # 1.0-3.5m range
    random_factor = random.uniform(0.8, 1.2)

    storm_surge = max(0.1, base_surge * random_factor)

    # Return simple numeric value
    return storm_surge


def _get_water_stress_at_point(latitude, longitude):
    """
    Get water stress level at a specific point from water stress data.
    Mock implementation for development - generates realistic water stress values.
    """
    import random
    import math

    # Create realistic water stress patterns
    # Varies based on climate zones and population density

    # Normalize coordinates for consistent results
    lat_norm = (latitude - 12.0) / 5.0
    lng_norm = (longitude - 121.0) / 5.0

    # Simulate climate variation (simplified model)
    # Some areas are naturally drier than others
    climate_factor = 0.5 + 0.5 * math.sin(lat_norm * 2) * math.cos(lng_norm * 2)

    # Base water stress calculation
    base_stress = 15 + climate_factor * 35  # 15-50% range
    random_factor = random.uniform(0.9, 1.1)

    water_stress = max(5, min(95, base_stress * random_factor))

    # Return simple numeric value
    return water_stress


def _aggregate_hazard_results(hazard_results, selected_hazards):
    """
    Aggregate hazard analysis results for a polygon.
    Returns statistics for each hazard type across all sample points.
    Simplified to work with numeric hazard values.
    """
    aggregated = {}

    for hazard in selected_hazards:
        hazard_values = []
        valid_points = 0

        for point_result in hazard_results:
            hazard_value = point_result['hazards'].get(hazard)
            if hazard_value is not None:
                hazard_values.append(hazard_value)
                valid_points += 1

        if hazard_values:
            aggregated[hazard] = {
                'valid_points': valid_points,
                'total_points': len(hazard_results),
                'statistics': {
                    'min': min(hazard_values),
                    'max': max(hazard_values),
                    'mean': sum(hazard_values) / len(hazard_values),
                    'median': sorted(hazard_values)[len(hazard_values) // 2]
                }
            }

            # Add risk classification based on hazard type
            if hazard.lower() == 'flood':
                aggregated[hazard]['risk_classification'] = _classify_flood_risk(hazard_values)
            elif hazard.lower() == 'heat':
                aggregated[hazard]['risk_classification'] = _classify_heat_risk(hazard_values)
            elif hazard.lower() in ['tropical cyclones', 'wind']:
                aggregated[hazard]['risk_classification'] = _classify_wind_risk(hazard_values)
            elif hazard.lower() in ['landslide', 'rainfall induced landslide', 'rainfall-induced landslide']:
                aggregated[hazard]['risk_classification'] = _classify_landslide_risk(hazard_values)
            elif hazard.lower() == 'storm surge':
                aggregated[hazard]['risk_classification'] = _classify_surge_risk(hazard_values)
            elif hazard.lower() == 'sea level rise':
                aggregated[hazard]['risk_classification'] = _classify_slr_risk(hazard_values)
            elif hazard.lower() == 'water stress':
                aggregated[hazard]['risk_classification'] = _classify_water_stress_risk(hazard_values)
        else:
            aggregated[hazard] = {
                'valid_points': 0,
                'total_points': len(hazard_results),
                'statistics': None,
                'risk_classification': 'No Data'
            }

    return aggregated


def _classify_flood_risk(flood_values):
    """Classify flood risk based on flood depth values."""
    if not flood_values:
        return 'No Data'

    avg_depth = sum(flood_values) / len(flood_values)

    if avg_depth < 0.5:
        return 'Low'
    elif avg_depth < 1.5:
        return 'Medium'
    else:
        return 'High'


def _classify_heat_risk(heat_values):
    """Classify heat risk based on temperature increase values."""
    if not heat_values:
        return 'No Data'

    avg_increase = sum(heat_values) / len(heat_values)

    if avg_increase < 2.0:
        return 'Low'
    elif avg_increase < 4.0:
        return 'Medium'
    else:
        return 'High'


def _classify_wind_risk(wind_values):
    """Classify wind risk based on wind speed values."""
    if not wind_values:
        return 'No Data'

    avg_speed = sum(wind_values) / len(wind_values)

    if avg_speed < 50:  # km/h
        return 'Low'
    elif avg_speed < 100:
        return 'Medium'
    else:
        return 'High'


def _classify_landslide_risk(landslide_values):
    """Classify landslide risk based on factor of safety values."""
    if not landslide_values:
        return 'No Data'

    avg_fos = sum(landslide_values) / len(landslide_values)

    if avg_fos > 1.5:
        return 'Low'
    elif avg_fos > 1.0:
        return 'Medium'
    else:
        return 'High'


def _classify_surge_risk(surge_values):
    """Classify storm surge risk based on surge height values."""
    if not surge_values:
        return 'No Data'

    avg_surge = sum(surge_values) / len(surge_values)

    if avg_surge < 1.0:  # meters
        return 'Low'
    elif avg_surge < 2.5:
        return 'Medium'
    else:
        return 'High'


def _classify_slr_risk(slr_values):
    """Classify sea level rise risk based on SLR values."""
    if not slr_values:
        return 'No Data'

    avg_slr = sum(slr_values) / len(slr_values)

    if avg_slr < 0.5:  # meters
        return 'Low'
    elif avg_slr < 1.5:
        return 'Medium'
    else:
        return 'High'


def _classify_water_stress_risk(water_stress_values):
    """Classify water stress risk based on water stress percentage values."""
    if not water_stress_values:
        return 'No Data'

    avg_stress = sum(water_stress_values) / len(water_stress_values)

    if avg_stress < 25:  # percentage
        return 'Low'
    elif avg_stress < 50:
        return 'Medium'
    else:
        return 'High'


def _handle_6step_workflow_results(request, analysis_results, selected_hazards):
    """
    6-Step Workflow functionality has been removed.
    This function is no longer available.
    """
    logger.warning("_handle_6step_workflow_results called but 6-Step Workflow has been removed")
    return render(request, 'climate_hazards_analysis_v2/results.html', {
        'error': 'The 6-Step Workflow functionality has been removed. Please use the streamlined polygon workflow instead.',
        'data': [],
        'columns': [],
        'selected_hazards': selected_hazards,
        'facility_count': 0
    })

# Original function removed - 6-Step Workflow functionality removed
# def _handle_6step_workflow_results(request, analysis_results, selected_hazards):
    """
    Handle results from the new 6-step workflow.
    Creates a results table showing one row per polygon with aggregated hazard data.
    """
    try:
        logger.info(f"Creating 6-step workflow results table for {len(analysis_results)} assets")

        # Create aggregated results data for the template
        aggregated_data = []
        columns = ['Facility', 'Asset Archetype', 'Area (km²)', 'Sample Points']

        # Add hazard columns based on selected hazards
        hazard_columns = []
        for hazard in selected_hazards:
            if hazard.lower() == 'flood':
                hazard_columns.extend([f'{hazard} Risk', f'{hazard} Depth (m)'])
            elif hazard.lower() == 'heat':
                hazard_columns.extend([f'{hazard} Risk', f'{hazard} Increase (°C)'])
            elif hazard.lower() == 'wind':
                hazard_columns.extend([f'{hazard} Risk', f'{hazard} Speed (km/h)'])
            elif hazard.lower() == 'landslide':
                hazard_columns.extend([f'{hazard} Risk', f'{hazard} Susceptibility (%)'])
            elif hazard.lower() == 'sea level rise':
                hazard_columns.extend([f'{hazard} Risk', f'{hazard} Rise (m)'])
            else:
                hazard_columns.append(f'{hazard} Risk')

        columns.extend(hazard_columns)
        columns.extend(['Overall Risk', 'Data Coverage'])

        # Process each asset result
        for asset_result in analysis_results:
            asset_type = asset_result.get('asset_type', 'regular')

            if asset_type == 'polygon_centroid':
                # Create centroid row (parent)
                row = {
                    'Facility': f"🟢 {asset_result.get('asset_name', 'Unknown')} (Centroid)",
                    'Asset Archetype': f"{asset_result.get('asset_archetype', 'default archetype')} - Polygon Centroid",
                    'Area (km²)': f"{asset_result.get('area_km2', 0):.2f}",
                    'Sample Points': asset_result.get('sample_points_count', 0),
                    'has_granular_analysis': True,
                    'is_parent_facility': True,
                    'sample_point_count': asset_result.get('sample_points_count', 0),
                    'polygon_geometry': asset_result.get('geometry'),
                    'hazard_analysis': asset_result.get('hazard_analysis', {}),
                    'asset_id': asset_result.get('asset_id'),
                    'parent_asset_id': None,
                    'point_number': None,
                    'asset_type': 'polygon_centroid'
                }
            elif asset_type == 'polygon_granular':
                # Create granular point row (child)
                parent_name = asset_result.get('asset_name', 'Unknown')
                point_num = asset_result.get('point_number', 1)
                row = {
                    'Facility': f"🔵 {parent_name} - Granular Point {point_num}",
                    'Asset Archetype': f"{asset_result.get('asset_archetype', 'default archetype')} - Granular Point",
                    'Area (km²)': "N/A",
                    'Sample Points': "1",
                    'has_granular_analysis': False,
                    'is_parent_facility': False,
                    'is_sample_point': True,
                    'sample_point_count': 1,
                    'polygon_geometry': None,
                    'hazard_analysis': asset_result.get('hazard_analysis', {}),
                    'asset_id': asset_result.get('asset_id'),
                    'parent_asset_id': asset_result.get('parent_asset_id'),
                    'point_number': point_num,
                    'grid_position': asset_result.get('grid_position', f"Point {point_num}"),
                    'latitude': asset_result.get('latitude'),
                    'longitude': asset_result.get('longitude'),
                    'asset_type': 'polygon_granular'
                }
            else:
                # Regular asset
                row = {
                    'Facility': asset_result.get('asset_name', 'Unknown'),
                    'Asset Archetype': asset_result.get('asset_archetype', 'default archetype'),
                    'Area (km²)': "N/A",
                    'Sample Points': "1",
                    'has_granular_analysis': False,
                    'is_parent_facility': True,
                    'sample_point_count': 1,
                    'polygon_geometry': None,
                    'hazard_analysis': asset_result.get('hazard_analysis', {}),
                    'asset_id': asset_result.get('asset_id'),
                    'parent_asset_id': None,
                    'point_number': None,
                    'asset_type': 'regular'
                }

            # Add hazard data based on asset type
            hazard_analysis = asset_result.get('hazard_analysis', {})

            if asset_type == 'polygon_centroid':
                # Use aggregated results for centroid
                aggregated_results = hazard_analysis.get('aggregated_results', {})
                hazards = hazard_analysis.get('hazards', {})

                for hazard in selected_hazards:
                    # Use centroid-calculated hazard value
                    hazard_value = hazards.get(hazard)
                    risk_classification = 'No Data'

                    if hazard_value is not None:
                        # Classify risk based on hazard value
                        if hazard.lower() == 'flood':
                            if hazard_value > 2.0:
                                risk_classification = 'High'
                            elif hazard_value > 1.0:
                                risk_classification = 'Medium'
                            elif hazard_value > 0.5:
                                risk_classification = 'Low'
                            else:
                                risk_classification = 'Very Low'
                            row[f'{hazard} Depth (m)'] = f"{hazard_value:.2f}"
                        elif hazard.lower() == 'heat':
                            if hazard_value > 3.0:
                                risk_classification = 'High'
                            elif hazard_value > 2.0:
                                risk_classification = 'Medium'
                            elif hazard_value > 1.0:
                                risk_classification = 'Low'
                            else:
                                risk_classification = 'Very Low'
                            row[f'{hazard} Increase (°C)'] = f"{hazard_value:.1f}"
                        else:
                            risk_classification = 'Medium'  # Default
                            row[f'{hazard} Risk'] = risk_classification

                    row[f'{hazard} Risk'] = risk_classification

            elif asset_type == 'polygon_granular':
                # Use individual point hazard data
                hazards = hazard_analysis.get('hazards', {})

                for hazard in selected_hazards:
                    hazard_value = hazards.get(hazard)
                    risk_classification = 'No Data'

                    if hazard_value is not None:
                        # Classify risk for individual point using numeric hazard value
                        if hazard.lower() == 'flood':
                            if hazard_value > 2.0:
                                risk_classification = 'High'
                            elif hazard_value > 1.0:
                                risk_classification = 'Medium'
                            elif hazard_value > 0.5:
                                risk_classification = 'Low'
                            else:
                                risk_classification = 'Very Low'
                            row[f'{hazard} Depth (m)'] = f"{hazard_value:.2f}"
                        elif hazard.lower() == 'heat':
                            if hazard_value > 3.0:
                                risk_classification = 'High'
                            elif hazard_value > 2.0:
                                risk_classification = 'Medium'
                            elif hazard_value > 1.0:
                                risk_classification = 'Low'
                            else:
                                risk_classification = 'Very Low'
                            row[f'{hazard} Increase (°C)'] = f"{hazard_value:.1f}"
                        elif hazard.lower() in ['tropical cyclones', 'wind']:
                            if hazard_value > 120:
                                risk_classification = 'High'
                            elif hazard_value > 80:
                                risk_classification = 'Medium'
                            elif hazard_value > 50:
                                risk_classification = 'Low'
                            else:
                                risk_classification = 'Very Low'
                            row[f'{hazard} Speed (km/h)'] = f"{hazard_value:.0f}"
                        elif hazard.lower() == 'storm surge':
                            if hazard_value > 3.0:
                                risk_classification = 'High'
                            elif hazard_value > 2.0:
                                risk_classification = 'Medium'
                            elif hazard_value > 1.0:
                                risk_classification = 'Low'
                            else:
                                risk_classification = 'Very Low'
                            row[f'{hazard} Depth (m)'] = f"{hazard_value:.2f}"
                        elif hazard.lower() in ['landslide', 'rainfall induced landslide', 'rainfall-induced landslide']:
                            if hazard_value < 0.7:
                                risk_classification = 'High'
                            elif hazard_value < 1.0:
                                risk_classification = 'Medium'
                            elif hazard_value < 1.5:
                                risk_classification = 'Low'
                            else:
                                risk_classification = 'Very Low'
                            row[f'{hazard} Factor of Safety'] = f"{hazard_value:.2f}"
                        elif hazard.lower() == 'sea level rise':
                            if hazard_value > 2.0:
                                risk_classification = 'High'
                            elif hazard_value > 1.0:
                                risk_classification = 'Medium'
                            elif hazard_value > 0.5:
                                risk_classification = 'Low'
                            else:
                                risk_classification = 'Very Low'
                            row[f'{hazard} (m)'] = f"{hazard_value:.2f}"
                        elif hazard.lower() == 'water stress':
                            if hazard_value > 60:
                                risk_classification = 'High'
                            elif hazard_value > 40:
                                risk_classification = 'Medium'
                            elif hazard_value > 20:
                                risk_classification = 'Low'
                            else:
                                risk_classification = 'Very Low'
                            row[f'{hazard} (%)'] = f"{hazard_value:.1f}"
                        else:
                            risk_classification = 'Medium'
                            row[f'{hazard} Risk'] = risk_classification

                    row[f'{hazard} Risk'] = risk_classification

            else:
                # Regular asset - no hazard data
                for hazard in selected_hazards:
                    row[f'{hazard} Risk'] = 'No Data'
                    if hazard.lower() == 'flood':
                        row[f'{hazard} Depth (m)'] = 'N/A'
                    elif hazard.lower() == 'heat':
                        row[f'{hazard} Increase (°C)'] = 'N/A'

            # Calculate overall risk and data coverage
            risk_scores = []
            data_count = 0

            for hazard in selected_hazards:
                risk_key = f'{hazard} Risk'
                risk_value = row.get(risk_key, 'No Data')

                if risk_value != 'No Data' and risk_value != 'N/A':
                    data_count += 1
                    if risk_value == 'Very Low':
                        risk_scores.append(0)
                    elif risk_value == 'Low':
                        risk_scores.append(1)
                    elif risk_value == 'Medium':
                        risk_scores.append(2)
                    elif risk_value == 'High':
                        risk_scores.append(3)

            # Calculate data coverage
            avg_coverage = (data_count / len(selected_hazards) * 100) if selected_hazards else 0
            row['Data Coverage'] = f"{avg_coverage:.1f}%"

            # Calculate overall risk
            if risk_scores:
                avg_risk = sum(risk_scores) / len(risk_scores)
                if avg_risk < 1:
                    row['Overall Risk'] = 'Low'
                elif avg_risk < 2:
                    row['Overall Risk'] = 'Medium'
                else:
                    row['Overall Risk'] = 'High'
            else:
                row['Overall Risk'] = 'No Data'

            aggregated_data.append(row)

        # Create context for template
        context = {
            'data': aggregated_data,
            'columns': columns,
            'selected_hazards': selected_hazards,
            'facility_count': len(aggregated_data),
            'analysis_type': '6-step-workflow',
            'groups': {
                'Asset Information': 4,  # Facility, Asset Archetype, Area, Sample Points
                'Hazard Analysis': len(hazard_columns),
                'Summary': 2  # Overall Risk, Data Coverage
            },
            'show_6step_workflow': True,
            'analysis_results': analysis_results  # Pass raw results for detailed modals
        }

        logger.info(f"Rendering 6-step workflow results with {len(aggregated_data)} rows and {len(columns)} columns")

        return render(request, 'climate_hazards_analysis_v2/results.html', context)

    except Exception as e:
        logger.exception(f"Error handling 6-step workflow results: {str(e)}")
        # Fallback to regular results processing
        return render(request, 'climate_hazards_analysis_v2/results.html', {
            'error': f'Error processing 6-step workflow results: {str(e)}',
            'data': [],
            'columns': [],
            'selected_hazards': selected_hazards,
            'facility_count': 0
        })


@csrf_exempt
@require_http_methods(["POST"])
def execute_complete_granular_workflow(request):
    """
    API endpoint to execute the complete end-to-end granular analysis workflow.

    This endpoint orchestrates the entire pipeline:
    1. Polygon drawing → Grid generation
    2. Grid point creation → Hazard analysis (optional)
    3. Batch processing → Results aggregation
    4. Heatmap generation → Results table integration

    Expected JSON payload:
    {
        "asset_name": "My Polygon Asset",
        "polygon_geometry": {...GeoJSON...},
        "selected_hazards": ["Heat", "Flooding", "Sea Level Rise"] (optional),
        "archetype": "default archetype",
        "grid_spacing": 0.001,
        "scenario": "current"
    }
    """
    try:
        # No authentication required for point generation
        # This is a stateless endpoint for grid point generation only

        # Debug: Print the incoming request data (always visible)
        print(f"=== DEBUG: Request received ===")
        print(f"Request body: {request.body}")
        print(f"Request headers: {dict(request.headers)}")
        print(f"Request method: {request.method}")
        print(f"Request content type: {request.content_type}")

        try:
            data = json.loads(request.body)
            print(f"Parsed JSON data: {data}")
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Raw body content: {request.body}")
            return JsonResponse({
                'success': False,
                'error': f'Invalid JSON data: {str(e)}'
            }, status=400)
        except Exception as e:
            print(f"Unexpected error parsing request: {e}")
            return JsonResponse({
                'success': False,
                'error': f'Error parsing request: {str(e)}'
            }, status=400)

        # Validate required fields
        if not data.get('asset_name', '').strip():
            return JsonResponse({
                'success': False,
                'error': 'Asset name is required'
            }, status=400)

        if not data.get('polygon_geometry'):
            return JsonResponse({
                'success': False,
                'error': 'Polygon geometry is required'
            }, status=400)

        # Note: selected_hazards is no longer required for pure grid point generation

        # Extract parameters
        asset_name = data['asset_name'].strip()
        polygon_geometry = data['polygon_geometry']
        selected_hazards = data.get('selected_hazards', [])  # Optional for pure point generation
        archetype = data.get('archetype', 'default archetype').strip() or 'default archetype'
        grid_spacing = float(data.get('grid_spacing', 0.001))
        scenario = data.get('scenario', 'current')

        # Validate grid spacing
        if grid_spacing <= 0 or grid_spacing > 1:
            return JsonResponse({
                'success': False,
                'error': 'Grid spacing must be between 0 and 1 degree'
            }, status=400)

        logger.info(f"Starting complete granular workflow for asset: {asset_name}")
        logger.info(f"Selected hazards: {selected_hazards}")
        logger.info(f"Grid spacing: {grid_spacing}")

        # Execute complete workflow using the service
        workflow_results = execute_granular_analysis_workflow(
            polygon_geometry=polygon_geometry,
            asset_name=asset_name,
            selected_hazards=selected_hazards,
            archetype=archetype,
            scenario=scenario,
            grid_spacing=grid_spacing
        )

        if not workflow_results.get('success'):
            return JsonResponse({
                'success': False,
                'error': workflow_results.get('error', 'Workflow execution failed'),
                'failed_step': workflow_results.get('step', 'unknown'),
                'partial_results': workflow_results.get('partial_results', {})
            }, status=500)

        # Store results in session for immediate display
        GranularAnalysisSessionManager.store_workflow_results(request, workflow_results)

        # Update session with asset ID for workflow tracking
        asset_id = workflow_results.get('asset_id')
        if asset_id:
            GranularAnalysisSessionManager.store_asset_id(request, asset_id)

        logger.info(f"Complete granular workflow executed successfully for {asset_name}")
        logger.info(f"Generated {workflow_results.get('grid_points_generated', 0)} grid points")
        logger.info(f"Processed {len(workflow_results.get('table_results', []))} hazard results")

        return JsonResponse({
            'success': True,
            'workflow_results': workflow_results,
            'asset_id': asset_id,
            'message': f'Successfully completed granular analysis for {asset_name}',
            # 'redirect_url': reverse('climate_hazards_analysis_v2:show_results') + f'?asset_id={asset_id}&granular_analysis=true',
            'next_step': 'display_results'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data provided'
        }, status=400)
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': f'Invalid parameter value: {str(e)}'
        }, status=400)
    except Exception as e:
        logger.exception(f"Error executing complete granular workflow: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to execute complete granular analysis workflow'
        }, status=500)


@require_GET
def get_workflow_results_table(request, asset_id):
    """
    API endpoint to retrieve granular analysis results formatted for the hazard exposure table.

    Args:
        request: Django request object
        asset_id: ID of the asset with granular analysis
    """
    try:
        asset = Asset.objects.get(id=asset_id)

        if not asset.has_granular_analysis:
            return JsonResponse({
                'success': False,
                'error': 'Asset does not have granular analysis enabled'
            }, status=400)

        # Get selected hazards from session or use all available
        selected_hazards = request.GET.getlist('hazards')
        if not selected_hazards:
            # Get hazard types from granular results
            selected_hazards = list(GranularAnalysisResult.objects.filter(
                asset=asset
            ).values_list('hazard_type', flat=True).distinct())

        # Use workflow service to get table results
        workflow_service = GranularAnalysisWorkflowService()

        # Get aggregated results
        aggregated_results = {}
        for hazard_type in selected_hazards:
            stats = calculate_granular_statistics(asset, hazard_type)
            if stats:
                aggregated_results[hazard_type] = {
                    'statistics': stats,
                    'risk_summary': workflow_service._calculate_risk_summary(stats),
                    'exposure_distribution': workflow_service._calculate_exposure_distribution(asset, hazard_type, 'current')
                }

        # Prepare table results
        table_results = workflow_service._prepare_hazard_exposure_table(
            asset, selected_hazards, aggregated_results
        )

        # Format response for data table
        response_data = {
            'success': True,
            'data': table_results,
            'columns': list(table_results[0].keys()) if table_results else [],
            'asset_info': {
                'id': asset.id,
                'name': asset.name,
                'asset_type': asset.asset_type,
                'granular_analysis_status': asset.granular_analysis_status,
                'grid_points_count': asset.granular_grid_points_count
            },
            'summary': {
                'total_rows': len(table_results),
                'hazard_types': selected_hazards,
                'analysis_complete': asset.granular_analysis_status == 'completed'
            }
        }

        return JsonResponse(response_data)

    except Asset.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Asset not found'
        }, status=404)
    except Exception as e:
        logger.exception(f"Error getting workflow results table: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to get workflow results table'
        }, status=500)


# ============================================================================
# STREAMLINED DRAW POLYGON WORKFLOW
# ============================================================================

def select_hazards_streamlined(request):
    """
    Streamlined hazard selection for draw polygon assets.
    Auto-selects all hazards and redirects directly to hazard analysis results.
    """
    # Check if this is a polygon workflow
    if not GranularAnalysisSessionManager.is_granular_workflow(request):
        # Redirect to regular hazard selection for non-polygon workflows
        return redirect('climate_hazards_analysis_v2:select_hazards')

    # Auto-select all hazards for streamlined workflow
    all_hazards = [
        'Flood',
        'Water Stress',
        'Heat',
        'Sea Level Rise',
        'Tropical Cyclones',
        'Storm Surge',
        'Rainfall Induced Landslide'
    ]

    # Store selected hazards in session
    request.session['climate_hazards_v2_selected_hazards'] = all_hazards

    # Get polygon geometry from session
    polygon_geometry = GranularAnalysisSessionManager.get_polygon_geometry(request)
    if not polygon_geometry:
        logger.error("No polygon geometry found in session")
        return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
            'error': 'No polygon geometry found. Please draw polygon again.',
            'hazard_types': all_hazards,
            'selected_hazards': all_hazards
        })

    # Redirect directly to streamlined hazard analysis results
    return redirect('climate_hazards_analysis_v2:hazard_exposure_results_streamlined')


def hazard_exposure_results_streamlined(request):
    """
    Streamlined hazard exposure results for draw polygon assets.
    Bypasses 6-step workflow and goes directly to hazard analysis.
    """
    logger.info("=== STREAMLINED HAZARD EXPOSURE RESULTS ===")

    # Validate session data
    selected_hazards = request.session.get('climate_hazards_v2_selected_hazards', [])
    if not selected_hazards:
        logger.error("No selected hazards found")
        return redirect('climate_hazards_analysis_v2:select_hazards')

    # Get polygon geometry from session
    polygon_geometry = GranularAnalysisSessionManager.get_polygon_geometry(request)
    if not polygon_geometry:
        logger.error("No polygon geometry found in session")
        return redirect('climate_hazards_analysis_v2:view_map')

    try:
        # Calculate polygon centroid
        centroid = calculate_polygon_centroid(polygon_geometry)

        # Create polygon asset data structure
        polygon_asset = {
            'id': 'streamlined_polygon',
            'Facility': 'Drawn Polygon Asset',
            'AssetType': 'polygon',
            'Archetype': 'default archetype',
            'Lat': centroid[0],
            'Long': centroid[1],
            'geometry': polygon_geometry,
            'polygon_area_km2': calculate_polygon_area_km2(polygon_geometry),
            'grid_spacing_meters': None,
            'granular-points': [],
            'granular_analysis_enabled': False,
            'sample_points_count': 0
        }

        # Analyze hazards for all points (centroid + granular points)
        hazard_analysis_results = _analyze_polygon_asset_hazards_streamlined(
            polygon_asset, selected_hazards, request.session.session_key, centroid_only=True
        )

        if not hazard_analysis_results:
            logger.error("Failed to analyze hazards for polygon asset")
            return render(request, 'climate_hazards_analysis_v2/hazard_exposure_results_streamlined.html', {
                'error': 'Failed to analyze hazards for the drawn polygon.',
                'selected_hazards': selected_hazards
            })

        # Prepare hierarchical results for template
        hierarchical_results = _prepare_hierarchical_results_streamlined(
            hazard_analysis_results, selected_hazards
        )

        context = {
            'polygon_asset': polygon_asset,
            'hierarchical_results': hierarchical_results,
            'selected_hazards': selected_hazards,
            'total_points': 1,  # centroid only
            'analysis_timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'streamlined_workflow': True,
            'requires_hierarchical_display': False
        }

        return render(request, 'climate_hazards_analysis_v2/hazard_exposure_results_streamlined.html', context)

    except Exception as e:
        logger.exception(f"Error in streamlined hazard exposure results: {str(e)}")
        return render(request, 'climate_hazards_analysis_v2/hazard_exposure_results_streamlined.html', {
            'error': f'An error occurred during hazard analysis: {str(e)}',
            'selected_hazards': selected_hazards
        })


def _analyze_polygon_asset_hazards_streamlined(polygon_asset, selected_hazards, session_key, centroid_only=False):
    """
    Analyze hazards for polygon asset using existing hazard functions.
    Supports centroid-only mode (no granular points) while keeping structure for future granular reuse.
    """
    try:
        geometry = polygon_asset.get('geometry')
        if not geometry:
            logger.error("Polygon asset has no geometry")
            return None

        granular_points = [] if centroid_only else polygon_asset.get('granular-points', [])
        if granular_points:
            logger.info(f"Analyzing hazards for {len(granular_points)} granular points + centroid")
        else:
            logger.info("Granular analysis disabled: analyzing centroid only")

        # Analyze hazards for each granular point (skipped when centroid_only is True)
        granular_results = []
        for i, point in enumerate(granular_points):
            if isinstance(point, dict):
                lat = point.get('latitude') or point.get('lat')
                lng = point.get('longitude') or point.get('lng') or point.get('long')
            else:
                lat, lng = point[0], point[1]

            point_result = {
                'point_id': f'point_{i+1}',
                'latitude': lat,
                'longitude': lng,
                'hazards': {}
            }

            for hazard in selected_hazards:
                try:
                    hazard_value = _get_hazard_value_at_point(lat, lng, hazard)
                    point_result['hazards'][hazard] = hazard_value
                except Exception as e:
                    logger.warning(f"Error getting {hazard} value at point {lat}, {lng}: {str(e)}")
                    point_result['hazards'][hazard] = None

            granular_results.append(point_result)

        # Analyze hazards for centroid (parent row)
        centroid_lat = polygon_asset.get('Lat')
        centroid_lng = polygon_asset.get('Long')
        centroid_result = {
            'point_id': 'centroid',
            'latitude': centroid_lat,
            'longitude': centroid_lng,
            'hazards': {}
        }

        # Calculate centroid hazard values
        for hazard in selected_hazards:
            if granular_results:
                point_values = [
                    point['hazards'].get(hazard)
                    for point in granular_results
                    if point['hazards'].get(hazard) is not None
                ]
                if point_values:
                    centroid_result['hazards'][hazard] = sum(point_values) / len(point_values)
                    continue

            # Fallback: analyze actual centroid location (used in centroid-only mode)
            try:
                centroid_result['hazards'][hazard] = _get_hazard_value_at_point(
                    centroid_lat, centroid_lng, hazard
                )
            except Exception as e:
                logger.warning(f"Error getting {hazard} value at centroid: {str(e)}")
                centroid_result['hazards'][hazard] = None

        hierarchical_analysis = {
            'centroid': centroid_result,
            'granular_points': granular_results,
            'aggregated_stats': _calculate_aggregated_hazard_stats(granular_results, selected_hazards)
        }

        logger.info(
            f"Completed hazard analysis for polygon asset: {len(granular_results)} granular points + centroid"
        )
        return hierarchical_analysis

    except Exception as e:
        logger.exception(f"Error analyzing polygon asset hazards: {str(e)}")
        return None


def _prepare_hierarchical_results_streamlined(hazard_analysis_results, selected_hazards):
    """
    Prepare hierarchical results data for template rendering.
    Creates parent-child structure for centroid and granular points.
    """
    try:
        if not hazard_analysis_results:
            return []

        centroid = hazard_analysis_results.get('centroid')
        granular_points = hazard_analysis_results.get('granular_points', [])
        aggregated_stats = hazard_analysis_results.get('aggregated_stats', {})

        hierarchical_data = []

        # Create parent row (centroid)
        centroid_row = {
            'id': 'centroid',
            'parent_id': None,
            'facility_name': 'Drawn Polygon Asset (Centroid)',
            'asset_type': 'centroid',
            'latitude': centroid['latitude'],
            'longitude': centroid['longitude'],
            'is_parent': True,
            'is_expanded': False,
            'child_count': len(granular_points),
            'hazards': {}
        }

        # Process centroid hazards
        for hazard in selected_hazards:
            hazard_value = centroid['hazards'].get(hazard)
            risk_level = _calculate_risk_level(hazard_value, hazard)

            centroid_row['hazards'][hazard] = {
                'value': hazard_value,
                'risk_level': risk_level,
                'display_value': _format_hazard_value(hazard_value, hazard),
                'risk_color': _get_risk_color(risk_level)
            }

        hierarchical_data.append(centroid_row)

        # Create child rows (granular points)
        for i, point in enumerate(granular_points):
            point_row = {
                'id': point['point_id'],
                'parent_id': 'centroid',
                'facility_name': f'Analysis Point {i+1}',
                'asset_type': 'granular_point',
                'latitude': point['latitude'],
                'longitude': point['longitude'],
                'is_parent': False,
                'is_child': True,
                'hazards': {}
            }

            # Process point hazards
            for hazard in selected_hazards:
                hazard_value = point['hazards'].get(hazard)
                risk_level = _calculate_risk_level(hazard_value, hazard)

                point_row['hazards'][hazard] = {
                    'value': hazard_value,
                    'risk_level': risk_level,
                    'display_value': _format_hazard_value(hazard_value, hazard),
                    'risk_color': _get_risk_color(risk_level)
                }

            hierarchical_data.append(point_row)

        return hierarchical_data

    except Exception as e:
        logger.exception(f"Error preparing hierarchical results: {str(e)}")
        return []


def _calculate_aggregated_hazard_stats(granular_results, selected_hazards):
    """Calculate aggregated statistics for all granular points."""
    try:
        stats = {}

        for hazard in selected_hazards:
            values = [point['hazards'].get(hazard) for point in granular_results if point['hazards'].get(hazard) is not None]

            if values:
                stats[hazard] = {
                    'min': min(values),
                    'max': max(values),
                    'avg': sum(values) / len(values),
                    'count': len(values),
                    'null_count': len(granular_results) - len(values)
                }
            else:
                stats[hazard] = {
                    'min': None,
                    'max': None,
                    'avg': None,
                    'count': 0,
                    'null_count': len(granular_results)
                }

        return stats

    except Exception as e:
        logger.exception(f"Error calculating aggregated hazard stats: {str(e)}")
        return {}


# Helper functions for streamlined workflow
def calculate_polygon_centroid(polygon_geometry):
    """Calculate centroid of polygon geometry."""
    try:
        coordinates = polygon_geometry['coordinates'][0]  # Exterior ring
        lats = [coord[1] for coord in coordinates]
        lngs = [coord[0] for coord in coordinates]
        return (sum(lats) / len(lats), sum(lngs) / len(lngs))
    except Exception as e:
        logger.exception(f"Error calculating polygon centroid: {str(e)}")
        return (0.0, 0.0)


def calculate_polygon_area_km2(polygon_geometry):
    """Calculate approximate area of polygon in km²."""
    try:
        # Simple approximation using bounding box
        coordinates = polygon_geometry['coordinates'][0]
        lats = [coord[1] for coord in coordinates]
        lngs = [coord[0] for coord in coordinates]

        lat_diff = max(lats) - min(lats)
        lng_diff = max(lngs) - min(lngs)

        # Convert to approximate area (very rough approximation)
        lat_km = lat_diff * 111.32  # 1 degree latitude ≈ 111.32 km
        lng_km = lng_diff * 111.32 * abs(sum(lats) / len(lats))  # Adjust for latitude

        return lat_km * lng_km
    except Exception as e:
        logger.exception(f"Error calculating polygon area: {str(e)}")
        return 0.0


def _get_hazard_value_at_point(latitude, longitude, hazard_type):
    """Get hazard value at a specific point using existing hazard functions."""
    try:
        from .utils import load_cached_hazard_data

        # Load hazard data
        hazard_data = load_cached_hazard_data(hazard_type)

        # Use existing hazard analysis functions
        if hazard_type.lower() == 'flood':
            from .utils import _get_flood_depth_at_point
            return _get_flood_depth_at_point(latitude, longitude, hazard_data)
        elif hazard_type.lower() == 'heat':
            from .utils import _get_heat_increase_at_point
            return _get_heat_increase_at_point(latitude, longitude, hazard_data)
        elif hazard_type.lower() == 'water stress':
            from .utils import _get_water_stress_at_point
            return _get_water_stress_at_point(latitude, longitude, hazard_data)
        elif hazard_type.lower() == 'sea level rise':
            from .utils import _get_sea_level_rise_at_point
            return _get_sea_level_rise_at_point(latitude, longitude, hazard_data)
        elif hazard_type.lower() == 'tropical cyclones':
            from .utils import _get_cyclone_probability_at_point
            return _get_cyclone_probability_at_point(latitude, longitude, hazard_data)
        elif hazard_type.lower() == 'storm surge':
            from .utils import _get_storm_surge_at_point
            return _get_storm_surge_at_point(latitude, longitude, hazard_data)
        elif hazard_type.lower() == 'rainfall induced landslide':
            from .utils import _get_landslide_susceptibility_at_point
            return _get_landslide_susceptibility_at_point(latitude, longitude, hazard_data)
        else:
            logger.warning(f"Unknown hazard type: {hazard_type}")
            return None

    except Exception as e:
        logger.exception(f"Error getting hazard value at point: {str(e)}")
        return None


def _calculate_risk_level(hazard_value, hazard_type):
    """Calculate risk level based on hazard value and type."""
    if hazard_value is None:
        return 'No Data'

    try:
        if hazard_type.lower() == 'flood':
            if hazard_value <= 0:
                return 'No Risk'
            elif hazard_value <= 0.5:
                return 'Low'
            elif hazard_value <= 1.5:
                return 'Medium'
            elif hazard_value <= 3.0:
                return 'High'
            else:
                return 'Very High'
        elif hazard_type.lower() == 'heat':
            if hazard_value <= 0:
                return 'No Risk'
            elif hazard_value <= 1.0:
                return 'Low'
            elif hazard_value <= 2.0:
                return 'Medium'
            elif hazard_value <= 3.5:
                return 'High'
            else:
                return 'Very High'
        elif hazard_type.lower() == 'water stress':
            if hazard_value <= 0.1:
                return 'No Risk'
            elif hazard_value <= 0.2:
                return 'Low'
            elif hazard_value <= 0.4:
                return 'Medium'
            elif hazard_value <= 0.6:
                return 'High'
            else:
                return 'Very High'
        else:
            # Default risk classification
            if hazard_value <= 0:
                return 'No Risk'
            elif hazard_value <= 0.3:
                return 'Low'
            elif hazard_value <= 0.6:
                return 'Medium'
            elif hazard_value <= 0.8:
                return 'High'
            else:
                return 'Very High'
    except Exception as e:
        logger.exception(f"Error calculating risk level: {str(e)}")
        return 'Unknown'


def _format_hazard_value(hazard_value, hazard_type):
    """Format hazard value for display."""
    if hazard_value is None:
        return 'N/A'

    try:
        if hazard_type.lower() == 'flood':
            return f"{hazard_value:.2f} m"
        elif hazard_type.lower() == 'heat':
            return f"{hazard_value:.1f}°C"
        elif hazard_type.lower() == 'water stress':
            return f"{hazard_value:.1%}"
        elif hazard_type.lower() == 'sea level rise':
            return f"{hazard_value:.2f} m"
        elif hazard_type.lower() == 'tropical cyclones':
            return f"{hazard_value:.1%}"
        elif hazard_type.lower() == 'storm surge':
            return f"{hazard_value:.2f} m"
        elif hazard_type.lower() == 'rainfall induced landslide':
            return f"{hazard_value:.1%}"
        else:
            return f"{hazard_value:.3f}"
    except Exception as e:
        logger.exception(f"Error formatting hazard value: {str(e)}")
        return str(hazard_value)


def _get_risk_color(risk_level):
    """Get color code for risk level."""
    risk_colors = {
        'No Data': '#6c757d',
        'No Risk': '#28a745',
        'Low': '#ffc107',
        'Medium': '#fd7e14',
        'High': '#dc3545',
        'Very High': '#6f42c1',
        'Unknown': '#6c757d'
    }
    return risk_colors.get(risk_level, '#6c757d')


@require_GET
def load_granular_data(request):
    """
    Load combined_output.csv data for granular hazard exposure visualization.

    Returns:
        HttpResponse: CSV file content as plain text
    """
    try:
        # Path to the combined_output.csv file
        csv_path = os.path.join(settings.BASE_DIR, 'climate_hazards_analysis', 'static', 'input_files', 'combined_output.csv')

        # Check if file exists
        if not os.path.exists(csv_path):
            logger.error(f"Combined output CSV file not found at: {csv_path}")
            return JsonResponse({
                'error': 'Granular analysis data file not found',
                'message': 'Please ensure a granular analysis has been completed.'
            }, status=404)

        # Read and return the CSV content
        with open(csv_path, 'r', encoding='utf-8') as file:
            csv_content = file.read()

        # Create response with proper content type
        response = HttpResponse(csv_content, content_type='text/csv')
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET'
        response['Access-Control-Allow-Headers'] = 'Content-Type'

        logger.info(f"Successfully loaded granular data with {len(csv_content.split(chr(10)))} lines")
        return response

    except Exception as e:
        logger.exception(f"Error loading granular data: {str(e)}")
        return JsonResponse({
            'error': 'Failed to load granular data',
            'message': str(e)
        }, status=500)


class EnhancedHazardExposureMapView(TemplateView):
    """
    Enhanced view for hazard exposure map with granular point visualization.
    Provides comprehensive interactive mapping features for 11 granular analysis points.
    """
    template_name = 'climate_hazards_analysis_v2/enhanced_hazard_exposure_map.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add map configuration
        context.update({
            'page_title': 'Enhanced Hazard Exposure Map',
            'mapbox_token': getattr(settings, 'MAPBOX_ACCESS_TOKEN', ''),
            'map_style': 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
            'default_center': [121.074, 14.267],  # Center of granular points
            'default_zoom': 14,
            'enable_granular_analysis': True,
            'max_granular_points': 50,  # Performance limit
            'supported_hazards': [
                'flood', 'water_stress', 'sea_level_rise',
                'tropical_cyclone', 'heat', 'storm_surge', 'landslide'
            ],
            'scenarios': ['current', 'moderate', 'worst']
        })

        # Check if granular data is available
        csv_path = os.path.join(settings.BASE_DIR, 'climate_hazards_analysis', 'static', 'input_files', 'combined_output.csv')
        context['granular_data_available'] = os.path.exists(csv_path)

        if context['granular_data_available']:
            try:
                # Get file modification time
                file_mtime = os.path.getmtime(csv_path)
                from datetime import datetime
                context['data_last_updated'] = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                context['data_last_updated'] = 'Unknown'
        else:
            context['data_last_updated'] = None

        return context


# ============================================================================
# JSON WORKFLOW FUNCTIONS
# ============================================================================

def _create_unified_assets_json(request):
    """
    Create a unified JSON structure containing all uploaded assets.
    This consolidates all asset data from multiple file uploads into a single JSON structure.
    """
    try:
        from .models import Asset

        # Get all uploaded assets from the current session
        session_key = request.session.session_key
        uploaded_asset_ids = request.session.get('climate_hazards_v2_uploaded_asset_ids', [])

        # Primary source of truth: all assets for this session key
        session_assets_qs = Asset.objects.filter(session_key=session_key, source='uploaded_file') if session_key else Asset.objects.none()
        session_asset_ids = list(session_assets_qs.values_list('id', flat=True))

        # Merge with any tracked IDs in session (legacy safety)
        if uploaded_asset_ids:
            session_asset_ids = list({*session_asset_ids, *uploaded_asset_ids})

        if not session_asset_ids:
            logger.info("No uploaded assets to create unified JSON")
            return None

        # Normalize and persist the merged IDs back to the session
        unique_asset_ids = list(set(session_asset_ids))
        if len(unique_asset_ids) != len(uploaded_asset_ids):
            logger.info(f"Session asset IDs refreshed from DB for session_key={session_key}; total {len(unique_asset_ids)} assets")
        request.session['climate_hazards_v2_uploaded_asset_ids'] = unique_asset_ids
        request.session.modified = True

        # Get all assets from database using the unified list
        assets = Asset.objects.filter(id__in=unique_asset_ids, source='uploaded_file')

        # Create unified JSON structure
        unified_assets = {
            "metadata": {
                "total_assets": assets.count(),
                "upload_session_id": request.session.session_key,
                "created_at": timezone.now().isoformat(),
                "files_uploaded": [],
                "asset_types": {"point_assets": 0, "polygon_assets": 0}
            },
            "assets": []
        }

        # Process each asset
        for asset in assets:
            asset_data = {
                "database_id": asset.id,
                "name": asset.name,
                "latitude": float(asset.latitude),
                "longitude": float(asset.longitude),
                "archetype": asset.archetype,
                "asset_type": asset.asset_type,
                "source": asset.source,
                "created_at": asset.created_at.isoformat(),
                "properties": asset.properties,
                "polygon_geometry": asset.polygon_geometry
            }

            unified_assets["assets"].append(asset_data)

            # Track file uploads
            original_filename = asset.properties.get('original_filename', 'unknown')
            if original_filename not in [f['filename'] for f in unified_assets["metadata"]["files_uploaded"]]:
                file_info = {
                    "filename": original_filename,
                    "file_type": asset.properties.get('file_type', 'unknown'),
                    "upload_id": asset.properties.get('file_upload_id', 'unknown'),
                    "asset_count": 0
                }
                unified_assets["metadata"]["files_uploaded"].append(file_info)

            # Update file asset count
            for file_info in unified_assets["metadata"]["files_uploaded"]:
                if file_info["filename"] == original_filename:
                    file_info["asset_count"] += 1

            # Count asset types
            if asset.asset_type == 'polygon':
                unified_assets["metadata"]["asset_types"]["polygon_assets"] += 1
            else:
                unified_assets["metadata"]["asset_types"]["point_assets"] += 1

        # Store unified JSON in session for easy access
        request.session['unified_uploaded_assets_json'] = unified_assets
        request.session.modified = True

        logger.info(f"Created unified JSON for {unified_assets['metadata']['total_assets']} assets "
                   f"from {len(unified_assets['metadata']['files_uploaded'])} files")

        return unified_assets

    except Exception as e:
        logger.error(f"Error creating unified assets JSON: {str(e)}")
        logger.exception("Full traceback:")
        return None


def _get_all_uploaded_assets_json(request):
    """
    Get the unified JSON containing all uploaded assets.
    Returns the stored unified JSON or creates it if it doesn't exist.
    """
    try:
        # Check if unified JSON already exists in session
        unified_assets = request.session.get('unified_uploaded_assets_json')

        if not unified_assets:
            logger.info("No unified assets JSON found in session, creating new one")
            unified_assets = _create_unified_assets_json(request)

        return unified_assets

    except Exception as e:
        logger.error(f"Error getting unified assets JSON: {str(e)}")
        return None


def _update_unified_json_on_file_removal(request, removed_file_id):
    """
    Update the unified JSON when a file is removed.
    This ensures the unified JSON stays synchronized with the current session state.
    """
    try:
        # Recreate unified JSON to reflect changes
        _create_unified_assets_json(request)
        logger.info(f"Updated unified JSON after removing file {removed_file_id}")

    except Exception as e:
        logger.error(f"Error updating unified JSON on file removal: {str(e)}")


def _store_hazard_selections_in_unified_json(request, selected_hazards):
    """
    Store hazard selections in the unified JSON structure.
    This adds the selected hazards to the existing unified assets JSON.
    """
    try:
        # Get or create unified JSON
        unified_assets = _get_all_uploaded_assets_json(request)

        if not unified_assets:
            logger.warning("No unified assets found, creating empty structure for hazard selection")
            unified_assets = {
                "metadata": {
                    "total_assets": 0,
                    "upload_session_id": request.session.session_key,
                    "created_at": timezone.now().isoformat(),
                    "files_uploaded": [],
                    "asset_types": {"point_assets": 0, "polygon_assets": 0},
                    "hazard_selection": {
                        "selected_hazards": [],
                        "selection_timestamp": None,
                        "total_hazards_available": 0,
                        "selection_source": "unknown"
                    }
                },
                "assets": []
            }

        # Update hazard selection metadata
        from datetime import datetime
        unified_assets["metadata"]["hazard_selection"] = {
            "selected_hazards": selected_hazards,
            "selection_timestamp": datetime.now().isoformat(),
            "total_hazards_available": 7,  # Total available hazard types
            "selection_source": "web_form",
            "hazards_count": len(selected_hazards)
        }

        # Add hazard analysis parameters to each asset
        for asset in unified_assets["assets"]:
            asset["selected_hazards"] = selected_hazards
            asset["hazard_analysis_status"] = "pending"

        # Store updated unified JSON in session
        request.session['unified_uploaded_assets_json'] = unified_assets
        request.session.modified = True

        logger.info(f"Stored {len(selected_hazards)} hazard selections in unified JSON for session {request.session.session_key[:8]}...")

        return unified_assets

    except Exception as e:
        logger.error(f"Error storing hazard selections in unified JSON: {str(e)}")
        logger.exception("Full traceback:")
        return None


def _get_unified_json_for_analysis(request):
    """
    Get the unified JSON structure ready for analysis.
    Includes both asset data and selected hazards for the analysis engine.
    """
    try:
        # Ensure data consistency with display workflow by rebuilding combined facility data
        # This fixes the multi-file upload inconsistency issue
        _rebuild_combined_facility_data(request)

        unified_assets = _get_all_uploaded_assets_json(request)

        if not unified_assets:
            logger.error("No unified assets found for analysis")
            return None

        # Check if hazards have been selected
        hazard_selection = unified_assets["metadata"].get("hazard_selection", {})
        selected_hazards = hazard_selection.get("selected_hazards", [])

        if not selected_hazards:
            logger.warning("No hazards selected for analysis")
            return None

        # SAFEGUARD: Validate that assets in unified JSON match current session assets
        session_asset_ids = request.session.get('climate_hazards_v2_uploaded_asset_ids', [])
        unified_asset_ids = [asset['database_id'] for asset in unified_assets.get('assets', [])]

        if not unified_asset_ids or (session_asset_ids and set(session_asset_ids) != set(unified_asset_ids)):
            logger.warning(f"Unified asset IDs ({len(unified_asset_ids)}) out of sync with session ({len(session_asset_ids)}) - rebuilding unified JSON")
            logger.debug(f"Session IDs: {session_asset_ids}")
            logger.debug(f"Unified IDs: {unified_asset_ids}")
            unified_assets = _create_unified_assets_json(request)
            if not unified_assets:
                logger.error("Failed to rebuild unified JSON")
                return None
            hazard_selection = unified_assets["metadata"].get("hazard_selection", {})
            selected_hazards = hazard_selection.get("selected_hazards", [])
            if not selected_hazards:
                logger.warning("No hazards found after unified JSON rebuild")
                return None

        # Prepare analysis data structure
        analysis_data = {
            "metadata": {
                "session_id": unified_assets["metadata"]["upload_session_id"],
                "total_assets": unified_assets["metadata"]["total_assets"],
                "selected_hazards": selected_hazards,
                "selection_timestamp": hazard_selection.get("selection_timestamp"),
                "files_uploaded": unified_assets["metadata"]["files_uploaded"],
                "asset_types": unified_assets["metadata"]["asset_types"],
                "analysis_status": "ready"
            },
            "assets_for_analysis": []
        }

        # Prepare assets for analysis with required keys
        for asset in unified_assets["assets"]:
            analysis_asset = {
                "Facility": asset["name"],
                "Lat": float(asset["latitude"]),
                "Long": float(asset["longitude"]),
                "Archetype": asset["archetype"],
                "_file_id": asset.get("properties", {}).get("file_upload_id"),
                "selected_hazards": selected_hazards,
                "asset_id": asset["database_id"],
                "asset_type": asset["asset_type"],
                "source_file": asset.get("properties", {}).get("original_filename", "unknown")
            }

            # Add polygon geometry if available
            if asset.get("polygon_geometry"):
                analysis_asset["polygon_geometry"] = asset["polygon_geometry"]

            analysis_data["assets_for_analysis"].append(analysis_asset)

        logger.info(f"Prepared {len(analysis_data['assets_for_analysis'])} assets for hazard analysis with {len(selected_hazards)} selected hazards")

        return analysis_data

    except Exception as e:
        logger.error(f"Error preparing unified JSON for analysis: {str(e)}")
        logger.exception("Full traceback:")
        return None


def _execute_climate_analysis_unified_json(request):
    """
    Execute climate hazards analysis using unified JSON data.
    This function uses the consolidated JSON structure containing both assets and hazards.
    """
    try:
        # Get unified JSON ready for analysis
        analysis_data = _get_unified_json_for_analysis(request)

        if not analysis_data:
            logger.error("No unified JSON data available for analysis")
            return None

        # Extract analysis parameters
        selected_hazards = analysis_data["metadata"]["selected_hazards"]
        assets_for_analysis = analysis_data["assets_for_analysis"]

        if not assets_for_analysis:
            logger.error("No assets available for analysis")
            return None

        logger.info(f"Starting climate hazards analysis for {len(assets_for_analysis)} assets with {len(selected_hazards)} hazards")

        # Log analysis step to console
        from .json_console_simple import simple_json_console
        simple_json_console.log_analysis_step(
            analysis_data=assets_for_analysis,
            hazards=selected_hazards,
            processing_status="starting_unified_json_analysis"
        )

        # Create temporary CSV from unified JSON for analysis engine compatibility
        import pandas as pd
        from django.conf import settings
        import tempfile
        import uuid

        # Convert assets to DataFrame
        df = pd.DataFrame(assets_for_analysis)

        # Create temporary CSV file
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        temp_filename = f'unified_analysis_{uuid.uuid4().hex[:8]}.csv'
        temp_csv_path = os.path.join(UPLOAD_DIR, temp_filename)

        # Clean up old JSON files to prevent conflicts
        import glob
        import time
        old_json_pattern = os.path.join(UPLOAD_DIR, 'combined_output*.json')
        old_json_files = glob.glob(old_json_pattern)
        for old_json in old_json_files:
            try:
                file_age = time.time() - os.path.getmtime(old_json)
                if file_age > 3600:  # Remove files older than 1 hour
                    os.remove(old_json)
                    logger.info(f"Removed old JSON file: {old_json}")
            except Exception as e:
                logger.warning(f"Could not remove old JSON file {old_json}: {e}")

        # Save to CSV for analysis engine
        df.to_csv(temp_csv_path, index=False)
        logger.info(f"Created temporary unified analysis CSV: {temp_csv_path}")

        # Execute analysis using existing engine
        from climate_hazards_analysis.utils.climate_hazards_analysis import generate_climate_hazards_analysis

        result = generate_climate_hazards_analysis(
            facility_csv_path=temp_csv_path,
            selected_fields=selected_hazards,
            flood_scenarios=['current', 'moderate', 'worst']
        )

        # Clean up temporary file
        try:
            if os.path.exists(temp_csv_path):
                os.remove(temp_csv_path)
                logger.info(f"Cleaned up temporary file: {temp_csv_path}")
        except Exception as e:
            logger.warning(f"Could not remove temporary file {temp_csv_path}: {e}")

        # Check for errors
        if result is None or 'error' in result:
            error_message = result.get('error', 'Unknown error') if result else 'Analysis failed.'
            logger.error(f"Climate hazards analysis error: {error_message}")

            # Log error to console
            simple_json_console.log_analysis_step(
                analysis_data=assets_for_analysis,
                hazards=selected_hazards,
                processing_status=f"error: {error_message}"
            )
            return None

        # Log successful completion
        simple_json_console.log_analysis_step(
            analysis_data=assets_for_analysis,
            hazards=selected_hazards,
            processing_status="completed_successfully"
        )

        # Add unified metadata to result
        result['unified_analysis_metadata'] = {
            'session_id': analysis_data['metadata']['session_id'],
            'total_assets_analyzed': len(assets_for_analysis),
            'hazards_processed': selected_hazards,
            'analysis_method': 'unified_json_workflow',
            'temporary_csv_used': temp_filename
        }

        logger.info(f"Successfully completed climate hazards analysis for {len(assets_for_analysis)} assets")
        return result

    except Exception as e:
        logger.error(f"Error in unified JSON climate analysis: {str(e)}")
        logger.exception("Full traceback:")
        return None


def _handle_unified_json_analysis_results(request, unified_analysis_data):
    """
    Handle the results display for unified JSON analysis workflow.
    This function executes analysis using unified JSON data and displays results.
    """
    try:
        selected_hazards = unified_analysis_data["metadata"]["selected_hazards"]
        assets_for_analysis = unified_analysis_data["assets_for_analysis"]

        logger.info(f"Executing unified JSON analysis for {len(assets_for_analysis)} assets with {len(selected_hazards)} hazards")

        # Execute analysis using unified JSON data
        result = _execute_climate_analysis_unified_json(request)

        if not result:
            logger.error("Unified JSON analysis failed")
            return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
                'error': 'Analysis failed. Please try again.',
                'facility_count': len(assets_for_analysis),
                'hazard_types': [
                    'Flood', 'Water Stress', 'Heat', 'Sea Level Rise',
                    'Tropical Cyclones', 'Storm Surge', 'Rainfall Induced Landslide'
                ],
                'selected_hazards': selected_hazards
            })

        # Load results from the generated JSON file
        from .json_csv_loader import json_csv_loader
        file_paths = json_csv_loader.get_analysis_file_paths(result)
        combined_json_path = file_paths['json_path']

        if not combined_json_path or not os.path.exists(combined_json_path):
            logger.error("Analysis completed but JSON result file not found")
            return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
                'error': 'Analysis results not found. Please try again.',
                'facility_count': len(assets_for_analysis),
                'hazard_types': [
                    'Flood', 'Water Stress', 'Heat', 'Sea Level Rise',
                    'Tropical Cyclones', 'Storm Surge', 'Rainfall Induced Landslide'
                ],
                'selected_hazards': selected_hazards
            })

        # Load analysis results data
        data, columns = json_csv_loader.load_analysis_results(json_path=combined_json_path)
        df = pd.DataFrame(data)

        if df.empty:
            logger.error("Analysis results loaded but DataFrame is empty")
            return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
                'error': 'Analysis results are empty. Please check your data and try again.',
                'facility_count': len(assets_for_analysis),
                'hazard_types': [
                    'Flood', 'Water Stress', 'Heat', 'Sea Level Rise',
                    'Tropical Cyclones', 'Storm Surge', 'Rainfall Induced Landslide'
                ],
                'selected_hazards': selected_hazards
            })

        # Prepare column groups for template
        groups = _build_column_groups(columns, selected_hazards)

        # Persist results in session for downstream flows (e.g., sensitivity analysis)
        session_results = {
            'data': data,
            'columns': columns,
            'plot_path': result.get('plot_path'),
            'all_plots': result.get('all_plots', [])
        }
        request.session['climate_hazards_v2_results'] = session_results
        if 'climate_hazards_v2_baseline_results' not in request.session:
            request.session['climate_hazards_v2_baseline_results'] = copy.deepcopy(session_results)
        request.session.modified = True

        # Log results to console
        from .json_console_simple import simple_json_console
        simple_json_console.log_results_step(
            results_data=data,
            columns=columns,
            groups=groups,
            asset_count=len(assets_for_analysis)
        )

        # Prepare context for template
        context = {
            'data': data,  # Fixed: template expects 'data' not 'facilities'
            'selected_hazards': selected_hazards,
            'columns': columns,
            'groups': groups,
            'results_count': len(df),
            'total_facilities': len(assets_for_analysis),
            'analysis_metadata': result.get('unified_analysis_metadata', {}),
            'unified_workflow': True,
            'json_file_path': combined_json_path,
        }

        logger.info(f"Successfully displayed {len(df)} analysis results from unified JSON workflow")
        return render(request, 'climate_hazards_analysis_v2/results.html', context)

    except Exception as e:
        logger.error(f"Error handling unified JSON analysis results: {str(e)}")
        logger.exception("Full traceback:")

        return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
            'error': f'An error occurred during analysis: {str(e)}',
            'facility_count': unified_analysis_data.get('metadata', {}).get('total_assets', 0) if unified_analysis_data else 0,
            'hazard_types': [
                'Flood', 'Water Stress', 'Heat', 'Sea Level Rise',
                'Tropical Cyclones', 'Storm Surge', 'Rainfall Induced Landslide'
            ],
            'selected_hazards': unified_analysis_data.get('metadata', {}).get('selected_hazards', []) if unified_analysis_data else []
        })


def _export_unified_assets_to_file(request, filename=None):
    """
    Export the unified assets JSON to a file for download or backup.
    """
    try:
        unified_assets = _get_all_uploaded_assets_json(request)

        if not unified_assets:
            return None, "No uploaded assets to export"

        if not filename:
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f'unified_assets_{timestamp}.json'

        # Create file path in input_files directory
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        file_path = os.path.join(UPLOAD_DIR, filename)

        # Write unified JSON to file
        import json
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(unified_assets, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Exported unified assets JSON to {file_path}")
        return file_path, None

    except Exception as e:
        error_msg = f"Error exporting unified assets JSON: {str(e)}"
        logger.error(error_msg)
        return None, error_msg

def _store_uploaded_assets_as_json(facility_data, original_filename, file_upload_id, session_key=None):
    """
    Store uploaded facility data as Asset records for JSON workflow.
    Enhanced to support both point and polygon assets from all file types.

    Args:
        facility_data: List of facility records from uploaded file
        original_filename: Original uploaded file name
        file_upload_id: UUID for the uploaded file batch

    Returns:
        List of created Asset IDs
    """
    from .models import Asset

    created_asset_ids = []

    try:
        for facility_record in facility_data:
            # Extract asset data from facility record
            name = facility_record.get('Facility', facility_record.get('name', 'Unknown Facility'))
            latitude = float(facility_record.get('Lat', facility_record.get('latitude', 0.0)))
            longitude = float(facility_record.get('Long', facility_record.get('longitude', 0.0)))
            archetype = facility_record.get('Archetype', facility_record.get('Asset Archetype', 'default'))

            # Determine asset type and handle polygon geometry
            asset_type = 'point'
            polygon_geometry = None

            # Check if this is a polygon asset from shapefile/geopackage
            if facility_record.get('AssetType') == 'polygon' or facility_record.get('geometry'):
                asset_type = 'polygon'
                polygon_geometry = facility_record.get('geometry')
                logger.info(f"Creating polygon asset: {name} with geometry type: {type(polygon_geometry)}")

            # Check if coordinates are valid (for point assets)
            if asset_type == 'point' and latitude == 0.0 and longitude == 0.0:
                logger.warning(f"Skipping asset with invalid coordinates: {name}")
                continue  # Skip invalid coordinates

            # Create Asset record with enhanced properties
            asset_properties = {
                'original_filename': original_filename,
                'file_upload_id': file_upload_id,
                'upload_method': 'json_workflow',
                'original_data': facility_record,
                'file_type': original_filename.split('.')[-1].lower() if '.' in original_filename else 'unknown'
            }

            # Add polygon-specific metadata
            if asset_type == 'polygon':
                asset_properties.update({
                    'geometry_type': polygon_geometry.get('type') if polygon_geometry else 'unknown',
                    'has_centroid': True if latitude != 0.0 or longitude != 0.0 else False
                })

            asset = Asset.objects.create(
                name=name,
                latitude=latitude,
                longitude=longitude,
                archetype=archetype,
                asset_type=asset_type,
                polygon_geometry=polygon_geometry,
                source='uploaded_file',
                properties=asset_properties,
                session_key=session_key
            )

            created_asset_ids.append(asset.id)

            # Log individual asset creation for debugging
            if asset_type == 'polygon':
                logger.info(f"Created polygon asset: {name} (ID: {asset.id}) with centroid: {latitude}, {longitude}")
            else:
                logger.info(f"Created point asset: {name} (ID: {asset.id}) at: {latitude}, {longitude}")

        logger.info(f"Successfully created {len(created_asset_ids)} Asset records from uploaded file: {original_filename}")

        # Log breakdown by asset type
        from collections import Counter
        asset_types_created = Counter([Asset.objects.get(id=aid).asset_type for aid in created_asset_ids])
        logger.info(f"Asset breakdown: {dict(asset_types_created)}")

    except Exception as e:
        logger.error(f"Error storing uploaded assets as JSON: {str(e)}")
        logger.exception("Full traceback:")

    return created_asset_ids


# ============================================================================
# FILE MANAGEMENT SYSTEM
# ============================================================================

def _init_uploaded_files_session(request):
    """
    Initialize the uploaded files tracking in session if it doesn't exist.
    """
    if 'climate_hazards_v2_uploaded_files' not in request.session:
        request.session['climate_hazards_v2_uploaded_files'] = {}
        request.session.modified = True


def _migrate_legacy_session_data(request):
    """
    Migrate legacy session data to the new per-file tracking structure.
    This should be called when accessing uploaded files to ensure proper data structure.
    """
    uploaded_files = request.session.get('climate_hazards_v2_uploaded_files', {})
    existing_facility_data = request.session.get('climate_hazards_v2_facility_data', [])

    # Check if we have legacy data (files without facility_data tracked per file)
    has_legacy_data = False
    for file_id, file_metadata in uploaded_files.items():
        if 'facility_data' not in file_metadata and existing_facility_data:
            has_legacy_data = True
            break

    if has_legacy_data and existing_facility_data:
        # Migrate existing facility data to be associated with the first uploaded file
        # This is a best-effort migration for backward compatibility
        if uploaded_files:
            first_file_id = list(uploaded_files.keys())[0]
            # Remove drawn polygons from the migration
            non_polygon_facilities = [f for f in existing_facility_data if f.get('source') != 'drawn_polygon']

            if non_polygon_facilities:
                uploaded_files[first_file_id]['facility_data'] = non_polygon_facilities
                request.session['climate_hazards_v2_uploaded_files'] = uploaded_files
                request.session.modified = True
                logger.info(f"Migrated {len(non_polygon_facilities)} legacy facilities to file {first_file_id}")


def _rebuild_combined_facility_data(request):
    """
    Rebuild the combined facility data from all uploaded files plus drawn polygon assets.
    This ensures that facility data is properly tracked per file while maintaining
    backward compatibility with existing code that expects combined data.
    """
    # First, migrate any legacy data
    _migrate_legacy_session_data(request)

    combined_facility_data = []

    # Get drawn polygon assets and legacy session data
    existing_facility_data = request.session.get('climate_hazards_v2_facility_data', [])
    drawn_polygon_assets = [f for f in existing_facility_data if f.get('source') == 'drawn_polygon']
    legacy_session_facilities = [
        f for f in existing_facility_data
        if f.get('source') != 'drawn_polygon' and not f.get('_file_id')
    ]
    combined_facility_data.extend(legacy_session_facilities)
    combined_facility_data.extend(drawn_polygon_assets)

    # Add facility data from all uploaded files
    uploaded_files = request.session.get('climate_hazards_v2_uploaded_files', {})
    for file_id, file_metadata in uploaded_files.items():
        file_facility_data = file_metadata.get('facility_data', [])
        # Add file_id to each facility record to track which file it came from
        for facility in file_facility_data:
            facility['_file_id'] = file_id
        combined_facility_data.extend(file_facility_data)

    # Store the combined data for backward compatibility
    request.session['climate_hazards_v2_facility_data'] = combined_facility_data
    request.session.modified = True

    logger.info(f"Rebuilt combined facility data: {len(combined_facility_data)} total facilities "
                f"({len(drawn_polygon_assets)} drawn polygons + "
                f"{len(combined_facility_data) - len(drawn_polygon_assets)} from uploaded files)")


def _add_file_to_session(request, file_id, file_metadata):
    """
    Add a file to the session tracking.
    """
    _init_uploaded_files_session(request)
    request.session['climate_hazards_v2_uploaded_files'][file_id] = file_metadata
    request.session.modified = True


def _remove_file_from_session(request, file_id):
    """
    Remove a file from the session tracking and update unified JSON.
    """
    file_removed = False
    if 'climate_hazards_v2_uploaded_files' in request.session:
        if file_id in request.session['climate_hazards_v2_uploaded_files']:
            del request.session['climate_hazards_v2_uploaded_files'][file_id]
            request.session.modified = True
            file_removed = True

    # Update unified JSON to reflect file removal
    if file_removed:
        _update_unified_json_on_file_removal(request, file_id)
        logger.info(f"Removed file {file_id} from session and updated unified JSON")

    return file_removed


def _get_file_from_session(request, file_id):
    """
    Get file metadata from session.
    """
    if 'climate_hazards_v2_uploaded_files' in request.session:
        return request.session['climate_hazards_v2_uploaded_files'].get(file_id)
    return None


def _delete_physical_file(file_path):
    """
    Safely delete a physical file from the filesystem.
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception as e:
        logger.error(f"Error deleting file {file_path}: {str(e)}")
    return False


@require_POST
def remove_file(request):
    """
    Remove a specific uploaded file and all associated facility data, then redirect back to main page.
    """
    try:
        # Get file_id from request
        file_id = request.POST.get('file_id')
        if not file_id:
            messages.error(request, 'File ID is required')
            return redirect('climate_hazards_analysis_v2:view_map')

        # Get file metadata from session
        file_metadata = _get_file_from_session(request, file_id)
        if not file_metadata:
            messages.error(request, 'File not found in session')
            return redirect('climate_hazards_analysis_v2:view_map')

        # Delete physical file
        file_path = file_metadata.get('file_path')
        if file_path:
            _delete_physical_file(file_path)

        # Collect asset IDs tied to this upload (by file_id and session_key) for cleanup
        from .models import Asset
        session_key = request.session.session_key
        assets_to_remove = Asset.objects.filter(
            source='uploaded_file',
            properties__file_upload_id=file_id
        )
        if session_key:
            assets_to_remove = assets_to_remove.filter(session_key=session_key)
        asset_ids_to_remove = list(assets_to_remove.values_list('id', flat=True))

        # Delete asset records for this file
        deleted_count, _ = assets_to_remove.delete()
        if deleted_count:
            logger.info(f"Deleted {deleted_count} Asset records for upload {file_id}")

        # Delete CSV file generated from this upload
        csv_path = file_metadata.get('csv_path')
        if csv_path:
            _delete_physical_file(csv_path)

        # Remove facility data only for the specific file being removed
        # Rebuild combined data without this file's facilities
        _rebuild_combined_facility_data(request)

        # Clear analysis results that might be affected by removing this file's data
        analysis_keys_to_clear = [
            'climate_hazards_v2_selected_hazards',
            'climate_hazards_v2_parent_facilities',
            'climate_hazards_v2_asset_inventory',
            'climate_hazards_v2_results',
            'climate_hazards_v2_baseline_results',
            'climate_hazards_v2_archetype_params',
            'climate_hazards_v2_revised_params',
            'climate_hazards_v2_sensitivity_results',
            'climate_hazards_v2_analysis_results',
            'climate_hazards_v2_asset_exposure_updated_csv_path',
            'climate_hazards_v2_uploaded_asset_ids',  # CRITICAL FIX: Clear asset IDs to prevent contamination
            'unified_uploaded_assets_json'  # Clear unified JSON to prevent stale data
        ]

        for key in analysis_keys_to_clear:
            if key in request.session:
                del request.session[key]
                logger.info(f"Cleared session key: {key}")

        # Log critical session cleanup
        cleared_asset_ids = 'climate_hazards_v2_uploaded_asset_ids' in analysis_keys_to_clear
        cleared_unified_json = 'unified_uploaded_assets_json' in analysis_keys_to_clear
        logger.info(f"Session cleanup completed - Asset IDs cleared: {cleared_asset_ids}, Unified JSON cleared: {cleared_unified_json}")

        # Update uploaded filename if this was the most recent file
        current_filename = request.session.get('climate_hazards_v2_uploaded_filename')
        if current_filename == file_metadata.get('name'):
            # Try to get the most recent remaining file's name
            uploaded_files = request.session.get('climate_hazards_v2_uploaded_files', {})
            remaining_files = [f for f in uploaded_files.values() if f.get('id') != file_id]
            if remaining_files:
                # Get the most recent remaining file
                most_recent_file = max(remaining_files, key=lambda f: f.get('upload_time', ''))
                request.session['climate_hazards_v2_uploaded_filename'] = most_recent_file.get('name')
            else:
                # No files left, clear the filename
                if 'climate_hazards_v2_uploaded_filename' in request.session:
                    del request.session['climate_hazards_v2_uploaded_filename']

        # Update facility CSV path if needed
        current_csv_path = request.session.get('climate_hazards_v2_facility_csv_path')
        if current_csv_path == file_metadata.get('csv_path'):
            # Regenerate CSV from remaining data
            remaining_facility_data = request.session.get('climate_hazards_v2_facility_data', [])
            if remaining_facility_data:
                new_csv_path = _save_facility_data_to_csv(request, remaining_facility_data)
                request.session['climate_hazards_v2_facility_csv_path'] = new_csv_path
            else:
                # No facilities left, clear the CSV path
                if 'climate_hazards_v2_facility_csv_path' in request.session:
                    del request.session['climate_hazards_v2_facility_csv_path']

        # Clear polygon assets that were created from uploaded files (not user-drawn)
        Asset.objects.filter(source='session_polygon_workflow').delete()

        # Remove file from session
        if _remove_file_from_session(request, file_id):
            logger.info(f"Successfully removed file and all associated data: {file_metadata.get('name')} (ID: {file_id})")
            messages.success(request, f'File "{file_metadata.get("name")}" and all associated facility data removed successfully')
        else:
            messages.error(request, 'Failed to remove file from session')

        # Remove deleted asset IDs from session tracking and rebuild unified JSON
        if asset_ids_to_remove:
            current_ids = request.session.get('climate_hazards_v2_uploaded_asset_ids', [])
            remaining_ids = [aid for aid in current_ids if aid not in asset_ids_to_remove]
            request.session['climate_hazards_v2_uploaded_asset_ids'] = remaining_ids
            logger.info(f"Removed {len(asset_ids_to_remove)} asset IDs from session; {len(remaining_ids)} remain")
        _create_unified_assets_json(request)

        request.session.modified = True
        return redirect('climate_hazards_analysis_v2:view_map')

    except Exception as e:
        logger.exception(f"Error removing file: {str(e)}")
        messages.error(request, 'An unexpected error occurred while removing the file')
        return redirect('climate_hazards_analysis_v2:view_map')


@require_POST
def clear_all_files(request):
    """
    Clear all uploaded files and redirect back to main page.
    """
    try:
        uploaded_files = request.session.get('climate_hazards_v2_uploaded_files', {})
        removed_count = 0

        # Delete all physical files from tracked files
        for file_id, file_metadata in uploaded_files.items():
            file_path = file_metadata.get('file_path')
            if file_path:
                if _delete_physical_file(file_path):
                    removed_count += 1

            # Also delete CSV files generated from uploads
            csv_path = file_metadata.get('csv_path')
            if csv_path:
                _delete_physical_file(csv_path)

        # Clean up any old uploaded files in the directory that aren't tracked
        try:
            if os.path.exists(UPLOAD_DIR):
                # Get list of tracked files
                tracked_files = set()
                for file_metadata in uploaded_files.values():
                    file_path = file_metadata.get('file_path')
                    if file_path:
                        tracked_files.add(os.path.basename(file_path))

                # Clean up untracked CSV files (except template files)
                for filename in os.listdir(UPLOAD_DIR):
                    if filename.endswith('.csv') and not filename.startswith('asset_template'):
                        file_full_path = os.path.join(UPLOAD_DIR, filename)
                        if filename not in tracked_files:
                            if _delete_physical_file(file_full_path):
                                removed_count += 1
        except Exception as cleanup_error:
            logger.warning(f"Error during cleanup of old files: {str(cleanup_error)}")

        # Clear polygon assets that were created from uploaded files (not user-drawn)
        Asset.objects.filter(source='session_polygon_workflow').delete()
        Asset.objects.filter(source='uploaded_file', session_key=request.session.session_key).delete()

        # Clear session data
        request.session['climate_hazards_v2_uploaded_files'] = {}

        # Also clear all related session data
        session_keys_to_clear = [
            'climate_hazards_v2_facility_data',
            'climate_hazards_v2_uploaded_filename',
            'climate_hazards_v2_facility_csv_path',
            'climate_hazards_v2_selected_hazards',
            'climate_hazards_v2_parent_facilities',
            'climate_hazards_v2_asset_inventory',
            'climate_hazards_v2_results',
            'climate_hazards_v2_baseline_results',
            'climate_hazards_v2_archetype_params',
            'climate_hazards_v2_revised_params',
            'climate_hazards_v2_sensitivity_results',
            'climate_hazards_v2_analysis_results',
            'climate_hazards_v2_asset_exposure_updated_csv_path',
            'climate_hazards_v2_uploaded_asset_ids',  # Clear accumulated asset IDs
            'unified_uploaded_assets_json'  # Clear unified JSON cache
        ]

        for key in session_keys_to_clear:
            if key in request.session:
                del request.session[key]

        request.session.modified = True

        logger.info(f"Cleared {removed_count} uploaded files and all associated facility data")
        messages.success(request, f'Successfully removed {removed_count} uploaded files and all associated map markers and preview data')

        return redirect('climate_hazards_analysis_v2:view_map')

    except Exception as e:
        logger.exception(f"Error clearing all files: {str(e)}")
        messages.error(request, 'An unexpected error occurred while clearing files')
        return redirect('climate_hazards_analysis_v2:view_map')


@require_GET
def get_uploaded_files(request):
    """
    API endpoint to get list of uploaded files.
    """
    try:
        uploaded_files = request.session.get('climate_hazards_v2_uploaded_files', {})

        # Convert to list format for JSON response
        files_list = []
        for file_id, file_metadata in uploaded_files.items():
            files_list.append({
                'id': file_id,
                'name': file_metadata.get('name'),
                'size': file_metadata.get('size', 0),
                'type': file_metadata.get('type', 'unknown'),
                'record_count': file_metadata.get('record_count', 0),
                'upload_time': file_metadata.get('upload_time'),
                'file_path': file_metadata.get('file_path')
            })

        # Sort by upload time (newest first)
        files_list.sort(key=lambda x: x.get('upload_time', ''), reverse=True)

        return JsonResponse({
            'success': True,
            'files': files_list,
            'total_count': len(files_list)
        })

    except Exception as e:
        logger.exception(f"Error getting uploaded files: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred while retrieving files'
        }, status=500)
