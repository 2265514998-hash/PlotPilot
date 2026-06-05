# PlotPilot 开发环境搭建指南

## 前置要求

| 工具 | 最低版本 | 说明 |
|------|----------|------|
| Python | 3.11+ | 推荐 3.12 |
| pip | 23.0+ | 随 Python 安装 |
| Git | 2.30+ | 版本管理 |
| Node.js | 18+ | 仅前端开发需要 |
| Docker | 24+ | 可选，容器化部署 |

## 快速开始（3 步）

### 1. 克隆仓库

```bash
git clone https://github.com/shenminglinyi/PlotPilot.git
cd PlotPilot
```

### 2. 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 安装核心依赖
pip install -e ".[dev]"

# 如需本地向量模型（零 API 费用，首次下载约 2GB）
pip install -e ".[local]"
```

### 3. 启动服务

```bash
# 方式一：Make
make run

# 方式二：直接启动
uvicorn interfaces.main:app --host 127.0.0.1 --port 8005 --reload

# 方式三：Docker
docker compose up -d
```

启动后访问 `http://127.0.0.1:8005/docs` 查看 API 文档。

## 项目结构

```
PlotPilot/
├── domain/           # 领域层 — 核心业务逻辑（零外部依赖）
│   ├── novel/        #   小说、章节、伏笔
│   ├── bible/        #   角色深度档案、世界观
│   ├── cast/         #   角色关系图谱
│   ├── knowledge/    #   知识三元组
│   ├── ai/           #   LLM 服务接口定义
│   └── shared/       #   基类、异常
├── application/      # 应用层 — 用例编排
│   ├── engine/       #   核心引擎（AI 生成、自动驾驶、DAG）
│   ├── blueprint/    #   宏观规划（部-卷-幕）
│   ├── world/        #   世界观管理
│   ├── audit/        #   质量审阅
│   ├── analyst/      #   文风分析
│   └── reader/       #   读者模拟
├── infrastructure/   # 基础设施层 — 技术实现
│   ├── ai/           #   LLM 客户端、向量存储、提示词包
│   └── persistence/  #   SQLite 仓储
├── interfaces/       # 接口层 — FastAPI 路由
│   └── api/v1/       #   REST API v1
├── engine/           # 叙事引擎领域库（3.0-alpha）
├── frontend/         # Vue 3 前端 SPA
├── tests/            # 测试
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/             # 文档
├── scripts/          # 辅助脚本
└── tools/            # 工具（嵌入 Python 等）
```

## 配置 API Key

在项目根目录创建 `.env` 文件：

```env
# OpenAI 兼容 API
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.openai.com/v1

# 或使用 DeepSeek
# OPENAI_API_KEY=sk-your-deepseek-key
# OPENAI_BASE_URL=https://api.deepseek.com/v1

# 服务端口
PLOTPILOT_PORT=8005
```

## 运行测试

```bash
# 单元测试
make test

# 全部测试
make test-all

# 指定文件
pytest tests/unit/application/engine/dag/test_engine.py -v
```

## 代码规范

```bash
# 检查
make lint

# 自动格式化
make format

# 自动修复
make lint-fix

# 安装 pre-commit（每次 git commit 自动检查）
pre-commit install
```

## Docker 部署

```bash
# 构建并启动
make docker-up

# 查看日志
docker compose logs -f backend

# 停止
make docker-down
```

## 前端开发

前端使用 Vue 3 + Vite + TypeScript，仅需在后端 API 已启动的前提下运行：

```bash
cd frontend
npm install
npm run dev
```

## 常见问题

**Q: 导入报错 `ModuleNotFoundError: No module named 'domain'`**

A: 确保使用 `pip install -e .` 以开发模式安装，或运行 `export PYTHONPATH=.` / `set PYTHONPATH=.`。

**Q: ChromaDB 连接失败**

A: 使用 Docker Compose 时会自动启动 ChromaDB 容器。本地开发可安装 `pip install chromadb`。

**Q: 前端构建失败**

A: 检查 Node.js 版本 ≥ 18，运行 `node -v` 确认。

**Q: Windows 上 `make` 不可用**

A: 直接使用 Makefile 中的对应命令，或安装 `choco install make`。
