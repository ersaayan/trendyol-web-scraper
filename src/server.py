from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .app.api.routers import router as api_router


app = FastAPI(title="Trendyol Scraper UI")

# Mount API
app.include_router(api_router)

# Static and templates for dashboard
BASE_DIR = Path(__file__).parent
static_dir = BASE_DIR / "static"
templates_dir = BASE_DIR / "templates"
static_dir.mkdir(parents=True, exist_ok=True)
templates_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
analysis_dir = Path("analysis")
analysis_dir.mkdir(parents=True, exist_ok=True)
app.mount("/analysis", StaticFiles(directory=str(analysis_dir)), name="analysis")
templates = Jinja2Templates(directory=str(templates_dir))


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
