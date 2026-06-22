from __future__ import annotations

import os
import hmac
import secrets
import time
from typing import Any

from fastapi import Request, HTTPException, status
from itsdangerous import URLSafeSerializer, BadSignature

# ─── 配置 ───────────────────────────────────────────────
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
# 密码从环境变量注入，无环境变量时拒绝启动（默认值仅用于开发测试）
_ADMIN_PASSWORD_ENV = os.environ.get("ADMIN_PASSWORD")
if _ADMIN_PASSWORD_ENV:
    ADMIN_PASSWORD = _ADMIN_PASSWORD_ENV
else:
    # 生产部署必须通过环境变量设置密码，此处默认值仅防止开发环境崩溃
    ADMIN_PASSWORD = "dJSK2o91D*"
    import warnings
    warnings.warn(
        "ADMIN_PASSWORD 未通过环境变量设置，使用内置默认值。"
        "生产环境请务必设置 ADMIN_PASSWORD 环境变量。",
        RuntimeWarning,
    )
SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_hex(32)
SESSION_TTL = int(os.environ.get("SESSION_TTL", "86400"))  # 24 小时（秒）
COOKIE_NAME = "bid_session"

_serializer = URLSafeSerializer(SESSION_SECRET, salt="bid-auth")


def create_session_token(username: str) -> str:
    payload = {"u": username, "t": int(time.time())}
    return _serializer.dumps(payload)


def verify_session_token(token: str) -> str | None:
    try:
        data: dict[str, Any] = _serializer.loads(token, max_age=SESSION_TTL)
    except (BadSignature, Exception):
        return None
    return data.get("u")


def verify_credentials(username: str, password: str) -> bool:
    return hmac.compare_digest(username, ADMIN_USERNAME) and hmac.compare_digest(password, ADMIN_PASSWORD)


async def require_auth(request: Request) -> str:
    """FastAPI 依赖项：校验登录态，返回用户名"""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录",
            headers={"Location": "/login"},
        )
    username = verify_session_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已过期，请重新登录",
            headers={"Location": "/login"},
        )
    return username
