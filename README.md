# AI-SDLC

> **基于 AI Agent 的 IT 功能全链路自动化开发系统**
> 2026"歌尔杯"香港城市大学（东莞）第二届黑客马拉松 参赛项目

<p align="center">
  <img src="https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi" />
  <img src="https://img.shields.io/badge/Agent-CrewAI-8A2BE2" />
  <img src="https://img.shields.io/badge/LLM-LiteLLM-FF6B35" />
  <img src="https://img.shields.io/badge/Frontend-React_18-61DAFB?logo=react" />
  <img src="https://img.shields.io/badge/Scoring-SWEbench_+_RepoZero-4CAF50" />
  <img src="https://img.shields.io/badge/Chat-飞书-3370FF" />
</p>

<p align="center">
<pre>
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                      ║
║                        ___  _____      ___________ _     _____                       ║
║                       / _ \|_   _|    /  ___|  _  \ |   /  __ \                      ║
║                      / /_\ \ | |______\ `--.| | | | |   | /  \/                      ║
║                      |  _  | | |______|`--. \ | | | |   | |                          ║
║                      | | | |_| |_     /\__/ / |/ /| |___| \__/\                      ║
║                      \_| |_/\___/     \____/|___/ \_____/\____/                      ║
║                                                                                      ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                      ║
║     [Design] ──▶ [CodeGen] ──▶ [UnitTest] ──▶ [Scoring] ──▶ [Poster]                 ║
║      Qwen4B        GLM-5.1       DeepSeek     SWE+RepoZero      SDXL                 ║
║                        |                                                             ║
║                        +--> Review Loop: score &lt; 70 ? regenerate (max 3)             ║
║                                                                                      ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                      ║
║   +------------------------------------------------------------------------------+   ║
║   |  Text Chat  |  Voice Input  |  Multi-format Docs  |  Feishu Message  |           ║
║   +------------------------------------------------------------------------------+   ║
║                                                                                      ║
║   +------------------------------------------------------------------------------+   ║
║   |  Scoring Report (SWE-bench + RepoZero)  |  ZIP Export  |  SDXL Poster  |         ║
║   +------------------------------------------------------------------------------+   ║
║                                                                                      ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
</pre>
</p>

---

## 一、项目简介与功能概述

AI-SDLC 是一套基于多智能体协同的 IT 功能全链路自动化开发系统。用户只需输入一句话需求或上传任意格式的文档，系统即可自动完成 **概要设计 → 代码生成 → 单元测试 → 质量评分 → 交付海报** 全流程，真正实现"需求到交付"的一键式软件工程。

### 核心能力

```
用户输入 (文字/语音/docx/pptx/pdf/xlsx)
   │
   ├── 📝 提示词优化 (标准 / 西西弗斯多轮追问)
   │
   └── ⚙️ AI-SDLC Pipeline
        ├── 📐 概要设计 Agent (本地 Qwen3-4B LoRA 微调版)
        ├── 💻 代码生成 Agent (GLM-5.1)
        │    └── 🔄 代码审查回环 (评分 < 70 自动重生成，最多 3 轮)
        ├── 🧪 单元测试 Agent (DeepSeek)
        ├── 🏆 质量评分 (SWE-bench + RepoZero 四维度 100 分制)
        └── 🖼️ 交付海报 (SDXL 自动生成)
```

### 功能一览

| 功能模块 | 说明 |
|----------|------|
| 📐 概要设计 | 读取规格书 → 生成含 Mermaid 架构图、API 定义、数据模型的 7 章设计文档 |
| 💻 代码生成 | 基于设计文档生成 FastAPI 项目代码，含完整 CRUD、数据模型、入口文件 |
| 🔄 代码审查 | 生成后自动审查评分，低于阈值（70 分）自动重生成，最多 3 轮 |
| 🧪 单元测试 | 读取代码 → 生成 pytest 测试套件，覆盖正常/边界/异常场景 |
| 🏆 质量评分 | 四维度评分：设计质量 (25%) + 代码质量 (35%) + 测试质量 (15%) + RepoZero 验证 (25%) |
| 🖼️ 交付海报 | 基于项目名 + 评分自动生成 SDXL 1024×768 交付海报 |
| 💬 Chat 界面 | ChatGPT 风格对话，Pipeline 卡片 + ReAct 日志实时推送 |
| 🎤 语音输入 | Chrome/Edge 用 Web Speech API，Safari/Firefox 用本地 Whisper (large-v3) |
| 🗂️ 多格式上传 | 15+ 格式（.docx/.pptx/.pdf/.xlsx/.csv/.html/.json 等）自动 AI 预处理 |
| 🌓 主题切换 | 深色/浅色一键切换 |
| 📄 产出物预览 | 文件列表折叠/展开，Python/JS/JSON 等语法高亮预览，ZIP 一键下载 |
| 📱 飞书接入 | SDK WebSocket 长连接，对话式创建 + 阶段进度实时推送 |
| 📝 提示词优化 | 标准模式（一句话→规格书）/ 西西弗斯模式（多轮启发式追问） |
| 🧠 技能积累 | 高分产出→成功范例，失败节点→失败教训，后续批次自动检索注入 |

---

## 二、系统架构说明

### 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户交互层                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│  │  Web UI  │  │  飞书 Bot │  │ REST API │                      │
│  │(React 18)│  │(WSS 长连接)│  │(FastAPI) │                      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                      │
│       │              │              │                            │
│       └──────────────┼──────────────┘                            │
│                      │  WebSocket (keepalive 10s)               │
├──────────────────────┼──────────────────────────────────────────┤
│                      ▼          编排层                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              OrchestratorEngine                          │   │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐        │   │
│  │  │概要设计 │→ │代码生成 │→ │单元测试 │→ │质量评分 │        │   │
│  │  │ Agent  │  │ Agent  │  │ Agent  │  │(4维度) │        │   │
│  │  └────────┘  └───┬────┘  └────────┘  └────────┘        │   │
│  │                   │ 代码审查回环 (max 3 轮)               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│                       模型调度层                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     LiteLLM Gateway                      │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐   │   │
│  │  │ Qwen3-4B│  │ GLM-5.1 │  │DeepSeek │  │ OpenAI/  │   │   │
│  │  │ (本地vLLM)│  │ (智谱)  │  │         │  │ Anthropic│   │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └──────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│                       工具与存储层                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ 文件工具  │ │ 代码工具  │ │ 评分工具  │ │ 技能库   │           │
│  │ (LRU缓存)│ │(AST/pep8)│ │(radon/   │ │(成功+    │           │
│  │          │ │          │ │ pytest)  │ │ 失败)    │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                       │
│  │ 文档解析  │ │ 海报生成  │ │ 语音识别  │                       │
│  │(15+格式) │ │ (SDXL)   │ │(Whisper) │                       │
│  └──────────┘ └──────────┘ └──────────┘                       │
└──────────────────────────────────────────────────────────────────┘
```

### 多智能体协同机制

每个 Agent 采用 CrewAI ReAct 模式，独立配置 LLM 和工具集：

| Agent | 默认模型 | 职责 |
|-------|---------|------|
| 概要设计 | `openai/qwen-input` (本地 Qwen3-4B LoRA 微调) | 生成 7 章 Markdown 设计文档 |
| 代码生成 | `openai/glm-5.1` (智谱 GLM-5.1) | 生成 FastAPI 项目完整代码 |
| 单元测试 | `deepseek/deepseek-chat` | 生成 pytest 测试套件 |
| 代码审查 | `deepseek/deepseek-chat` | 审查回环，评分 < 70 触发重生成 |

### 质量评分体系

基于 SWE-bench (ICLR 2024) + RepoZero (NeurIPS 2026) 双基准：

| 维度 | 权重 | 评估内容 |
|------|------|----------|
| 概要设计 | 25% | 结构完整性 (30) + Mermaid 图表 (15) + API 端点 (15) + 数据模型 (15) + 文档长度 (10) + 技术选型 (15) |
| 代码生成 | 35% | 语法正确 (25) + 圈复杂度 (15) + 可维护性 (15) + flake8 (10) + 异常处理 (15) + docstring (10) + 模块化 (10) |
| 单元测试 | 15% | 静态分析 (80)：文件/函数/assert/conftest/行数；动态运行 (20)：F2P + P2P 双验证 |
| RepoZero | 25% | 黑盒输出验证 BOV (60) + API 覆盖度 (40) |

### 技术栈

| 层级 | 技术 |
|------|------|
| LLM 网关 | LiteLLM (DeepSeek / OpenAI / Anthropic / GLM / Qwen) |
| 多智能体 | CrewAI (ReAct mode, per-agent model) |
| Web 框架 | FastAPI + WebSocket (keepalive 10s ping) |
| 前端 | React 18 + TypeScript + Vite + Tailwind (深色/浅色主题) |
| 本地模型 | Qwen3-4B-Instruct (vLLM + LoRA rank=16 fine-tuned) |
| 语音 | Web Speech API + faster-whisper (large-v3) |
| 图像 | SDXL base 1.0 (poster generation) |
| 质量评估 | SWE-bench F2P/P2P + radon (CC/MI) + RepoZero BOV/API |
| 即时通讯 | 飞书 SDK WebSocket 长连接 |
| 语法高亮 | react-syntax-highlighter (atomOneDark, 10 语言) |

### 项目结构

```
ai-sdlc/
├── backend/
│   ├── main.py                    # FastAPI 入口
│   ├── config.py                  # 多模型 + per-agent + 飞书 + 审查回环配置
│   ├── api/
│   │   ├── routes_batch.py        # 批次 CRUD + stop/resume + ZIP export
│   │   ├── routes_prompt.py       # 提示词优化 (标准 / 西西弗斯)
│   │   ├── routes_ws.py           # WebSocket 实时流
│   │   ├── routes_stt.py          # 语音转文字 (Whisper)
│   │   └── routes_feishu.py       # 飞书 Bot (SDK 长连接 + 进度推送)
│   ├── orchestrator/
│   │   ├── engine.py              # 流程调度 + 质量评分 + 海报生成
│   │   ├── crew_factory.py        # CrewAI Agent 工厂 (per-agent model)
│   │   ├── state_manager.py       # JSON 状态持久化 (4 节点)
│   │   ├── code_review_loop.py    # 代码审查回环 (max 3 轮, threshold 70)
│   │   └── task_control.py        # 协作式任务取消 (StopRequested)
│   ├── agents/
│   │   ├── design_agent.py        # 概要设计 prompt
│   │   ├── codegen_agent.py       # 代码生成 prompt
│   │   ├── test_agent.py          # 单元测试 prompt
│   │   ├── quality_agent.py       # 质量审查 Agent
│   │   └── spec_preprocessor.py   # AI 预处理规格书 (15+ 格式)
│   ├── scoring/                   # 质量评分系统
│   │   ├── design_scorer.py       # 概要设计评分 (6 指标)
│   │   ├── code_scorer.py         # 代码质量评分 (7 指标, SWE-bench §C.7)
│   │   ├── test_scorer.py         # 单元测试评分 (静态 80 + 动态 20)
│   │   ├── repozero_scorer.py     # RepoZero 评分 (BOV + API 覆盖)
│   │   └── report_generator.py    # 评分报告 (JSON + Markdown)
│   ├── skills/skill_store.py      # 技能积累 (成功+失败+关键词检索)
│   ├── tools/
│   │   ├── file_tools.py          # 文件读写 (LRU 缓存)
│   │   ├── code_tools.py          # 语法检查 + 格式化
│   │   ├── quality_tools.py       # flake8 + pytest-cov + 评分计算
│   │   ├── document_tools.py      # 15+ 格式解析
│   │   └── poster_generator.py    # SDXL 海报生成
│   └── ws/manager.py              # WebSocket 连接管理
├── frontend/
│   └── src/
│       ├── App.tsx                # 主布局 + 侧边栏 + 主题切换
│       ├── components/
│       │   ├── ChatView.tsx       # 聊天主界面 + 评分卡片
│       │   ├── ChatInput.tsx      # 输入栏 (语音 + 多格式上传)
│       │   ├── ChatMessage.tsx    # 气泡渲染 + 产出物折叠预览 + 语法高亮
│       │   ├── PromptOptimizer.tsx# 提示词优化 (标准 + 西西弗斯)
│       │   ├── PipelineView.tsx   # 流水线进度 + 质量条 + 重试
│       │   └── ReActLog.tsx       # ReAct 日志实时流
│       ├── hooks/useVoiceInput.ts # 语音输入
│       └── types/index.ts        # BatchState, NodeStatus, ScoringReport
├── workspace/
│   ├── docs/
│   │   ├── 待生成/                # 输入：规格说明书
│   │   └── 已生成/{batch_id}/     # 输出：按批次组织
│   └── skills/skills.json        # 技能库
├── scripts/run.sh                 # 一键启动 (随机端口)
├── finetune/                      # Qwen3-4B LoRA 微调
└── .env.example                   # 环境变量模板
```

---

## 三、安装与运行指南

### 环境要求

- Python 3.10+
- Node.js 18+
- NVIDIA GPU（本地模型可选）
- DeepSeek / GLM / OpenAI API Key（至少一个）

### 安装步骤

```bash
# 1. 克隆项目
cd ai-sdlc

# 2. 后端依赖
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install radon flake8   # 代码质量评分依赖

# 3. 前端依赖
cd ../frontend
npm install

# 4. 配置环境变量
cd ..
cp .env.example .env
# 编辑 .env，填入 API Key 和模型配置
```

### 启动

```bash
# 方式一：一键启动（随机端口，推荐）
bash scripts/run.sh

# 方式二：手动启动
# 后端
cd backend && source venv/bin/activate
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 前端
cd frontend && npm run dev
```

浏览器打开终端输出的前端地址即可使用。

### .env 配置说明

```bash
# LLM API Keys（至少配一个）
DEEPSEEK_API_KEY=sk-xxx
OPENAI_API_KEY=sk-xxx
ZHIPU_API_KEY=xxx                   # GLM
ANTHROPIC_API_KEY=sk-ant-xxx

# 默认模型（所有 Agent 的兜底）
PRIMARY_MODEL=deepseek/deepseek-chat

# Per-agent model（为空则用 PRIMARY_MODEL）
DESIGN_MODEL=openai/qwen-input      # 本地 Qwen3-4B (LoRA)
CODEGEN_MODEL=openai/glm-5.1        # 智谱 GLM-5.1
TEST_MODEL=deepseek/deepseek-chat   # DeepSeek
PROMPT_MODEL=openai/qwen-input      # 本地 Qwen

# 本地 Qwen vLLM
QWEN_VLLM_API_BASE=http://127.0.0.1:8002/v1

# 代码审查回环
CODE_REVIEW_LOOP_ENABLED=true
CODE_REVIEW_MODEL=deepseek/deepseek-chat
CODE_REVIEW_MAX_ROUNDS=3
CODE_REVIEW_THRESHOLD=70

# 飞书 Bot
FEISHU_APP_ID=cli_xxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxx

# LLM 公共参数
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=8192
LLM_TIMEOUT=120
```

---

## 四、系统验证：员工临时车辆预约程序

以赛题要求的"员工临时车辆预约程序"为例，验证 AI-SDLC 全流程自动化能力。

### 输入

通过飞书发送一句话需求：

> 做一个员工临时车辆预约系统

系统自动生成规格书并启动流水线。

### 产出物概览

| 阶段 | 产出 | 详情 |
|------|------|------|
| 📐 概要设计 | `概要设计文档.md` (487 行) | 7/7 章节完整覆盖，含 2 个 Mermaid 架构图、13 个 API 端点定义、161 个字段定义 |
| 💻 代码生成 | 6 个 Python 文件 (1772 行, 76 个函数) | `app.py` + `models.py` + `routes.py` + `services.py` + `utils.py` + `data/` |
| 🧪 单元测试 | 5 个测试文件 (144 个 test_ 函数, 285 个 assert) | pytest 通过率 95% (20/21)，含 conftest.py |
| 🏆 质量评分 | 评分报告 (JSON + Markdown) | 综合评分 **84.4/100** ★★★★ |
| 🖼️ 交付海报 | `poster.png` (1024×768) | SDXL 基于项目名 + 评分自动生成 |

### 质量评分详情

| 维度 | 得分 | 关键指标 |
|------|------|----------|
| 概要设计 | **97.5**/100 | 7/7 章节命中，2 个 Mermaid 图，13 个 API 端点，487 行文档 |
| 代码生成 | **87.5**/100 | 6/6 文件语法正确，平均圈复杂度 3.17 (A级)，76/80 函数有 docstring |
| 单元测试 | **92.4**/100 | 144 个测试函数，285 个断言，20/21 通过，两次运行结果一致 |
| RepoZero | **62.3**/100 | API 覆盖 81% (8 精确 + 5 部分匹配 / 13 定义) |
| **综合** | **84.4**/100 | ★★★★ 等级 B — Good |

### 生成代码结构

```
代码生成/
├── app.py              # FastAPI 入口 (uvicorn 启动)
├── models.py           # 数据模型 (Reservation/Vehicle/Employee)
├── routes.py           # API 路由 (CRUD 端点)
├── services.py         # 业务逻辑层
├── utils.py            # 工具函数
├── requirements.txt    # 依赖清单
└── data/               # CSV 数据存储
```

### API 接口示例

```
GET    /api/reservations     # 查询所有预约
POST   /api/reservations     # 创建预约
GET    /api/reservations/{id} # 查询单个预约
PUT    /api/reservations/{id} # 更新预约
DELETE /api/reservations/{id} # 删除预约
GET    /api/vehicles         # 查询车辆
GET    /api/employees        # 查询员工
```

---

## 五、团队成员分工

| 成员 | 职责 |
|------|------|
| **陈秋宇** | AI 架构开发，团队开发整合 |
| **林泽涛** | 前端开发，总体架构设计 |
| **李骏宇** | 后端开发，Pipeline 贯通 |
| **王芃程** | AI 架构开发，LLM 开发 |
| **张子谦** | 总体架构设计，前后端协调 |

---

## 附录

### API 接口

```bash
# 上传多格式文件（自动 AI 预处理）
curl -X POST http://localhost:{port}/api/upload-spec -F "file=@需求.pptx"

# 创建并启动批次
curl -X POST http://localhost:{port}/api/batches/{id}/start

# 停止 / 恢复 / 删除
curl -X POST http://localhost:{port}/api/batches/{id}/stop
curl -X POST http://localhost:{port}/api/batches/{id}/resume
curl -X DELETE http://localhost:{port}/api/batches/{id}

# 重试失败节点
curl -X POST http://localhost:{port}/api/batches/{id}/retry/{node_id}

# 导出 ZIP
curl http://localhost:{port}/api/batches/{id}/export > output.zip

# 评分报告
curl http://localhost:{port}/api/batches/{id}/scoring-report

# 提示词优化
curl -X POST http://localhost:{port}/api/prompt/optimize -d '{"input":"做xxx系统"}'
curl -X POST http://localhost:{port}/api/prompt/sisyphus -d '{"input":"做xxx系统"}'

# 语音转文字
curl -X POST http://localhost:{port}/api/stt -F "audio=@recording.webm"
```

### 关键设计决策

| 决策 | 原因 |
|------|------|
| 飞书替代微信 | SDK WebSocket 长连接 > webhook 隧道，无需公网 URL |
| GLM-5.1 作代码生成 | monkey-patch litellm 禁用 thinking 模式，避免空 content |
| 代码审查回环 | 评分 < 70 自动重生成（最多 3 轮），提升代码质量 |
| 质量评分作为节点 | 加入 NODE_ORDER，前端实时显示评分进度，90s 超时保护 |
| 禁用 skill 注入 | CrewAI Jinja2 模板与 `{exc}` 等花括号冲突 |
| 直接 `_write_status()` | `update_node()` 会重算 duration，评分更新需绕过 |
| 后台质量审查 | threading 不阻塞节点推进，审查结果独立存储 |
| WS 指数退避重连 | 断线后 1s → 2s → 4s → 8s → 16s，最长 30s |

### 致谢

- **SWE-bench** — Jimenez et al., *Can Language Models Resolve Real-World GitHub Issues?*, ICLR 2024
- **RepoZero** — Zhang et al., *Can LLMs Generate a Code Repository from Scratch?*, NeurIPS 2026
- **CrewAI** — Multi-Agent Orchestration Framework
- **LiteLLM** — Unified LLM API Gateway
