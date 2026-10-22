"""Optional in-app help assistant (HANDOFF §10.3): answers "how do I…" questions grounded in the
help page text the client sends. Off unless llm.features.help_assistant is on and an LLM is
configured; never used for alerts, zone status or RPI."""

import time
from collections import defaultdict, deque
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.deps import DB, CurrentUser
from app.core.errors import AppError
from app.llm.base import LLMUnavailable
from app.llm.registry import get_llm
from app.services import settings as settings_svc

router = APIRouter(prefix="/help", tags=["help"])
PER_MINUTE = 10
_recent: dict[str, deque[float]] = defaultdict(deque)

HELP_SYSTEM = (
    "You are the in-app help assistant of Ignis Vision, a decision-support web app used by "
    "Rescue 1122 (Pakistan) fire and rescue teams. Answer the user's question about HOW TO USE "
    "THE APP using ONLY the help text provided. If the help text does not cover it, say so "
    "briefly and suggest asking the system administrator. Never decide whether a zone is safe, "
    "who to rescue first or any other operational call: the app's outputs are decision support "
    "and the commander decides. Keep answers short (at most 6 sentences or a short list). "
    "Write in {language}."
)


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    topic: str | None = Field(default=None, max_length=40)
    context: str = Field(max_length=30_000, description="Help page text shown to the user")
    lang: Literal["en", "ur"] = "en"


class AskOut(BaseModel):
    answer: str


def _throttle(user_id: str) -> None:
    now = time.monotonic()
    q = _recent[user_id]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= PER_MINUTE:
        raise AppError(429, "too_many_requests")
    q.append(now)


@router.post("/ask", response_model=AskOut)
async def ask(body: AskIn, user: CurrentUser, db: DB) -> AskOut:
    flags = (await settings_svc.load_all(db))["llm.features"]
    llm = get_llm()
    if not flags.get("help_assistant") or llm.name == "template":
        raise AppError(409, "help_assistant_off")
    _throttle(str(user.id))
    language = "Urdu (اردو)" if body.lang == "ur" else "English"
    try:
        answer = await llm.complete(
            HELP_SYSTEM.format(language=language),
            [
                {
                    "role": "user",
                    "content": f"Help text (topic: {body.topic or 'general'}):\n{body.context}\n\n"
                    f"Question: {body.question}",
                }
            ],
            max_tokens=600,
            lang=body.lang,
        )
    except LLMUnavailable as e:
        raise AppError(503, "help_assistant_unavailable") from e
    return AskOut(answer=answer)
