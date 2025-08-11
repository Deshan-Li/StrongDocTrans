# WebSocket实时进度同步功能说明

## 功能概述

本项目新增了WebSocket实时进度同步功能，解决了多用户排队时无法实时查看当前任务进度的问题。

## 主要特性

### 1. 实时进度显示
- **当前任务进度**：排队用户可以实时看到正在进行的翻译任务的详细进度
- **任务阶段显示**：显示当前翻译所处的阶段（提取、去重、翻译、完成等）
- **预计剩余时间**：基于历史数据智能估算剩余时间

### 2. 队列状态同步
- **排队文件列表**：显示所有排队的文件名
- **个人排队位置**：显示自己在队列中的位置
- **预计等待时间**：基于历史数据估算每个排队任务的等待时间

### 3. 连接状态提示
- **实时连接指示**：显示WebSocket连接状态
- **自动重连机制**：网络异常时自动重连
- **降级处理**：WebSocket不可用时自动降级到轮询模式

## 技术架构

### 组件结构
```
├── websocket_progress_manager.py  # WebSocket服务端管理
├── progress_state_manager.py      # 全局状态管理
├── static/js/progress_client.js   # 客户端WebSocket脚本
├── static/css/progress_ui.css     # 实时UI样式
└── app.py                         # Gradio集成
```

### 消息格式
```json
{
  "type": "progress_update",
  "task_id": "current_task",
  "data": {
    "progress": 0.65,
    "stage": "translating",
    "stage_description": "正在翻译第15/30段...",
    "eta_seconds": 45,
    "completed_segments": 15,
    "total_segments": 30
  }
}
```

## 使用方法

### 1. 安装依赖
```bash
pip install -r websocket_requirements.txt
```

### 2. 启动应用
正常使用：
```bash
python app.py
```

WebSocket服务器会自动在端口9981启动，与Gradio应用并行运行。

### 3. 多用户测试
- 打开浏览器访问 http://localhost:9980
- 在多个浏览器标签页或不同设备上同时访问
- 上传多个文件进行排队，观察实时进度同步

## 性能优化

### 1. 网络优化
- **消息压缩**：自动压缩传输数据
- **批量发送**：减少网络请求次数
- **心跳检测**：保持连接活跃

### 2. 内存管理
- **状态清理**：自动清理已完成任务的状态
- **连接池管理**：限制最大连接数
- **垃圾回收**：定期清理过期数据

## 故障排除

### 常见问题

#### 1. WebSocket连接失败
```bash
# 检查端口占用
netstat -ano | findstr :9981

# 修改端口（在websocket_progress_manager.py中）
# 修改 ProgressBroadcaster 类
```

#### 2. 防火墙问题
确保防火墙允许9981端口的TCP连接。

#### 3. 浏览器兼容性
- **支持**：Chrome 16+, Firefox 11+, Safari 6+, Edge 12+
- **降级**：IE11及以下使用轮询模式

### 调试方法
```javascript
// 在浏览器控制台查看WebSocket消息
WebSocketAPI.client.ws.onmessage = (event) => {
    console.log('WebSocket消息:', JSON.parse(event.data));
};
```

## API接口

### 客户端API
```javascript
// 获取全局实例
const client = window.progressClient;

// 订阅进度更新
client.subscribeToProgress((data) => {
    console.log('进度更新:', data);
});

// 订阅队列更新
client.subscribeToQueue((data) => {
    console.log('队列更新:', data);
});

// 检查连接状态
client.subscribeToConnection((data) => {
    console.log('连接状态:', data.connected);
});
```

### 服务端API
```python
from progress_state_manager import (
    start_task, update_progress, complete_task, update_queue
)

# 开始新任务
start_task("document.pdf", total_segments=50)

# 更新进度
update_progress(0.5, "translating", "正在翻译第25段...", 
               completed_segments=25, total_segments=50)

# 完成任务
complete_task(True, "翻译完成")

# 更新队列
update_queue(["file1.pdf", "file2.docx", "file3.txt"])
```

## 配置选项

### WebSocket配置
在`websocket_progress_manager.py`中修改：
```python
# 修改默认端口
progress_broadcaster = ProgressBroadcaster(host='localhost', port=9982)

# 修改重连间隔
client.reconnect_interval = 2000  # 2秒
```

### 性能调优
- **最大连接数**：默认100个并发连接
- **消息频率**：限制每秒最多10次更新
- **内存限制**：历史记录最多保存100个任务

## 安全考虑

### 1. 连接验证
- 简单的来源验证
- 防止恶意连接
- 限流机制

### 2. 数据安全
- 不传输敏感文件内容
- 仅传输文件名和进度信息
- 本地运行，无外网暴露

## 扩展功能

### 未来规划
1. **移动端适配**：响应式UI设计
2. **推送通知**：浏览器推送通知
3. **历史统计**：翻译任务统计面板
4. **性能监控**：实时性能指标

### 自定义集成
可以轻松集成到其他Python应用中：
```python
from websocket_progress_manager import ProgressBroadcaster

# 创建独立的进度广播器
broadcaster = ProgressBroadcaster(port=9999)
broadcaster.start_server()
```

## 测试验证

### 1. 单用户测试
- 上传单个文件，观察进度条
- 验证各阶段状态显示
- 测试取消功能

### 2. 多用户测试
- 同时打开多个浏览器标签
- 上传多个文件排队
- 验证实时同步效果

### 3. 压力测试
- 100个并发连接测试
- 大文件长时间翻译测试
- 网络波动重连测试

## 联系支持

如遇到问题，请提供：
1. 浏览器控制台日志
2. 服务端日志（包含WebSocket相关）
3. 具体的重现步骤

日志文件位置：`logs/app.log`