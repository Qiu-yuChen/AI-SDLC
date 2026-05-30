# AI-SDLC

> **基于 AI Agent 的 IT 功能全链路自动化开发系统**  
> 2026"歌尔杯"香港城市大学（东莞）第二届黑客马拉松 参赛项目

---

## 项目简介

AI-SDLC 是一个基于多智能体协同机制的自动化软件开发系统。输入产品规格说明书（Markdown），系统通过三个专用 AI Agent 协作，自动完成：

```
产品规格说明书 → [📐 概要设计 Agent] → [💻 代码生成 Agent] → [🧪 单元测试 Agent] → 可运行代码 
```

每个 Agent 采用 **ReAct（Reasoning + Acting）** 模式，可自主使用工具（读文件、写文件、语法检查等），在思考-行动-观察的循环中迭代优化产出物质量。

---

## 技术架构

```
┌──────────────────────────────────────────┐
│         React + Vite + Tailwind          │  前端仪表盘
│    实时进度 / ReAct日志 / 文件预览        │
├──────────────────────────────────────────┤
│         FastAPI + WebSocket              │  后端 API
├──────────────────────────────────────────┤
│         CrewAI Multi-Agent               │  多智能体编排
│  ┌────────┐  ┌────────┐  ┌────────┐     │
│  │Design  │→ │CodeGen │→ │ Test   │     │
│  │Agent   │  │Agent   │  │Agent   │     │
│  │(ReAct) │  │(ReAct) │  │(ReAct) │     │
│  └────────┘  └────────┘  └────────┘     │
├──────────────────────────────────────────┤
│         LiteLLM (LLM Gateway)            │  LLM 调用
│   DeepSeek / OpenAI / Claude / ...       │
└──────────────────────────────────────────┘
```

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- DeepSeek 或 OpenAI API Key

### 安装

```bash
# 1. 克隆项目
cd ai-sdlc

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 API Key

# 3. 一键启动
bash scripts/run.sh
```

### 手动启动

```bash
# 后端
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 前端（新终端）
cd frontend
npm install
npm run dev
```

访问：
- 前端：http://localhost:5173
- API 文档：http://localhost:8000/docs

---

## 使用指南

1. 打开前端页面，点击「新建」
2. 上传产品规格说明书（.md 文件）
3. 输入项目名称，点击「创建并启动」
4. 系统自动执行三个 Agent：
   - **📐 概要设计 Agent**：读取规格书 → 生成架构设计文档
   - **💻 代码生成 Agent**：读取设计文档 → 生成 Python FastAPI 代码
   - **🧪 单元测试 Agent**：读取代码 → 生成 pytest 测试
5. 在「ReAct 日志」面板可实时查看每个 Agent 的思考过程
6. 在「产出物文件」面板可预览生成的设计文档和代码

---

## 项目结构

```
ai-sdlc/
├── backend/                  # FastAPI 后端
│   ├── main.py              # 应用入口
│   ├── config.py            # 配置管理
│   ├── api/                 # REST API + WebSocket
│   ├── orchestrator/        # 编排引擎
│   │   ├── engine.py        # 流程调度
│   │   ├── crew_factory.py  # CrewAI Crew 工厂
│   │   └── state_manager.py # JSON 状态管理
│   ├── agents/              # Agent Prompt 定义
│   │   ├── design_agent.py
│   │   ├── codegen_agent.py
│   │   └── test_agent.py
│   ├── tools/               # ReAct 工具集
│   │   ├── file_tools.py
│   │   ├── code_tools.py
│   │   └── quality_tools.py
│   └── ws/                  # WebSocket 管理
├── frontend/                 # React 前端
│   └── src/
│       ├── App.tsx          # 主应用
│       ├── api/client.ts    # API + WebSocket 客户端
│       ├── components/      # UI 组件
│       │   ├── BatchCreator.tsx   # 批次创建
│       │   ├── PipelineView.tsx   # 流水线进度
│       │   ├── ReActLog.tsx       # ReAct 日志
│       │   └── FilePreview.tsx    # 文件预览
│       └── types/index.ts   # 类型定义
├── workspace/                # 产出物存储
│   └── docs/
│       ├── 待生成/           # 输入：规格说明书
│       └── 已生成/{批次ID}/  # 输出：按批次组织
│           ├── batch_status.json
│           ├── execution_log.json
│           ├── design/       # 概要设计产出
│           ├── codegen/      # 源代码产出
│           └── test/         # 测试代码产出
├── scripts/run.sh           # 一键启动
├── .env.example             # 环境变量模板
└── README.md                # 本文件
```

---

## 团队成员分工

| 角色 | 职责 |
|------|------|
| A — 后端架构 | FastAPI、API 设计、WebSocket、状态管理、配置文件 |
| B — 编排引擎 | CrewAI 集成、流程编排、Crew 工厂、ReAct 回调、增量重试 |
| C — Agent 开发(1) | 概要设计 Agent + 代码生成 Agent 的 Prompt 工程与工具开发 |
| D — Agent 开发(2) | 单元测试 Agent + 质量检查 + CSV 数据工具 |
| E — 前端 + 演示 | React 仪表盘、演示视频录制、README、测试用例验证 |

---

## 许可证

MIT
# AI-SDLC
