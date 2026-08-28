import os  # 读取环境变量
import json
import uuid  # 新增：生成 session_id
import httpx  # type: ignore  # HTTP 客户端，用来发请求给 DeepSeek
from fastapi import FastAPI, HTTPException  # type: ignore # 新增：HTTPException 用于返回明确错误
from fastapi.responses import StreamingResponse  # type: ignore
from pydantic import BaseModel, Field, ValidationError  # type: ignore # 新增：Field 定义字段约束，ValidationError 捕获验证失败
from typing import Literal, List, Optional  # 新增：类型注解
from dotenv import load_dotenv  # type: ignore # 从 .env 文件读取变量
# 在 main.py 中导入
from tools import tools_schema, ToolExecutor

# 然后在你的接口中使用

load_dotenv()  # 启动时把 .env 里的 DEEPSEEK_API_KEY 加载进环境变量

app = FastAPI()


# ============================================================
# ① 请求/响应的数据模型（Schemas）
# ============================================================

class ChatRequest(BaseModel):  # 定义 /chat 请求体的"形状"
    message: str = Field(description="用户输入的消息", min_length=1)  # 修改：加了 Field 约束，最短 1 个字符
    session_id: Optional[str] = Field(default=None, description="会话ID，用于多轮对话")  # 新增：可选会话ID


class ChatResponse(BaseModel):  # 新增：/chat 非流式响应用（备用）
    reply: str = Field(description="助手的回复内容")  # 新增
    session_id: str = Field(description="会话ID")  # 新增


class AnalyzeRequest(BaseModel):  # 新增：/analyze 请求体
    text: str = Field(description="待分析情感的文本", min_length=1)  # 新增


class SentimentResult(BaseModel):  # 新增：情感分析结构化结果
    sentiment: Literal["positive", "negative", "neutral"] = Field(  # 新增
        description="情感倾向：positive=积极, negative=消极, neutral=中立"  # 新增
    )  # 新增
    confidence: float = Field(  # 新增
        description="置信度，范围 0.0 到 1.0",  # 新增
        ge=0.0,  # 新增：大于等于 0
        le=1.0   # 新增：小于等于 1
    )  # 新增
    keywords: List[str] = Field(  # 新增
        description="支撑判断的关键词，1-5个",  # 新增
        min_length=1,  # 新增
        max_length=5   # 新增
    )  # 新增


class AnalyzeResponse(BaseModel):  # 新增：/analyze 响应体
    result: SentimentResult = Field(description="结构化分析结果")  # 新增
    model: str = Field(description="使用的模型名称")  # 新增


# ============ 新增：Function Calling 请求模型 ============
class FunctionCallRequest(BaseModel):
    message: str = Field(description="用户输入的消息", min_length=1)
    session_id: Optional[str] = Field(default=None, description="会话ID")


# ============================================================
# ② 会话存储（简单内存版，生产环境应换 Redis）
# ============================================================

sessions: dict = {}  # 新增：存多轮对话历史


# ============================================================
# ③ 原有接口：/ping
# ============================================================

@app.get("/ping")  # 装饰器，注册一个接口    "/ping" 是请求目录  “/” 是根目录
def ping():  # 定义一个函数从服务器拿数据（比如访问 /ping）
    return {"msg": "pong"}  # 接口返回的内容


# ============================================================
# ④ 原有接口：/chat（流式，保留原有逻辑 + 新增 session 记录）
# ============================================================

@app.post("/chat")  # POST 接口，路径 /chat  给服务器送数据（比如发聊天消息）
async def chat(req: ChatRequest):  # async def 异步函数；参数类型是 ChatRequest
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:  # 没配 key 时给个明白的提示，而不是悄悄 401
        return {"error": "没找到 DEEPSEEK_API_KEY：请在 Chat-API 目录下新建 .env 文件，写入一行 DEEPSEEK_API_KEY=sk-你的key"}

    session_id = req.session_id or str(uuid.uuid4())  # 新增：没传 session_id 就自动生成一个

    async def generate():
        full_reply = ""  # 新增：收集完整回复，流结束后存入 session

        async with httpx.AsyncClient(timeout=30) as client:  # timeout=30 防 DeepSeek 卡死导致接口一直挂着
            async with client.stream(
                "POST",
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "你是一个乐于助人的助手"},
                        {"role": "user", "content": req.message}],
                    "stream": True
                }
            ) as response:
                async for chunk in response.aiter_lines():
                    if chunk.startswith("data: "):
                        data = chunk[6:]
                        if data == "[DONE]":
                            break
                        try:
                            parsed = json.loads(data)
                        except json.JSONDecodeError:  # 只吞"不是 JSON"这一种，其他异常让它浮出来
                            continue

                        # 先独立处理 usage：DeepSeek 把用量放在"choices 为空"的最后一块里
                        if "usage" in parsed:
                            print(f"Token 用量: {parsed['usage']}")

                        # 再处理回答内容：最后一块的 choices 是空的，必须先进 if 判断
                        choices = parsed.get("choices")
                        if choices:
                            delta = choices[0].get("delta", {})
                            if "content" in delta:
                                full_reply += delta["content"]  # 新增：累积完整回复
                                yield delta["content"]  # yield：函数暂停，把当前值发出去，然后继续执行下一行

        # 新增：流结束后把本轮对话存入 session
        if session_id not in sessions:  # 新增
            sessions[session_id] = []  # 新增
        sessions[session_id].append({"user": req.message, "assistant": full_reply})  # 新增

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Session-ID": session_id}  # 新增：把 session_id 放在响应头返回给前端
    )


# ============================================================
# ⑤ 新增接口：/analyze（结构化输出）
# ============================================================

ANALYZE_SYSTEM_PROMPT = """  # 新增：情感分析的 System Prompt
你是一个专业的情感分析引擎。

分析用户输入的文本，判断其情感倾向。

判断标准：
- positive: 表达了积极、满意、开心、赞扬等正面情绪
- negative: 表达了消极、不满、愤怒、批评等负面情绪
- neutral: 客观陈述事实，或无明显情感倾向

keywords 字段要求：
- 提取文本中最能支撑你判断的关键词
- 数量 1-5 个
- 按重要性从高到低排列
"""  # 新增


def build_structured_prompt(system_prompt: str, schema: type[BaseModel]) -> str:  # 新增：把 Pydantic Schema 嵌入提示词
    """把 Pydantic Schema 嵌入提示词，生成完整的 System Prompt"""  # 新增
    schema_json = schema.model_json_schema()  # 新增：Pydantic 自动生成 JSON Schema
    schema_text = json.dumps(schema_json, ensure_ascii=False, indent=2)  # 新增：转成格式化字符串
    
    return f"""  # 新增
{system_prompt}  # 新增

【输出格式要求】  # 新增
你必须输出一个 JSON 对象，严格符合以下 JSON Schema：  # 新增

{schema_text}  # 新增

【硬性规则】  # 新增
- 只输出 JSON 对象，不要有任何解释性文字、前缀或后缀  # 新增
- 不要用 ```json 代码块包裹  # 新增
- 所有字段必须填写，不能省略  # 新增
- confidence 字段表示你对自己判断的把握程度  # 新增
"""  # 新增


def clean_json_response(text: str) -> str:  # 新增：清洗 LLM 输出
    """清洗 LLM 输出，去掉可能的 markdown 代码块包裹"""  # 新增
    text = text.strip()  # 新增
    if text.startswith("```"):  # 新增：如果以 ``` 开头
        lines = text.split("\n")  # 新增
        lines = [l for l in lines if not l.strip().startswith("```")]  # 新增：过滤掉代码块标记行
        text = "\n".join(lines)  # 新增
    return text.strip()  # 新增


@app.post("/analyze", response_model=AnalyzeResponse)  # 新增：POST 接口 /analyze
async def analyze(req: AnalyzeRequest):  # 新增
    """情感分析接口，返回 Pydantic 验证过的结构化结果"""  # 新增
    
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")  # 新增
    if not api_key:  # 新增
        raise HTTPException(status_code=500, detail="没找到 DEEPSEEK_API_KEY")  # 新增

    # 1. 构建嵌入了 Schema 的完整提示词
    full_prompt = build_structured_prompt(ANALYZE_SYSTEM_PROMPT, SentimentResult)  # 新增

    # 2. 调用 DeepSeek（非流式，因为我们要完整 JSON）
    async with httpx.AsyncClient(timeout=60) as client:  # 新增：timeout 给足 60 秒
        response = await client.post(  # 新增：非流式请求
            "https://api.deepseek.com/chat/completions",  # 新增
            headers={  # 新增
                "Authorization": f"Bearer {api_key}",  # 新增
                "Content-Type": "application/json"  # 新增
            },  # 新增
            json={  # 新增
                "model": "deepseek-chat",  # 新增
                "messages": [  # 新增
                    {"role": "system", "content": full_prompt},  # 新增
                    {"role": "user", "content": req.text}  # 新增
                ],  # 新增
                "stream": False  # 新增：关键！非流式，等完整结果
            }  # 新增
        )  # 新增

    if response.status_code != 200:  # 新增：DeepSeek 返回非 200 时
        raise HTTPException(status_code=502, detail=f"DeepSeek 调用失败: {response.text}")  # 新增

    # 3. 提取模型输出的文本
    data = response.json()  # 新增
    raw_content = data["choices"][0]["message"]["content"]  # 新增

    print(f"[analyze] 模型原始输出:\n{raw_content}\n")  # 新增：调试用，终端里能看到模型到底输出了什么

    # 4. 清洗 + Pydantic 验证
    cleaned = clean_json_response(raw_content)  # 新增

    try:  # 新增
        result = SentimentResult.model_validate_json(cleaned)  # 新增：Pydantic 验证并解析
    except ValidationError as e:  # 新增：模型输出不合规时
        raise HTTPException(  # 新增
            status_code=502,  # 新增
            detail=f"模型输出格式不符合 Schema: {e.errors()}"  # 新增
        )  # 新增

    # 5. 返回结构化结果
    return AnalyzeResponse(result=result, model="deepseek-chat")  # 新增


# ============================================================
# ⑥ 新增接口：/chat-with-tools（Function Calling）
# ============================================================

@app.post("/chat-with-tools")
async def chat_with_tools(req: FunctionCallRequest):
    """支持 Function Calling 的聊天接口"""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="没找到 DEEPSEEK_API_KEY")
    
    session_id = req.session_id or str(uuid.uuid4())
    tool_executor = ToolExecutor()
    
    async def generate():
        full_reply = ""
        
        async with httpx.AsyncClient(timeout=60) as client:
            # 第一次调用：让模型决定是否使用工具
            print(f"\n🔍 第一次调用 DeepSeek，用户消息: {req.message}")
            
            response = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "你是一个智能助手，可以使用工具来帮助用户解决问题。当用户需要计算或查询天气时，使用相应的工具。"},
                        {"role": "user", "content": req.message}
                    ],
                    "tools": tools_schema,  # 关键：传入工具定义
                    "tool_choice": "auto"
                }
            )
            
            if response.status_code != 200:
                yield f"❌ DeepSeek 调用失败: {response.text}"
                return
            
            data = response.json()
            message = data["choices"][0]["message"]
            
            # 检查是否需要调用工具
            if "tool_calls" in message and message["tool_calls"]:
                yield "🔧 检测到工具调用需求\n\n"
                
                # 准备消息历史
                messages = [
                    {"role": "system", "content": "你是一个智能助手，可以使用工具来帮助用户解决问题。"},
                    {"role": "user", "content": req.message},
                    message  # 包含 tool_calls 的 assistant 消息
                ]
                
                # 执行每个工具调用
                for tool_call in message["tool_calls"]:
                    function_name = tool_call["function"]["name"]
                    function_args = json.loads(tool_call["function"]["arguments"])
                    
                    yield f"📞 调用工具: {function_name}\n"
                    yield f"📝 参数: {json.dumps(function_args, ensure_ascii=False)}\n"
                    
                    # 执行函数
                    function_response = tool_executor.execute(function_name, function_args)
                    
                    yield f"✅ 结果: {function_response}\n\n"
                    
                    # 添加工具结果到消息
                    messages.append({
                        "tool_call_id": tool_call["id"],
                        "role": "tool",
                        "name": function_name,
                        "content": function_response
                    })
                
                # 第二次调用：基于工具结果生成最终回答
                yield "🤖 生成最终回答...\n\n"
                
                final_response = await client.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": messages,
                        "stream": False
                    }
                )
                
                if final_response.status_code == 200:
                    final_data = final_response.json()
                    final_content = final_data["choices"][0]["message"]["content"]
                    full_reply = final_content
                    yield final_content
                else:
                    yield f"❌ 最终回答生成失败: {final_response.text}"
            else:
                # 没有工具调用，直接返回
                full_reply = message.get("content", "")
                yield full_reply
        
        # 保存会话
        if session_id not in sessions:
            sessions[session_id] = []
        sessions[session_id].append({"user": req.message, "assistant": full_reply})
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Session-ID": session_id}
    )

# ============================================================
# ⑥ 可选：调试接口，查看所有 session
# ============================================================

@app.get("/sessions")  # 新增：调试用
def list_sessions():  # 新增
    """查看当前内存中的所有会话"""  # 新增
    return {"sessions": sessions}  # 新增


# 启动方式：
#   .venv\Scripts\activate
#   uvicorn main:app --reload