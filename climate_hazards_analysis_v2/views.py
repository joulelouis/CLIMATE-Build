from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
import os
from io import BytesIO
import pandas as pd
import geopandas as gpd
import json
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_GET
from django.utils.decorators import method_decorator
from django.middleware.csrf import get_token
from .utils import standardize_facility_dataframe, load_cached_hazard_data, combine_facility_with_hazard_data, validate_shapefile
from .error_utils import handle_sensitivity_param_error
<<<<<<< HEAD
from .models import Asset, HazardAnalysisResult
=======
from .granular_analysis import (
    generate_sample_grid,
    query_hazard_for_points,
    classify_hazard_risk,
    consolidate_points_to_clusters,
    calculate_polygon_area_km2
)
>>>>>>> 0be1e2c07442b7f42f891a388f26ef23b01c6c06
import logging
import copy
import zipfile
import tempfile
import glob

# Import from climate_hazards_analysis module
from climate_hazards_analysis.utils.climate_hazards_analysis import generate_climate_hazards_analysis
from climate_hazards_analysis.utils.generate_report import generate_climate_hazards_report_pdf
from tropical_cyclone_analysis.utils.tropical_cyclone_analysis import generate_tropical_cyclone_analysis

logger = logging.getLogger(__name__)

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
    
    # If a facility CSV or Excel file has been uploaded through the form
    if request.method == 'POST' and request.FILES.get('facility_csv'):
        try:
            # Save the uploaded file
            upload_dir = os.path.join(settings.BASE_DIR, 'climate_hazards_analysis_v2', 'static', 'input_files')
            os.makedirs(upload_dir, exist_ok=True)
            
            file = request.FILES['facility_csv']
            file_path = os.path.join(upload_dir, file.name)
            
            with open(file_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            
            ext = os.path.splitext(file.name)[1].lower()

            # Process the uploaded file to get facility data
            if ext in ['.xls', '.xlsx']:
                df = pd.read_excel(file_path)

            elif ext in ['.shp', '.zip', '.gpkg']:
                if ext == '.zip':
                    with tempfile.TemporaryDirectory() as tmpdir:
                        with zipfile.ZipFile(file_path, 'r') as zip_ref:
                            zip_ref.extractall(tmpdir)
                        shp_files = [f for f in os.listdir(tmpdir) if f.lower().endswith('.shp')]
                        if not shp_files:
                            raise ValueError('No shapefile found in the uploaded zip archive')
                        shp_path = os.path.join(tmpdir, shp_files[0])
                        gdf = gpd.read_file(shp_path)
                elif ext == '.gpkg':
                    # Read GeoPackage file (reads first layer by default)
                    gdf = gpd.read_file(file_path)
                else:
                    # Direct .shp file
                    gdf = gpd.read_file(file_path)

                # Validate geospatial file structure before processing
                attribute_columns = validate_shapefile(gdf)
                logger.info(f"Geospatial file attribute columns: {attribute_columns}")

                gdf = gdf.to_crs('EPSG:4326')
                gdf['Lat'] = gdf.geometry.centroid.y
                gdf['Long'] = gdf.geometry.centroid.x
                df = pd.DataFrame(gdf.drop(columns='geometry'))

            else:
                df = pd.read_csv(file_path)

            # Standardize column names and validate data before saving
            df = standardize_facility_dataframe(df)


            # Store facility data in session for map display
<<<<<<< HEAD
            if ext in ['.shp', '.zip']:
                uploaded_facilities = []
=======
            if ext in ['.shp', '.zip', '.gpkg']:
                facility_data = []
>>>>>>> 0be1e2c07442b7f42f891a388f26ef23b01c6c06
                for i, row in df.iterrows():
                    record = row.to_dict()
                    geom = gdf.geometry.iloc[i]
                    if geom.geom_type == 'MultiPoint':
                        record['geometry'] = geom.convex_hull.__geo_interface__
                    elif geom.geom_type in ['Polygon', 'MultiPolygon']:
                        record['geometry'] = geom.__geo_interface__
<<<<<<< HEAD
                    uploaded_facilities.append(record)
=======

                    facility_data.append(record)
>>>>>>> 0be1e2c07442b7f42f891a388f26ef23b01c6c06
            else:
                uploaded_facilities = df.to_dict(orient='records')

            # Debug: Log the uploaded facility data
            logger.info(f"Processed {len(uploaded_facilities)} facilities from file: {str(uploaded_facilities)[:200]}...")

            # Get existing facility data (preserves drawn polygon assets)
            existing_facility_data = request.session.get('climate_hazards_v2_facility_data', [])
            logger.info(f"Found {len(existing_facility_data)} existing facilities in session")

            # Combine existing facilities with uploaded facilities
            # This preserves drawn polygon assets and adds uploaded file data
            facility_data = existing_facility_data + uploaded_facilities
            logger.info(f"Combined total: {len(facility_data)} facilities")

            # Explicitly store combined data in session
            request.session['climate_hazards_v2_facility_data'] = facility_data
            request.session.modified = True  # Ensure session is saved

            # Save facility data to CSV (creates standardized CSV file)
            csv_path = _save_facility_data_to_csv(request, facility_data)

            # Store uploaded filename in session for display
            request.session['climate_hazards_v2_uploaded_filename'] = file.name
            request.session.modified = True

            # Add success message to context
            total_facilities = len(facility_data)
            uploaded_count = len(uploaded_facilities)
            existing_count = len(existing_facility_data)

            if existing_count > 0:
                context['success_message'] = f"Successfully combined {uploaded_count} uploaded facilities with {existing_count} existing assets. Total: {total_facilities} facilities."
            else:
                context['success_message'] = f"Successfully loaded {total_facilities} facilities from {file.name}"
            
        except Exception as e:
            logger.exception(f"Error processing file: {str(e)}")
            context['error'] = f"Error processing file: {str(e)}"
    
    # Return the template with context
    return render(request, 'climate_hazards_analysis_v2/main.html', context)

def get_facility_data(request):
    """
    API endpoint to retrieve facility data for the map.
    Returns JSON with facility data including coordinates and available hazard data.
    Enhanced to include polygon assets from the database.
    """
    # Get base facility data from session
    facility_data = request.session.get('climate_hazards_v2_facility_data', [])

    # Get polygon assets from database for the current session
    try:
        session_key = request.session.session_key
        if session_key:
            polygon_assets = Asset.objects.filter(
                session_key=session_key,
                asset_type='polygon'
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
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='latin-1') as f:
            content = f.read()

    return HttpResponse(content, content_type='text/csv')

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
            name = data.get('name', f"New Facility at {lat:.4f}, {lng:.4f}")
            archetype = data.get('archetype', 'default archetype')
            geometry = data.get('geometry')  # Polygon geometry if provided
            grid_spacing = data.get('gridSpacing')  # Grid spacing from frontend modal
            area_km2 = data.get('areaKm2')  # Polygon area from frontend

            # Basic validation
            if lat is None or lng is None or not name or not name.strip():
                return JsonResponse({
                    'success': False,
                    'error': 'Name, latitude, and longitude are required'
                }, status=400)

            # Create database asset record (simplified)
            try:
                # Ensure session has a key
                if not request.session.session_key:
                    request.session.create()

                asset = Asset(
                    name=name.strip(),
                    archetype=archetype.strip() if archetype else 'default archetype',
                    latitude=lat,
                    longitude=lng,
                    session_key=request.session.session_key
                )

                # Set polygon geometry if provided
                if geometry and asset.set_polygon_from_geojson(geometry):
                    pass  # Geometry set successfully

                asset.save()

            except Exception:
                # Continue with session-based storage if database fails
                pass

            # Get existing facility data or initialize empty list
            facility_data = request.session.get('climate_hazards_v2_facility_data', [])

            # Add new facility with optional archetype and geometry
            new_facility = {
                'Facility': name,
                'Lat': lat,
                'Long': lng,
                'Archetype': archetype
            }

            # Add polygon geometry if provided
            if geometry:
                new_facility['geometry'] = geometry

                # Calculate area if not provided
                if area_km2 is None:
                    area_km2 = calculate_polygon_area_km2(geometry)

                new_facility['polygon_area_km2'] = area_km2

                # Check if polygon qualifies for granular analysis (≥ 6 km²)
                if area_km2 >= 6:
                    # Use provided grid spacing or default to 100m
                    if grid_spacing is None:
                        grid_spacing = 100  # Default
                        logger.info(f"No grid spacing provided, using default: {grid_spacing}m")

                    logger.info(f"Starting granular analysis for {name}: "
                              f"Area={area_km2:.4f} km², Grid spacing={grid_spacing}m")

                    # Generate sample grid
                    sample_points = generate_sample_grid(geometry, grid_spacing_meters=grid_spacing)

                    if sample_points:
                        new_facility['sample_points'] = sample_points
                        new_facility['grid_spacing_meters'] = grid_spacing
                        new_facility['sample_points_count'] = len(sample_points)

                        logger.info(f"Generated {len(sample_points)} sample points for {name}")
                    else:
                        logger.warning(f"Failed to generate sample points for {name}")
                else:
                    logger.info(f"Polygon area {area_km2:.2f} km² < 6 km², skipping granular analysis for {name}")

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
                'asset_id': asset.id if 'asset' in locals() else None
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
    """
    if not facility_data:
        return None

    # Create upload directory if it doesn't exist
    upload_dir = os.path.join(settings.BASE_DIR, 'climate_hazards_analysis_v2', 'static', 'input_files')
    os.makedirs(upload_dir, exist_ok=True)

    # Generate a filename (use session key for uniqueness)
    csv_filename = f"facility_data_{request.session.session_key or 'default'}.csv"
    csv_path = os.path.join(upload_dir, csv_filename)

    # Convert facility data to DataFrame (excluding geometry for CSV)
    df_data = []
    for facility in facility_data:
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

    logger.info(f"Saved facility data to CSV: {csv_path}")

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

    context = {
        'facility_count': len(facility_data),
        'hazard_types': hazard_types,
        'selected_hazards': request.session.get('climate_hazards_v2_selected_hazards', []),
    }

    # Handle form submission
    if request.method == 'POST':
        selected_hazards = request.POST.getlist('hazards')
        request.session['climate_hazards_v2_selected_hazards'] = selected_hazards

        # Redirect to results page
        return redirect('climate_hazards_analysis_v2:show_results')

    # For GET requests, just display the hazard selection form
    return render(request, 'climate_hazards_analysis_v2/select_hazards.html', context)

def _validate_and_prepare_session_data(request):
    """
    Validate and prepare session data for climate hazard analysis.

    Returns:
        tuple: (facility_data, selected_hazards, facility_csv_path) or redirect response if validation fails
    """
    facility_data = request.session.get('climate_hazards_v2_facility_data', [])
    selected_hazards = request.session.get('climate_hazards_v2_selected_hazards', [])
    facility_csv_path = request.session.get('climate_hazards_v2_facility_csv_path')

    # Check if we have the necessary data
    if not facility_data or not selected_hazards:
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


def show_results(request):
    """
    View to display climate hazard analysis results.
    Updated to work with simplified flood categories and tropical cyclone integration.
    """
    logger.info("SHOW_RESULTS function called - starting climate hazard analysis")

    # Validate and prepare session data
    facility_data, selected_hazards, facility_csv_path, redirect_response = _validate_and_prepare_session_data(request)
    if redirect_response:
        return redirect_response

    try:
        logger.info(f"Facility CSV path: {facility_csv_path}")
<<<<<<< HEAD
=======
        
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

                # Add the main facility row (centroid)
                expanded_rows.append({
                    'Facility': facility_name,
                    'Lat': lat,
                    'Long': lng,
                    'Archetype': archetype
                })

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
        
        # Check for errors in the result
        if result is None or 'error' in result:
            error_message = result.get('error', 'Unknown error') if result else 'Analysis failed.'
            logger.error(f"Climate hazards analysis error: {error_message}")
            
            return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
                'error': error_message,
                'facility_count': len(facility_data),
                'hazard_types': [
                    'Flood', 'Water Stress', 'Heat', 'Sea Level Rise', 
                    'Tropical Cyclones', 'Storm Surge', 'Rainfall Induced Landslide'
                ],
                'selected_hazards': selected_hazards
            })
        
        # Get the combined CSV path and load the data
        combined_csv_path = result.get('combined_csv_path')
        
        if not combined_csv_path or not os.path.exists(combined_csv_path):
            logger.error(f"Combined CSV not found: {combined_csv_path}")
            return render(request, 'climate_hazards_analysis_v2/select_hazards.html', {
                'error': 'Combined analysis output not found.',
                'facility_count': len(facility_data),
                'hazard_types': [
                    'Flood', 'Water Stress', 'Heat', 'Sea Level Rise', 
                    'Tropical Cyclones', 'Storm Surge', 'Rainfall Induced Landslide'
                ],
                'selected_hazards': selected_hazards
            })
        
        # Load the combined CSV file with explicit UTF-8 encoding
        logger.info(f"Loading combined CSV from: {combined_csv_path}")
        try:
            df = pd.read_csv(combined_csv_path, encoding='utf-8')
        except UnicodeDecodeError:
            # Try with different encodings if UTF-8 fails
            try:
                df = pd.read_csv(combined_csv_path, encoding='latin-1')
                logger.warning(f"CSV file {combined_csv_path} read with latin-1 encoding")
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(combined_csv_path, encoding='cp1252')
                    logger.warning(f"CSV file {combined_csv_path} read with cp1252 encoding")
                except UnicodeDecodeError:
                    logger.error(f"Could not read CSV file {combined_csv_path} with any encoding")
                    raise
>>>>>>> 0be1e2c07442b7f42f891a388f26ef23b01c6c06

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
        df, error = _load_and_process_combined_csv(result.get('combined_csv_path'))
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

<<<<<<< HEAD
=======
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

        # 🚨 EMERGENCY TC DEBUG - Final check before group creation
        logger.info("🚨 EMERGENCY TC DEBUG - PRE GROUP CREATION 🚨")
        tc_final_check = [col for col in tc_expected if col in columns]
        logger.info(f"TC columns in final data: {tc_final_check}")
        logger.info(f"TC column count in final data: {len(tc_final_check)}")
        logger.info("🚨 END EMERGENCY DEBUG - PRE GROUP CREATION 🚨")
        
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
        
>>>>>>> 0be1e2c07442b7f42f891a388f26ef23b01c6c06
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

        # Preserve a baseline copy of the results the first time they are
        # generated so we can restore them later if needed
        if 'climate_hazards_v2_baseline_results' not in request.session:
            request.session['climate_hazards_v2_baseline_results'] = copy.deepcopy(
                request.session['climate_hazards_v2_results']
            )

<<<<<<< HEAD
        # Build comprehensive column groups for hazard exposure table
        groups = _build_column_groups(df.columns.tolist(), selected_hazards)
=======
        # Note: Granular analysis is now handled via unified approach (see lines 820-898)
        # Sample points are included in the main analysis CSV and results are parsed
>>>>>>> 0be1e2c07442b7f42f891a388f26ef23b01c6c06

        # Prepare context for the template
        context = {
            'data': df.to_dict(orient="records"),
            'columns': df.columns.tolist(),
            'groups': groups,  # Now properly populated with column group data
            'plot_path': plot_path,
            'all_plots': all_plots,
            'selected_hazards': selected_hazards,
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
        'Rainfall-Induced Landslide': 'Rainfall-Induced Landslide'
    }

    # Always include Facility Information if we have basic columns
    facility_cols = [col for col in column_mappings['Facility Information'] if col in columns]
    if facility_cols:
        groups['Facility Information'] = len(facility_cols)
        logger.info(f"Added Facility Information group with {len(facility_cols)} columns: {facility_cols}")

    # Add groups for selected hazards based on actual column presence
    for hazard in selected_hazards:
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
            
            # Check if Apply Parameters button was clicked
            submit_type = request.POST.get('submit_type', '')
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
    Updates the session data and optionally saves to CSV file.
    """
    try:
        # Parse the JSON data from the request
        data = json.loads(request.body)
        changes = data.get('changes', [])
        
        if not changes:
            return JsonResponse({'success': False, 'error': 'No changes provided'})
        
        logger.info(f"Processing {len(changes)} table changes")
        
        # Get current asset exposure results data from session
        results_data = request.session.get('climate_hazards_v2_results', {})
        
        if not results_data or 'data' not in results_data:
            return JsonResponse({'success': False, 'error': 'No asset exposure data found in session'})
        
        # Get the current data
        table_data = results_data['data']
        
        # Apply changes to the data
        for change in changes:
            row_index = change['rowIndex']
            column_name = change['column']
            new_value = change['newValue']
            facility_name = change['facilityName']
            
            # Find the correct row in the data (match by facility name for safety)
            target_row = None
            for i, row in enumerate(table_data):
                if i == row_index and row.get('Facility') == facility_name:
                    target_row = row
                    break
            
            if target_row is None:
                logger.warning(f"Could not find row {row_index} for facility {facility_name}")
                continue
            
            # Convert value to appropriate type
            converted_value = convert_table_value(new_value, column_name)
            
            # Update the value
            target_row[column_name] = converted_value
            logger.info(f"Updated {facility_name} - {column_name}: {converted_value}")
        
        # Update session data for asset exposure results
        results_data['data'] = table_data
        request.session['climate_hazards_v2_results'] = results_data
        
        # Optionally save to CSV file for persistence
        try:
            save_updated_data_to_csv(table_data, request)
        except Exception as csv_error:
            logger.warning(f"Failed to save to CSV: {csv_error}")
            # Don't fail the request if CSV save fails
        
        return JsonResponse({
            'success': True, 
            'message': f'Successfully updated {len(changes)} values',
            'changes_applied': len(changes)
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in request: {e}")
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    
    except Exception as e:
        logger.exception(f"Error saving table changes: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


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


<<<<<<< HEAD
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
            temp_dir = os.path.join(settings.BASE_DIR, 'climate_hazards_analysis_v2', 'static', 'input_files')

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
        session_key = request.session.session_key

        # Get polygon assets from database
        assets = Asset.objects.filter(
            session_key=session_key,
            asset_type='polygon'
        ).order_by('-created_at')

        # Convert to GeoJSON FeatureCollection
        features = []
        for asset in assets:
            features.append(asset.geojson)

        geojson_data = {
            'type': 'FeatureCollection',
            'features': features
        }

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
        if not request.session.session_key:
            return JsonResponse({
                'success': False,
                'error': 'No active session'
            }, status=401)

        asset = Asset.objects.get(
            id=asset_id,
            session_key=request.session.session_key
        )

        data = json.loads(request.body)

        # Update basic fields
        if 'name' in data and data['name'].strip():
            asset.name = data['name'].strip()

        if 'archetype' in data:
            asset.archetype = data['archetype'].strip() if data['archetype'] else 'default archetype'

        # Update polygon geometry if provided
        if 'geometry' in data and data['geometry']:
            if asset.set_polygon_from_geojson(data['geometry']):
                logger.info(f"Updated polygon geometry for asset: {asset.name}")
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid polygon geometry provided'
                }, status=400)

        asset.save()

        return JsonResponse({
            'success': True,
            'asset': asset.geojson,
            'message': 'Polygon asset updated successfully'
        })

    except Asset.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Polygon asset not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data provided'
        }, status=400)
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
        if not request.session.session_key:
            return JsonResponse({
                'success': False,
                'error': 'No active session'
            }, status=401)

        asset = Asset.objects.get(
            id=asset_id,
            session_key=request.session.session_key
        )

        asset_name = asset.name
        asset.delete()

        return JsonResponse({
            'success': True,
            'message': f'Polygon asset "{asset_name}" deleted successfully'
        })

    except Asset.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Polygon asset not found'
        }, status=404)
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
        if not request.session.session_key:
            return JsonResponse({
                'success': False,
                'error': 'No active session'
            }, status=401)

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

        # Create the asset
        asset = Asset.objects.create(
            name=data['name'].strip(),
            archetype=data.get('archetype', 'default archetype').strip() or 'default archetype',
            latitude=centroid_lat,
            longitude=centroid_lng,
            polygon_geometry=geometry,
            asset_type='polygon',
            session_key=request.session.session_key
        )

        logger.info(f"Created new polygon asset: {asset.name} (ID: {asset.id})")

        return JsonResponse({
            'success': True,
            'asset': asset.geojson,
            'message': f'Polygon asset "{asset.name}" created successfully'
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
=======
def export_boundaries_shapefile(request):
    """
    Export facility boundaries with polygon geometry as a shapefile.
    Returns a zipped shapefile containing all boundary assets.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Only GET requests are allowed'}, status=405)

    try:
        # Get facility data from session
        facility_data = request.session.get('climate_hazards_v2_facility_data', [])

        # Filter facilities that have polygon geometry
        polygon_facilities = [f for f in facility_data if f.get('geometry')]

        if not polygon_facilities:
            return JsonResponse({
                'error': 'No boundary polygons found. Please add city boundaries first.'
            }, status=404)

        # Create GeoDataFrame from polygon facilities
        from shapely.geometry import shape

        geometries = []
        properties = []

        for facility in polygon_facilities:
            try:
                # Convert GeoJSON geometry to Shapely geometry
                geom = shape(facility['geometry'])
                geometries.append(geom)

                properties.append({
                    'name': facility.get('Facility', 'Unnamed'),
                    'archetype': facility.get('Archetype', ''),
                    'latitude': facility.get('Lat', 0),
                    'longitude': facility.get('Long', 0)
                })
            except Exception as e:
                logger.warning(f"Skipping invalid geometry for {facility.get('Facility')}: {e}")
                continue

        if not geometries:
            return JsonResponse({
                'error': 'No valid geometries found to export.'
            }, status=400)

        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(properties, geometry=geometries, crs='EPSG:4326')

        # Create temporary directory for shapefile
        with tempfile.TemporaryDirectory() as temp_dir:
            shapefile_name = 'city_boundaries'
            shapefile_path = os.path.join(temp_dir, f'{shapefile_name}.shp')

            # Save as shapefile
            gdf.to_file(shapefile_path, driver='ESRI Shapefile')

            # Create zip file containing all shapefile components
            zip_path = os.path.join(temp_dir, f'{shapefile_name}.zip')

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add all shapefile components (.shp, .shx, .dbf, .prj, etc.)
                for file in os.listdir(temp_dir):
                    if file.startswith(shapefile_name) and not file.endswith('.zip'):
                        file_path = os.path.join(temp_dir, file)
                        zipf.write(file_path, arcname=file)

            # Read zip file and return as response
            with open(zip_path, 'rb') as f:
                zip_data = f.read()

            response = HttpResponse(zip_data, content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{shapefile_name}.zip"'

            logger.info(f"Exported {len(geometries)} boundary polygons as shapefile")
            return response

    except Exception as e:
        logger.error(f"Error exporting boundaries as shapefile: {e}")
        return JsonResponse({
            'error': f'Failed to export shapefile: {str(e)}'
>>>>>>> 0be1e2c07442b7f42f891a388f26ef23b01c6c06
        }, status=500)