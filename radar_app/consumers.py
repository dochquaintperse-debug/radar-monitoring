import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils import timezone
from datetime import timedelta

class RadarConsumer(AsyncWebsocketConsumer):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.monitoring_task = None
        self.is_monitoring = False
    
    async def connect(self):
        await self.channel_layer.group_add("radar_group", self.channel_name)
        await self.accept()
        print("WebSocket连接已建立")
        
    async def disconnect(self, close_code):
        # 停止监测任务
        if self.monitoring_task:
            self.monitoring_task.cancel()
            self.is_monitoring = False
        await self.channel_layer.group_discard("radar_group", self.channel_name)
        print("WebSocket连接已断开")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            command = data.get('command')
            
            if command == 'start_monitoring':
                await self.start_monitoring()
            elif command == 'stop_monitoring':
                await self.stop_monitoring()
                
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error_message',
                'message': f'命令处理失败: {str(e)}'
            }))

    async def start_monitoring(self):
        """启动监测模式"""
        if self.is_monitoring:
            return
            
        self.is_monitoring = True
        await self.send(text_data=json.dumps({
            'type': 'monitoring_started',
            'message': '专注状态监测已启动'
        }))
        
        # 创建监测任务
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def _monitoring_loop(self):
        try:
            await asyncio.sleep(60)
            
            focus_state = False
            
            while self.is_monitoring:
                focus_data = []
                for i in range(5):
                    if not self.is_monitoring:
                        return
                    
                    recent_data = await self._get_recent_data()
                    focus_data.extend(recent_data)
                    await asyncio.sleep(1)
                
                # 判断专注状态 (所有数据都在15-17范围内)
                if focus_data:
                    is_focused = all(15 <= value <= 17 for value in focus_data)
                    
                    if is_focused and not focus_state:
                        await self.send(text_data=json.dumps({
                            'type': 'show_cloud',
                            'message': '检测到专注状态',
                            'data_count': len(focus_data)
                        }))
                        focus_state = True
                    elif not is_focused:
                        focus_state = False
                
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            print("监测任务已取消")
        except Exception as e:
            print(f"监测循环出错: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error_message',
                'message': f'监测出错: {str(e)}'
            }))

    async def stop_monitoring(self):
        """停止监测"""
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            self.monitoring_task = None
            
        await self.send(text_data=json.dumps({
            'type': 'monitoring_stopped',
            'message': '专注监测已停止'
        }))

    @sync_to_async
    def _get_recent_data(self):
        """获取最近1秒的数据"""
        from .models import RadarData
        
        one_second_ago = timezone.now() - timedelta(seconds=1)
        recent_data = list(RadarData.objects.filter(
            timestamp__gte=one_second_ago
        ).values_list('value', flat=True))
        
        return recent_data

    # 消息处理器
    async def radar_data(self, event):
        await self.send(text_data=json.dumps({
            'type': 'radar_data',
            'sensor_id': event['sensor_id'],
            'value': event['value'],
            'timestamp': event['timestamp']
        }))

    async def error_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'error_message',
            'message': event['message']
        }))
