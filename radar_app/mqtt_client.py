import paho.mqtt.client as mqtt
import json
import time
import threading
from django.db import transaction
from .models import RadarSensor, RadarData, TrainingResult
from asgiref.sync import async_to_sync, sync_to_async
from channels.layers import get_channel_layer

class MQTTClient:
    def __init__(self, broker="localhost", port=1883):
        self.client = mqtt.Client()
        self.broker = broker
        self.port = port
        self.data_topic = "radar/data/#"
        self.discover_topic = "radar/discover"
        self.discovered_sensors = set()
        
        # 模式状态
        self.monitoring_mode = False
        self.training_mode = False
        self.training_data = []
        self.training_start_time = None
        self.training_duration = 60
        self.training_timer = None
        self.current_sensor_id = None
        self.anomaly_values = []
        self.anomaly_start_time = None
        self.normal_range = None
        self.channel_layer = None

    def publish(self, topic, payload, qos=0, retain=False):
        """发布消息到MQTT主题"""
        if not self.client.is_connected():
            print("MQTT客户端未连接，尝试重连...")
            self.connect()
            time.sleep(1)
        
        if self.client.is_connected():
            try:
                if isinstance(payload, dict):
                    payload = json.dumps(payload)
                result = self.client.publish(topic, payload, qos, retain)
                result.wait_for_publish()
                print(f"消息已发布到主题 {topic}: {payload}")
                return True
            except Exception as e:
                print(f"MQTT发布失败: {e}")
                return False
        else:
            print("MQTT客户端仍未连接，无法发布消息")
            return False

    def set_current_sensor_id(self, sensor_id):
        """设置当前传感器ID"""
        self.current_sensor_id = sensor_id
        print(f"[MQTT] 设置当前传感器ID: {sensor_id}")

    def connect(self):
        """连接MQTT并订阅主题"""
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        try:
            self.client.connect(self.broker, self.port, 60)
            print(f"正在连接MQTT broker: {self.broker}:{self.port}")
            self.client.loop_start()
        except Exception as e:
            print(f"MQTT连接失败: {e}")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("MQTT连接成功，已订阅主题")
            self.client.subscribe(self.data_topic)
            self.client.subscribe(self.discover_topic)
        else:
            print(f"MQTT连接失败，错误代码: {rc}（检查broker是否运行）")

    def _on_message(self, client, userdata, msg):
        """处理接收到的MQTT消息"""
        try:
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)
            
            if not isinstance(data, dict):
                print(f"无效的消息格式，预期字典但得到: {type(data)}")
                return
                
            if data.get('type') == 'radar_data':
                # 在线程中处理雷达数据，避免阻塞MQTT循环
                threading.Thread(target=self._handle_radar_data_sync, args=(data,), daemon=True).start()
            elif data.get('type') == 'serial_ports':
                ports = data.get('ports', [])
                self._send_to_channel({
                    "type": "serial_ports",
                    "ports": ports
                })
            elif data.get('type') == 'sensor_connected':
                sensor_id = data.get('sensor_id')
                connected = data.get('connected', False)
                self._send_to_channel({
                    "type": "sensor_status",
                    "sensor_id": sensor_id,
                    "connected": connected
                })
            elif data.get('type') == 'error':
                self._send_to_channel({
                    "type": "error_message",
                    "message": data.get('message', '未知错误')
                })
                
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}，原始消息: {msg.payload}")
        except Exception as e:
            print(f"处理MQTT消息错误: {e}, 消息内容: {msg.payload}")
            import traceback
            traceback.print_exc()

    def _send_to_channel(self, message):
        """通过Channels发送消息到前端WebSocket"""
        if not self.channel_layer:
            self.channel_layer = get_channel_layer()
        
        if self.channel_layer:
            try:
                async_to_sync(self.channel_layer.group_send)(
                    "radar_group",
                    {
                        "type": message["type"],
                        **message
                    }
                )
                print(f"消息已发送到channel: {message}")
            except Exception as e:
                print(f"发送消息到channel失败: {e}")
        else:
            print("channel_layer未初始化，无法发送消息")

    def _handle_radar_data_sync(self, data):
        """在同步线程中处理雷达数据（修复异步上下文问题）"""
        sensor_id = data["sensor_id"]
        value = data.get("value")
        timestamp = data.get("timestamp", time.time())
        
        print(f"[数据处理] 传感器ID: {sensor_id}, 值: {value}, 当前传感器: {self.current_sensor_id}, 训练模式: {self.training_mode}")
        
        try:
            # 确保传感器存在
            sensor, created = RadarSensor.objects.get_or_create(
                name=sensor_id,
                defaults={"display_name": f"R60ABD1雷达_{sensor_id.split('_')[-1]}"}
            )
            if created:
                print(f"[数据处理] 创建新传感器: {sensor.name}")
            
            save_allowed = self.training_mode or \
                        (self.monitoring_mode and self.normal_range is not None)
            
            if save_allowed:
                RadarData.objects.create(sensor=sensor, value=value)
                print(f"数据已保存（模式: {'训练' if self.training_mode else '监测'}）: {value}")
            
                if self.monitoring_mode:
                    from django.utils import timezone
                    from datetime import timedelta
                    six_seconds_ago = timezone.now() - timedelta(seconds=6)
                    RadarData.objects.filter(sensor=sensor, timestamp__lt=six_seconds_ago).delete()
                    
                    five_seconds_ago = timezone.now() - timedelta(seconds=5)
                    recent_data = RadarData.objects.filter(
                        sensor=sensor, 
                        timestamp__gte=five_seconds_ago
                    ).order_by('timestamp')
                    
                    if recent_data.count() >= 5:
                        all_anomalies = all(
                            not (self.normal_range[0] <= d.value <= self.normal_range[1])
                            for d in recent_data
                        )
                        
                        if all_anomalies:
                            self._send_to_channel({
                                "type": "anomaly_detected",
                                "sensor_id": sensor_id,
                                "values": [d.value for d in recent_data],
                                "average": (self.normal_range[0] + self.normal_range[1]) / 2
                            })
                            
            # 发送实时数据到前端
            self._send_to_channel({
                "type": "radar_data",
                "sensor_id": sensor_id,
                "value": value,
                "hex_value": data.get("hex_value", f"0x{value:02X}"),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # 训练模式数据收集（关键修复：传感器ID匹配逻辑）
            if self.training_mode:
                # 修复：统一传感器ID格式或宽松匹配
                current_id_normalized = self.current_sensor_id.replace('_', '') if self.current_sensor_id else ''
                sensor_id_normalized = sensor_id.replace('_', '')
                
                if (sensor_id == self.current_sensor_id or 
                    current_id_normalized in sensor_id_normalized or 
                    sensor_id_normalized in current_id_normalized):
                    
                    self.training_data.append(value)
                    print(f"[训练数据收集] 匹配成功，已收集: {len(self.training_data)} 个数据点，最新值: {value}")
                else:
                    print(f"[训练数据收集] ID不匹配，跳过。期望: '{self.current_sensor_id}', 实际: '{sensor_id}'")
                
        except Exception as e:
            print(f"处理雷达数据错误: {e}")
            import traceback
            traceback.print_exc()
            self._send_to_channel({
                "type": "error_message",
                "message": f"数据处理失败: {str(e)}"
            })

    def start_training_mode(self, duration=60):
        """开始训练模式（使用线程避免异步冲突）"""
        def run_training_setup():
            try:
                print("开始执行训练模式初始化...")
                from . import serial_bridge
                
                if not serial_bridge.bridge_instance or not serial_bridge.bridge_instance.serial_port or not serial_bridge.bridge_instance.serial_port.is_open:
                    print("错误：bridge_instance未初始化，无法启动训练")
                    self._send_to_channel({
                        "type": "error_message",
                        "message": "串口桥未初始化，请先打开串口"
                    })
                    return
                
                # 设置训练模式标识
                self.training_mode = True
                serial_bridge.bridge_instance.set_training_mode(True)
                print("已设置训练模式标识")
                
                # 获取或创建传感器
                if self.current_sensor_id:
                    sensor, created = RadarSensor.objects.get_or_create(
                        name=self.current_sensor_id,
                        defaults={"display_name": f"R60ABD1雷达_{self.current_sensor_id.split('_')[-1]}"}
                    )
                    print(f"获取传感器: {sensor.name}（新建: {created}）")
                else:
                    print("警告：current_sensor_id为空，将匹配第一个接收到的传感器数据")
                
                # 清理旧数据
                if self.current_sensor_id:
                    with transaction.atomic():
                        RadarData.objects.filter(sensor__name=self.current_sensor_id).delete()
                        TrainingResult.objects.filter(sensor__name=self.current_sensor_id).delete()
                        print(f"已清理传感器 {self.current_sensor_id} 的旧训练数据和结果")
                
                # 重置训练状态
                self.training_data = []
                self.training_start_time = time.time()
                
                print(f"训练模式启动: {self.current_sensor_id}（持续{self.training_duration}秒）")
                self._send_to_channel({
                    "type": "training_started",
                    "message": f"传感器训练已开始，持续60秒"
                })
                
                # 设置自动结束定时器
                def auto_end_training():
                    print("训练时间到达，自动结束训练")
                    try:
                        if self.current_sensor_id:
                            sensor = RadarSensor.objects.get(name=self.current_sensor_id)
                        else:
                            # 如果没有指定传感器，使用最近的传感器
                            sensor = RadarSensor.objects.first()
                        
                        if sensor:
                            self._end_training_mode_sync(sensor)
                        else:
                            print("未找到可用传感器，无法结束训练")
                    except Exception as e:
                        print(f"自动结束训练时出错: {e}")
                
                self.training_timer = threading.Timer(self.training_duration, auto_end_training)
                self.training_timer.start()
                print(f"已设置{self.training_duration}秒自动结束定时器")
                
            except Exception as e:
                print(f"训练模式初始化错误: {str(e)}")
                import traceback
                traceback.print_exc()
                self._send_to_channel({
                    "type": "error_message",
                    "message": f"训练启动失败: {str(e)}"
                })
        
        # 在单独线程中执行，避免异步冲突
        threading.Thread(target=run_training_setup, daemon=True).start()

    def stop_training_mode(self):
        """手动停止训练模式"""
        def stop_training_sync():
            try:
                if not self.training_mode:
                    return
                    
                # 取消自动结束定时器
                if self.training_timer:
                    self.training_timer.cancel()
                    self.training_timer = None
                    print("已取消训练自动结束定时器")
                
                # 查找当前传感器并结束训练
                if self.current_sensor_id:
                    try:
                        sensor = RadarSensor.objects.get(name=self.current_sensor_id)
                        self._end_training_mode_sync(sensor)
                    except RadarSensor.DoesNotExist:
                        print(f"传感器 {self.current_sensor_id} 不存在")
                        self.training_mode = False
                else:
                    print("未指定传感器，结束训练模式")
                    self.training_mode = False
            except Exception as e:
                print(f"停止训练时出错: {e}")
        
        threading.Thread(target=stop_training_sync, daemon=True).start()

    def _end_training_mode_sync(self, sensor):
        """同步方式结束训练模式（修复异步上下文问题）"""
        print(f"训练结束，收集到 {len(self.training_data)} 个数据点")
        
        # 取消定时器
        if self.training_timer:
            self.training_timer.cancel()
            self.training_timer = None
        
        # 重置训练模式标识
        self.training_mode = False
        
        # 通知串口桥停止训练模式
        from . import serial_bridge
        if serial_bridge.bridge_instance:
            serial_bridge.bridge_instance.set_training_mode(False)
        
        if self.training_data:
            average = sum(self.training_data) / len(self.training_data)
            # 保存训练结果
            TrainingResult.objects.create(
                sensor=sensor,
                average_value=average
            )
            # 设置正常范围
            self.normal_range = (average - 1, average + 1)
            
            # 发送训练完成消息
            self._send_to_channel({
                "type": "training_complete",
                "sensor_id": sensor.name,
                "average_value": average
            })
            print(f"训练完成: 传感器={sensor.name}, 平均值={average:.2f}, 正常范围={self.normal_range}")
        else:
            self._send_to_channel({
                "type": "error_message",
                "message": "训练期间未收集到数据，请检查传感器连接"
            })
            
        # 重置训练状态
        self.training_data = []
        self.training_start_time = None

    def start_monitoring_mode(self):
        """开始监测模式"""
        def start_monitoring_sync():
            try:
                if not self.current_sensor_id:
                    self._send_to_channel({
                        "type": "error_message",
                        "message": "未检测到传感器，请先完成训练"
                    })
                    return
                
                sensor = RadarSensor.objects.get(name=self.current_sensor_id)
                latest_training = TrainingResult.objects.filter(sensor=sensor).first()
                if not latest_training:
                    self._send_to_channel({
                        "type": "error_message",
                        "message": "未找到训练结果，请先完成训练"
                    })
                    return
                
                # 清空监测数据
                RadarData.objects.filter(sensor=sensor).delete()
                print(f"已清空传感器 {sensor.name} 的监测数据")
                
                # 初始化正常范围（y±1）
                self.normal_range = (latest_training.average_value - 1, latest_training.average_value + 1)
                self.monitoring_mode = True
                self.anomaly_values = []
                self.anomaly_start_time = None
                print(f"监测模式启动: 正常范围={self.normal_range}")
                
                self._send_to_channel({
                    "type": "monitoring_started",
                    "message": f"开始监测（正常范围: {self.normal_range[0]:.2f}-{self.normal_range[1]:.2f}）"
                })
            except RadarSensor.DoesNotExist:
                self._send_to_channel({
                    "type": "error_message",
                    "message": "传感器不存在，请先训练"
                })
            except Exception as e:
                print(f"监测模式启动失败: {str(e)}")
                self._send_to_channel({
                    "type": "error_message",
                    "message": f"监测模式启动失败: {str(e)}"
                })
        
        threading.Thread(target=start_monitoring_sync, daemon=True).start()
            
    def stop_monitoring_mode(self):
        """停止监测模式"""
        self.monitoring_mode = False
        self.anomaly_start_time = None
        self.anomaly_values = []
        print("监测模式已停止")
        
        self._send_to_channel({
            "type": "monitoring_stopped",
            "message": "监测模式已停止"
        })

# 单例模式
_mqtt_client_instance = None
def get_mqtt_client():
    global _mqtt_client_instance
    if not _mqtt_client_instance:
        _mqtt_client_instance = MQTTClient()
    return _mqtt_client_instance
