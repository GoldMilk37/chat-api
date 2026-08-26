# ===== 起点：官方 Python 3.10 精简镜像 =====
# 镜像 = 一个预装好环境的"标准盒子"。python:3.10-slim 里已有 Python 3.10（和 .venv 版本一致）
FROM python:3.10-slim

# ===== 容器内默认工作目录 =====
# 进容器后所有命令都在这个目录下执行，相当于"cd /app"
WORKDIR /app

# ===== 先复制依赖清单 =====
# 先单独复制 requirements.txt 再装依赖：因为 Docker 有"层缓存"，
# 依赖清单没变时，之后改代码重新 build 就不用重装依赖，秒出结果
COPY requirements.txt .

# ===== 安装依赖 =====
# --no-cache-dir：不保留下载缓存，让镜像更小
RUN pip install --no-cache-dir -r requirements.txt

# ===== 复制项目文件 =====
# 把项目所有文件复制进容器（.dockerignore 会排除 .venv / .env 等，见同名文件）
COPY . .

# ===== 声明对外端口（礼貌性声明，方便阅读者知道该映射哪个端口）=====
EXPOSE 8000

# ===== 启动命令 =====
# 必须写 JSON 数组形式（不能用字符串），否则容器收不到 Ctrl+C/停止信号
# host 必须是 0.0.0.0：让容器接受来自"容器外"的请求，否则只能容器内部访问
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
