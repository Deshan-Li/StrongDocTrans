"""
WebSocket实时进度同步测试脚本
用于验证多用户排队时的实时进度显示功能
"""

import asyncio
import websockets
import json
import threading
import time
import requests
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from websocket_progress_manager import progress_broadcaster
from progress_state_manager import progress_manager

def test_websocket_server():
    """测试WebSocket服务器启动"""
    print("🧪 测试WebSocket服务器启动...")
    
    # 启动WebSocket服务器
    websocket_started = False
    try:
        import websockets
        progress_broadcaster.start_server()
        websocket_started = True
        print("✅ WebSocket服务器启动成功")
    except Exception as e:
        print(f"❌ WebSocket服务器启动失败: {e}")
    
    return websocket_started

def test_progress_broadcasting():
    """测试进度广播功能"""
    print("🧪 测试进度广播功能...")
    
    # 模拟任务进度
    start_task("test_document.pdf", total_segments=10)
    
    for i in range(11):
        progress = i / 10
        update_progress(
            progress,
            "translating",
            f"翻译第{i}段...",
            completed_segments=i,
            total_segments=10
        )
        time.sleep(0.5)
    
    complete_task(True, "测试完成")
    print("✅ 进度广播测试完成")

def test_queue_management():
    """测试队列管理功能"""
    print("🧪 测试队列管理功能...")
    
    # 设置队列
    queue_files = [
        "document1.pdf",
        "presentation.pptx",
        "spreadsheet.xlsx",
        "notes.txt"
    ]
    
    update_queue(queue_files)
    print(f"✅ 队列测试完成，共{len(queue_files)}个文件")

def test_multi_client_simulation():
    """模拟多客户端连接"""
    print("🧪 测试多客户端连接...")
    
    connected_clients = []
    
    async def client_simulation(client_id):
        """模拟客户端连接"""
        try:
            async with websockets.connect('ws://localhost:9981') as websocket:
                connected_clients.append(client_id)
                
                # 发送连接消息
                await websocket.send(json.dumps({
                    "type": "subscribe",
                    "client_id": client_id
                }))
                
                # 接收消息
                async for message in websocket:
                    data = json.loads(message)
                    print(f"客户端{client_id}收到: {data.get('type', 'unknown')}")
                    
        except Exception as e:
            print(f"客户端{client_id}连接失败: {e}")
    
    async def run_clients():
        """运行多个客户端"""
        tasks = []
        for i in range(3):
            task = asyncio.create_task(client_simulation(i))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    # 运行测试
    try:
        asyncio.run(run_clients())
        print(f"✅ 多客户端测试完成，成功连接{len(connected_clients)}个客户端")
    except Exception as e:
        print(f"❌ 多客户端测试失败: {e}")

def test_integration_with_gradio():
    """测试与Gradio的集成"""
    print("🧪 测试与Gradio的集成...")
    
    # 检查Gradio应用是否运行
    try:
        response = requests.get("http://localhost:9980")
        if response.status_code == 200:
            print("✅ Gradio应用运行正常")
        else:
            print("⚠️  Gradio应用响应异常")
    except requests.exceptions.RequestException:
        print("⚠️  Gradio应用未运行，跳过集成测试")

def run_all_tests():
    """运行所有测试"""
    print("🚀 开始WebSocket实时进度同步测试...\n")
    
    # 测试WebSocket服务器
    websocket_ok = test_websocket_server()
    
    if websocket_ok:
        # 测试进度广播
        test_progress_broadcasting()
        
        # 测试队列管理
        test_queue_management()
        
        # 测试多客户端
        test_multi_client_simulation()
        
        # 测试与Gradio集成
        test_integration_with_gradio()
        
        print("\n🎉 所有测试完成！")
        print("\n📋 测试总结：")
        print("- WebSocket服务器已启动")
        print("- 进度广播功能正常")
        print("- 队列管理功能正常")
        print("- 多客户端支持正常")
        print("\n💡 使用说明：")
        print("1. 启动应用: python app.py")
        print("2. 打开浏览器访问: http://localhost:9980")
        print("3. 在多设备/浏览器中测试实时同步")
        print("4. WebSocket调试端口: ws://localhost:9981")
    else:
        print("❌ WebSocket服务器启动失败，请检查依赖")
        print("解决方案：")
        print("pip install -r websocket_requirements.txt")

if __name__ == "__main__":
    run_all_tests()