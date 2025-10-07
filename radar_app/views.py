from django.shortcuts import render
from .models import RadarSensor, TrainingResult, RadarData
from django.http import JsonResponse, HttpResponse, FileResponse
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

@csrf_exempt
def download_bridge(request):
    """提供桥接器下载"""
    if request.method == 'GET':
        # 读取桥接器文件内容
        bridge_content = '''import sys
import os
import serial
import serial.tools.list_ports
import requests
import time
import json
class SimpleBridge:
    def __init__(self, cloud_url):
        self.cloud_url = cloud_url.rstrip('/')
        self.serial_port = None
        
    def find_ports(self):
        """查找可用串口"""
        ports = serial.tools.list_ports.comports()
        available_ports = []
        
        for port in ports:
            # 过滤串口
            if any(keyword in port.description.upper() for keyword in ["USB", "COM", "SERIAL"]):
                available_ports.append(port.device)
                
        return available_ports
    
    def test_radar_connection(self, port):
        """测试是否为雷达设备"""
        try:
            test_serial = serial.Serial(port, 115200, timeout=2)
            
            # 发送识别命令
            identify_cmd = b"\\x53\\x59\\x01\\x80\\x00\\x01\\x0F\\x3D\\x54\\x43"
            test_serial.write(identify_cmd)
            time.sleep(1)
            
            if test_serial.in_waiting > 0:
                response = test_serial.read(test_serial.in_waiting)
                print(f"端口 {port} 响应: {response.hex().upper()}")
                
                # 检查是否包含预期响应
                if identify_cmd in response:
                    test_serial.close()
                    return True
            
            test_serial.close()
            return False
            
        except Exception as e:
            print(f"端口 {port} 测试失败: {e}")
            return False
    
    def connect(self, port):
        """连接串口"""
        try:
            self.serial_port = serial.Serial(port, 115200, timeout=2)
            print(f"✅ 已连接串口: {port}")
            return True
        except Exception as e:
            print(f"❌ 连接串口失败: {e}")
            return False
    
    def send_to_cloud(self, data):
        """发送数据到云端"""
        try:
            response = requests.post(
                f"{self.cloud_url}/radar/api/radar-data/",
                json=data,
                timeout=5,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print(f"📤 数据发送成功: 值={data['value']}")
                return True
            else:
                print(f"❌ 云端响应错误: {response.status_code}")
                print(f"   响应内容: {response.text[:100]}")
                return False
                
        except requests.exceptions.ConnectionError:
            print(f"❌ 无法连接到云端: {self.cloud_url}")
            return False
        except requests.exceptions.Timeout:
            print("❌ 请求超时")
            return False
        except Exception as e:
            print(f"❌ 发送错误: {e}")
            return False
    
    def parse_radar_data(self, raw_data):
        """解析雷达数据"""
        if len(raw_data) != 10:
            return None
            
        # 检查帧头帧尾
        if raw_data[:2] != b"\\x53\\x59" or raw_data[-2:] != b"\\x54\\x43":
            return None
            
        # 检查是否为呼吸数据回复
        if raw_data[2:6] != b"\\x81\\x82\\x00\\x01":
            return None
            
        # 提取数值
        value = raw_data[6]
        return {
            "value": value,
            "hex_value": f"0x{value:02X}"
        }
    
    def run(self):
        """运行监控"""
        print("🔍 正在扫描串口...")
        ports = self.find_ports()
        
        if not ports:
            print("❌ 未发现可用串口")
            return
            
        print(f"发现串口: {ports}")
        
        # 查找雷达设备
        radar_port = None
        for port in ports:
            print(f"🧪 测试端口 {port}...")
            if self.test_radar_connection(port):
                radar_port = port
                print(f"✅ 发现雷达设备: {port}")
                break
            else:
                print(f"❌ 端口 {port} 不是雷达设备")
        
        if not radar_port:
            print("❌ 未发现雷达设备")
            return
        
        # 连接雷达
        if not self.connect(radar_port):
            return
        
        print("🚀 开始数据传输...")
        print("按 Ctrl+C 停止")
        print("-" * 50)
        
        consecutive_errors = 0
        max_errors = 5
        
        try:
            while True:
                try:
                    # 发送查询命令
                    query_cmd = b"\\x53\\x59\\x81\\x82\\x00\\x01\\x0F\\xBF\\x54\\x43"
                    self.serial_port.write(query_cmd)
                    time.sleep(0.1)
                    
                    # 读取响应
                    if self.serial_port.in_waiting >= 10:
                        raw_data = self.serial_port.read(10)
                        print(f"📡 接收数据: {raw_data.hex().upper()}")
                        
                        parsed = self.parse_radar_data(raw_data)
                        if parsed:
                            # 准备云端数据
                            cloud_data = {
                                "sensor_id": f"LOCAL_RADAR_{radar_port.replace('COM', '')}",
                                "value": parsed["value"],
                                "hex_value": parsed["hex_value"],
                                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                            }
                            
                            # 发送到云端
                            if self.send_to_cloud(cloud_data):
                                consecutive_errors = 0
                            else:
                                consecutive_errors += 1
                        else:
                            print("⚠️ 数据解析失败")
                    
                    # 错误处理
                    if consecutive_errors >= max_errors:
                        print(f"❌ 连续 {max_errors} 次发送失败，请检查网络连接")
                        break
                    
                    time.sleep(2)  # 每2秒查询一次
                    
                except KeyboardInterrupt:
                    print("\\n⏹️ 用户手动停止")
                    break
                except Exception as e:
                    print(f"❌ 运行时错误: {e}")
                    time.sleep(5)
                    
        finally:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                print("🔌 串口已关闭")
def main():
    print("🌐 雷达数据云端桥接器 v1.0")
    print("=" * 50)
    
    # 获取云端网址
    while True:
        cloud_url = input("请输入您的Render应用网址: ").strip()
        
        if not cloud_url:
            print("❌ 网址不能为空")
            continue
            
        # 自动添加协议
        if not cloud_url.startswith(('http://', 'https://')):
            cloud_url = 'https://' + cloud_url
            
        print(f"🎯 目标云端: {cloud_url}")
        
        # 测试连接
        try:
            print("🧪 测试云端连接...")
            response = requests.get(cloud_url, timeout=10)
            if response.status_code == 200:
                print("✅ 云端连接正常")
                break
            else:
                print(f"⚠️ 云端响应异常: {response.status_code}")
                retry = input("是否继续？(y/n): ")
                if retry.lower() == 'y':
                    break
        except Exception as e:
            print(f"❌ 云端连接失败: {e}")
            retry = input("是否重新输入网址？(y/n): ")
            if retry.lower() != 'y':
                return
    
    # 启动桥接器
    bridge = SimpleBridge(cloud_url)
    bridge.run()
if __name__ == "__main__":
    main()
'''
        
        # 返回文件下载
        response = HttpResponse(bridge_content, content_type='text/x-python')
        response['Content-Disposition'] = 'attachment; filename="radar_bridge.py"'
        return response
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)
@csrf_exempt  
def download_requirements(request):
    """提供requirements.txt下载"""
    if request.method == 'GET':
        requirements_content = '''pyserial==3.5
requests==2.31.0
'''
        response = HttpResponse(requirements_content, content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="requirements.txt"'
        return response
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)
@csrf_exempt
def download_setup_script(request):
    """提供一键安装脚本"""
    if request.method == 'GET':
        # Windows批处理脚本
        if 'windows' in request.GET:
            script_content = '''@echo off
echo 🚀 雷达桥接器一键安装脚本
echo ================================
echo 📦 正在安装Python依赖...
pip install pyserial requests
echo 📥 正在下载桥接器...
curl -o radar_bridge.py ''' + request.build_absolute_uri('/radar/download/bridge/') + '''
echo ✅ 安装完成！
echo.
echo 📋 使用方法：
echo   python radar_bridge.py
echo.
pause
'''
            response = HttpResponse(script_content, content_type='text/plain')
            response['Content-Disposition'] = 'attachment; filename="install.bat"'
            return response
        
        # Linux/Mac 脚本
        else:
            script_content = '''#!/bin/bash
echo "🚀 雷达桥接器一键安装脚本"
echo "================================"
echo "📦 正在安装Python依赖..."
pip3 install pyserial requests
echo "📥 正在下载桥接器..."
curl -o radar_bridge.py ''' + request.build_absolute_uri('/radar/download/bridge/') + '''
echo "✅ 安装完成！"
echo ""
echo "📋 使用方法："
echo "  python3 radar_bridge.py"
echo ""
'''
            response = HttpResponse(script_content, content_type='text/plain')
            response['Content-Disposition'] = 'attachment; filename="install.sh"'
            return response
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)