# PlotPilot Dockerfile
# 多阶段构建：先安装依赖，再运行应用

FROM python:3.11-slim AS base

LABEL org.opencontainers.image.title="PlotPilot"
LABEL org.opencontainers.image.description="AI 辅助长篇小说创作叙事引擎内核"
LABEL org.opencontainers.image.source="https://github.com/shenminglinyi/PlotPilot"

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt requirements-local.txt ./

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-local.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8005

# 环境变量
ENV PYTHONUNBUFFERED=1
ENV PLOTPILOT_HOST=0.0.0.0
ENV PLOTPILOT_PORT=8005

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8005/health || exit 1

# 启动
CMD ["python", "-m", "uvicorn", "interfaces.main:app", "--host", "0.0.0.0", "--port", "8005"]
