"""
全局进度状态管理器
提供线程安全的全局状态管理，支持WebSocket广播
"""

import threading
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class GlobalProgressManager:
    """全局进度管理器 - 单例模式"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
            
        self._initialized = True
        self._state_lock = threading.Lock()
        
        # 当前任务状态
        self.current_task = {
            "filename": None,
            "progress": 0.0,
            "stage": "idle",
            "stage_description": "等待任务",
            "start_time": None,
            "eta_seconds": 0,
            "total_segments": 0,
            "completed_segments": 0,
            "failed_segments": 0
        }
        
        # 队列状态
        self.queue_state = {
            "queue_files": [],
            "queue_length": 0,
            "estimated_total_wait_time": 0
        }
        
        # 任务历史
        self.task_history = []
        self.max_history_size = 100
        
        # WebSocket广播器引用
        self.websocket_broadcaster = None
    
    def set_websocket_broadcaster(self, broadcaster):
        """设置WebSocket广播器"""
        self.websocket_broadcaster = broadcaster
    
    def start_new_task(self, filename: str, total_segments: int = 0):
        """开始新任务"""
        with self._state_lock:
            self.current_task.update({
                "filename": filename,
                "progress": 0.0,
                "stage": "initializing",
                "stage_description": "初始化翻译任务",
                "start_time": time.time(),
                "eta_seconds": 0,
                "total_segments": total_segments,
                "completed_segments": 0,
                "failed_segments": 0
            })
            self._broadcast_current_state()
    
    def update_progress(self, progress: float, stage: str = None, stage_description: str = None, 
                       completed_segments: int = None, failed_segments: int = None):
        """更新进度"""
        with self._state_lock:
            self.current_task["progress"] = max(0.0, min(1.0, progress))
            
            if stage:
                self.current_task["stage"] = stage
            if stage_description:
                self.current_task["stage_description"] = stage_description
            if completed_segments is not None:
                self.current_task["completed_segments"] = completed_segments
            if failed_segments is not None:
                self.current_task["failed_segments"] = failed_segments
                
            # 计算ETA
            if self.current_task["start_time"] and progress > 0:
                elapsed = time.time() - self.current_task["start_time"]
                if progress > 0.1:  # 避免除零错误
                    total_estimated = elapsed / progress
                    self.current_task["eta_seconds"] = max(0, int(total_estimated - elapsed))
            
            self._broadcast_current_state()
    
    def update_stage(self, stage: str, description: str):
        """更新任务阶段"""
        self.update_progress(self.current_task["progress"], stage, description)
    
    def complete_task(self, success: bool = True, message: str = None):
        """完成任务"""
        with self._state_lock:
            task_data = dict(self.current_task)
            task_data["end_time"] = time.time()
            task_data["success"] = success
            task_data["message"] = message or ("完成" if success else "失败")
            
            # 添加到历史记录
            self.task_history.append(task_data)
            if len(self.task_history) > self.max_history_size:
                self.task_history.pop(0)
            
            # 重置当前任务
            self.current_task.update({
                "filename": None,
                "progress": 0.0,
                "stage": "idle",
                "stage_description": "等待任务",
                "start_time": None,
                "eta_seconds": 0,
                "total_segments": 0,
                "completed_segments": 0,
                "failed_segments": 0
            })
            
            self._broadcast_current_state()
    
    def update_queue(self, queue_files: List[str]):
        """更新队列状态"""
        with self._state_lock:
            self.queue_state["queue_files"] = queue_files
            self.queue_state["queue_length"] = len(queue_files)
            
            # 根据历史数据估算等待时间
            if self.task_history:
                avg_task_time = sum(
                    (task.get("end_time", 0) - task.get("start_time", 0))
                    for task in self.task_history[-10:]  # 最近10个任务
                ) / min(10, len(self.task_history))
                
                self.queue_state["estimated_total_wait_time"] = int(
                    avg_task_time * len(queue_files)
                )
            else:
                self.queue_state["estimated_total_wait_time"] = 0
            
            self._broadcast_queue_state()
    
    def get_current_state(self) -> Dict[str, Any]:
        """获取当前完整状态"""
        with self._state_lock:
            return {
                "current_task": dict(self.current_task),
                "queue_state": dict(self.queue_state),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_current_task_info(self) -> Dict[str, Any]:
        """获取当前任务信息"""
        with self._state_lock:
            return dict(self.current_task)
    
    def get_queue_info(self) -> Dict[str, Any]:
        """获取队列信息"""
        with self._state_lock:
            return dict(self.queue_state)
    
    def _broadcast_current_state(self):
        """广播当前状态"""
        if self.websocket_broadcaster:
            state = self.get_current_state()
            self.websocket_broadcaster.broadcast_progress_sync(
                "current_task", 
                {"current_task": state["current_task"]}
            )
    
    def _broadcast_queue_state(self):
        """广播队列状态"""
        if self.websocket_broadcaster:
            state = self.get_current_state()
            self.websocket_broadcaster.broadcast_queue_update_sync(
                state["queue_state"]
            )
    
    def is_task_running(self) -> bool:
        """检查是否有任务正在运行"""
        return self.current_task["filename"] is not None
    
    def get_wait_time_for_position(self, position: int) -> int:
        """根据排队位置计算预计等待时间"""
        with self._state_lock:
            if not self.task_history:
                return position * 60  # 默认每个任务1分钟
            
            avg_task_time = sum(
                (task.get("end_time", 0) - task.get("start_time", 0))
                for task in self.task_history[-10:]
            ) / min(10, len(self.task_history))
            
            return int(avg_task_time * position)


# 创建全局实例
progress_manager = GlobalProgressManager()

# 便捷的接口函数
def start_task(filename: str, total_segments: int = 0):
    """开始新任务"""
    progress_manager.start_new_task(filename, total_segments)


def update_progress(progress: float, stage: str = None, description: str = None, **kwargs):
    """更新进度"""
    progress_manager.update_progress(progress, stage, description, **kwargs)


def complete_task(success: bool = True, message: str = None):
    """完成任务"""
    progress_manager.complete_task(success, message)


def update_queue(queue_files: List[str]):
    """更新队列"""
    progress_manager.update_queue(queue_files)


def get_current_progress_info() -> Dict[str, Any]:
    """获取当前进度信息"""
    return progress_manager.get_current_state()