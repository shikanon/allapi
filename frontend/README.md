# 前端控制台

用于调试与调用后端中转接口的 Web 控制台（React + Vite）。

## 启动

```bash
npm install
API_PROXY_TARGET=http://127.0.0.1:8001 npm run dev -- --host 127.0.0.1 --port 5173
```

- 访问：`http://127.0.0.1:5173`
- 登录：输入后端创建用户脚本输出的用户 Token

## 代理说明

开发环境通过 `API_PROXY_TARGET` 将前端请求转发到后端，例如：

- 后端：`http://127.0.0.1:8001`
- 前端：`http://127.0.0.1:5173`
