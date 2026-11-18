"""线上演示的访问保护：一个共享密码 + 签名 Cookie。

APP_PASSWORD 为空时完全不启用（本地开发、测试）。启用后，除健康检查和登录接口外，
所有 /api 请求都要带有效 Cookie；EventSource 同源请求会自动带上它，SSE 也受保护。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.errors import ApiError
from app.schemas import ErrorResponse

COOKIE = "aps_session"
TTL_S = 7 * 24 * 3600
OPEN_PATHS = ("/api/health", "/api/auth/")
MAX_FAILS, WINDOW_S = 5, 600

router = APIRouter(prefix="/api/auth")


class LoginRequest(BaseModel):
    password: str


def _secret(app: FastAPI) -> bytes:
    if not getattr(app.state, "auth_secret", None):
        s = app.state.settings.app_secret or secrets.token_hex(32)
        app.state.auth_secret = hashlib.sha256(f"{s}:{app.state.settings.app_password}".encode()).digest()
    return app.state.auth_secret


def _sign(app: FastAPI, exp: int) -> str:
    return f"{exp}.{hmac.new(_secret(app), str(exp).encode(), hashlib.sha256).hexdigest()}"


def _valid(app: FastAPI, token: str | None) -> bool:
    if not token or "." not in token:
        return False
    exp, _, _sig = token.partition(".")
    return exp.isdigit() and int(exp) > time.time() and hmac.compare_digest(token, _sign(app, int(exp)))


def enabled(app: FastAPI) -> bool:
    return bool(app.state.settings.app_password)


def _client_ip(request: Request) -> str:
    # 线上在 Cloudflare 后面，真实 IP 在这个头里
    return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "?")


@router.get("/status")
async def status(request: Request):
    app = request.app
    return {"required": enabled(app), "authenticated": (not enabled(app)) or _valid(app, request.cookies.get(COOKIE))}


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response):
    app = request.app
    if not enabled(app):
        return {"ok": True}
    fails: dict[str, deque] = app.state.login_fails
    ip, now = _client_ip(request), time.time()
    q = fails[ip]
    while q and now - q[0] > WINDOW_S:
        q.popleft()
    if len(q) >= MAX_FAILS:
        raise ApiError(429, "TOO_MANY_ATTEMPTS", "密码错误次数过多，请 10 分钟后再试")
    if not hmac.compare_digest(body.password.encode(), app.state.settings.app_password.encode()):
        q.append(now)
        raise ApiError(401, "UNAUTHORIZED", "密码不正确")
    q.clear()
    exp = int(now) + TTL_S
    response.set_cookie(
        COOKIE, _sign(app, exp), max_age=TTL_S, httponly=True, samesite="lax",
        secure=app.state.settings.cookie_secure, path="/",
    )
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


def install(app: FastAPI) -> None:
    app.state.login_fails = defaultdict(deque)

    @app.middleware("http")
    async def require_login(request: Request, call_next):
        path = request.url.path
        if enabled(app) and path.startswith("/api/") and not path.startswith(OPEN_PATHS):
            if not _valid(app, request.cookies.get(COOKIE)):
                body = ErrorResponse(code="UNAUTHORIZED", message="请先输入访问密码").model_dump()
                return JSONResponse(status_code=401, content=body)
        return await call_next(request)

    app.include_router(router)
