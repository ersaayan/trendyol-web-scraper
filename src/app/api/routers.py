from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.jobs import JOB_MANAGER


router = APIRouter(prefix="/api", tags=["jobs", "analysis"])


class StartJobRequest(BaseModel):
    url: str = Field(..., description="Trendyol sr URL")
    max_pages: int = 50
    max_items: Optional[int] = None
    out: str = "output.ndjson"
    fmt: str = Field("ndjson", pattern="^(csv|ndjson)$")
    checkpoint: Optional[str] = ".checkpoints/ui.json"
    resume: bool = True
    delay_ms: int = 800
    log_level: str = Field("INFO", pattern="^(CRITICAL|ERROR|WARNING|INFO|DEBUG)$")


class StartJobResponse(BaseModel):
    job_id: str
    pid: int


@router.post("/jobs", response_model=StartJobResponse)
def start_job(req: StartJobRequest):
    cmd = [
        sys.executable,
        "-m",
        "src.cli",
        "--url",
        req.url,
        "--max-pages",
        str(req.max_pages),
        "--out",
        req.out,
        "--format",
        req.fmt,
        "--delay-ms",
        str(req.delay_ms),
        "--log-level",
        req.log_level,
    ]
    if req.max_items is not None:
        cmd += ["--max-items", str(req.max_items)]
    if req.checkpoint:
        cmd += ["--checkpoint", req.checkpoint]
    if req.resume:
        cmd += ["--resume"]

    job = JOB_MANAGER.start(cmd)
    pid = job.process.pid if job.process else -1
    return StartJobResponse(job_id=job.id, pid=pid)


# ---------------------- PDP scrape ----------------------
class StartPDPJobRequest(BaseModel):
    urls: List[str]
    out: str = "pdp.ndjson"
    delay_ms: int = 800
    log_level: str = Field("INFO", pattern="^(CRITICAL|ERROR|WARNING|INFO|DEBUG)$")


@router.post("/pdp", response_model=StartJobResponse)
def start_pdp_job(req: StartPDPJobRequest):
    if not req.urls:
        raise HTTPException(status_code=400, detail="urls boş olamaz")
    cmd = [
        sys.executable,
        "-m",
        "src.pdp_cli",
        "--out",
        req.out,
        "--delay-ms",
        str(req.delay_ms),
        "--log-level",
        req.log_level,
        "--urls",
    ] + req.urls
    job = JOB_MANAGER.start(cmd)
    pid = job.process.pid if job.process else -1
    return StartJobResponse(job_id=job.id, pid=pid)


@router.get("/jobs")
def list_jobs():
    return JOB_MANAGER.list()


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = JOB_MANAGER.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    pid = job.process.pid if job.process else None
    status = "running"
    if job.returncode is not None:
        status = "succeeded" if job.returncode == 0 else "failed"
    return {
        "job_id": job.id,
        "status": status,
        "pid": pid,
        "returncode": job.returncode,
        "started_at": job.start_time,
        "stdout": str(job.stdout_path),
        "stderr": str(job.stderr_path),
    }


@router.get("/jobs/{job_id}/logs")
def get_logs(job_id: str):
    try:
        return JOB_MANAGER.logs(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


# ---------------------- Analysis ----------------------
class StartAnalysisRequest(BaseModel):
    inp: str
    format: str = Field("ndjson", pattern="^(csv|ndjson)$")
    commission: float
    default_cost: float
    tiers: str = '[{"up_to":150,"fee":42.70},{"up_to":300,"fee":72.20}]'
    margins: str = "5,10,15"
    out_dir: str = "analysis"
    use_llm: bool = False
    llm_model: Optional[str] = None


class StartAnalysisResponse(BaseModel):
    job_id: str
    pid: int


@router.post("/analyze", response_model=StartAnalysisResponse)
def start_analysis(req: StartAnalysisRequest):
    cmd = [
        sys.executable,
        "-m",
        "src.analyze",
        "--in",
        req.inp,
        "--format",
        req.format,
        "--commission",
        str(req.commission),
        "--default-cost",
        str(req.default_cost),
        "--tiers",
        req.tiers,
        "--margins",
        req.margins,
        "--out-dir",
        req.out_dir,
    ]
    if req.use_llm:
        cmd.append("--use-llm")
        if req.llm_model:
            cmd += ["--llm-model", req.llm_model]
    job = JOB_MANAGER.start(cmd)
    pid = job.process.pid if job.process else -1
    return StartAnalysisResponse(job_id=job.id, pid=pid)


@router.get("/analysis/recent")
def list_recent_analysis(limit: int = 10):
    base = Path("analysis")
    if not base.exists():
        return []
    files = list(base.glob("analysis-*.json")) + list(base.glob("analysis-*.md"))
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for p in files[:limit]:
        out.append(
            {
                "name": p.name,
                "path": str(p),
                "mtime": p.stat().st_mtime,
                "type": p.suffix.lstrip("."),
            }
        )
    return out


# ---------------------- Outputs (for analysis inputs) ----------------------
@router.get("/outputs/recent")
def list_recent_outputs(limit: int = 50):
    root = Path(".")
    exclude_dirs = {"analysis", ".git", ".logs", ".venv", "__pycache__", "node_modules"}
    files = []
    for pattern in ("**/*.ndjson", "**/*.csv"):
        for p in root.glob(pattern):
            # Exclude directories and hidden/system
            parts = set(part for part in p.parts if part)
            if parts & exclude_dirs:
                continue
            if any(part.startswith(".") and part not in {".env"} for part in p.parts):
                continue
            if not p.is_file():
                continue
            try:
                stat = p.stat()
            except FileNotFoundError:
                continue
            files.append(
                {
                    "name": p.name,
                    "path": str(p),
                    "mtime": stat.st_mtime,
                    "size": stat.st_size,
                    "type": p.suffix.lstrip("."),
                }
            )
    files.sort(key=lambda x: x["mtime"], reverse=True)
    return files[:limit]


# ---------------------- Generic NDJSON reader (for UI previews) ----------------------
@router.get("/ndjson")
def read_ndjson_file(path: str, limit: int = 200):
    p = Path(path)
    # Basic guard: only allow files under current working directory
    try:
        cwd = Path.cwd().resolve()
        rp = p.resolve()
        if cwd not in rp.parents and rp != cwd:
            raise HTTPException(status_code=400, detail="Geçersiz yol")
        if not rp.exists() or not rp.is_file():
            raise HTTPException(status_code=404, detail="Dosya bulunamadı")
    except Exception:
        raise HTTPException(status_code=400, detail="Yol işlenemedi")

    items = []
    total = 0
    with rp.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            if len(items) < max(1, min(2000, limit)):
                try:
                    import json as _json

                    items.append(_json.loads(line))
                except Exception:
                    pass
    return {"items": items, "total": total, "truncated": total > len(items)}


# ---------------------- PDP LLM Scoring ----------------------
class StartPDPScoreRequest(BaseModel):
    inp: str
    out: Optional[str] = None
    llm_model: Optional[str] = None
    rate_limit_ms: int = 0


@router.post("/pdp/score", response_model=StartJobResponse)
def start_pdp_score(req: StartPDPScoreRequest):
    # Validate input exists and is not empty
    inp_path = Path(req.inp)
    if not inp_path.exists() or not inp_path.is_file():
        raise HTTPException(status_code=400, detail="Girdi dosyası bulunamadı")
    # Check at least one non-empty line
    has_line = False
    try:
        with inp_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.strip():
                    has_line = True
                    break
    except Exception:
        pass
    if not has_line:
        raise HTTPException(
            status_code=400, detail="Girdi dosyası boş görünüyor (satır yok)"
        )

    # Normalize output path; avoid overwriting input
    out_path = None
    if req.out:
        out_path = Path(req.out)
        if out_path.resolve() == inp_path.resolve():
            # auto-suffix
            out_path = inp_path.with_name(inp_path.stem + "-scored" + inp_path.suffix)
    cmd = [
        sys.executable,
        "-m",
        "src.pdp_score",
        "--in",
        req.inp,
    ]
    if out_path:
        cmd += ["--out", str(out_path)]
    if req.llm_model:
        cmd += ["--llm-model", req.llm_model]
    if req.rate_limit_ms and req.rate_limit_ms > 0:
        cmd += ["--rate-limit-ms", str(req.rate_limit_ms)]
    job = JOB_MANAGER.start(cmd)
    pid = job.process.pid if job.process else -1
    return StartJobResponse(job_id=job.id, pid=pid)
