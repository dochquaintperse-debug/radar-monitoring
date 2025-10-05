# radar_app/views.py
from django.shortcuts import render
from .models import RadarSensor, TrainingResult, RadarData
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def receive_radar_data(request):
    """接收本地桥接器发送的雷达数据 - 主要API端点"""
    if request.method == 'POST':
        try:
            # 解析JSON数据
            data = json.loads(request.body)
            print(f"✅ 接收到API数据: {data}")
            
            # 保存到数据库
            sensor, created = RadarSensor.objects.get_or_create(
                name=data['sensor_id'],
                defaults={"display_name": f"雷达_{data['sensor_id'][-4:]}"}
            )
            
            RadarData.objects.create(
                sensor=sensor,
                value=data['value']
            )
            
            # 发送到WebSocket（如果可用）
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    "radar_group",
                    {
                        "type": "radar_data",
                        "sensor_id": data['sensor_id'],
                        "value": data['value'],
                        "hex_value": data.get('hex_value', ''),
                        "timestamp": data['timestamp']
                    }
                )
            except Exception as ws_error:
                print(f"⚠️ WebSocket发送失败: {ws_error}")
            
            return JsonResponse({
                'success': True,
                'message': '数据接收成功'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False, 
                'error': '无效的JSON格式'
            }, status=400)
        except Exception as e:
            print(f"❌ API错误: {e}")
            return JsonResponse({
                'success': False, 
                'error': str(e)
            }, status=500)
    
    # GET请求返回API信息
    return JsonResponse({
        'api': 'radar-data',
        'method': 'POST',
        'status': 'ready'
    })

@csrf_exempt
def scan_ports(request):
    """扫描串口 - 云端环境返回提示信息"""
    if request.method == 'GET':
        return JsonResponse({
            'ports': [],
            'sensors': [],
            'message': '云端环境无法直接访问串口，请在本地运行桥接器',
            'bridge_required': True
        })
    return JsonResponse({'success': False})

@csrf_exempt
def open_port(request):
    """打开串口 - 云端环境不支持"""
    if request.method == 'POST':
        return JsonResponse({
            'success': False, 
            'error': '云端环境不支持直接串口操作，请使用本地桥接器'
        })
    return JsonResponse({'success': False})

@csrf_exempt
def close_port(request):
    """关闭串口 - 云端环境不支持"""
    if request.method == 'POST':
        return JsonResponse({
            'success': False,
            'error': '云端环境不支持直接串口操作'
        })
    return JsonResponse({'success': False})

@csrf_exempt
def restart_bridge(request):
    """重启桥接器 - 云端环境不支持"""
    if request.method == 'POST':
        return JsonResponse({
            'success': False,
            'error': '云端环境不支持桥接器操作'
        })
    return JsonResponse({'success': False})

def index(request):
    """主页面"""
    sensors = RadarSensor.objects.all()
    for sensor in sensors:
        sensor.latest_training = TrainingResult.objects.filter(
            sensor=sensor
        ).order_by('-created_at').first()
    
    return render(request, 'index.html', {'sensors': sensors})
