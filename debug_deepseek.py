# 诊断脚本:绕过 FastAPI,直接问 DeepSeek,把原始回复打出来
# 用法(在 Chat-API 目录、且设好 key 的终端里运行):
#   .venv\Scripts\python.exe debug_deepseek.py

import os
import httpx # type: ignore

key = os.environ.get("DEEPSEEK_API_KEY", "")
print("1. 终端里是否读到了 key:", "是(长度 %d)" % len(key) if key else "否 ← 问题在这!")

if key:
    try:
        r = httpx.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": "你好"}]
            },
            timeout=30,  # 30 秒超时,避免干等
        )
        print("2. HTTP 状态码:", r.status_code)
        print("3. DeepSeek 原始回复(前 1000 字符):")
        print(r.text[:1000])
    except Exception as e:
        print("2. 请求过程中抛了异常:", type(e).__name__, "-", e)
