from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from settings import settings


SESSION_COOKIE = "discovery_workspace"
SESSION_MAX_AGE = 60 * 60 * 24 * 30

RATE_LIMITS: Dict[Tuple[str, str], Tuple[int, int]] = {
    ("POST", "/documents/upload"): (6, 3600),
    ("POST", "/use-cases"): (30, 3600),
    ("POST", "/use-cases/discover"): (10, 3600),
    ("POST", "/gap-analysis"): (30, 3600),
    ("POST", "/generate-connectors"): (10, 3600),
    ("POST", "/validate"): (20, 3600),
    ("POST", "/integrations/llm/verify"): (20, 3600),
    ("DELETE", "/inventory"): (10, 3600),
}

_RATE_STATE: Dict[str, Deque[float]] = defaultdict(deque)


def _signing_key() -> bytes:
    if not settings.session_secret:
        raise RuntimeError("Workspace isolation requires a configured signing key.")
    return settings.session_secret.encode("utf-8")


def _signature(workspace_id: str) -> str:
    return hmac.new(_signing_key(), workspace_id.encode("utf-8"), hashlib.sha256).hexdigest()


def _encode_workspace(workspace_id: str) -> str:
    return f"{workspace_id}.{_signature(workspace_id)}"


def _decode_workspace(token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    workspace_id, supplied_signature = token.rsplit(".", 1)
    if len(workspace_id) != 32 or not all(ch in "0123456789abcdef" for ch in workspace_id.lower()):
        return None
    if not hmac.compare_digest(_signature(workspace_id), supplied_signature):
        return None
    return workspace_id


def _rate_limit_key(request: Request, workspace_id: str) -> str:
    client = request.client.host if request.client else "unknown"
    return f"{workspace_id}:{client}:{request.method}:{request.url.path}"


def _check_rate_limit(request: Request, workspace_id: str) -> tuple[bool, int]:
    if not settings.rate_limit_enabled:
        return True, 0
    limit_spec = RATE_LIMITS.get((request.method.upper(), request.url.path))
    if not limit_spec:
        return True, 0

    max_requests, window_seconds = limit_spec
    key = _rate_limit_key(request, workspace_id)
    now = time.monotonic()
    bucket = _RATE_STATE[key]
    while bucket and now - bucket[0] >= window_seconds:
        bucket.popleft()
    if len(bucket) >= max_requests:
        retry_after = max(1, int(window_seconds - (now - bucket[0])))
        return False, retry_after
    bucket.append(now)

    if len(_RATE_STATE) > 5000:
        for stale_key in list(_RATE_STATE.keys())[:1000]:
            if not _RATE_STATE[stale_key]:
                _RATE_STATE.pop(stale_key, None)
    return True, 0


def _apply_security_headers(response: Response, request_id: str) -> None:
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    if settings.is_production:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"


async def security_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or secrets.token_hex(12)
    workspace_id = "default"
    should_set_cookie = False

    if settings.workspace_isolation:
        existing = _decode_workspace(request.cookies.get(SESSION_COOKIE))
        workspace_id = existing or uuid4().hex
        should_set_cookie = existing is None

    request.state.workspace_id = workspace_id
    request.state.request_id = request_id

    allowed, retry_after = _check_rate_limit(request, workspace_id)
    if not allowed:
        response = JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded for this workspace. Please retry later.", "request_id": request_id},
            headers={"Retry-After": str(retry_after)},
        )
        _apply_security_headers(response, request_id)
        return response

    response = await call_next(request)
    if settings.workspace_isolation and should_set_cookie:
        response.set_cookie(
            SESSION_COOKIE,
            _encode_workspace(workspace_id),
            max_age=SESSION_MAX_AGE,
            httponly=True,
            secure=settings.is_production,
            samesite="lax",
            path="/",
        )
    _apply_security_headers(response, request_id)
    return response
