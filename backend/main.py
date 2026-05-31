"""FastAPI Application Entry Point"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings, ROOT_DIR, WORKSPACE_ROOT
from api.routes_batch import router as batch_router
from api.routes_prompt import router as prompt_router
from api.routes_ws import router as ws_router
from api.routes_stt import router as stt_router
from api.routes_wechat import router as wechat_router

app = FastAPI(
    title="AI-SDLC",
    version="3.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

workspace_abs = str(WORKSPACE_ROOT.resolve())
app.mount("/workspace", StaticFiles(directory=workspace_abs), name="workspace")

# API Routes
app.include_router(batch_router, prefix="/api")
app.include_router(prompt_router, prefix="/api")
app.include_router(stt_router, prefix="/api")
app.include_router(wechat_router, prefix="/api")
app.include_router(ws_router, prefix="/ws")


@app.on_event("startup")
async def startup_feishu():
    from api.routes_feishu import start_feishu_wss
    start_feishu_wss()


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
