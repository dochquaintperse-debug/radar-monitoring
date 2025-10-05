# radar_app/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
import os

class RadarConsumer(AsyncWebsocketConsumer):
    
    async def connect(self):
        await self.channel_layer.group_add("radar_group", self.channel_name)
        await self.accept()
        print("WebSocket连接已建立")
        
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("radar_group", self.channel_name)
        print("WebSocket连接已断开")

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            command = text_data_json.get('command')
            print(f"收到WebSocket命令: {command}")
            
            # 检测环境：云端还是本地
            is_cloud = os.environ.get('RENDER') is not None
            
            if is_cloud:
                # 云端环境：直接调用Django视图函数，不使用HTTP请求
                await self._handle_cloud_command(command)
            else:
                # 本地环境：使用MQTT客户端和串口桥
                await self._handle_local_command(command)
                
        except Exception as e:
            print(f"WebSocket命令处理错误: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error_message',
                'message': f'命令处理失败: {str(e)}'
            }))

    async def _handle_cloud_command(self, command):
        """云端环境命令处理 - 直接调用Django视图函数"""
        if command == 'start_training':
            # 直接调用启动训练函数
            success = await self._start_cloud_training()
            if success:
                await self.send(text_data=json.dumps({
                    'type': 'training_started',
                    'message': '训练模式已启动，等待桥接器数据...'
                }))
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error_message',
                    'message': '启动训练失败：无法初始化训练状态'
                }))
            
        elif command == 'stop_training':
            success = await self._stop_cloud_training()
            await self.send(text_data=json.dumps({
                'type': 'training_stopped', 
                'message': '训练已手动停止'
            }))
            
        elif command == 'start_monitoring':
            # 检查是否有训练结果
            has_training = await self._check_training_results()
            if has_training:
                await self.send(text_data=json.dumps({
                    'type': 'monitoring_started',
                    'message': '监测模式已启动'
                }))
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error_message',
                    'message': '请先完成训练再开始监测'
                }))
                
        elif command == 'stop_monitoring':
            await self.send(text_data=json.dumps({
                'type': 'monitoring_stopped',
                'message': '监测模式已停止'
            }))

    @sync_to_async
    def _start_cloud_training(self):
        """启动云端训练模式 - 直接调用"""
        try:
            # 导入视图模块中的全局状态
            from . import views
            
            # 取消之前的定时器
            if views.CLOUD_TRAINING_STATE['timer']:
                views.CLOUD_TRAINING_STATE['timer'].cancel()
            
            # 重置并启动训练
            views.CLOUD_TRAINING_STATE = {
                'is_training': True,
                'training_data': [],
                'start_time': None,
                'sensor_id': None,
                'timer': None
            }
            
            print("🚀 云端训练模式已启动（WebSocket直接调用）")
            return True
            
        except Exception as e:
            print(f"启动云端训练失败: {e}")
            return False

    @sync_to_async
    def _stop_cloud_training(self):
        """停止云端训练模式 - 直接调用"""
        try:
            from . import views
            from .models import RadarSensor
            
            # 取消定时器
            if views.CLOUD_TRAINING_STATE['timer']:
                views.CLOUD_TRAINING_STATE['timer'].cancel()
                views.CLOUD_TRAINING_STATE['timer'] = None
            
            # 如果有数据，完成训练
            if views.CLOUD_TRAINING_STATE['training_data'] and views.CLOUD_TRAINING_STATE['sensor_id']:
                try:
                    sensor = RadarSensor.objects.get(name=views.CLOUD_TRAINING_STATE['sensor_id'])
                    views._complete_cloud_training(sensor)
                except RadarSensor.DoesNotExist:
                    # 直接停止
                    views.CLOUD_TRAINING_STATE = {
                        'is_training': False,
                        'training_data': [],
                        'start_time': None,
                        'sensor_id': None,
                        'timer': None
                    }
            else:
                # 直接停止
                views.CLOUD_TRAINING_STATE = {
                    'is_training': False,
                    'training_data': [],
                    'start_time': None,
                    'sensor_id': None,
                    'timer': None
                }
            
            print("⏹️ 云端训练模式已停止（WebSocket直接调用）")
            return True
            
        except Exception as e:
            print(f"停止云端训练失败: {e}")
            return False

    async def _handle_local_command(self, command):
        """本地环境命令处理（原有逻辑）"""
        from .mqtt_client import get_mqtt_client
        mqtt_client = get_mqtt_client()
        
        if command == 'start_training':
            mqtt_client.start_training_mode()
            
        elif command == 'stop_training':
            mqtt_client.stop_training_mode()
            await self.send(text_data=json.dumps({
                'type': 'training_stopped',
                'message': '训练已手动停止'
            }))
            
        elif command == 'start_monitoring':
            mqtt_client.start_monitoring_mode()
            
        elif command == 'stop_monitoring':
            mqtt_client.stop_monitoring_mode()

    @sync_to_async
    def _check_training_results(self):
        """检查是否存在训练结果"""
        from .models import TrainingResult
        return TrainingResult.objects.exists()

    # WebSocket消息处理器（保持不变）
    async def radar_data(self, event):
        await self.send(text_data=json.dumps({
            'type': 'radar_data',
            'sensor_id': event['sensor_id'],
            'value': event['value'],
            'hex_value': event.get('hex_value', ''),
            'timestamp': event['timestamp']
        }))

    async def training_started(self, event):
        await self.send(text_data=json.dumps({
            'type': 'training_started',
            'message': event['message']
        }))

    async def training_complete(self, event):
        await self.send(text_data=json.dumps({
            'type': 'training_complete',
            'sensor_id': event['sensor_id'],
            'average_value': event['average_value']
        }))

    async def training_stopped(self, event):
        await self.send(text_data=json.dumps({
            'type': 'training_stopped',
            'message': event.get('message', '训练已停止'),
            'sensor_id': event.get('sensor_id')
        }))

    async def monitoring_started(self, event):
        await self.send(text_data=json.dumps({
            'type': 'monitoring_started',
            'message': event.get('message', '监测模式已启动'),
            'sensor_id': event.get('sensor_id')
        }))

    async def monitoring_stopped(self, event):
        await self.send(text_data=json.dumps({
            'type': 'monitoring_stopped',
            'message': event.get('message', '监测模式已停止'),
            'sensor_id': event.get('sensor_id')
        }))

    async def anomaly_detected(self, event):
        await self.send(text_data=json.dumps({
            'type': 'anomaly_detected',
            'sensor_id': event['sensor_id'],
            'values': event['values'],
            'average': event['average']
        }))

    async def error_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'error_message',
            'message': event['message']
        }))
