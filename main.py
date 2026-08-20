import os  #读取环境变量
import json
import httpx #HTTP 客户端，用来发请求给 DeepSeek
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel# 导入 Pydantic
app = FastAPI()
class ChatRequest(BaseModel):# ② 定义请求体的"形状"
    message: str#    告诉 FastAPI，来请求的人必须发 {"message": "字符串"}
@app.get("/ping")#装饰器，注册一个接口
def ping():#定义一个函数从服务器拿数据（比如访问 /ping）
    return {"msg": "pong"}#接口返回的内容
@app.post("/chat")# ③ POST 接口，路径 /chat  给服务器送数据（比如发聊天消息）
# async def	异步函数
async def chat(req: ChatRequest): #    参数类型是 ChatRequest
    async def generate():
        async with httpx.AsyncClient() as client:# httpx.AsyncClient()	异步 HTTP 客户端
            async with client.stream(
                "POST",
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}",
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
                            delta = parsed["choices"][0]["delta"]
                            if "content" in delta:
                                yield delta["content"]#yield：函数暂停，把当前值发出去，然后继续执行下一行
                            if "usage" in parsed:
                                print(f"Token 用量: {parsed['usage']}")    
                        except:
                            pass

    return StreamingResponse(generate(), media_type="text/event-stream")
#StreamingResponse：FastAPI 提供的特殊响应类型,把生成器里的内容一段一段发给浏览器，而不是等生成器结束才发

# 让 uvicorn 启动 main.py 文件里的 app 对象
# 开启自动重启模式。 

#   .venv\Scripts\activate
#   uvicorn main:app --reload