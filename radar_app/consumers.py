import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async, async_to_sync
from .mqtt_client import get_mqtt_client
class RadarConsumer(AsyncWebsocketConsumer):
    
    async def connect(self):
        await self.channel_layer.group_add("radar_group", self.channel_name)
        await self.accept()
        
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("radar_group", self.channel_name)
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        command = text_data_json.get('command')
        print(f"收到命令: {command}")
        
        # 获取MQTT客户端实例
        mqtt_client = get_mqtt_client()
        
        if command == 'start_training':
            # 启动训练模式
            mqtt_client.start_training_mode()
            
        elif command == 'stop_training':
            # 手动停止训练模式（关键新增）
            mqtt_client.stop_training_mode()
            await self.send(text_data=json.dumps({
                'type': 'training_stopped',
                'message': '训练已手动停止'
            }))
            
        elif command == 'start_monitoring':
            mqtt_client.start_monitoring_mode()
            await self.send(text_data=json.dumps({
                'type': 'monitoring_started',
                'message': '监测模式已启动'
            }))
            
        elif command == 'stop_monitoring':
            mqtt_client.stop_monitoring_mode()
            await self.send(text_data=json.dumps({
                'type': 'monitoring_stopped',
                'message': '监测模式已停止'
            }))
    # 处理传感器发现消息
    async def sensor_discovered(self, event):
        await self.send(text_data=json.dumps({
            'type': 'sensor_discovered',
            'sensor_id': event['sensor_id'],
            'sensor_name': event['sensor_name']
        }))
    # 处理雷达数据消息
    async def radar_data(self, event):
        await self.send(text_data=json.dumps({
            'type': 'radar_data',
            'sensor_id': event['sensor_id'],
            'value': event['value'],
            'hex_value': event.get('hex_value', ''),
            'timestamp': event['timestamp']
        }))
    # 处理训练开始消息
    async def training_started(self, event):
        await self.send(text_data=json.dumps({
            'type': 'training_started',
            'message': event['message']
        }))
    # 处理训练完成消息
    async def training_complete(self, event):
        await self.send(text_data=json.dumps({
            'type': 'training_complete',
            'sensor_id': event['sensor_id'],
            'average_value': event['average_value']
        }))
    # 新增：处理训练停止消息
    async def training_stopped(self, event):
        await self.send(text_data=json.dumps({
            'type': 'training_stopped',
            'message': event.get('message', '训练已停止'),
            'sensor_id': event.get('sensor_id')
        }))
    # 处理监测开始消息
    async def monitoring_started(self, event):
        await self.send(text_data=json.dumps({
            'type': 'monitoring_started',
            'message': event.get('message', '监测模式已启动'),
            'sensor_id': event.get('sensor_id')
        }))
    # 处理监测停止消息
    async def monitoring_stopped(self, event):
        await self.send(text_data=json.dumps({
            'type': 'monitoring_stopped',
            'message': event.get('message', '监测模式已停止'),
            'sensor_id': event.get('sensor_id')
        }))
    # 处理异常检测消息
    async def anomaly_detected(self, event):
        await self.send(text_data=json.dumps({
            'type': 'anomaly_detected',
            'sensor_id': event['sensor_id'],
            'values': event['values'],
            'average': event['average']
        }))
    # 处理错误消息
    async def error_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'error_message',
            'message': event['message']
        }))