# 需求原文（已打码）

本文件用于保留需求背景与接口示例，但已将可能暴露环境/供应商信息的内容替换为占位符。

## 二、核心目标

1. 实现 API 接口的中转售卖，通过用户请求计费实现商业变现；
2. 完成用户请求参数与目标 API 参数的适配（APIKey、model 名称映射），保障中转请求正常响应；
3. 建立用户余额管理机制，确保请求前余额校验、请求后消耗扣减与记录的准确性；
4. 支持视频类相关三类接口的稳定中转，保障接口响应效率与数据一致性。

## 三、核心功能需求

### 3.1 用户认证与余额管理

1. 用户 Token 校验：用户发起 API 请求时，需携带专属 Token，系统通过 Token 查询用户表，验证用户合法性及当前可用余额；
2. 余额校验规则：请求发起前，系统需判断用户余额是否满足本次请求的费用消耗，若余额不足，直接返回“余额不足”提示，拒绝转发请求；若余额充足，执行后续中转流程；
3. 余额扣减与记录：请求转发至目标 API 并获取有效响应后，系统根据预设计费规则计算本次请求消耗的 Token 数量，自动从用户余额中扣减对应额度；同时生成消耗记录，留存关键信息供后续查询。

### 3.2 API 中转与参数转换

1. 参数映射配置：系统支持预设参数映射规则，实现用户请求中的 APIKey、model 名称与目标 API 参数的映射转换；
2. 请求转发机制：通过 Token 校验和余额校验后，系统完成参数转换并转发至目标 API；
3. 响应转发机制：目标 API 返回响应结果后，系统直接将响应转发给用户（除必要日志记录外）。

### 3.3 视频类接口中转（具体接口需求）

#### 3.3.1 视频任务生成接口

1. 接口功能：接收用户发起的视频生成任务请求，完成参数转换、余额校验后，转发至目标视频生成接口并返回结果；
2. 参数映射：支持用户请求携带的自定义 APIKey、model 名称映射；
3. 计费规则：按任务复杂度预设固定或动态 Token 消耗标准。

#### 3.3.2 视频生成任务结果查询接口

1. 接口功能：接收用户发起的视频任务结果查询请求，完成参数转换后转发至目标查询接口，返回任务结果；
2. 参数映射：确保任务 ID、APIKey 等正确映射；
3. 计费规则：可固定或按频率/复杂度动态计费。

#### 3.3.3 视频生成任务取消接口

1. 接口功能：接收用户发起的视频任务取消请求，完成参数转换后转发至目标取消接口，返回取消结果；
2. 参数映射：确保任务 ID、APIKey 等正确映射；
3. 计费规则：按取消结果执行扣费（示例：成功扣费、失败不扣费）。

### 3.4 消耗记录管理

1. 记录内容：包含用户 ID、请求接口类型、请求时间、消耗 Token 数量、剩余余额、请求状态等关键信息；
2. 记录留存：消耗记录长期留存并可查询；
3. 数据一致性：确保消耗记录与余额扣减同步，异常需有补扣/回滚机制。

## 接口示例（占位符）

下述示例仅用于展示格式，所有上游地址、资源 URL、Key 均为占位符：

### 创建上游视频生成任务（示例）

```bash
curl -X POST '<UPSTREAM_BASE_URL>/api/v3/contents/generations/tasks' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <UPSTREAM_API_KEY>' \
  -d '{
    "model": "<UPSTREAM_MODEL_ID>",
    "content": [
      {"type":"text","text":"<PROMPT_TEXT>"},
      {"type":"image_url","image_url":{"url":"https://example.com/ref1.jpg"},"role":"reference_image"}
    ],
    "ratio": "16:9",
    "duration": 5,
    "watermark": false
  }'
```

### 查询上游任务结果（示例）

```bash
curl -X GET '<UPSTREAM_BASE_URL>/api/v3/contents/generations/tasks/<TASK_ID>' \
  -H 'Authorization: Bearer <UPSTREAM_API_KEY>'
```

### 上游返回结构（示例）

```json
{
  "id": "cgt-xxxxxxxxxxxx",
  "model": "<UPSTREAM_MODEL_ID>",
  "status": "succeeded",
  "content": {"video_url": "https://example.com/video.mp4"},
  "usage": {"completion_tokens": 108900, "total_tokens": 108900},
  "created_at": 1700000000,
  "updated_at": 1700000001
}
```
