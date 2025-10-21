import os
import pandas as pd
import logging
from io import BytesIO
from django.http import HttpResponse
import datetime
from django.conf import settings
from django.shortcuts import render, redirect
from climate_hazards_analysis.utils.climate_hazards_analysis import generate_climate_hazards_analysis
from climate_hazards_analysis.utils.generate_report import generate_climate_hazards_report_pdf
from .constants import CLIMATE_HAZARD_TYPES, TC_WIND_COLUMNS, NAN_REPLACEMENTS, FLOOD_SCENARIOS

logger = logging.getLogger(__name__)

# Use a local UPLOAD_DIR variable defined in this views.py file
UPLOAD_DIR = os.path.join(settings.BASE_DIR, 'climate_hazards_analysis', 'static', 'input_files')

def process_data(data):
    """
    Replace NaN values in a list of dictionaries with custom strings.
    Uses constants for maintainability.
    """
    for row in data:
        for key, value in row.items():
            if pd.isna(value):
                if key == 'Elevation (meter above sea level)':
                    row[key] = NAN_REPLACEMENTS['Elevation (meter above sea level)']
                elif 'Sea Level Rise' in key:
                    row[key] = NAN_REPLACEMENTS['Sea Level Rise']
                elif key in TC_WIND_COLUMNS:
                    row[key] = NAN_REPLACEMENTS['Tropical Cyclones']
                else:
                    row[key] = NAN_REPLACEMENTS['default']
    return data

def upload_facility_csv(request):
    """
    Handles the upload of facility CSV files and stores selected climate hazards.
    """
    # Use centralized climate hazard types from constants
    climate_hazards_fields = CLIMATE_HAZARD_TYPES
    
    if request.method == 'POST' and request.FILES.get('facility_csv'):
        os.makedirs(UPLOAD_DIR, exist_ok=True)  # Ensure directory exists

        file = request.FILES['facility_csv']
        file_path = os.path.join(UPLOAD_DIR, file.name)

        # Save the uploaded file
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        # Store file path in session
        request.session['facility_csv_path'] = file_path

        # Retrieve the list of selected climate hazards from the checkboxes
        selected_fields = request.POST.getlist('fields')
        request.session['selected_dynamic_fields'] = selected_fields

        logger.info(f"Uploaded facility CSV file path: {file_path}")
        logger.info(f"Selected climate hazards: {selected_fields}")

        return redirect('climate_hazards_analysis:climate_hazards_analysis')
    
    # For GET requests, render the upload form with the climate hazard checkboxes
    # Use just the template name as it should be within the app's template directory
    return render(request, 'upload.html', {
        'climate_hazards_fields': climate_hazards_fields
    })

def climate_hazards_analysis(request):
    """
    Processes the uploaded facility CSV and selected climate hazards.
    Generates a combined analysis and displays the results.
    """
    # Use centralized climate hazard types from constants
    climate_hazards_fields = CLIMATE_HAZARD_TYPES
    
    # Retrieve the uploaded facility CSV file path from the session.
    facility_csv_path = request.session.get('facility_csv_path')
    if not facility_csv_path or not os.path.exists(facility_csv_path):
        return render(request, 'upload.html', {
            'error': 'No facility file uploaded or file not found.',
            'climate_hazards_fields': climate_hazards_fields  # Include fields in error response
        })

    # Retrieve the list of selected climate hazards from the session.
    selected_fields = request.session.get('selected_dynamic_fields', [])
    logger.info(f"Climate Hazards selected: {selected_fields}")

    # Call the climate hazards analysis function with flood scenarios
    result = generate_climate_hazards_analysis(
        facility_csv_path=facility_csv_path,
        selected_fields=selected_fields,
        flood_scenarios=FLOOD_SCENARIOS
    )

    # Check for errors in the result.
    if result is None or 'error' in result:
        error_message = result.get('error', 'Unknown error') if result else 'Analysis failed.'
        # Use existing error template if available, or fall back to upload template
        try:
            return render(request, 'error.html', {
                'error': error_message,
                'climate_hazards_fields': climate_hazards_fields,  # Include fields in error response
                'groups': {}  # Empty groups for error case
            })
        except:
            return render(request, 'upload.html', {
                'error': error_message,
                'climate_hazards_fields': climate_hazards_fields,  # Include fields in error response
                'groups': {}  # Empty groups for error case
            })

    # Get the path to the combined output CSV.
    combined_csv_path = result.get('combined_csv_path')
    if not combined_csv_path or not os.path.exists(combined_csv_path):
        return render(request, 'upload.html', {
            'error': 'Combined CSV output not found.',
            'climate_hazards_fields': climate_hazards_fields,  # Include fields in error response
            'groups': {}  # Empty groups for error case
        })

    # Load the combined CSV file.
    df = pd.read_csv(combined_csv_path)
    data = df.to_dict(orient="records")
    columns = df.columns.tolist()

    # Get the paths to any generated plots.
    plot_path = result.get('plot_path')
    all_plots = result.get('all_plots', [])

    # Create column groups for table header
    groups = {}

    # Base group - Facility Information
    facility_cols = ['Facility', 'Lat', 'Long']
    facility_count = sum(1 for col in facility_cols if col in columns)
    if facility_count > 0:
        groups['Facility Information'] = facility_count

    # Create groups for each hazard type based on available columns
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
            'Extreme Windspeed 100 year Return Period (km/h)'
        ],
        'Heat': [
            'Days over 30° Celsius',
            'Days over 33° Celsius',
            'Days over 35° Celsius'
        ],
        'Storm Surge': [
            'Storm Surge Flood Depth (meters)'
        ],
        'Rainfall Induced Landslide': [
            'Rainfall-Induced Landslide (factor of safety)'
        ]
    }

    # Add column groups for each hazard type that has columns in the data
    for hazard, cols in hazard_columns.items():
        count = sum(1 for col in cols if col in columns)
        if count > 0:
            groups[hazard] = count

    context = {
        'data': data,
        'columns': columns,
        'plot_path': plot_path,
        'all_plots': all_plots,
        'selected_dynamic_fields': selected_fields,
        'climate_hazards_fields': climate_hazards_fields,  # Add climate_hazards_fields to the context
        'groups': groups  # Add column groups for table header
    }

    # Use the existing analysis template if available
    template_name = 'climate_hazards_analysis.html'
    
    # Fallback options if needed
    try:
        return render(request, template_name, context)
    except:
        # If the template doesn't exist, try alternative template names
        alternative_templates = [
            'climate_hazard_analysis.html',
            'climate_hazards.html',
            'analysis.html'
        ]
        
        for alt_template in alternative_templates:
            try:
                return render(request, alt_template, context)
            except:
                continue
        
        # If all else fails, use the upload template to display a basic result
        return render(request, 'upload.html', {
            'data': data,
            'columns': columns,
            'error': 'Analysis completed but display template not found.',
            'climate_hazards_fields': climate_hazards_fields,  # Include fields in basic result
            'groups': groups  # Include groups even in fallback
        })

def water_stress_mapbox_fetch(request):
    return render(request, 'water_stress_mapbox.html')

def flood_exposure_mapbox_fetch(request):
    return render(request, 'flood_exposure_mapbox.html')

def heat_exposure_mapbox_fetch(request):
    return render(request, 'heat_exposure_mapbox.html')

def sea_level_rise_mapbox_fetch(request):
    return render(request, 'sea_level_rise_mapbox.html')

def tropical_cyclone_mapbox_fetch(request):
    return render(request, 'tropical_cyclone_mapbox.html')

def multi_hazard_mapbox_fetch(request):
    selected_dynamic_fields = request.session.get('selected_dynamic_fields', [])
    return render(request, 'multi_hazard_mapbox.html', {'selected_dynamic_fields': selected_dynamic_fields})

def generate_report(request):
    """
    Django view that generates the PDF report and returns it as an HTTP response.
    """
    selected_fields = request.session.get('selected_dynamic_fields', [])
    buffer = BytesIO()
    generate_climate_hazards_report_pdf(buffer, selected_fields)  # Use the updated function name
    pdf = buffer.getvalue()
    buffer.close()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="Climate_Hazard_Exposure_Report.pdf"'
    return response