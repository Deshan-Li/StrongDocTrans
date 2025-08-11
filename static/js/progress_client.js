/**
 * WebSocket进度客户端
 * 处理实时进度更新和队列状态同步
 */

class ProgressWebSocketClient {
    constructor(serverUrl = 'ws://localhost:9981') {
        this.serverUrl = serverUrl;
        this.ws = null;
        this.reconnectInterval = 1000;
        this.maxReconnectDelay = 30000;
        this.reconnectTimer = null;
        this.isConnected = false;
        this.messageQueue = [];
        
        // 事件监听器
        this.listeners = {
            'progress_update': [],
            'queue_update': [],
            'connection_change': [],
            'error': []
        };
        
        this.init();
    }
    
    init() {
        this.connect();
    }
    
    connect() {
        try {
            this.ws = new WebSocket(this.serverUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket连接已建立');
                this.isConnected = true;
                this.clearReconnectTimer();
                this.flushMessageQueue();
                this.emit('connection_change', { connected: true });
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleMessage(message);
                } catch (error) {
                    console.error('解析消息失败:', error);
                    this.emit('error', { type: 'parse_error', error });
                }
            };
            
            this.ws.onclose = (event) => {
                console.log('WebSocket连接关闭:', event.code, event.reason);
                this.isConnected = false;
                this.emit('connection_change', { connected: false });
                this.scheduleReconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket错误:', error);
                this.emit('error', { type: 'websocket_error', error });
            };
            
        } catch (error) {
            console.error('创建WebSocket失败:', error);
            this.scheduleReconnect();
        }
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.clearReconnectTimer();
        this.isConnected = false;
    }
    
    scheduleReconnect() {
        if (this.reconnectTimer) return;
        
        this.reconnectTimer = setTimeout(() => {
            console.log('尝试重新连接...');
            this.connect();
        }, this.reconnectInterval);
        
        // 指数退避
        this.reconnectInterval = Math.min(this.reconnectInterval * 2, this.maxReconnectDelay);
    }
    
    clearReconnectTimer() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        this.reconnectInterval = 1000; // 重置重连间隔
    }
    
    handleMessage(message) {
        const { type, data, task_id } = message;
        
        switch (type) {
            case 'progress_update':
                this.emit('progress_update', { task_id, data });
                this.updateProgressUI(data);
                break;
                
            case 'queue_update':
                this.emit('queue_update', { data });
                this.updateQueueUI(data);
                break;
                
            case 'full_state':
                this.handleFullState(data);
                break;
                
            default:
                console.warn('未知消息类型:', type);
        }
    }
    
    handleFullState(data) {
        if (data.current_task) {
            this.emit('progress_update', { 
                task_id: 'current_task', 
                data: data.current_task 
            });
        }
        if (data.queue_state) {
            this.emit('queue_update', { data: data.queue_state });
        }
    }
    
    send(message) {
        if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        } else {
            this.messageQueue.push(message);
        }
    }
    
    flushMessageQueue() {
        while (this.messageQueue.length > 0 && this.isConnected) {
            const message = this.messageQueue.shift();
            this.send(message);
        }
    }
    
    // 事件系统
    on(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
    }
    
    off(event, callback) {
        if (this.listeners[event]) {
            const index = this.listeners[event].indexOf(callback);
            if (index > -1) {
                this.listeners[event].splice(index, 1);
            }
        }
    }
    
    emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error('事件监听器错误:', error);
                }
            });
        }
    }
    
    // UI更新方法
    updateProgressUI(progressData) {
        const progressBar = document.getElementById('current-task-progress');
        const progressText = document.getElementById('current-task-text');
        const stageText = document.getElementById('current-task-stage');
        const etaText = document.getElementById('current-task-eta');
        
        if (progressBar) {
            const progressPercent = Math.round(progressData.progress * 100);
            progressBar.style.width = `${progressPercent}%`;
            progressBar.setAttribute('aria-valuenow', progressPercent);
            progressBar.textContent = `${progressPercent}%`;
        }
        
        if (progressText) {
            progressText.textContent = progressData.filename || '等待任务';
        }
        
        if (stageText) {
            stageText.textContent = progressData.stage_description || progressData.stage || '';
        }
        
        if (etaText && progressData.eta_seconds > 0) {
            const eta = this.formatETA(progressData.eta_seconds);
            etaText.textContent = `预计剩余: ${eta}`;
        }
    }
    
    updateQueueUI(queueData) {
        const queueContainer = document.getElementById('queue-container');
        const queueList = document.getElementById('queue-list');
        const queueLength = document.getElementById('queue-length');
        const totalWaitTime = document.getElementById('total-wait-time');
        
        if (queueLength) {
            queueLength.textContent = queueData.queue_length || 0;
        }
        
        if (totalWaitTime && queueData.estimated_total_wait_time > 0) {
            const waitTime = this.formatETA(queueData.estimated_total_wait_time);
            totalWaitTime.textContent = `总等待时间: ${waitTime}`;
        }
        
        if (queueList && queueData.queue_files) {
            queueList.innerHTML = '';
            queueData.queue_files.forEach((filename, index) => {
                const item = document.createElement('div');
                item.className = 'queue-item';
                item.innerHTML = `
                    <span class="queue-position">${index + 1}.</span>
                    <span class="queue-filename">${filename}</span>
                `;
                queueList.appendChild(item);
            });
        }
    }
    
    formatETA(seconds) {
        if (seconds < 60) {
            return `${Math.ceil(seconds)}秒`;
        } else if (seconds < 3600) {
            return `${Math.ceil(seconds / 60)}分钟`;
        } else {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.ceil((seconds % 3600) / 60);
            return `${hours}小时${minutes}分钟`;
        }
    }
    
    // 便捷的订阅方法
    subscribeToProgress(callback) {
        this.on('progress_update', callback);
    }
    
    subscribeToQueue(callback) {
        this.on('queue_update', callback);
    }
    
    subscribeToConnection(callback) {
        this.on('connection_change', callback);
    }
}

// 全局实例
window.progressClient = new ProgressWebSocketClient();

// Gradio集成
function initGradioIntegration() {
    // 确保在Gradio加载后执行
    const checkGradio = setInterval(() => {
        if (window.gradioApp) {
            clearInterval(checkGradio);
            setupGradioEventListeners();
        }
    }, 100);
}

function setupGradioEventListeners() {
    // 监听进度更新
    window.progressClient.subscribeToProgress((data) => {
        updateGradioProgress(data.data);
    });
    
    // 监听队列更新
    window.progressClient.subscribeToQueue((data) => {
        updateGradioQueue(data.data);
    });
    
    // 监听连接状态
    window.progressClient.subscribeToConnection((data) => {
        updateConnectionStatus(data.connected);
    });
}

function updateGradioProgress(progressData) {
    // 更新Gradio界面中的进度
    const progressElements = document.querySelectorAll('[data-testid="progress"]');
    progressElements.forEach(element => {
        if (element.textContent.includes('正在翻译')) {
            const percent = Math.round(progressData.progress * 100);
            element.textContent = `正在翻译: ${percent}%`;
        }
    });
}

function updateGradioQueue(queueData) {
    // 更新Gradio队列显示
    const queueDisplay = document.querySelector('.queue-display');
    if (queueDisplay) {
        queueDisplay.innerHTML = formatQueueDisplay(queueData);
    }
}

function updateConnectionStatus(connected) {
    const statusIndicator = document.getElementById('connection-status');
    if (statusIndicator) {
        statusIndicator.className = `connection-status ${connected ? 'connected' : 'disconnected'}`;
        statusIndicator.textContent = connected ? '实时更新已启用' : '连接断开，自动重连中...';
    }
}

function formatQueueDisplay(queueData) {
    const currentTask = window.progressManager?.current_task;
    const queueFiles = queueData.queue_files || [];
    
    let html = `
        <div class="queue-display">
            <div class="current-task">
                <h4>🔄 当前任务</h4>
                <div class="progress-container">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${(currentTask?.progress || 0) * 100}%"></div>
                    </div>
                    <div class="progress-text">
                        ${currentTask?.filename || '无任务'}
                        <small>${currentTask?.stage_description || ''}</small>
                    </div>
                </div>
            </div>
    `;
    
    if (queueFiles.length > 0) {
        html += `
            <div class="queue-list">
                <h4>⏰ 排队中 (${queueFiles.length}个文件)</h4>
                <ol>
                    ${queueFiles.map((file, index) => `
                        <li class="queue-item">
                            <span class="filename">${file}</span>
                            <span class="eta">预计等待: ${formatETA(queueData.estimated_total_wait_time / queueFiles.length * (index + 1))}</span>
                        </li>
                    `).join('')}
                </ol>
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

// 初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initGradioIntegration);
} else {
    initGradioIntegration();
}

// 导出API供外部使用
window.WebSocketAPI = {
    client: window.progressClient,
    formatETA: window.progressClient.formatETA,
    initGradioIntegration
};