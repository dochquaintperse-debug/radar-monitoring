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
        try:
            await self.channel_layer.group_add("radar_group", self.channel_name)
            await self.accept()
            print("WebSocket连接已建立")
        except Exception as e:
            print(f"WebSocket连接失败: {e}")
            await self.close()
        
    async def disconnect(self, close_code):
        # 停止监测任务
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            self.is_monitoring = False
        
        try:
            await self.channel_layer.group_discard("radar_group", self.channel_name)
        except:
            pass
        print(f"WebSocket连接已断开: {close_code}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            command = data.get('command')
            
            if command == 'start_monitoring':
                await self.start_monitoring()
            elif command == 'stop_monitoring':
                await self.stop_monitoring()
            elif command == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong'
                }))
                
        except Exception as e:
            print(f"消息处理错误: {e}")

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
        """简化的监测循环"""
        try:
            focus_state = False
            
            while self.is_monitoring:
                # 获取最近5秒的数据
                recent_data = await self._get_recent_data(5)
                
                if recent_data and len(recent_data) >= 3:
                    # 专注判断
                    focus_values = [v for v in recent_data if 15 <= v <= 17]
                    focus_ratio = len(focus_values) / len(recent_data)
                    
                    is_focused = focus_ratio >= 1
                    
                    if is_focused and not focus_state:
                        await self.send(text_data=json.dumps({
                            'type': 'show_cloud',
                            'message': '检测到专注状态',
                            'data_count': len(recent_data),
                            'focus_ratio': round(focus_ratio * 100, 1)
                        }))
                        focus_state = True
                    elif not is_focused and focus_state:
                        focus_state = False
                
                await asyncio.sleep(2)  # 每2秒检测一次
                
        except asyncio.CancelledError:
            print("监测任务已取消")
        except Exception as e:
            print(f"监测循环出错: {e}")

    async def stop_monitoring(self):
        """停止监测"""
        self.is_monitoring = False
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            self.monitoring_task = None
            
        await self.send(text_data=json.dumps({
            'type': 'monitoring_stopped',
            'message': '专注监测已停止'
        }))

    @sync_to_async
    def _get_recent_data(self, seconds):
        """获取最近几秒的数据"""
        try:
            from .models import RadarData
            time_ago = timezone.now() - timedelta(seconds=seconds)
            return list(RadarData.objects.filter(
                timestamp__gte=time_ago
            ).values_list('value', flat=True)[:20])  # 限制数据量
        except Exception as e:
            print(f"获取数据失败: {e}")
            return []

    # 消息处理器
    async def radar_data(self, event):
        try:
            await self.send(text_data=json.dumps({
                'type': 'radar_data',
                'sensor_id': event['sensor_id'],
                'value': event['value'],
                'timestamp': event['timestamp']
            }))
        except Exception as e:
            print(f"发送数据失败: {e}")
