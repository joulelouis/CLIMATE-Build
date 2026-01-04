import os
import pandas as pd
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render, redirect
from .utils.flood_exposure_analysis import generate_flood_exposure_analysis
from .models import Address
from django.views.generic.edit import CreateView



UPLOAD_DIR = os.path.join(settings.BASE_DIR, 'flood_exposure_analysis/static/input_files')

class AddressView(CreateView):
    model = Address
    fields = ['address']
    template_name = 'water_stress/water_stress_mapbox.html'
    # success_url = 'water_stress/water_stress_mapbox.html'

# Create your views here.
def upload_facility_csv(request):
    
    # List of available fields for the flood exposure analysis
    available_fields = [
        '75th Percentile',
        'Exposure',
    ]

    if request.method == 'POST' and request.FILES.get('facility_csv'):
        os.makedirs(UPLOAD_DIR, exist_ok=True)  # Ensure directory exists

        file = request.FILES['facility_csv']
        file_path = os.path.join(UPLOAD_DIR, file.name)

        # Save the uploaded file
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        # Store file path in session
        request.session['flood_exposure_facility_csv_path'] = file_path

        print(request.session.get('flood_exposure_facility_csv_path'))

        # Retrieve the list of selected dynamic fields from the checkboxes
        selected_fields = request.POST.getlist('fields')
        request.session['selected_dynamic_fields'] = selected_fields

        print("Uploaded facility CSV file path:", file_path)
        print("Selected dynamic fields:", selected_fields)

        return redirect('flood_exposure_analysis:flood_exposure_analysis')  # Redirect to table & plot page
    
    # For GET requests, render the upload form with the dynamic checkboxes.
    context = {
        'available_fields': available_fields,
    }

    return render(request, 'flood_exposure_analysis/upload.html', context)  # Upload form template

def flood_exposure_analysis(request):

    available_fields = [
        '75th Percentile',
        'Exposure',
    ]

    file_path = request.session.get('flood_exposure_facility_csv_path')

    if not file_path or not os.path.exists(file_path):
        return render(request, 'flood_exposure_analysis/upload.html', {'error': 'No file uploaded or file not found.'})

    # Run all three scenarios (current, SSP245, SSP585) to populate expected columns
    output = generate_flood_exposure_analysis(
        file_path,
        scenarios=['current', 'moderate', 'worst']
    )

    if output and 'error' not in output and output.get('combined_csv_paths'):
        updated_csv_path = output['combined_csv_paths'][0]
    else:
        updated_csv_path = None

    if updated_csv_path and os.path.exists(updated_csv_path):
        df = pd.read_csv(updated_csv_path)
        data = df.to_dict(orient="records")
        columns = df.columns.tolist()
    else:
        data, columns = [], []
        if output and 'error' in output:
            print(f"Flood analysis error: {output['error']}")

    return render(request, 'flood_exposure_analysis/flood_exposure_analysis.html', {
        'data': data,
        'columns': columns,
        'output_path': updated_csv_path,
        'available_fields': available_fields
    })
