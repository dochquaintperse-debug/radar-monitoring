from django.urls import path
from . import views

# 应用命名空间
app_name = 'radar_app'

urlpatterns = [
    # 主页面
    path('', views.index, name='index'),
    
    # 串口管理功能
    path('restart-bridge/', views.restart_bridge, name='restart_bridge'),
    path('scan-ports/', views.scan_ports, name='scan_ports'),
    path('open-port/', views.open_port, name='open_port'),
    path('close-port/', views.close_port, name='close_port'),
    
    # API端点
    path('api/radar-data/', views.receive_radar_data, name='receive_radar_data'),
    path('api/start-training/', views.start_cloud_training, name='start_cloud_training'),
    path('api/stop-training/', views.stop_cloud_training, name='stop_cloud_training'),
    
    # 数据查看API
    path('api/get-radar-data/', views.get_radar_data, name='get_radar_data'),
    path('api/get-sensors/', views.get_sensors, name='get_sensors'),
    path('api/get-training-results/', views.get_training_results, name='get_training_results'),

    # API测试端点
    path('api/test/', views.api_test, name='api_test'),
    path('api/status/', views.api_status, name='api_status'),

    # 下载相关
    path('download/bridge/', views.download_bridge, name='download_bridge'),
    path('download/requirements/', views.download_requirements, name='download_requirements'),
    path('download/setup/', views.download_setup_script, name='download_setup_script'),
]
