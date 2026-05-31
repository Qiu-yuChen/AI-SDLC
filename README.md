# AI-SDLC

> **基于 AI Agent 的 IT 功能全链路自动化开发系统**  
> 2026"歌尔杯"香港城市大学（东莞）第二届黑客马拉松 参赛项目

<p align="center">
  <img src="https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi" />
  <img src="https://img.shields.io/badge/Agent-CrewAI-8A2BE2" />
  <img src="https://img.shields.io/badge/LLM-LiteLLM-FF6B35" />
  <img src="https://img.shields.io/badge/Frontend-React_18-61DAFB?logo=react" />
  <img src="https://img.shields.io/badge/Deploy-SDXL-FF69B4" />
</p>

---

## 项目简介

AI-SDLC 输入一句话或任意格式的文档，自动完成 **概要设计 → 代码生成 → 单元测试 → 质量评分 → 交付海报** 全流程。
系统基于多智能体协同机制（ReAct 模式），支持 DeepSeek / OpenAI / Anthropic / Kimi / 本地 Qwen 4B 等多模型灵活调度。

```
用户输入 (文字/语音/docx/pptx/pdf)
   │
   ├── 📝 提示词优化 (标准 / 西西弗斯多轮追问)
   │
   └── ⚙️ AI-SDLC Pipeline
        ├── 📐 概要设计 Agent (本地 Qwen 4B)
        ├── 💻 代码生成 Agent (DeepSeek)
        ├── 🧪 单元测试 Agent (可配置)
        ├── 📊 质量评分 (SWE-bench + RepoZero)
        └── 🖼️ 交付海报 (SDXL)
```

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- NVIDIA GPU（本地模型可选）
- DeepSeek / Kimi / OpenAI API Key（至少一个）

### 安装

```bash
cd ai-sdlc
cp .env.example .env     # 编辑 .env，填入 API Key
bash scripts/run.sh       # 一键启动（随机分配端口）
```

浏览器打开终端输出的前端地址即可使用。

---

## 功能特性

### 核心流水线

| 阶段 | 说明 |
|------|------|
| 📐 概要设计 | 读取规格书 → 生成含 Mermaid 架构图、API 定义、数据模型的 7 章设计文档 |
| 💻 代码生成 | `openai/glm-5.1` | 智谱 GLM-5.1 |
| 🧪 单元测试 | 读取代码 → 生成 pytest 测试套件，覆盖正常/边界/异常场景 |
| 📊 质量评分 | SWE-bench F2P/P2P + radon 圈复杂度 + RepoZero 黑盒验证 |
| 🖼️ 交付海报 | SDXL 生成 1024×768 项目交付海报 |

### 交互界面

| 功能 | 说明 |
|------|------|
| 💬 Chat 界面 | ChatGPT 风格对话，Pipeline 卡片 + ReAct 日志实时推送 |
| 🎤 语音输入 | Chrome/Edge 用 Web Speech API，Safari/Firefox 用本地 Whisper |
| 🗂️ 多格式上传 | 支持 15+ 格式（.docx/.pptx/.pdf/.xlsx/.csv/.html/.json 等）自动 AI 预处理 |
| 🌓 主题切换 | 深色/浅色一键切换，localStorage 记忆 |
| 📥 ZIP 下载 | 所有产物一键打包下载 |

### 提示词优化

| 模式 | 说明 |
|------|------|
| 标准模式 | 一句话 → 完整 7 章 Markdown 规格书 |
| 西西弗斯模式 | 多轮启发式追问（就绪度评分 + 覆盖度摘要），逐步完善需求 |

### 技能积累系统

- ✅ 高分产出自动保存为"成功范例"
- ❌ 失败节点自动保存为"失败教训"
- 🔍 后续批次根据任务相似度检索相关范例，注入 Agent prompt

### 多模型架构

每个 Agent 可独立指定不同 LLM 供应商：

| Agent | 默认模型 | 说明 |
|-------|---------|------|
| 概要设计 | `openai/qwen-input` | 本地 Qwen 4B (LoRA 微调版) |
| 代码生成 | `openai/glm-5.1` | 智谱 GLM-5.1 |
| 单元测试 | 可配置 | Kimi / GLM / OpenAI 任意 |
| 提示词优化 | `openai/qwen-input` | 本地 Qwen 4B |

通过 `.env` 修改 `DESIGN_MODEL` / `CODEGEN_MODEL` / `TEST_MODEL` / `PROMPT_MODEL` 即可切换。

### 飞书接入

飞书 SDK 长连接模式，无需公网 URL：

```

飞书发消息 → lark-oapi WSS → AI-SDLC → 自动执行流水线 → 回复 + 进度推送

```

配置 `.env` 中 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`，飞书开放平台开启长连接即可。

支持每个阶段完成自动推送到飞书（概要设计/代码生成/测试/评分）。

---

## 项目结构

```
ai-sdlc/
├── backend/
│   ├── main.py                    # FastAPI 入口
│   ├── config.py                  # 多模型 + per-agent 配置
│   ├── api/
│   │   ├── routes_batch.py        # 批次 CRUD + stop/resume + ZIP export
│   │   ├── routes_prompt.py       # 提示词优化 (标准 / 西西弗斯)
│   │   ├── routes_ws.py           # WebSocket 流
│   │   ├── routes_stt.py          # 语音转文字 (Whisper)
│   │   └── routes_feishu.py       # 飞书 Bot (SDK 长连接)
│   ├── orchestrator/
│   │   ├── engine.py              # 流程调度 + 质量审查 + 海报生成
│   │   ├── crew_factory.py        # CrewAI Agent 工厂 (per-agent model)
│   │   ├── state_manager.py       # JSON 状态持久化
│   │   └── task_control.py        # 协作式任务取消
│   ├── agents/
│   │   ├── design_agent.py        # 概要设计 prompt
│   │   ├── codegen_agent.py       # 代码生成 prompt
│   │   ├── test_agent.py          # 单元测试 prompt
│   │   ├── quality_agent.py       # 质量审查 Agent
│   │   └── spec_preprocessor.py   # AI 预处理规格书
│   ├── scoring/                   # 质量评分系统
│   ├── skills/skill_store.py      # 技能积累 (成功+失败)
│   ├── tools/
│   │   ├── file_tools.py          # 文件读写 (LRU 缓存)
│   │   ├── code_tools.py          # 语法检查 + 格式化
│   │   ├── quality_tools.py       # flake8 + pytest-cov
│   │   ├── document_tools.py      # 15+ 格式解析
│   │   └── poster_generator.py    # SDXL 海报生成
│   └── ws/manager.py              # WebSocket 连接管理
├── frontend/
│   └── src/
│       ├── App.tsx                # 主布局 + 侧边栏
│       ├── api/client.ts          # REST + WebSocket 客户端
│       ├── components/
│       │   ├── ChatView.tsx        # 聊天主界面
│       │   ├── ChatInput.tsx       # 输入栏 (语音+文件)
│       │   ├── ChatMessage.tsx     # 气泡渲染 (React/文件/海报)
│       │   ├── PromptOptimizer.tsx # 提示词优化弹窗
│       │   ├── BatchCreator.tsx    # 批次创建 (预留)
│       │   ├── PipelineView.tsx    # 流水线进度 (预留)
│       │   ├── ReActLog.tsx        # ReAct 日志 (预留)
│       │   └── FilePreview.tsx     # 文件预览 (预留)
│       ├── hooks/useVoiceInput.ts  # 语音输入 hook
│       └── types/
│           ├── index.ts           # 通用类型
│           └── chat.ts            # 聊天类型
├── workspace/
│   ├── docs/
│   │   ├── 待生成/                # 输入：规格说明书
│   │   └── 已生成/{batch_id}/     # 输出：按批次组织
│   │       ├── 概要设计/
│   │       ├── 代码生成/
│   │       ├── 单元测试/
│   │       ├── 质量评分/
│   │       └── 交付海报/
│   └── skills/skills.json        # 技能库
├── scripts/run.sh                 # 一键启动 (随机端口)
├── .env.example                   # 环境变量模板
├── finetune/finetune.py           # Qwen LoRA 微调脚本
└── README.md
```

---

## 批量处理命令

```bash
# 上传多格式文件（自动 AI 预处理）
curl -X POST http://localhost:{port}/api/upload-spec -F "file=@需求.pptx"

# 创建并启动批次
curl -X POST http://localhost:{port}/api/batches/{id}/start

# 停止 / 恢复
curl -X POST http://localhost:{port}/api/batches/{id}/stop
curl -X POST http://localhost:{port}/api/batches/{id}/resume

# 重试失败节点
curl -X POST http://localhost:{port}/api/batches/{id}/retry/概要设计

# 导出 ZIP
curl http://localhost:{port}/api/batches/{id}/export > output.zip
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| LLM 网关 | LiteLLM (DeepSeek / OpenAI / Anthropic / Kimi / GLM) |
| 多智能体 | CrewAI 1.14.5 (ReAct mode) |
| Web 框架 | FastAPI + WebSocket |
| 前端 | React 18 + TypeScript + Vite + Tailwind |
| 本地模型 | Qwen3-4B-Instruct (vLLM + LoRA fine-tuned) |
| 语音 | Web Speech API / faster-whisper (large-v3) |
| 图像 | SDXL base 1.0 (poster generation) |
| 质量 | SWE-bench metrics + radon + pytest-cov |

---

## .env 配置示例

```bash
# API Keys
DEEPSEEK_API_KEY=sk-xxx
MOONSHOT_API_KEY=sk-xxx           # Kimi
ZHIPU_API_KEY=xxx                 # GLM
OPENAI_API_KEY=sk-xxx

# 默认模型（兜底）
PRIMARY_MODEL=deepseek/deepseek-chat

# Per-agent model（为空则用 PRIMARY_MODEL）
DESIGN_MODEL=openai/qwen-input    # 本地 Qwen
CODEGEN_MODEL=deepseek/deepseek-chat
TEST_MODEL=deepseek/deepseek-chat
PROMPT_MODEL=openai/qwen-input

# 本地 Qwen vLLM
QWEN_VLLM_API_BASE=http://127.0.0.1:8002/v1

# Kimi Code API
MOONSHOT_API_BASE=https://api.kimi.com/coding/v1

# Feishu Bot
FEISHU_APP_ID=cli_xxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxx
