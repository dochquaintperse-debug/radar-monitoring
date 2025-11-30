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
        self.connection_check_task = None
        self.is_monitoring = False
        self.bridge_connected = False
        self.last_data_time = None
        self.focus_state = False
        self.warning_shown = False
        
    async def connect(self):
        try:
            await self.channel_layer.group_add("radar_group", self.channel_name)
            await self.accept()
            
            # 启动连接检查任务
            self.connection_check_task = asyncio.create_task(self.connection_check())
            
            # 发送连接状态
            await self.send(text_data=json.dumps({
                'type': 'websocket_connected',
                'message': 'WebSocket已连接，等待桥接器数据...'
            }))
            
        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
            await self.close()
        
    async def disconnect(self, close_code):
        # 停止所有任务
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
        
        if self.connection_check_task and not self.connection_check_task.done():
            self.connection_check_task.cancel()
            
        self.is_monitoring = False
        
        try:
            await self.channel_layer.group_discard("radar_group", self.channel_name)
        except:
            pass
        logger.info(f"WebSocket连接已断开: {close_code}")

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
            elif command == 'dismiss_warning':
                # 用户手动关闭警告
                self.warning_shown = False
                await self.send(text_data=json.dumps({
                    'type': 'warning_dismissed'
                }))
                
        except Exception as e:
            logger.error(f"消息处理错误: {e}")

    async def start_monitoring(self):
        """启动监测模式 - 需要桥接器连接"""
        if not self.bridge_connected:
            await self.send(text_data=json.dumps({
                'type': 'error_message',
                'message': '请先启动桥接器连接！'
            }))
            return
            
        if self.is_monitoring:
            return
            
        self.is_monitoring = True
        self.focus_state = False
        self.warning_shown = False
        
        await self.send(text_data=json.dumps({
            'type': 'monitoring_started',
            'message': '专注监测已启动'
        }))
        
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def _monitoring_loop(self):
        try:
            for i in range(60):
                if not self.is_monitoring:
                    return
                await asyncio.sleep(1)
            
            if not self.is_monitoring:
                return
            
            # 主监测循环
            while self.is_monitoring:
                focus_data = []
                
                # 持续5秒收集数据
                start_time = timezone.now()
                end_time = start_time + timedelta(seconds=5)
                
                while timezone.now() < end_time and self.is_monitoring:
                    # 获取最新数据
                    recent_data = await self._get_recent_data(1)  # 获取1秒内的新数据
                    
                    if recent_data:
                        focus_data.extend(recent_data)
                    
                    await asyncio.sleep(0.5)  # 小间隔检查新数据
                
                if focus_data:
                    await self._process_focus_data(focus_data)
                
                if self.is_monitoring:
                    await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info("监测任务已取消")
        except Exception as e:
            logger.error(f"监测循环出错: {e}")
            # 静默处理错误，避免打扰用户

    async def _process_focus_data(self, focus_data):

        # 统计各个值的出现次数
        value_counts = {}
        for value in focus_data:
            if value not in value_counts:
                value_counts[value] = 0
            value_counts[value] += 1
        
        # 特定值的计数
        counts_15 = value_counts.get(15, 0)
        counts_16 = value_counts.get(16, 0)
        counts_17 = value_counts.get(17, 0)
        
        total_data = len(focus_data)
        
        # 判断逻辑：数据都为15，或都为16，或都为17
        is_all_15 = counts_15 == total_data and total_data > 0
        is_all_16 = counts_16 == total_data and total_data > 0
        is_all_17 = counts_17 == total_data and total_data > 0
        
        is_focused = is_all_15 or is_all_16 or is_all_17
        
        logger.info(f"数据分析: 总数={total_data}, 全15={is_all_15}, 全16={is_all_16}, 全17={is_all_17}, 专注={is_focused}")
        
        
        if is_focused:
            # 进入专注状态
            if not self.focus_state:
                self.focus_state = True
                self.warning_shown = False  # 清除警告状态
                
                await self.send(text_data=json.dumps({
                    'type': 'show_cloud',
                    'message': '检测到专注状态！',
                    'data_count': total_data,
                    'focus_value': 15 if is_all_15 else (16 if is_all_16 else 17)
                }))
                
                logger.info("用户进入专注状态")
            else:

                logger.info("用户保持专注状态")
        else:
            # 非专注状态
            if self.focus_state:
                self.focus_state = False
                logger.info("用户离开专注状态")
            
            # 显示红色警告牌
            if not self.warning_shown:
                self.warning_shown = True
                await self.send(text_data=json.dumps({
                    'type': 'show_warning',
                    'message': '注意力分散！请专注！',
                    'data_count': total_data,
                    'counts': value_counts,
                    'unfocus_values': list(set(focus_data) - {15, 16, 17})
                }))
                logger.info("⚠️ 显示专注警告")

    async def stop_monitoring(self):
        """停止监测"""
        self.is_monitoring = False
        self.focus_state = False
        self.warning_shown = False
        
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
            ).values_list('value', flat=True)[:50])  # 限制数据量
        except Exception as e:
            logger.error(f"获取数据失败: {e}")
            return []

    # 消息处理器
    async def radar_data(self, event):
        """处理雷达数据"""
        try:
            # 更新桥接器连接状态
            if not self.bridge_connected:
                self.bridge_connected = True
                await self.send(text_data=json.dumps({
                    'type': 'bridge_connected',
                    'message': '桥接器已连接，可以开始监测'
                }))
            
            self.last_data_time = timezone.now()
            
            # 发送数据到前端
            await self.send(text_data=json.dumps({
                'type': 'radar_data',
                'sensor_id': event['sensor_id'],
                'value': event['value'],
                'timestamp': event['timestamp']
            }))
            
        except Exception as e:
            logger.error(f"发送数据失败: {e}")

    async def connection_check(self):
        """定期检查桥接器连接"""
        while True:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次
                
                if self.last_data_time:
                    time_diff = timezone.now() - self.last_data_time
                    if time_diff.total_seconds() > 60:  # 超过60秒无数据
                        if self.bridge_connected:
                            self.bridge_connected = False
                            await self.send(text_data=json.dumps({
                                'type': 'bridge_disconnected',
                                'message': '桥接器连接中断，请检查'
                            }))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"连接检查错误: {e}")
