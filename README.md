# DeepSeek 流式聊天 API
一个基于 **FastAPI** 的聊天接口，调用 **DeepSeek API**，支持 **SSE 流式返回**（打字机效果）、**多轮会话**、**结构化输出** 和 **Function Calling**（工具调用）。

## ✨ 功能

| 接口 | 方法 | 说明 |
|------|------|------|
| `/ping` | GET | 健康检查，返回 `{"msg":"pong"}` |
| `/chat` | POST | 发送消息，流式返回 DeepSeek 回复；支持 `session_id` 多轮会话 |
| `/analyze` | POST | 情感分析，返回经过 Pydantic 校验的结构化 JSON |
| `/chat-with-tools` | POST | 支持 Function Calling 的聊天，模型可调用计算器/天气工具 |
| `/sessions` | GET | 调试接口，查看内存中所有会话记录 |
| `/docs` | GET | FastAPI 自动生成的接口文档 |

## 📁 项目结构
    chat-api/
    ├── main.py              # FastAPI 后端：/chat 流式、/analyze 结构化、/chat-with-tools 工具调用
    ├── tools.py             # 工具定义与执行器：calculator（ast 安全求值）、get_weather（模拟数据）
    ├── Dockerfile           # Docker 容器化配置
    ├── requirements.txt     # Python 依赖清单
    ├── .env                 # 存 DEEPSEEK_API_KEY（不进 Git）
    ├── .gitignore           # 忽略 .venv、__pycache__、.env
    └── README.md            # 项目说明（本文件）

## 🔑 核心代码逻辑

### /chat 流式对话
    用户输入消息
        ↓
    POST /chat  (FastAPI 接收，Pydantic 校验；没传 session_id 就 uuid4 生成)
        ↓
    httpx.AsyncClient 请求 DeepSeek API（stream=True）
        ↓
    async for 逐行读取 DeepSeek 返回的 SSE 数据
        ↓
    解析 delta.content → yield 出去
        ↓
    StreamingResponse 逐段推送给前端
        ↓
    流结束后把本轮问答存入 sessions，session_id 放在响应头 X-Session-ID 返回

### /analyze 结构化输出
    Pydantic 模型 (SentimentResult) --model_json_schema()--> JSON Schema
        ↓
    build_structured_prompt: System Prompt + Schema + 硬性规则 拼成完整提示词
        ↓
    DeepSeek 非流式请求（stream=False，要完整 JSON）
        ↓
    clean_json_response 清洗（剥掉模型包的 ```markdown 代码块）
        ↓
    SentimentResult.model_validate_json 校验，不合规 → HTTP 502
        ↓
    返回 {result: {sentiment, confidence, keywords}, model}

### /chat-with-tools Function Calling
    第一次调用 DeepSeek（附带 tools_schema，tool_choice="auto"）
        ↓
    模型返回 tool_calls？（自己判断要不要用工具）
        ↓  是
    ToolExecutor 执行真正的 Python 函数（calculator / get_weather）
        ↓
    工具结果以 role="tool" 消息追加进对话历史
        ↓
    第二次调用 DeepSeek → 基于工具结果生成最终回答
        ↓
    （不需要工具时直接返回普通回复）

## 📝 学习笔记
    这个项目练习并掌握了：
    venv — 虚拟环境的创建与激活，理解项目依赖隔离
    装饰器 — @app.get() / @app.post() 路由注册原理
    Pydantic BaseModel — 请求体类型校验，字段错误自动返回 422
    async / await — 异步编程，等待 DeepSeek 回复期间不阻塞其他请求
    httpx.AsyncClient — 异步 HTTP 客户端的使用
    SSE 流式响应 — 与普通 JSON 响应的区别：生成一点发一点，不等全部完成
    git / GitHub — 版本管理与代码托管
    dotenv — 用 .env 文件管理密钥，避免把 key 写死在代码里
        "DeepSeek 最后一块 choices 为空 → choices[0] 抛 IndexError 被 except 吞 → 解法：usage 和取 delta 拆开、精确捕获"
        "requirements.txt 中文注释 → GBK 解码炸 → 配置文件保持纯 ASCII"
        "/chat 一直 500 → 取 choices 前没检查 HTTP 状态码 → debug 脚本直连 API 看原始回复定位 401；教训=先看状态码再取字段"
        "设了 DEEPSEEK_API_KEY 读不到 → 环境变量按终端窗口隔离，关窗口即失 → .env + load_dotenv() 一劳永逸"

    流式输出的一行chunk（数据块）
                    └── choices（选择数组，通常1个）
                    ├── index（索引：0, 1, 2...）
                    └── delta（增量内容）
                        ├── role（角色，通常只在第一块）
                        └── content（文本片段）

    Pydantic Schema 就是使用 Pydantic 的 BaseModel 定义的数据模型，它提供了：
        ✅ 类型检查
        ✅ 数据验证
        ✅ 自动转换（如字符串 "123" 转为整数 123）
        ✅ JSON 序列化
        ✅ 文档生成
        在 FastAPI 等现代 Python Web 框架中，Schema 是定义 API 接口数据格式的标准方式。

    Function Calling 的两段式：
        第一问："这是工具清单，用户问题是你来答还是要用工具？" → 模型返回 tool_calls 或普通回答
        执行：服务端跑真函数，结果包装成 {"result": ...}
        第二问：把工具结果塞回 messages（role="tool"）→ 模型基于真实数据组织最终回答
        要点：模型只会"决定调用"，从不真正执行——执行永远在服务端手里。

    calculator 为什么用 ast 而不是 eval()？
        eval() 会执行任意代码，模型传来的字符串不可信；
        ast.parse(mode='eval') 只解析成语法树，白名单里只有四则运算节点，其他一律拒绝。

## 🛠 技术栈
- **FastAPI** — Web 框架
- **uvicorn** — ASGI 服务器
- **httpx** — 异步 HTTP 客户端，调用 DeepSeek API
- **Pydantic** — 请求体校验 + 结构化输出 Schema
- **SSE (Server-Sent Events)** — 流式响应
- **Function Calling** — 工具调用（calculator / get_weather）
- **python-dotenv** — 从 .env 加载环境变量
- **Docker** — 容器化部署
- **DeepSeek API** — 大模型对话（`deepseek-chat`，`stream=True`）
