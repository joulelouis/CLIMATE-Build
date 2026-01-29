from django.shortcuts import render


def index(request):
    return render(request, 'structural_impact_analysis/index.html')
