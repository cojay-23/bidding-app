from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from .analyzer import analyze_project
from .auth import ADMIN_PASSWORD, ADMIN_USERNAME, COOKIE_NAME, create_session_token, require_auth, verify_credentials
from .config import APP_DIR, PROJECTS_DIR, ensure_dirs
from .database import add_file, create_project, delete_project, get_project, init_db, list_files, list_projects, list_reports, report_stored_path


app = FastAPI(title="Bidding Analyst Internal App", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    ensure_dirs()
    init_db()


# ─── 登录/登出 ──────────────────────────────────────────
@app.post("/api/login")
async def api_login(request: Request):
    import json
    body = await request.body()
    try:
        data = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="请求格式错误")
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not verify_credentials(username, password):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token = create_session_token(username)
    resp = JSONResponse({"status": "ok", "username": username})
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
        path="/",
    )
    return resp


@app.post("/api/logout")
async def api_logout():
    resp = JSONResponse({"status": "ok"})
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


@app.get("/api/me")
def api_me(username: str = Depends(require_auth)) -> dict:
    return {"username": username}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.post("/api/projects")
def api_create_project(name: str = Form("未命名标书分析项目"), _: str = Depends(require_auth)) -> dict:
    project_id = uuid.uuid4().hex[:12]
    project = create_project(project_id, name.strip() or "未命名标书分析项目")
    project_dir = PROJECTS_DIR / project_id
    for sub in ("uploads", "extracted", "reports", "logs"):
        (project_dir / sub).mkdir(parents=True, exist_ok=True)
    return project


@app.get("/api/projects")
def api_list_projects(_: str = Depends(require_auth)) -> list[dict]:
    projects = list_projects()
    for project in projects:
        project["files"] = list_files(project["id"])
    return projects


@app.get("/api/projects/{project_id}")
def api_get_project(project_id: str, _: str = Depends(require_auth)) -> dict:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    project["files"] = list_files(project_id)
    return project


@app.delete("/api/projects/{project_id}")
def api_delete_project(project_id: str, _: str = Depends(require_auth)) -> dict[str, str]:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    delete_project(project_id)
    project_dir = PROJECTS_DIR / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)
    return {"status": "deleted"}


@app.post("/api/projects/{project_id}/files")
async def api_upload_files(project_id: str, files: list[UploadFile] = File(...), _: str = Depends(require_auth)) -> dict:
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
def api_analyze_project(project_id: str, background_tasks: BackgroundTasks, analyze_type: str = Query("general"), _: str = Depends(require_auth)) -> dict[str, str]:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    files = list_files(project_id)
    if not files:
        raise HTTPException(status_code=400, detail="请先上传招标文件或方案文件")
    background_tasks.add_task(analyze_project, project_id, analyze_type)
    return {"status": "queued"}


@app.get("/api/projects/{project_id}/report")
def api_report(project_id: str, _: str = Depends(require_auth)) -> FileResponse:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    report_path = project.get("report_path")
    if not report_path or not Path(report_path).exists():
        raise HTTPException(status_code=404, detail="报告尚未生成")
    return FileResponse(report_path, media_type="text/html; charset=utf-8")


@app.get("/api/projects/{project_id}/reports")
def api_list_reports(project_id: str, _: str = Depends(require_auth)) -> list[dict]:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return list_reports(project_id)


@app.get("/api/projects/{project_id}/reports/{report_id}")
def api_get_report(project_id: str, report_id: str, _: str = Depends(require_auth)) -> FileResponse:
    reports = list_reports(project_id)
    target = next((r for r in reports if str(r["id"]) == report_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="报告不存在")
    path = report_stored_path(project_id, target["stored_name"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="报告文件已丢失")
    return FileResponse(path, media_type="text/html; charset=utf-8", filename=target["filename"])


@app.get("/api/projects/{project_id}/download")
def api_download(project_id: str, _: str = Depends(require_auth)) -> FileResponse:
    zip_path = PROJECTS_DIR / project_id / "reports" / "result-package.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="结果包尚未生成")
    return FileResponse(zip_path, filename=f"{project_id}-result-package.zip")


# ─── 静态文件 & 登录页（路由必须在 mount 之前） ─────
static_dir = APP_DIR / "static"


@app.get("/login", include_in_schema=False)
def login_page() -> FileResponse:
    return FileResponse(static_dir / "login.html", media_type="text/html; charset=utf-8")


app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
