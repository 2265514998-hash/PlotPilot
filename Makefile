# PlotPilot Makefile
# 常用开发命令速查

.PHONY: help install dev-install run test lint format clean docker-build docker-up docker-down

help:  ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## 安装核心依赖
	pip install -r requirements.txt

dev-install:  ## 安装全部开发依赖（含本地向量模型）
	pip install -e ".[dev,local]"

run:  ## 启动 API 服务器（开发模式，热重载）
	uvicorn interfaces.main:app --host 127.0.0.1 --port 8005 --reload

serve:  ## 启动 API 服务器（生产模式）
	uvicorn interfaces.main:app --host 0.0.0.0 --port 8005

test:  ## 运行单元测试
	pytest tests/unit -v --tb=short

test-all:  ## 运行全部测试
	pytest tests/ -v --tb=short

lint:  ## 代码检查
	ruff check .

format:  ## 代码格式化
	ruff format .

lint-fix:  ## 自动修复代码问题
	ruff check --fix .

clean:  ## 清理缓存与构建产物
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ htmlcov/ .coverage

docker-build:  ## 构建 Docker 镜像
	docker compose build

docker-up:  ## 启动 Docker 服务
	docker compose up -d

docker-down:  ## 停止 Docker 服务
	docker compose down

db-reset:  ## 重置数据库（危险操作）
	rm -f data/*.sqlite data/*.sqlite-shm data/*.sqlite-wal
	@echo "数据库已重置，重启服务即可自动重建"
