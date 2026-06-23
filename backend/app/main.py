import shutil
import uuid
import logging
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .analyzer import analyze_project
from .auth import ADMIN_PASSWORD, ADMIN_USERNAME, COOKIE_NAME, create_session_token, require_auth, verify_credentials
from .config import APP_DIR, PROJECTS_DIR, ensure_dirs
from .database import add_file, create_project, delete_project, get_project, init_db, list_files, list_projects, list_reports, report_stored_path
from .security import SecurityHeadersMiddleware, CSRFTokenMiddleware, SlowAPIMiddleware, limiter


app = FastAPI(title="Bidding Analyst Internal App", version="0.1.0")
logger = logging.getLogger(__name__)

# ─── 安全中间件（顺序很重要：先 CSRF，再安全头） ────────
app.add_middleware(CSRFTokenMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SlowAPIMiddleware)

# 注册速率限制超限处理器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
def startup() -> None:
    ensure_dirs()
    init_db()


# ─── 登录/登出 ──────────────────────────────────────────
@app.post("/api/login")
@limiter.limit("10/minute")
async def api_login(request: Request):
    import json
    body = await request.body()
    try:
        data = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="请求格式错误")
    username = data.get("username", "").strip()
    password = data.get("password", "")

    # 输入长度验证
    if len(username) > 100 or len(password) > 128:
        raise HTTPException(status_code=400, detail="账号或密码长度超出限制")

    if not username or not password:
        raise HTTPException(status_code=401, detail="账号或密码错误")

    if not verify_credentials(username, password):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token = create_session_token(username)
    resp = JSONResponse({"status": "ok", "username": username})
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
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


@app.get("/api/csrf-token")
def csrf_token(request: Request, response: Response) -> dict[str, str]:
    """返回 CSRF token，前端在 POST 请求前调用以获取 token。"""
    from .security import generate_csrf_token, CSRF_COOKIE_NAME
    token = generate_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        samesite="strict",
        secure=request.url.scheme == "https",
        path="/",
        max_age=86400,
    )
    return {"csrf_token": token}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.post("/api/projects")
def api_create_project(name: str = Form("未命名标书分析项目"), _: str = Depends(require_auth)) -> dict:
    project_id = uuid.uuid4().hex[:12]
    project_dir = PROJECTS_DIR / project_id
    try:
        for sub in ("uploads", "extracted", "reports", "logs"):
            (project_dir / sub).mkdir(parents=True, exist_ok=True)
        return create_project(project_id, name.strip() or "未命名标书分析项目")
    except OSError as exc:
        logger.exception("Failed to create project directories under %s", project_dir)
        raise HTTPException(
            status_code=500,
            detail="项目数据目录不可写，请检查 /app/data 挂载目录权限。",
        ) from exc
    except Exception as exc:
        logger.exception("Failed to create project record %s", project_id)
        if project_dir.exists():
            shutil.rmtree(project_dir, ignore_errors=True)
        raise HTTPException(
            status_code=500,
            detail="项目数据库写入失败，请检查 /app/data/app.db 权限。",
        ) from exc


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
    project_dir = PROJECTS_DIR / project_id
    try:
        if project_dir.exists():
            shutil.rmtree(project_dir)
    except OSError as exc:
        logger.exception("Failed to remove project directory %s", project_dir)
        raise HTTPException(
            status_code=500,
            detail="项目数据目录删除失败，请检查 /app/data/projects 权限。",
        ) from exc
    try:
        delete_project(project_id)
    except Exception as exc:
        logger.exception("Failed to delete project record %s", project_id)
        raise HTTPException(
            status_code=500,
            detail="项目数据库删除失败，请检查 /app/data/app.db 权限。",
        ) from exc
    return {"status": "deleted"}


# ─── 文件上传安全常量 ──────────────────────────────────
ALLOWED_EXTENSIONS = {".docx", ".pdf", ".txt", ".md"}
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_FILE_COUNT = 10


@app.post("/api/projects/{project_id}/files")
@limiter.limit("30/minute")
async def api_upload_files(project_id: str, request: Request, files: list[UploadFile] = File(...), _: str = Depends(require_auth)) -> dict:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 文件数量限制
    if len(files) > MAX_FILE_COUNT:
        raise HTTPException(status_code=400, detail=f"单次最多上传 {MAX_FILE_COUNT} 个文件")

    upload_dir = PROJECTS_DIR / project_id / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for upload in files:
        original = Path(upload.filename or "upload.bin").name
        suffix = Path(original).suffix.lower()

        # 服务端文件类型校验
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型：{suffix}。允许的类型：{', '.join(ALLOWED_EXTENSIONS)}",
            )

        # 文件名清洗：移除路径分隔符和危险字符，保留中文
        safe_name = "".join(c for c in original if c.isalnum() or c in "._-() （）（）" or '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')
        if not safe_name:
            safe_name = "upload.bin"
        stored_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        target = upload_dir / stored_name

        # 防止路径穿越（双重保险）
        try:
            target.resolve().relative_to(upload_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的文件名")

        # 写入文件并检查大小
        with target.open("wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)
        size = target.stat().st_size

        # 文件大小限制
        if size > MAX_UPLOAD_SIZE:
            target.unlink()  # 删除超大文件
            raise HTTPException(status_code=400, detail=f"文件 {safe_name} 超过大小限制（最大 50MB）")

        add_file(project_id, safe_name, stored_name, size)
        saved.append({"filename": safe_name, "size": size})
    return {"saved": saved}


@app.post("/api/projects/{project_id}/analyze")
@limiter.limit("10/minute")
def api_analyze_project(project_id: str, request: Request, background_tasks: BackgroundTasks, analyze_type: str = Query("general"), _: str = Depends(require_auth)) -> dict[str, str]:
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
def api_get_report(project_id: str, report_id: str, download: bool = Query(False), _: str = Depends(require_auth)) -> FileResponse:
    reports = list_reports(project_id)
    target = next((r for r in reports if str(r["id"]) == report_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="报告不存在")
    path = report_stored_path(project_id, target["stored_name"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="报告文件已丢失")
    if download:
        return FileResponse(path, media_type="text/html; charset=utf-8", filename=target["filename"])
    return FileResponse(path, media_type="text/html; charset=utf-8")


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
