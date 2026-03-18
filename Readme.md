# API 中转售卖系统（最小可运行版本）

本项目提供一个可运行的 API 中转与计费系统：接收下游请求，完成用户鉴权、余额校验、参数映射与转发，并在满足计费条件时扣费与记录用量。

## 功能概览

- 用户 Token 鉴权与余额管理
- 视频任务创建 / 查询 / 取消三类接口的中转
- `model` 映射与上游 Bearer Token 选择（按别名映射）
- 扣费记录落库与用量查询（`/v1/usage`）

## 快速开始

### 1) 启动后端

```bash
pip3 install -r requirements.txt
cp config.example.yaml config.yaml
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

**提示：开启 DEBUG 日志**
- 方法 A：修改 `config.yaml` 中 `app.log_level` 为 `DEBUG`。
- 方法 B：启动时增加环境变量 `LOG_LEVEL=DEBUG`，例如：
  `LOG_LEVEL=DEBUG python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8001`
- 方法 C：如需查看 uvicorn 框架本身的 debug 日志，请增加 `--log-level debug` 参数。

### 1.1) 创建用户（获取登录/调用用 Token）

创建一个用户并设置初始余额（单位：人民币），脚本会在 stdout 输出该用户 Token：

```bash
python3 scripts/create_user.py --balance_rmb 1000
```

也可以手动指定 Token（便于本地固定使用）。注意：`token` 字段全局唯一，重复创建会报错：

```bash
python3 scripts/create_user.py --token user_001 --balance_rmb 1000
```

### 2) 启动前端控制台

```bash
cd frontend
npm install
API_PROXY_TARGET=http://127.0.0.1:8001 npm run dev -- --host 127.0.0.1 --port 5173
```

- 控制台地址：`http://127.0.0.1:5173`
- 登录方式：输入 `create_user.py` 输出的用户 Token

## 配置说明（上游 / 下游）

上游三方凭证通过 `Authorization: Bearer <token>` 注入到上游请求中；仓库内不放真实 Key。

- 全局默认 Bearer：`config.yaml -> upstream.default_bearer_token`
- 按别名映射 Bearer：`config.yaml -> upstream.api_key_mapping`
  - 用户请求 body 或 query 中可带 `api_key`（仅作为别名 key，不会透传到上游 body）
- 模型映射：`config.yaml -> upstream.model_mapping`

也支持用环境变量覆盖（优先级高于 `config.yaml`），详见 `docs/API.md`。

## 计费规则（当前实现）

- 以 `task_id` 为唯一：仅当 `GET /v1/video/tasks/{task_id}` 返回 `status=succeeded` 且包含 `content.video_url` 与 `usage.total_tokens` 时，对该 `task_id` 扣费一次
- 用量记录：`GET /v1/usage` 默认仅返回已计费记录，并包含 `tokens_charged` 与 `amount_rmb`

## 文档

- 后端接口与调试：`docs/API.md`
- 前端控制台说明：`frontend/README.md`

## 安全提示

- 不要在仓库中提交真实的三方 API Key、用户 Token、数据库连接串等敏感信息
- 建议只在本地 `config.yaml` / `.env` 中配置上游信息（仓库已在 `.gitignore` 忽略 `config.yaml`、`.env*`、`logs/`、`data/` 等本地敏感/运行时文件）

## 需求背景（已打码）

为避免 README 暴露上游域名/示例资源地址等信息，原始需求与接口示例已迁移至：`docs/REQUIREMENTS_ORIGINAL.md`。
