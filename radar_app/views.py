from django.shortcuts import render
from .models import RadarSensor, TrainingResult, RadarData
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta
import json
import threading
import time

# 全局训练状态（云端环境使用）
CLOUD_TRAINING_STATE = {
    'is_training': False,
    'training_data': [],
    'start_time': None,
    'sensor_id': None,
    'timer': None
}

@csrf_exempt
def receive_radar_data(request):
    """接收本地桥接器发送的雷达数据"""
    if request.method == 'POST':
        try:
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
            
            # 云端训练逻辑
            global CLOUD_TRAINING_STATE
            if CLOUD_TRAINING_STATE['is_training']:
                if not CLOUD_TRAINING_STATE['sensor_id']:
                    CLOUD_TRAINING_STATE['sensor_id'] = data['sensor_id']
                    CLOUD_TRAINING_STATE['start_time'] = timezone.now()
                    print(f"🎯 训练锁定传感器: {data['sensor_id']}")
                    
                    # 设置60秒自动结束定时器
                    def auto_complete_training():
                        if CLOUD_TRAINING_STATE['is_training']:
                            print("⏰ 训练时间到达，自动结束")
                            _complete_cloud_training(sensor)
                    
                    CLOUD_TRAINING_STATE['timer'] = threading.Timer(60.0, auto_complete_training)
                    CLOUD_TRAINING_STATE['timer'].start()
                
                if CLOUD_TRAINING_STATE['sensor_id'] == data['sensor_id']:
                    CLOUD_TRAINING_STATE['training_data'].append(data['value'])
                    print(f"📊 训练数据收集: {len(CLOUD_TRAINING_STATE['training_data'])} 个数据点")
            
            # 发送到WebSocket
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
                'message': '数据接收成功',
                'training_active': CLOUD_TRAINING_STATE['is_training'],
                'training_count': len(CLOUD_TRAINING_STATE['training_data'])
            })
            
        except Exception as e:
            print(f"❌ API错误: {e}")
            return JsonResponse({
                'success': False, 
                'error': str(e)
            }, status=500)
    
    return JsonResponse({
        'api': 'radar-data',
        'method': 'POST',
        'status': 'ready',
        'training_active': CLOUD_TRAINING_STATE['is_training']
    })

def _complete_cloud_training(sensor):
    """完成云端训练"""
    global CLOUD_TRAINING_STATE
    
    # 取消定时器
    if CLOUD_TRAINING_STATE['timer']:
        CLOUD_TRAINING_STATE['timer'].cancel()
        CLOUD_TRAINING_STATE['timer'] = None
    
    if CLOUD_TRAINING_STATE['training_data']:
        avg_value = sum(CLOUD_TRAINING_STATE['training_data']) / len(CLOUD_TRAINING_STATE['training_data'])
        
        # 保存训练结果
        training_result = TrainingResult.objects.create(
            sensor=sensor,
            average_value=avg_value
        )
        
        print(f"🎉 云端训练完成: 传感器={sensor.name}, 平均值={avg_value:.2f}")
        
        # 发送训练完成消息
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "radar_group",
                {
                    "type": "training_complete",
                    "sensor_id": sensor.name,
                    "average_value": avg_value
                }
            )
        except Exception as e:
            print(f"发送训练完成消息失败: {e}")
    else:
        print("⚠️ 训练期间未收集到数据")
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "radar_group",
                {
                    "type": "error_message",
                    "message": "训练期间未收集到数据，请检查桥接器连接"
                }
            )
        except Exception as e:
            print(f"发送错误消息失败: {e}")
    
    # 重置训练状态
    CLOUD_TRAINING_STATE = {
        'is_training': False,
        'training_data': [],
        'start_time': None,
        'sensor_id': None,
        'timer': None
    }

@csrf_exempt
def start_cloud_training(request):
    """启动云端训练模式"""
    if request.method == 'POST':
        global CLOUD_TRAINING_STATE
        
        # 取消之前的定时器
        if CLOUD_TRAINING_STATE['timer']:
            CLOUD_TRAINING_STATE['timer'].cancel()
        
        # 重置并启动训练
        CLOUD_TRAINING_STATE = {
            'is_training': True,
            'training_data': [],
            'start_time': None,
            'sensor_id': None,
            'timer': None
        }
        
        print("🚀 云端训练模式已启动")
        
        return JsonResponse({
            'success': True,
            'message': '云端训练模式已启动'
        })
    
    return JsonResponse({'success': False})

@csrf_exempt
def stop_cloud_training(request):
    """停止云端训练模式"""
    if request.method == 'POST':
        global CLOUD_TRAINING_STATE
        
        # 取消定时器
        if CLOUD_TRAINING_STATE['timer']:
            CLOUD_TRAINING_STATE['timer'].cancel()
            CLOUD_TRAINING_STATE['timer'] = None
        
        # 如果有数据，完成训练
        if CLOUD_TRAINING_STATE['training_data'] and CLOUD_TRAINING_STATE['sensor_id']:
            try:
                sensor = RadarSensor.objects.get(name=CLOUD_TRAINING_STATE['sensor_id'])
                _complete_cloud_training(sensor)
            except RadarSensor.DoesNotExist:
                pass
        else:
            # 直接停止
            CLOUD_TRAINING_STATE = {
                'is_training': False,
                'training_data': [],
                'start_time': None,
                'sensor_id': None,
                'timer': None
            }
        
        print("⏹️ 云端训练模式已停止")
        
        return JsonResponse({
            'success': True,
            'message': '云端训练模式已停止'
        })
    
    return JsonResponse({'success': False})

# 其他视图函数保持不变
@csrf_exempt
def scan_ports(request):
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
    if request.method == 'POST':
        return JsonResponse({
            'success': False, 
            'error': '云端环境不支持直接串口操作，请使用本地桥接器'
        })
    return JsonResponse({'success': False})

@csrf_exempt
def close_port(request):
    if request.method == 'POST':
        return JsonResponse({
            'success': False,
            'error': '云端环境不支持直接串口操作'
        })
    return JsonResponse({'success': False})

@csrf_exempt
def restart_bridge(request):
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
