import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from asr_core.client import ASRCoreClient
from asr_core.config import MODEL_CHOICES, SOCKET_PATH

from .systemd import SystemdManager

app = FastAPI(title="Voice-to-Text Dashboard")

static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

systemd = SystemdManager(user=True)


def _asr_status() -> dict:
    if not os.path.exists(SOCKET_PATH):
        return {"state": "unloaded", "model_name": None, "gpu_memory_mb": None}
    try:
        with ASRCoreClient(auto_start=False) as client:
            return client.status()
    except Exception as e:
        return {"state": "error", "model_name": None, "error_message": str(e)}


def _full_status() -> dict:
    return {
        "asr": _asr_status(),
        "services": [
            {
                "name": s.name,
                "active": s.active,
                "status": s.status,
                "uptime": s.uptime,
            }
            for s in systemd.all_statuses()
        ],
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    status = _full_status()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "asr": status["asr"],
            "services": status["services"],
            "models": MODEL_CHOICES,
        },
    )


@app.get("/api/status")
def api_status():
    return _full_status()
from pydantic import BaseModel


class LoadModelRequest(BaseModel):
    model_name: str


@app.post("/api/asr/load")
def api_asr_load(payload: LoadModelRequest):
    try:
        with ASRCoreClient() as client:
            return client.load_model(payload.model_name)
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/asr/unload")
def api_asr_unload():
    try:
        with ASRCoreClient(auto_start=False) as client:
            return client.unload_model()
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/services/{name}/start")
def api_service_start(name: str):
    return {"name": name, "result": systemd.start(name)}


@app.post("/api/services/{name}/stop")
def api_service_stop(name: str):
    return {"name": name, "result": systemd.stop(name)}


@app.post("/api/services/{name}/restart")
def api_service_restart(name: str):
    return {"name": name, "result": systemd.restart(name)}


@app.get("/api/services/{name}/logs")
def api_service_logs(name: str, lines: int = 50):
    return {"name": name, "logs": systemd.logs(name, lines)}


@app.get("/partials/status", response_class=HTMLResponse)
def partial_status(request: Request):
    status = _full_status()
    return templates.TemplateResponse(
        request,
        "partials/status.html",
        {
            "asr": status["asr"],
            "services": status["services"],
            "models": MODEL_CHOICES,
        },
    )


@app.get("/partials/logs/{name}", response_class=HTMLResponse)
def partial_logs(request: Request, name: str, lines: int = 50):
    return templates.TemplateResponse(
        request,
        "partials/logs.html",
        {
            "name": name,
            "logs": systemd.logs(name, lines),
        },
    )
