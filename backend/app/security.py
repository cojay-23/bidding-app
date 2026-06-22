"""安全中间件模块 — 安全响应头、CSRF 保护、速率限制。"""

from __future__ import annotations

import secrets
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware


# ─── 速率限制器 ─────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


# ─── 安全响应头中间件 ───────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """为所有响应添加安全相关的 HTTP 头。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        headers = response.headers

        # 防止 MIME 类型嗅探
        headers.setdefault("X-Content-Type-Options", "nosniff")

        # 点击劫持保护
        headers.setdefault("X-Frame-Options", "DENY")

        # XSS 过滤器（旧浏览器）
        headers.setdefault("X-XSS-Protection", "1; mode=block")

        # HSTS（仅 HTTPS 环境下生效）
        if request.url.scheme == "https":
            headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains; preload",
            )

        # Referrer Policy
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

        # 权限策略 — 禁用不必要的浏览器功能
        headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )

        # Content Security Policy — 报告页面需要内联样式和脚本（图表/交互功能）
        # 开发环境下放宽 script-src，生产环境应收紧
        csp_parts = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "object-src 'none'",
        ]
        headers.setdefault("Content-Security-Policy", "; ".join(csp_parts))

        # 移除服务端信息泄露
        headers.setdefault("Server", "")

        return response


# ─── CSRF 保护 ──────────────────────────────────────────
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def generate_csrf_token() -> str:
    return secrets.token_hex(32)


class CSRFTokenMiddleware(BaseHTTPMiddleware):
    """基于双重提交 Cookie 模式的 CSRF 保护。

    非安全方法（POST/PUT/DELETE/PATCH）必须在请求头中携带 X-CSRF-Token，
    其值必须与 Cookie 中的 csrf_token 一致。
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 跳过不需要 CSRF 的路径
        if request.url.path in ("/api/health", "/favicon.ico", "/login", "/api/login", "/api/csrf-token"):
            return await call_next(request)

        # 安全方法（GET/HEAD/OPTIONS）不需要 CSRF 检查
        if request.method in CSRF_SAFE_METHODS:
            response = await call_next(request)
            # 确保响应中有 CSRF Cookie
            self._ensure_csrf_cookie(request, response)
            return response

        # 非安全方法：验证 CSRF token
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)

        if not cookie_token or not header_token:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token 验证失败：缺少 token"},
            )

        if not secrets.compare_digest(cookie_token, header_token):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token 验证失败：token 不匹配"},
            )

        response = await call_next(request)
        self._ensure_csrf_cookie(request, response)
        return response

    @staticmethod
    def _ensure_csrf_cookie(request: Request, response: Response) -> None:
        """确保响应中包含 CSRF Cookie。"""
        if CSRF_COOKIE_NAME not in request.cookies:
            token = generate_csrf_token()
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=token,
                httponly=False,  # 前端 JS 需要读取
                samesite="strict",
                secure=request.url.scheme == "https",
                path="/",
                max_age=86400,
            )
