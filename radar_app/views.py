from django.shortcuts import render
from .models import RadarSensor, TrainingResult, RadarData
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta
import json
import threading
import time
import logging

logger = logging.getLogger(__name__)

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
        
        try:
            # 取消之前的定时器
            if CLOUD_TRAINING_STATE['timer']:
                CLOUD_TRAINING_STATE['timer'].cancel()
                logger.info("取消了之前的训练定时器")
            
            # 重置并启动训练
            CLOUD_TRAINING_STATE = {
                'is_training': True,
                'training_data': [],
                'start_time': None,
                'sensor_id': None,
                'timer': None
            }
            
            logger.info("🚀 云端训练模式已启动")
            print("🚀 云端训练模式已启动")
            
            return JsonResponse({
                'success': True,
                'message': '云端训练模式已启动'
            })
            
        except Exception as e:
            logger.error(f"启动云端训练失败: {e}")
            print(f"❌ 启动云端训练失败: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

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
    """主页面 - 同时支持网页和API访问"""
    sensors = RadarSensor.objects.all()
    for sensor in sensors:
        sensor.latest_training = TrainingResult.objects.filter(
            sensor=sensor
        ).order_by('-created_at').first()
    
    # 如果是API请求（Accept: application/json）
    if request.headers.get('Accept') == 'application/json' or 'api' in request.GET:
        sensor_list = []
        for sensor in sensors:
            latest_data = RadarData.objects.filter(
                sensor=sensor
            ).order_by('-timestamp').first()
            
            sensor_list.append({
                'id': sensor.id,
                'name': sensor.name,
                'display_name': sensor.display_name,
                'latest_value': float(latest_data.value) if latest_data else None,
                'latest_timestamp': latest_data.timestamp.isoformat() if latest_data else None,
                'latest_training': float(sensor.latest_training.average_value) if sensor.latest_training else None
            })
        
        return JsonResponse({
            'success': True,
            'message': '雷达监测系统仪表板',
            'sensors': sensor_list,
            'total_sensors': len(sensor_list),
            'cloud_training_active': CLOUD_TRAINING_STATE['is_training']
        })
    
    # 网页请求 - 检查模板是否存在
    try:
        return render(request, 'index.html', {
            'sensors': sensors,
            'cloud_training_active': CLOUD_TRAINING_STATE['is_training']
        })
    except Exception as e:
        # 如果模板不存在，返回JSON响应
        logger.warning(f"模板渲染失败，返回JSON响应: {e}")
        return JsonResponse({
            'success': True,
            'message': '雷达监测系统仪表板（API模式）',
            'note': '前端模板未配置，当前为API模式',
            'sensors_count': sensors.count(),
            'endpoints': {
                'get_sensors': '/radar/api/get-sensors/',
                'get_data': '/radar/api/get-radar-data/',
                'receive_data': '/radar/api/radar-data/'
            }
        })

@csrf_exempt
def get_radar_data(request):
    """获取雷达数据的API端点"""
    if request.method == 'GET':
        try:
            # 获取查询参数
            sensor_id = request.GET.get('sensor_id')
            limit = int(request.GET.get('limit', 100))
            
            # 构建查询
            query = RadarData.objects.all()
            if sensor_id:
                query = query.filter(sensor__name=sensor_id)
            
            # 获取最新数据
            latest_data = query.order_by('-timestamp')[:limit]
            
            data_list = []
            for data in latest_data:
                data_list.append({
                    'id': data.id,
                    'sensor_id': data.sensor.name,
                    'sensor_name': data.sensor.display_name,
                    'value': float(data.value),
                    'timestamp': data.timestamp.isoformat()
                })
            
            return JsonResponse({
                'success': True,
                'data': data_list,
                'count': len(data_list),
                'message': f'获取到 {len(data_list)} 条数据'
            })
            
        except Exception as e:
            logger.error(f"获取雷达数据时出错: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'获取数据失败: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Method not allowed'
    }, status=405)
@csrf_exempt
def get_sensors(request):
    """获取所有传感器信息"""
    if request.method == 'GET':
        try:
            sensors = RadarSensor.objects.all()
            sensor_list = []
            
            for sensor in sensors:
                # 获取最新数据
                latest_data = RadarData.objects.filter(
                    sensor=sensor
                ).order_by('-timestamp').first()
                
                # 获取最新训练结果
                latest_training = TrainingResult.objects.filter(
                    sensor=sensor
                ).order_by('-created_at').first()
                
                sensor_info = {
                    'id': sensor.id,
                    'name': sensor.name,
                    'display_name': sensor.display_name,
                    'created_at': sensor.created_at.isoformat(),
                    'latest_data': {
                        'value': float(latest_data.value) if latest_data else None,
                        'timestamp': latest_data.timestamp.isoformat() if latest_data else None
                    },
                    'latest_training': {
                        'average_value': float(latest_training.average_value) if latest_training else None,
                        'created_at': latest_training.created_at.isoformat() if latest_training else None
                    }
                }
                sensor_list.append(sensor_info)
            
            return JsonResponse({
                'success': True,
                'sensors': sensor_list,
                'count': len(sensor_list)
            })
            
        except Exception as e:
            logger.error(f"获取传感器信息时出错: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'获取传感器失败: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Method not allowed'
    }, status=405)
@csrf_exempt
def get_training_results(request):
    """获取训练结果"""
    if request.method == 'GET':
        try:
            sensor_id = request.GET.get('sensor_id')
            limit = int(request.GET.get('limit', 50))
            
            # 构建查询
            query = TrainingResult.objects.all()
            if sensor_id:
                query = query.filter(sensor__name=sensor_id)
            
            # 获取训练结果
            training_results = query.order_by('-created_at')[:limit]
            
            results_list = []
            for result in training_results:
                results_list.append({
                    'id': result.id,
                    'sensor_id': result.sensor.name,
                    'sensor_name': result.sensor.display_name,
                    'average_value': float(result.average_value),
                    'created_at': result.created_at.isoformat()
                })
            
            return JsonResponse({
                'success': True,
                'training_results': results_list,
                'count': len(results_list)
            })
            
        except Exception as e:
            logger.error(f"获取训练结果时出错: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'获取训练结果失败: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Method not allowed'
    }, status=405)

@csrf_exempt
def api_test(request):
    """API测试端点"""
    return JsonResponse({
        'success': True,
        'message': 'API正常工作',
        'timestamp': timezone.now().isoformat(),
        'method': request.method,
        'cloud_training_active': CLOUD_TRAINING_STATE['is_training'],
        'endpoints': {
            'receive_data': '/radar/api/radar-data/',
            'get_data': '/radar/api/get-radar-data/',
            'get_sensors': '/radar/api/get-sensors/',
            'get_training': '/radar/api/get-training-results/',
            'start_training': '/radar/api/start-training/',
            'stop_training': '/radar/api/stop-training/',
        }
    })
@csrf_exempt
def api_status(request):
    """系统状态端点"""
    try:
        # 统计数据
        total_sensors = RadarSensor.objects.count()
        total_data_points = RadarData.objects.count()
        total_trainings = TrainingResult.objects.count()
        
        # 最近数据
        recent_data = RadarData.objects.filter(
            timestamp__gte=timezone.now() - timedelta(minutes=5)
        ).count()
        
        return JsonResponse({
            'success': True,
            'status': 'operational',
            'statistics': {
                'total_sensors': total_sensors,
                'total_data_points': total_data_points,
                'total_training_results': total_trainings,
                'recent_data_points': recent_data
            },
            'cloud_training': {
                'is_active': CLOUD_TRAINING_STATE['is_training'],
                'sensor_locked': CLOUD_TRAINING_STATE['sensor_id'],
                'data_collected': len(CLOUD_TRAINING_STATE['training_data']),
                'start_time': CLOUD_TRAINING_STATE['start_time'].isoformat() if CLOUD_TRAINING_STATE['start_time'] else None
            },
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'status': 'error',
            'error': str(e)
        }, status=500)