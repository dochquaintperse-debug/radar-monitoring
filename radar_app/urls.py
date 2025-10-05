from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('restart-bridge/', views.restart_bridge, name='restart_bridge'),
    path('scan-ports/', views.scan_ports, name='scan_ports'),
    path('open-port/', views.open_port, name='open_port'),
    path('close-port/', views.close_port, name='close_port'),
    path('api/web-serial-data/', views.web_serial_data, name='web_serial_data'),
    path('api/sensor-status/', views.get_sensor_status, name='sensor_status'),
]