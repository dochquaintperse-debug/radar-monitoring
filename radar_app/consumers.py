import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class RadarConsumer(AsyncWebsocketConsumer):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.monitoring_task = None
        self.is_monitoring = False
        self.heartbeat_task = None
        self.last_data_time = None
    
    async def connect(self):
        await self.channel_layer.group_add("radar_group", self.channel_name)
        await self.accept()
        logger.info(f"WebSocket连接已建立: {self.channel_name}")
        
        # 启动心跳检测
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
    async def disconnect(self, close_code):
        # 停止所有任务
        if self.monitoring_task:
            self.monitoring_task.cancel()
            self.is_monitoring = False
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            
        await self.channel_layer.group_discard("radar_group", self.channel_name)
        logger.info(f"WebSocket连接已断开: {self.channel_name}, 代码: {close_code}")

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
                    'type': 'pong',
                    'timestamp': timezone.now().isoformat()
                }))
                
        except Exception as e:
            logger.error(f"命令处理失败: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error_message',
                'message': f'命令处理失败: {str(e)}'
            }))

    async def _heartbeat_loop(self):
        """心跳检测循环"""
        try:
            while True:
                await asyncio.sleep(30) 
                
                if self.last_data_time:
                    time_diff = timezone.now() - self.last_data_time
                    if time_diff.total_seconds() > 60: 
                        await self.send(text_data=json.dumps({
                            'type': 'connection_warning',
                            'message': '数据连接可能中断，请检查桥接器'
                        }))
                
        except asyncio.CancelledError:
            logger.info("心跳检测已停止")
        except Exception as e:
            logger.error(f"心跳检测出错: {e}")

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
        """优化的监测循环"""
        try:
            focus_state = False
            consecutive_focus_count = 0
            
            while self.is_monitoring:
                # 收集5秒内的数据
                focus_data = []
                for i in range(5):
                    if not self.is_monitoring:
                        return
                    
                    recent_data = await self._get_recent_data(1)
                    focus_data.extend(recent_data)
                    await asyncio.sleep(1)
                
                if focus_data:
                    # 专注状态判断
                    focus_values = [v for v in focus_data if 15 <= v <= 17]
                    focus_ratio = len(focus_values) / len(focus_data)
                    
                    is_focused = focus_ratio >= 0.8 and len(focus_data) >= 3
                    
                    if is_focused:
                        consecutive_focus_count += 1
                        if consecutive_focus_count >= 2 and not focus_state: 
                            await self.send(text_data=json.dumps({
                                'type': 'show_cloud',
                                'message': '检测到专注状态',
                                'data_count': len(focus_data),
                                'focus_ratio': round(focus_ratio * 100, 1)
                            }))
                            focus_state = True
                    else:
                        consecutive_focus_count = 0
                        if focus_state:
                            focus_state = False
                            await self.send(text_data=json.dumps({
                                'type': 'focus_lost',
                                'message': '专注状态结束'
                            }))
                
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info("监测任务已取消")
        except Exception as e:
            logger.error(f"监测循环出错: {e}")
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
    def _get_recent_data(self, seconds):
        """获取最近几秒的数据"""
        from .models import RadarData
        
        time_ago = timezone.now() - timedelta(seconds=seconds)
        recent_data = list(RadarData.objects.filter(
            timestamp__gte=time_ago
        ).values_list('value', flat=True))
        
        return recent_data

    # 消息处理器
    async def radar_data(self, event):
        self.last_data_time = timezone.now()
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
