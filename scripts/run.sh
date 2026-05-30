#!/bin/bash
# AI-SDLC 一键启动脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PORT_FILE="$PROJECT_DIR/.running_ports"

echo "🚀 AI-SDLC 启动中..."
echo ""

# ── 查找空闲端口 ──
find_free_port() {
    python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1]); s.close()"
}

BACKEND_PORT=$(find_free_port)
FRONTEND_PORT=$(find_free_port)

echo "🎲 分配端口: 后端=$BACKEND_PORT, 前端=$FRONTEND_PORT"

# ── Backend ──
echo "📦 启动后端 (FastAPI)..."
cd "$PROJECT_DIR/backend"

if [ ! -d "venv" ]; then
    echo "   创建 Python 虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate

if [ ! -f "venv/.deps_installed" ]; then
    echo "   安装 Python 依赖..."
    pip install -q -r requirements.txt
    touch venv/.deps_installed
fi

uvicorn main:app --reload --reload-exclude "venv/*" --host 127.0.0.1 --port "$BACKEND_PORT" &
BACKEND_PID=$!
echo "   后端 PID: $BACKEND_PID"

echo "   等待后端就绪..."
for i in $(seq 1 30); do
    curl -s "http://127.0.0.1:$BACKEND_PORT/health" > /dev/null 2>&1 && break
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

BACKEND_PORT=$BACKEND_PORT FRONTEND_PORT=$FRONTEND_PORT npm run dev &
FRONTEND_PID=$!
echo "   前端 PID: $FRONTEND_PID"

# Save ports for cleanup
echo "BACKEND_PORT=$BACKEND_PORT" > "$PORT_FILE"
echo "FRONTEND_PORT=$FRONTEND_PORT" >> "$PORT_FILE"

echo ""
echo "✅ 启动完成！"
echo "   后端: http://localhost:$BACKEND_PORT"
echo "   前端: http://localhost:$FRONTEND_PORT"
echo "   API文档: http://localhost:$BACKEND_PORT/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"

cleanup() {
    echo ""
    echo "🛑 停止服务..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    if [ -f "$PORT_FILE" ]; then
        source "$PORT_FILE" 2>/dev/null
        lsof -ti:$BACKEND_PORT 2>/dev/null | xargs -r kill -9 2>/dev/null
        lsof -ti:$FRONTEND_PORT 2>/dev/null | xargs -r kill -9 2>/dev/null
        rm -f "$PORT_FILE"
    fi
    exit
}
trap cleanup SIGINT SIGTERM
wait
