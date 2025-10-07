from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import RadarSensor, RadarData
import json

@csrf_exempt
def receive_radar_data(request):
    """接收桥接器数据"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            sensor, created = RadarSensor.objects.get_or_create(
                name=data['sensor_id'],
                defaults={"display_name": f"雷达_{data['sensor_id'][-4:]}"}
            )
            
            RadarData.objects.create(sensor=sensor, value=data['value'])
            
            # 发送到WebSocket
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "radar_group",
                {
                    "type": "radar_data",
                    "sensor_id": data['sensor_id'],
                    "value": data['value'],
                    "timestamp": data['timestamp']
                }
            )
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False})

def index(request):
    """主页面"""
    return render(request, 'index.html')

@csrf_exempt
def api_test(request):
    return JsonResponse({
        'success': True,
        'message': '专注状态监测系统',
        'github': 'https://github.com/yourusername/radar-bridge'
    })
