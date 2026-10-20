import asyncio
import uuid

import jwt
from fastapi import WebSocket

from app.core.security import decode_access_token
from app.db.engine import SessionLocal
from app.models import User

AUTH_TIMEOUT_S = 10

# Application close codes (4000–4999).
UNAUTHORIZED = 4401
FORBIDDEN = 4403
NOT_FOUND = 4404


class WsReject(Exception):
    def __init__(self, code: int, reason: str):
        self.code = code
        self.reason = reason


async def authenticate(ws: WebSocket) -> User:
    """First message must be {"type": "auth", "token": "<access token>"} (never in the URL,
    which would end up in proxy logs)."""
    try:
        msg = await asyncio.wait_for(ws.receive_json(), AUTH_TIMEOUT_S)
    except (TimeoutError, ValueError) as e:
        raise WsReject(UNAUTHORIZED, "auth_required") from e
    if not isinstance(msg, dict) or msg.get("type") != "auth" or not msg.get("token"):
        raise WsReject(UNAUTHORIZED, "auth_required")
    try:
        claims = decode_access_token(str(msg["token"]))
    except jwt.ExpiredSignatureError as e:
        raise WsReject(UNAUTHORIZED, "token_expired") from e
    except jwt.InvalidTokenError as e:
        raise WsReject(UNAUTHORIZED, "invalid_token") from e
    async with SessionLocal() as db:
        user = await db.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active:
        raise WsReject(UNAUTHORIZED, "invalid_token")
    if user.must_change_password:
        raise WsReject(FORBIDDEN, "password_change_required")
    return user
