from django.urls import path

from .views import index

app_name = 'structural_impact_analysis'

urlpatterns = [
    path('', index, name='index'),
]
