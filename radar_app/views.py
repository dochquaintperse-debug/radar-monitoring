from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import threading
import json
import os
import time

# 🔧 修复：添加所有必要的模型导入
from .models import RadarSensor, RadarData, TrainingResult
from .mqtt_client import get_mqtt_client
from .serial_bridge import SerialToMQTTBridge
from .serial_scanner import SerialScanner
from . import serial_bridge

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
    """扫描串口 - 支持云环境演示"""
    if request.method == 'GET':
        # 检测是否为Render环境
        if os.environ.get('RENDER'):
            # Render环境：返回模拟串口
            demo_ports = ['COM3', 'COM4', '/dev/ttyUSB0']
            demo_sensors = []
            
            for port in demo_ports:
                sensor_id = f"R60ABD1_BREATH_DEMO"
                demo_sensors.append({
                    'sensor_id': sensor_id,
                    'port': port
                })
                
                # 确保演示传感器存在于数据库
                RadarSensor.objects.get_or_create(
                    name=sensor_id,
                    defaults={"display_name": f"演示雷达传感器"}
                )
            
            return JsonResponse({
                'ports': demo_ports,
                'sensors': demo_sensors,
                'demo_mode': True
            })
        
        # 本地环境：实际扫描串口
        global bridge_instance
        if bridge_instance:
            bridge_instance.stop()

        try:
            sensors = SerialScanner.find_sensors()
            valid_sensor_ids = [sensor['sensor_id'] for sensor in sensors]
            
            # 清理不存在的传感器
            RadarSensor.objects.exclude(name__in=valid_sensor_ids).delete()
            
            # 保存传感器到数据库
            for sensor in sensors:
                RadarSensor.objects.get_or_create(
                    name=sensor['sensor_id'],
                    defaults={"display_name": f"R60ABD1雷达_{sensor['port']}"}
                )
            
            return JsonResponse({
                'ports': [sensor['port'] for sensor in sensors],
                'sensors': [{
                    'sensor_id': sensor['sensor_id'],
                    'port': sensor['port']
                } for sensor in sensors],
                'demo_mode': False
            })
        except Exception as e:
            print(f"扫描串口错误: {e}")
            return JsonResponse({
                'ports': [],
                'sensors': [],
                'demo_mode': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False})

@csrf_exempt
def open_port(request):
    """打开指定串口"""
    global bridge_instance
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            port = data.get('port')
            if not port:
                return JsonResponse({'success': False, 'error': '未指定端口'})
            
            # Render环境：模拟串口连接成功
            if os.environ.get('RENDER'):
                # 设置演示传感器ID
                mqtt_client = get_mqtt_client()
                mqtt_client.set_current_sensor_id("R60ABD1_BREATH_DEMO")
                
                return JsonResponse({
                    'success': True, 
                    'message': f'演示模式：已连接到 {port}',
                    'demo_mode': True
                })
                
            # 本地环境：实际连接串口
            if bridge_instance:
                bridge_instance.stop()
            
            bridge_instance = SerialToMQTTBridge()
            serial_bridge.bridge_instance = bridge_instance
            
            bridge_instance.connect_mqtt()
            success = bridge_instance.connect_serial(port)
            
            if success:
                bridge_instance.start()
                bridge_instance.start_sending_commands()
                return JsonResponse({'success': True})
            return JsonResponse({'success': False, 'error': '连接失败'})
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'JSON解析错误'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False})

@csrf_exempt
def close_port(request):
    """关闭串口"""
    global bridge_instance
    if request.method == 'POST':
        try:
            # Render环境：模拟关闭
            if os.environ.get('RENDER'):
                return JsonResponse({'success': True, 'demo_mode': True})
                
            # 本地环境：实际关闭
            if bridge_instance:
                bridge_instance.stop()
                return JsonResponse({'success': True})
            
            return JsonResponse({'success': False, 'error': '没有活动的串口连接'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False})

@csrf_exempt
def web_serial_data(request):
    """接收Web Serial API数据 - 🆕 新增API"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            sensor_id = data.get('sensor_id')
            value = data.get('value')
            timestamp = data.get('timestamp')
            
            if not sensor_id or value is None:
                return JsonResponse({
                    'success': False, 
                    'error': '缺少必需参数: sensor_id 或 value'
                })
            
            # 确保传感器存在
            sensor, created = RadarSensor.objects.get_or_create(
                name=sensor_id,
                defaults={"display_name": "Web串口雷达传感器"}
            )
            
            if created:
                print(f"📡 创建新的Web Serial传感器: {sensor_id}")
            
            # 保存雷达数据
            radar_data = RadarData.objects.create(
                sensor=sensor, 
                value=int(value)
            )
            
            print(f"💾 Web Serial数据已保存: {sensor_id} = {value}")
            
            return JsonResponse({
                'success': True, 
                'saved': True,
                'data_id': radar_data.id,
                'sensor_created': created
            })
            
        except json.JSONDecodeError as e:
            return JsonResponse({
                'success': False, 
                'error': f'JSON解析错误: {str(e)}'
            })
        except ValueError as e:
            return JsonResponse({
                'success': False, 
                'error': f'数值转换错误: {str(e)}'
            })
        except Exception as e:
            print(f"❌ Web Serial数据保存错误: {e}")
            return JsonResponse({
                'success': False, 
                'error': f'服务器错误: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'error': '仅支持POST请求'})

@csrf_exempt
def get_sensor_status(request):
    """获取传感器状态 - 🆕 新增API"""
    if request.method == 'GET':
        try:
            sensors = RadarSensor.objects.all()
            sensor_data = []
            
            for sensor in sensors:
                # 获取最新训练结果
                latest_training = TrainingResult.objects.filter(
                    sensor=sensor
                ).order_by('-created_at').first()
                
                # 获取最新数据
                latest_data = RadarData.objects.filter(
                    sensor=sensor
                ).order_by('-timestamp').first()
                
                sensor_info = {
                    'id': sensor.id,
                    'name': sensor.name,
                    'display_name': sensor.display_name,
                    'created_at': sensor.created_at.isoformat(),
                    'latest_training': {
                        'average_value': latest_training.average_value,
                        'created_at': latest_training.created_at.isoformat()
                    } if latest_training else None,
                    'latest_data': {
                        'value': latest_data.value,
                        'timestamp': latest_data.timestamp.isoformat()
                    } if latest_data else None,
                    'data_count': RadarData.objects.filter(sensor=sensor).count()
                }
                
                sensor_data.append(sensor_info)
            
            return JsonResponse({
                'success': True,
                'sensors': sensor_data,
                'total_sensors': len(sensor_data)
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': '仅支持GET请求'})

def index(request):
    """主页面"""
    try:
        # 获取所有传感器
        sensors = RadarSensor.objects.all()
        
        # 为每个传感器添加最新训练结果
        for sensor in sensors:
            sensor.latest_training = TrainingResult.objects.filter(
                sensor=sensor
            ).order_by('-created_at').first()
            
            # 添加最新数据计数
            sensor.data_count = RadarData.objects.filter(sensor=sensor).count()
        
        # 调试信息
        print(f"📊 页面加载 - 传感器数量: {sensors.count()}")
        for sensor in sensors:
            print(f"   🔍 传感器 {sensor.name}: 训练={sensor.latest_training is not None}, 数据={sensor.data_count}条")
        
        context = {
            'sensors': sensors,
            'demo_mode': os.environ.get('RENDER', False),
            'total_data_points': RadarData.objects.count(),
            'total_training_results': TrainingResult.objects.count()
        }
        
        return render(request, 'index.html', context)
        
    except Exception as e:
        print(f"❌ 页面加载错误: {e}")
        # 确保即使出错也能显示基本页面
        return render(request, 'index.html', {
            'sensors': [],
            'demo_mode': True,
            'error_message': str(e)
        })
