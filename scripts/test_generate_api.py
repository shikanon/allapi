import json
import time
import requests
import websocket
import subprocess
import os

# 配置
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8001")
WS_URL = BASE_URL.replace("http://", "ws://") + "/v1/video/tasks/ws"

def get_token():
    """创建一个新用户并返回 Token"""
    try:
        # 使用 create_user.py 脚本
        res = subprocess.run(
            ["python3", "scripts/create_user.py", "--balance_rmb", "1000"],
            capture_output=True, text=True, check=True
        )
        token = res.stdout.strip().split("\n")[-1]
        print(f"[*] 创建测试用户成功, Token: {token}")
        return token
    except Exception as e:
        print(f"[!] 创建用户失败: {e}")
        return None

def test_http_generate(token):
    """测试 HTTP :generate 接口"""
    print("\n--- 测试 HTTP :generate ---")
    url = f"{BASE_URL}/v1/video/tasks:generate"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "model": "next-light",
        "content": [{"type": "text", "text": "测试 HTTP 一键生成"}],
        "timeout_seconds": 30,
        "poll_interval_seconds": 1
    }
    
    start = time.time()
    resp = requests.post(url, headers=headers, json=payload)
    duration = time.time() - start
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"[+] 响应成功 ({duration:.2f}s)")
        print(f"    - Task ID: {data.get('id')}")
        print(f"    - Status: {data.get('status')}")
        print(f"    - Video URL: {data.get('content', {}).get('video_url')}")
        
        # 检查 Token
        total_tokens = data.get('usage', {}).get('total_tokens')
        print(f"    - Total Tokens (from response): {total_tokens}")
        
        if not total_tokens:
            print("[!] 响应体中未包含 total_tokens")
        
        # 验证计费记录
        check_usage(token, data.get('id'))
    else:
        print(f"[!] 响应失败: {resp.status_code}")
        print(f"    - Detail: {resp.text}")

def test_ws_generate(token):
    """测试 WebSocket /ws 接口"""
    print("\n--- 测试 WebSocket /ws ---")
    
    ws = websocket.create_connection(WS_URL)
    try:
        # 发送初始消息
        initial_msg = {
            "token": token,
            "payload": {
                "model": "next-light",
                "content": [{"type": "text", "text": "测试 WS 一键生成"}],
                "timeout_seconds": 30,
                "poll_interval_seconds": 1
            }
        }
        ws.send(json.dumps(initial_msg))
        
        task_id = None
        while True:
            result = ws.recv()
            data = json.loads(result)
            msg_type = data.get("type")
            
            if msg_type == "status":
                print(f"[*] 状态推送: {data.get('status')} - {data.get('message')}")
                if data.get("task_id"):
                    task_id = data.get("task_id")
            elif msg_type == "result":
                print(f"[+] 结果返回: {data.get('data', {}).get('status')}")
                print(f"    - Video URL: {data.get('data', {}).get('content', {}).get('video_url')}")
                print(f"    - Total Tokens: {data.get('data', {}).get('usage', {}).get('total_tokens')}")
                
                if task_id:
                    check_usage(token, task_id)
                break
            elif msg_type == "error":
                print(f"[!] 错误推送: {data.get('message')}")
                break
    finally:
        ws.close()

def check_usage(token, task_id):
    """检查 /v1/usage 记录"""
    print(f"[*] 正在验证计费记录 (Task ID: {task_id})...")
    url = f"{BASE_URL}/v1/usage"
    headers = {"Authorization": f"Bearer {token}"}
    
    # 稍微等一秒确保 DB 写入完成
    time.sleep(1)
    
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        records = resp.json().get("items", [])
        # 找到对应 task_id 的 video.charge 记录
        charge_record = next((r for r in records if r.get("task_id") == task_id and r.get("endpoint") == "video.charge"), None)
        
        if charge_record:
            print(f"[√] 计费记录验证成功:")
            print(f"    - Tokens Charged: {charge_record.get('tokens_charged')}")
            print(f"    - Amount RMB: {charge_record.get('amount_rmb')} 元")
            print(f"    - Balance After: {charge_record.get('balance_after')} 元")
        else:
            print(f"[!] 未找到该任务的计费记录 (video.charge)")
    else:
        print(f"[!] 获取计费记录失败: {resp.status_code}")

if __name__ == "__main__":
    token = get_token()
    if token:
        # 你需要先确保后端已启动并监听 8001 端口
        # 以及 Mock Upstream 已启动并监听 9000 端口
        test_http_generate(token)
        test_ws_generate(token)
