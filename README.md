# DeepSeek 流式聊天 API
一个基于 **FastAPI** 的聊天接口，调用 **DeepSeek API**，支持 **SSE 流式返回**（打字机效果）。

## ✨ 功能

| 接口 | 方法 | 说明 |
|------|------|------|
| `/ping` | GET | 健康检查，返回 `{"msg":"pong"}` |
| `/chat` | POST | 发送消息，流式返回 DeepSeek 回复 |
| `/docs` | GET | FastAPI 自动生成的接口文档 |

## 📁 项目结构
    chat-api/
    ├── main.py              # FastAPI 后端：/chat 流式接口、/ping、/ 静态页面
    ├── index.html           # 前端聊天页面（fetch + ReadableStream 实现打字机效果）
    ├── requirements.txt     # Python 依赖清单
    ├── .gitignore          # 忽略 .venv、__pycache__、.env
    └── README.md           # 项目说明（本文件）

## 🔑 核心代码逻辑
    用户输入消息
        ↓
    POST /chat  (FastAPI 接收，Pydantic 校验)
        ↓
    httpx.AsyncClient 请求 DeepSeek API（stream=True）
        ↓
    async for 逐行读取 DeepSeek 返回的 SSE 数据
        ↓
    解析 delta.content → yield 出去
        ↓
    StreamingResponse 逐段推送给前端
        ↓
    浏览器 fetch + reader.read() 逐字渲染

## 📝 学习笔记
    这个项目练习并掌握了：
    venv — 虚拟环境的创建与激活，理解项目依赖隔离
    装饰器 — @app.get() / @app.post() 路由注册原理
    Pydantic BaseModel — 请求体类型校验，字段错误自动返回 422
    async / await — 异步编程，等待 DeepSeek 回复期间不阻塞其他请求
    httpx.AsyncClient — 异步 HTTP 客户端的使用
    SSE 流式响应 — 与普通 JSON 响应的区别：生成一点发一点，不等全部完成
    git / GitHub — 版本管理与代码托管
        "DeepSeek 最后一块 choices 为空 → choices[0] 抛 IndexError 被 except 吞 → 解法：usage 和取 delta 拆开、精确捕获"
        "requirements.txt 中文注释 → GBK 解码炸 → 配置文件保持纯 ASCII"

## 🛠 技术栈
- **FastAPI** — Web 框架
- **uvicorn** — ASGI 服务器
- **httpx** — 异步 HTTP 客户端，调用 DeepSeek API
- **Pydantic** — 请求体校验
- **SSE (Server-Sent Events)** — 流式响应
- **DeepSeek API** — 大模型对话（`deepseek-chat`，`stream=True`）

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/GoldMilk37/chat-api.git
cd chat-api

    ## 2. 创建并激活虚拟环境
    bash
    python -m venv .venv
    Windows：

    bash
    .venv\Scripts\activate
    Mac / Linux：

    bash
    source .venv/bin/activate
    ##3. 安装依赖
    bash
    pip install -r requirements.txt
    ##4. 设置 DeepSeek API Key
    先去 platform.deepseek.com 注册并创建 API Key。

    Windows PowerShell：

    powershell
    $env:DEEPSEEK_API_KEY="sk-你的key"
    Windows CMD：

    cmd
    set DEEPSEEK_API_KEY=sk-你的key
    Mac / Linux：

    bash
    export DEEPSEEK_API_KEY="sk-你的key"
    ##5. 启动服务
    bash
    uvicorn main:app --reload

        📡 API 说明
        POST /chat
        请求体：

        json
        {
        "message": "写一首关于秋天的短诗"
        }
        响应： text/event-stream 流式输出，逐字返回 DeepSeek 的回复。

        curl 测试：

        bash
        curl -X POST http://127.0.0.1:8000/chat \
        -H "Content-Type: application/json" \
        -d '{"message": "你好"}'

    