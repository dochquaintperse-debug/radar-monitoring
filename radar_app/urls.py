from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/radar-data/', views.receive_radar_data, name='receive_radar_data'),
    path('api/test/', views.api_test, name='api_test'),
]
