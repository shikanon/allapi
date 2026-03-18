# API中转售卖系统 - 接口说明

本系统对外提供“视频生成任务”三类接口的统一中转，同时完成：用户Token鉴权、余额校验、扣费与消耗记录。

## 1. 鉴权

- Header：`Authorization: Bearer <用户Token>`
- 也支持：`X-User-Token: <用户Token>`

当 Token 无效或用户被禁用时返回 `401`。

### 1.1 如何生成用户Token

方式A（推荐）：创建用户脚本

```bash
python3 scripts/create_user.py --balance_rmb 1000
```

输出内容即为用户Token，调用接口时作为 `Authorization: Bearer <用户Token>`。

也可手动指定：

```bash
python3 scripts/create_user.py --token user_001 --balance_rmb 1000
```

方式B：Demo脚本（会额外写入一条默认模型映射）

```bash
python3 scripts/seed_demo.py
```

## 2. 余额与计费

- 余额单位：人民币（RMB）
- 扣费基准：上游返回 `usage.total_tokens`（系统按配置折算为人民币并扣减余额，同时记录 tokens 与人民币）

余额不足返回 `402`。

系统会将每次请求的扣费结果写入数据库表 `consumption_records`，同时在 `logs/app.log` 记录运行日志。

### 2.0 视频任务计费规则（按 task_id 一次性计费）

- 创建任务（`POST /v1/video/tasks`）：不扣费（只创建任务并记录）。
- 查询任务（`GET /v1/video/tasks/{task_id}`）：当且仅当满足以下条件时触发扣费：
  - 上游返回 `status = succeeded`
  - 返回体包含 `content.video_url`
  - 返回体包含 `usage.total_tokens` 且 > 0

满足条件时按该 `task_id` **只扣费一次**（重复查询不会重复扣费）。扣费金额为 `usage.total_tokens` 按配置折算后的人民币；若余额不足会返回 `402`。

取消任务（`POST /v1/video/tasks/{task_id}/cancel`）：不扣费（仅转发与记录）。

### 2.2 一键生成并实时推送（WebSocket）

如果希望通过 WebSocket 实现一键生成并实时接收状态更新（排队、生成中、成功/失败），可使用：

`WS /v1/video/tasks/ws`

#### 协议流程：
1. **连接建立**：客户端发起 WebSocket 连接。
2. **发送参数**：连接成功后，客户端发送第一个 JSON 消息，包含 `token` 和任务参数 `payload`。
3. **状态推送**：服务端在任务执行过程中推送 `type: "status"` 消息。
4. **结果返回**：任务成功产出后，服务端推送 `type: "result"` 消息并关闭连接。
5. **错误处理**：发生错误或超时，服务端推送 `type: "error"` 消息并关闭连接。

#### 消息格式：

**客户端发送 (Initial Message):**
```json
{
  "token": "你的用户Token",
  "payload": {
    "model": "next-light",
    "content": [...],
    "poll_interval_seconds": 2,
    "timeout_seconds": 300
  }
}
```

**服务端推送 (Status Update):**
```json
{
  "type": "status",
  "status": "creating",
  "message": "正在创建视频生成任务..."
}
```

**服务端推送 (Final Result):**
```json
{
  "type": "result",
  "data": {
    "id": "cgt-xxx",
    "status": "succeeded",
    "content": { "video_url": "..." },
    "usage": { "total_tokens": 108900 }
  }
}
```

**服务端推送 (Error):**
```json
{
  "type": "error",
  "message": "等待任务结果超时",
  "detail": { ... }
}
```

### 2.3 一键生成并同步返回（HTTP 轮询）

`POST /v1/video/tasks:generate`

请求体与 `POST /v1/video/tasks` 基本一致，额外支持：

- `poll_interval_seconds`：轮询间隔秒数（默认 2，范围 0.2~10）
- `timeout_seconds`：最大等待秒数（默认 300，范围 1~1800）

该接口会在任务成功产出后完成扣费，并返回最终任务查询响应；超时返回 `504`。

### 2.1 RMB 计费（用于核算/测试）

如果需要按上游返回的 `usage.total_tokens` 折算人民币，可使用：

`POST /v1/billing/quote`

计费单价（默认）：

- 含视频输入：28 元 / 100万 tokens
- 不含视频输入：46 元 / 100万 tokens

单价配置位置：`config.yaml -> pricing.money`，或环境变量覆盖：

- `BILLING_RMB_PER_MILLION_WITH_VIDEO_INPUT`
- `BILLING_RMB_PER_MILLION_WITHOUT_VIDEO_INPUT`

示例（直接给 total_tokens 与是否含视频输入）：

```bash
curl -X POST http://localhost:8001/v1/billing/quote \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <用户Token>' \
  -d '{"total_tokens":108900,"has_video_input":true}'
```

也支持传入包含 `content` 的请求体，不显式传 `has_video_input` 时会自动判断是否存在 `type=video_url` 或 `role=reference_video`。

### 2.4 接口测试示例 (Python)

你可以使用以下脚本快速验证“一键生成”接口及其计费逻辑：

```python
import requests
import json
import time

# 替换为你的 Token 和后端地址
TOKEN = "your_token"
BASE_URL = "http://127.0.0.1:8001"

def test_generate():
    url = f"{BASE_URL}/v1/video/tasks:generate"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    payload = {
        "model": "next-light",
        "content": [{"type": "text", "text": "测试一键生成"}],
        "timeout_seconds": 60
    }
    
    print("[*] 正在请求一键生成...")
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code == 200:
        data = resp.json()
        task_id = data.get("id")
        print(f"[+] 任务成功: {task_id}")
        # 校验返回体中的 Token
        print(f"    - 上游返回 Token: {data.get('usage', {}).get('total_tokens')}")
        
        # 延迟 1s 等待计费落库
        time.sleep(1)
        
        # 校验费用记录
        usage_resp = requests.get(f"{BASE_URL}/v1/usage", headers=headers)
        records = usage_resp.json().get("items", [])
        # 找到对应 task_id 的扣费记录 (video.charge)
        record = next((r for r in records if r.get("task_id") == task_id and r.get("endpoint") == "video.charge"), None)
        
        if record:
            print(f"[√] 费用记录已生成:")
            print(f"    - 扣费 Token: {record.get('tokens_charged')}")
            print(f"    - 扣费金额: {record.get('amount_rmb')} 元")
            print(f"    - 扣后余额: {record.get('balance_after')} 元")
        else:
            print("[!] 未找到扣费记录")
    else:
        print(f"[!] 请求失败: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    test_generate()
```

### 3.1 model 映射

用户侧提交的 `model` 会按以下优先级映射为上游 `model`：

1. 数据库表 `model_mappings`（`public_name -> upstream_model`）
2. 配置 `config.yaml`：`upstream.model_mapping`
3. 若都不存在映射，则透传原值

### 3.2 api_key 映射

用户可以在请求中携带 `api_key`（仅作为“别名Key”，不会透传给上游 body），系统将其映射为上游 `Authorization: Bearer <token>`：

1. 数据库表 `api_key_mappings`（`public_key -> upstream_bearer_token`）
2. 配置 `config.yaml`：`upstream.api_key_mapping`
3. 若都不存在，则使用 `upstream.default_bearer_token`

## 3.3 配置位置与环境变量覆盖

默认从 `config.yaml` 读取配置（可用环境变量 `CONFIG_PATH` 指定路径）。同时支持环境变量覆盖（优先级更高）：

- `DATABASE_URL`
- `UPSTREAM_BASE_URL`
- `UPSTREAM_TIMEOUT_SECONDS`
- `UPSTREAM_DEFAULT_BEARER_TOKEN`
- `UPSTREAM_API_KEY_MAPPING`
- `UPSTREAM_MODEL_MAPPING`
- `LOG_LEVEL` (设置为 `DEBUG` 可查看详细请求日志)

其中 `UPSTREAM_API_KEY_MAPPING` / `UPSTREAM_MODEL_MAPPING` 支持两种格式：

1) JSON：`{"next-light":"doubao-seedance-2-0-260128"}`

2) k=v 列表：`next-light=doubao-seedance-2-0-260128,foo=bar`

## 4. 接口

上游默认基址：`<UPSTREAM_BASE_URL>`，路径按上游 `api/v3` 规则转发（可通过 `config.yaml` 或 `UPSTREAM_BASE_URL` 配置）。

### 4.1 创建视频生成任务

`POST /v1/video/tasks`

请求体：保持与上游一致，额外支持字段 `api_key` 用于选择上游 Bearer。

示例：

```bash
curl -X POST http://localhost:8001/v1/video/tasks \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <用户Token>' \
  -d '{
    "api_key": "demo-key",
    "model": "next-light",
    "content": [{"type":"text","text":"hello"}],
    "duration": 5,
    "ratio": "16:9",
    "watermark": false
  }'
```

返回：透传上游响应（通常包含 `id`）。

### 4.2 查询任务结果

`GET /v1/video/tasks/{task_id}`

可选 query：`api_key=<别名Key>`

示例：

```bash
curl -X GET 'http://localhost:8001/v1/video/tasks/cgt-xxx?api_key=demo-key' \
  -H 'Authorization: Bearer <用户Token>'
```

返回：透传上游响应。

### 4.3 取消任务

`POST /v1/video/tasks/{task_id}/cancel`

也支持别名路径：`POST /v1/video/tasks/{task_id}:cancel`

请求体可选：`{"api_key":"demo-key"}`

示例：

```bash
curl -X POST http://localhost:8001/v1/video/tasks/cgt-xxx/cancel \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <用户Token>' \
  -d '{"api_key":"demo-key"}'
```

返回：透传上游响应。

### 4.4 查询消耗记录

`GET /v1/usage`

默认仅返回“已计费记录”（按 `task_id` 唯一、在查询结果成功后计费）。

参数：

- `limit`：默认 50，最大 200
- `offset`：默认 0
- `charged_only`：是否仅返回计费记录，默认 `true`

示例：

```bash
curl -X GET 'http://localhost:8001/v1/usage?limit=20&offset=0' \
  -H 'Authorization: Bearer <用户Token>'
```

返回：当前用户的扣费与请求结果列表。

### 4.5 健康检查

`GET /healthz`

## 5. 本地运行

1. 安装依赖：`pip install -r requirements.txt`
2. 复制配置：`cp config.example.yaml config.yaml` 并填写 `upstream.default_bearer_token`
3. 初始化一个 demo 用户：`python scripts/seed_demo.py`
4. 启动服务：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 6. Debug 日志（排查映射/漏参）

后端支持以 debug 级别输出：用户入站完整请求、映射后的上游转发请求（用于核对 model 映射、参数是否遗漏）。

- 启动方式：

```bash
LOG_LEVEL=DEBUG python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

- 日志文件：`logs/app.log`
- 安全：`Authorization`、`X-User-Token` 以及 body 中的 `api_key/token` 字段会做脱敏（不会输出完整密钥）。
- 如需排查鉴权问题并输出明文（强烈建议仅本地/内网临时开启）：

```bash
LOG_LEVEL=DEBUG LOG_INCLUDE_SENSITIVE=1 python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

- 截断：可用 `LOG_BODY_MAX_CHARS` 控制非 JSON body 的最长输出字符数（默认 20000；设为 0 表示不截断）。
