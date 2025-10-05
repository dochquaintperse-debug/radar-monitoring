from django.shortcuts import render
from .models import RadarSensor, TrainingResult
from .mqtt_client import get_mqtt_client
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .serial_bridge import SerialToMQTTBridge
from .serial_scanner import SerialScanner
import threading
import json
from . import serial_bridge
from .models import RadarSensor, RadarData, TrainingResult

# 全局桥接器实例
bridge_instance = None

@csrf_exempt
def restart_bridge(request):
    """重启桥接器"""
    global bridge_instance
    if request.method == 'POST':
        def restart():
            global bridge_instance
            if bridge_instance:
                bridge_instance.stop()
            bridge_instance = SerialToMQTTBridge()
            bridge_instance.start()
        threading.Thread(target=restart).start()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})

@csrf_exempt
def scan_ports(request):
    if request.method == 'GET':
        
        global bridge_instance
        # 刷新前关闭当前串口连接（关键修复）
        if bridge_instance:
            bridge_instance.stop()

        sensors = SerialScanner.find_sensors()

        valid_sensor_ids = [sensor['sensor_id'] for sensor in sensors]
        RadarSensor.objects.exclude(name__in=valid_sensor_ids).delete()
        
        # 保存传感器到数据库
        for sensor in sensors:
            RadarSensor.objects.get_or_create(
                name=sensor['sensor_id'],
                defaults={"display_name": f"R60ABD1雷达_{sensor['port']}"}
            )
        
        # 返回可用串口和传感器
        return JsonResponse({
            'ports': [sensor['port'] for sensor in sensors],
            'sensors': [{
                'sensor_id': sensor['sensor_id'],
                'port': sensor['port']
            } for sensor in sensors]
        })
    return JsonResponse({'success': False})

@csrf_exempt
def open_port(request):
    """打开指定串口"""
    global bridge_instance
    if request.method == 'POST':
        data = json.loads(request.body)
        port = data.get('port')
        if not port:
            return JsonResponse({'success': False, 'error': '未指定端口'})
            
        # 关键修改：先关闭现有连接
        if bridge_instance:
            bridge_instance.stop()
        
        # 重新创建实例并同步到serial_bridge模块
        bridge_instance = SerialToMQTTBridge()
        serial_bridge.bridge_instance = bridge_instance  # 同步实例到模块变量
        
        bridge_instance.connect_mqtt()
        success = bridge_instance.connect_serial(port)
        
        if success:
            bridge_instance.start()
            bridge_instance.start_sending_commands()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': '连接失败'})
    return JsonResponse({'success': False})

@csrf_exempt
def close_port(request):
    """关闭串口"""
    global bridge_instance
    if request.method == 'POST' and bridge_instance:
        bridge_instance.stop()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})

@csrf_exempt
def receive_radar_data(request):
    """接收本地桥接器发送的雷达数据"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # 保存到数据库
            sensor, created = RadarSensor.objects.get_or_create(
                name=data['sensor_id'],
                defaults={"display_name": f"本地雷达_{data['sensor_id'][-4:]}"}
            )
            
            RadarData.objects.create(
                sensor=sensor,
                value=data['value']
            )
            
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
                    "hex_value": data.get('hex_value', ''),
                    "timestamp": data['timestamp']
                }
            )
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False})
# 模拟串口扫描（云端显示说明）
def scan_ports(request):
    """云端模拟串口扫描"""
    return JsonResponse({
        'ports': [],
        'message': '云端环境无法直接访问串口，请在本地运行桥接器',
        'bridge_required': True
    })

def index(request):
    """主页面"""
    sensors = RadarSensor.objects.all()
    for sensor in sensors:
        sensor.latest_training = TrainingResult.objects.filter(
            sensor=sensor
        ).order_by('-created_at').first()
    
    # 添加调试信息
    print(f"传感器数量: {sensors.count()}")
    for sensor in sensors:
        print(f"传感器 {sensor.name}: 训练结果存在={sensor.latest_training is not None}")
    
    return render(request, 'index.html', {'sensors': sensors})
