from __future__ import annotations

import hmac
import secrets
import time
from typing import Any

from fastapi import Request, HTTPException, status
from itsdangerous import URLSafeSerializer, BadSignature

# ─── 配置 ───────────────────────────────────────────────
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "dJSK2o91D*"
SESSION_SECRET = secrets.token_hex(32)  # 每次启动随机生成，重启后已登录用户需重新登录
SESSION_TTL = 86400  # 24 小时（秒）
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
