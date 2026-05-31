"""FastAPI Application Entry Point"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings, ROOT_DIR, WORKSPACE_ROOT
from api.routes_batch import router as batch_router
from api.routes_prompt import router as prompt_router
from api.routes_ws import router as ws_router

app = FastAPI(
    title="AI-SDLC",
    description="基于 AI Agent 的 IT 功能全链路自动化开发系统",
    version="1.0.0",
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(batch_router, prefix="/api")
app.include_router(prompt_router, prefix="/api")
app.include_router(ws_router, prefix="/ws")

# Static file serving (workspace output preview)
workspace_abs = str(WORKSPACE_ROOT.resolve())
app.mount("/workspace", StaticFiles(directory=workspace_abs), name="workspace")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "AI-SDLC"}


@app.get("/api/config")
async def get_config():
    return {
        "model": settings.primary_model,
        "temperature": settings.llm_temperature,
        "workspace": str(WORKSPACE_ROOT),
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
