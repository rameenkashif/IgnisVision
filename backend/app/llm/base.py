"""LLM behind an interface (HANDOFF §10). Only for report narratives, trainer feedback and the
help assistant — never for alerts, voice guidance, zone status or RPI. Every caller has a
deterministic template fallback, so the app works with no LLM configured."""

from typing import Literal, Protocol

Lang = Literal["en", "ur"]


class LLMUnavailable(Exception):
    """Raised when the provider can't produce text; callers fall back to templates."""


class LLMProvider(Protocol):
    name: str

    async def complete(
        self, system: str, messages: list[dict], max_tokens: int, lang: Lang
    ) -> str: ...


class TemplateProvider:
    """Default: no network. Signals callers to use their own deterministic template."""

    name = "template"

    async def complete(self, system: str, messages: list[dict], max_tokens: int, lang: Lang) -> str:
        raise LLMUnavailable("no LLM configured")
