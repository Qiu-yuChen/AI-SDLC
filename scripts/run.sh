#!/bin/bash
# AI-SDLC 一键启动脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 AI-SDLC 启动中..."
echo ""

# ── 端口清理 ──
echo "🧹 清理旧进程..."
lsof -ti:7070 2>/dev/null | xargs -r kill -9 2>/dev/null || true
lsof -ti:5050 2>/dev/null | xargs -r kill -9 2>/dev/null || true
sleep 0.5

# ── Backend ──
echo "📦 启动后端 (FastAPI)..."
cd "$PROJECT_DIR/backend"

# Create venv if not exists
if [ ! -d "venv" ]; then
    echo "   创建 Python 虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate

# Install dependencies
if [ ! -f "venv/.deps_installed" ]; then
    echo "   安装 Python 依赖..."
    pip install -q -r requirements.txt
    touch venv/.deps_installed
fi

# Start backend in background
uvicorn main:app --reload --reload-exclude "venv/*" --host 0.0.0.0 --port 7070 &
BACKEND_PID=$!
echo "   后端 PID: $BACKEND_PID"

# Wait for backend to be ready
echo "   等待后端就绪..."
for i in $(seq 1 30); do
  curl -s http://localhost:7070/health > /dev/null 2>&1 && break
  sleep 0.3
done
echo "   后端已就绪"

# ── Frontend ──
echo "📦 启动前端 (React + Vite)..."
cd "$PROJECT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    echo "   安装 Node 依赖..."
    npm install
fi

npm run dev &
FRONTEND_PID=$!
echo "   前端 PID: $FRONTEND_PID"

echo ""
echo "✅ 启动完成！"
echo "   后端: http://localhost:7070"
echo "   前端: http://localhost:5050"
echo "   API文档: http://localhost:7070/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"

# Cleanup on exit (kill process tree + free ports)
cleanup() {
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    lsof -ti:7070 2>/dev/null | xargs -r kill -9 2>/dev/null
    lsof -ti:5050 2>/dev/null | xargs -r kill -9 2>/dev/null
    exit
}
trap cleanup SIGINT SIGTERM
wait
