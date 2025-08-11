"""
WebSocket实时进度管理器
提供WebSocket服务，实现多用户实时进度同步
"""

import asyncio
import json
import websockets
import threading
import time
from typing import Dict, Set, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ProgressBroadcaster:
    """WebSocket进度广播管理器"""
    
    def __init__(self, host='localhost', port=9981):
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.task_states: Dict[str, Dict[str, Any]] = {}
        self.server = None
        self._lock = threading.Lock()
        
    def start_server(self):
        """启动WebSocket服务器"""
        def run_server():
            asyncio.set_event_loop(asyncio.new_event_loop())
            loop = asyncio.get_event_loop()
            self.server = loop.run_until_complete(
                websockets.serve(self._handle_client, self.host, self.port)
            )
            logger.info(f"WebSocket服务器启动在 ws://{self.host}:{self.port}")
            loop.run_forever()
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
    async def _handle_client(self, websocket, path):
        """处理客户端连接"""
        self.clients.add(websocket)
        logger.info(f"客户端连接: {websocket.remote_address}")
        
        try:
            # 发送当前状态给新连接的客户端
            await self._send_current_state(websocket)
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._handle_message(websocket, data)
                except json.JSONDecodeError:
                    logger.error("收到无效的JSON消息")
                    
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            logger.info(f"客户端断开: {websocket.remote_address}")
    
    async def _send_current_state(self, websocket):
        """发送当前状态给新连接的客户端"""
        with self._lock:
            state = {
                "type": "full_state",
                "data": {
                    "tasks": self.task_states,
                    "timestamp": datetime.now().isoformat()
                }
            }
        await websocket.send(json.dumps(state))
    
    async def _handle_message(self, websocket, data):
        """处理客户端消息"""
        msg_type = data.get("type")
        
        if msg_type == "subscribe":
            # 客户端订阅特定任务
            task_id = data.get("task_id")
            if task_id:
                await websocket.send(json.dumps({
                    "type": "subscribed",
                    "task_id": task_id
                }))
    
    async def broadcast_progress(self, task_id: str, progress_data: Dict[str, Any]):
        """广播进度更新给所有连接的客户端"""
        with self._lock:
            self.task_states[task_id] = {
                **progress_data,
                "last_update": datetime.now().isoformat()
            }
            
            message = {
                "type": "progress_update",
                "task_id": task_id,
                "data": progress_data
            }
            
            if self.clients:
                websockets.broadcast(self.clients, json.dumps(message))
    
    def broadcast_progress_sync(self, task_id: str, progress_data: Dict[str, Any]):
        """同步版本的进度广播（线程安全）"""
        asyncio.run_coroutine_threadsafe(
            self.broadcast_progress(task_id, progress_data),
            asyncio.get_event_loop()
        )
    
    async def broadcast_queue_update(self, queue_data: Dict[str, Any]):
        """广播队列更新"""
        message = {
            "type": "queue_update",
            "data": queue_data
        }
        
        if self.clients:
            websockets.broadcast(self.clients, json.dumps(message))
    
    def broadcast_queue_update_sync(self, queue_data: Dict[str, Any]):
        """同步版本的队列更新广播"""
        asyncio.run_coroutine_threadsafe(
            self.broadcast_queue_update(queue_data),
            asyncio.get_event_loop()
        )
    
    def cleanup_task(self, task_id: str):
        """清理已完成的任务状态"""
        with self._lock:
            if task_id in self.task_states:
                del self.task_states[task_id]
    
    def get_task_state(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        with self._lock:
            return self.task_states.get(task_id, {})
    
    def shutdown(self):
        """关闭WebSocket服务器"""
        if self.server:
            self.server.close()


class ProgressStateManager:
    """全局进度状态管理器"""
    
    def __init__(self):
        self.current_task = None
        self.current_progress = 0.0
        self.current_stage = "waiting"
        self.queue_files = []
        self.eta_seconds = 0
        self.start_time = None
        self._lock = threading.Lock()
    
    def set_current_task(self, filename: str):
        """设置当前任务"""
        with self._lock:
            self.current_task = filename
            self.current_progress = 0.0
            self.current_stage = "starting"
            self.start_time = time.time()
    
    def update_progress(self, progress: float, stage: str = "translating", eta_seconds: int = 0):
        """更新当前任务进度"""
        with self._lock:
            self.current_progress = progress
            self.current_stage = stage
            self.eta_seconds = eta_seconds
    
    def set_queue_files(self, files: list):
        """设置排队文件列表"""
        with self._lock:
            self.queue_files = files
    
    def get_state(self) -> Dict[str, Any]:
        """获取当前状态"""
        with self._lock:
            return {
                "current_task": self.current_task,
                "current_progress": self.current_progress,
                "current_stage": self.current_stage,
                "queue_files": self.queue_files,
                "eta_seconds": self.eta_seconds,
                "queue_length": len(self.queue_files),
                "start_time": self.start_time
            }


# 全局实例
progress_broadcaster = ProgressBroadcaster()
progress_state_manager = ProgressStateManager()


def initialize_websocket_server():
    """初始化WebSocket服务器"""
    try:
        import websockets
        progress_broadcaster.start_server()
        return True
    except ImportError:
        logger.warning("websockets库未安装，WebSocket功能将不可用")
        return False


def broadcast_progress(task_id: str, progress: float, stage: str = "translating", eta_seconds: int = 0, **kwargs):
    """广播进度更新（简化接口）"""
    progress_data = {
        "progress": progress,
        "stage": stage,
        "eta_seconds": eta_seconds,
        "timestamp": datetime.now().isoformat(),
        **kwargs
    }
    progress_broadcaster.broadcast_progress_sync(task_id, progress_data)


def broadcast_queue_update(current_task: str = None, queue_files: list = None, **kwargs):
    """广播队列更新"""
    queue_data = {
        "current_task": current_task,
        "queue_files": queue_files or [],
        "queue_length": len(queue_files or []),
        **kwargs
    }
    progress_broadcaster.broadcast_queue_update_sync(queue_data)