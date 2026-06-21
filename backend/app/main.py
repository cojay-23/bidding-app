from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .analyzer import analyze_project
from .config import APP_DIR, PROJECTS_DIR, ensure_dirs
from .database import add_file, create_project, delete_project, get_project, init_db, list_files, list_projects


app = FastAPI(title="Bidding Analyst Internal App", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    ensure_dirs()
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.post("/api/projects")
def api_create_project(name: str = Form("未命名标书分析项目")) -> dict:
    project_id = uuid.uuid4().hex[:12]
    project = create_project(project_id, name.strip() or "未命名标书分析项目")
    project_dir = PROJECTS_DIR / project_id
    for sub in ("uploads", "extracted", "reports", "logs"):
        (project_dir / sub).mkdir(parents=True, exist_ok=True)
    return project


@app.get("/api/projects")
def api_list_projects() -> list[dict]:
    projects = list_projects()
    for project in projects:
        project["files"] = list_files(project["id"])
    return projects


@app.get("/api/projects/{project_id}")
def api_get_project(project_id: str) -> dict:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    project["files"] = list_files(project_id)
    return project


@app.delete("/api/projects/{project_id}")
def api_delete_project(project_id: str) -> dict[str, str]:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    delete_project(project_id)
    project_dir = PROJECTS_DIR / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)
    return {"status": "deleted"}


@app.post("/api/projects/{project_id}/files")
async def api_upload_files(project_id: str, files: list[UploadFile] = File(...)) -> dict:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    upload_dir = PROJECTS_DIR / project_id / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for upload in files:
        original = Path(upload.filename or "upload.bin").name
        stored_name = f"{uuid.uuid4().hex[:8]}_{original}"
        target = upload_dir / stored_name
        with target.open("wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)
        size = target.stat().st_size
        add_file(project_id, original, stored_name, size)
        saved.append({"filename": original, "size": size})
    return {"saved": saved}


@app.post("/api/projects/{project_id}/analyze")
def api_analyze_project(project_id: str, background_tasks: BackgroundTasks, analyze_type: str = Query("general")) -> dict[str, str]:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    files = list_files(project_id)
    if not files:
        raise HTTPException(status_code=400, detail="请先上传招标文件或方案文件")
    background_tasks.add_task(analyze_project, project_id, analyze_type)
    return {"status": "queued"}


@app.get("/api/projects/{project_id}/report")
def api_report(project_id: str) -> FileResponse:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    report_path = project.get("report_path")
    if not report_path or not Path(report_path).exists():
        raise HTTPException(status_code=404, detail="报告尚未生成")
    return FileResponse(report_path, media_type="text/html; charset=utf-8")


@app.get("/api/projects/{project_id}/download")
def api_download(project_id: str) -> FileResponse:
    zip_path = PROJECTS_DIR / project_id / "reports" / "result-package.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="结果包尚未生成")
    return FileResponse(zip_path, filename=f"{project_id}-result-package.zip")


static_dir = APP_DIR / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
