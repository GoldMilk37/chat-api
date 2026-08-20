import httpx

with httpx.stream(
    "POST",
    "http://127.0.0.1:8000/chat",
    json={"message": "写一首关于秋天的短诗"}
) as response:
    for chunk in response.iter_text():
        print(chunk, end="", flush=True)