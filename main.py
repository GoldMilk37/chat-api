import os  # 读取环境变量
import json
import httpx  # type: ignore  # HTTP 客户端，用来发请求给 DeepSeek
from fastapi import FastAPI  # type: ignore
from fastapi.responses import StreamingResponse  # type: ignore
from pydantic import BaseModel  # type: ignore  # 导入 Pydantic
from dotenv import load_dotenv  # 从 .env 文件读取变量

load_dotenv()  # 启动时把 .env 里的 DEEPSEEK_API_KEY 加载进环境变量

app = FastAPI()


class ChatRequest(BaseModel):  # ② 定义请求体的"形状"
    message: str  # 告诉 FastAPI，来请求的人必须发 {"message": "字符串"}


@app.get("/ping")  # 装饰器，注册一个接口
def ping():  # 定义一个函数从服务器拿数据（比如访问 /ping）
    return {"msg": "pong"}  # 接口返回的内容


@app.post("/chat")  # ③ POST 接口，路径 /chat  给服务器送数据（比如发聊天消息）
async def chat(req: ChatRequest):  # async def 异步函数；参数类型是 ChatRequest
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:  # 没配 key 时给个明白的提示，而不是悄悄 401
        return {"error": "没找到 DEEPSEEK_API_KEY：请在 Chat-API 目录下新建 .env 文件，写入一行 DEEPSEEK_API_KEY=sk-你的key"}

    async def generate():
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

                        # ① 先独立处理 usage：DeepSeek 把用量放在"choices 为空"的最后一块里
                        if "usage" in parsed:
                            print(f"Token 用量: {parsed['usage']}")

                        # ② 再处理回答内容：最后一块的 choices 是空的，必须先进 if 判断
                        choices = parsed.get("choices")
                        if choices:
                            delta = choices[0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]  # yield：函数暂停，把当前值发出去，然后继续执行下一行

    return StreamingResponse(generate(), media_type="text/event-stream")
    # StreamingResponse：FastAPI 提供的特殊响应类型，把生成器里的内容一段一段发给浏览器，而不是等生成器结束才发


# 启动方式：
#   .venv\Scripts\activate
#   uvicorn main:app --reload
