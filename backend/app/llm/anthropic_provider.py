import logging

import anthropic

from app.llm.base import Lang, LLMUnavailable

log = logging.getLogger(__name__)


class AnthropicProvider:
    """Claude via the official SDK. The API key comes from settings and is never logged."""

    name = "anthropic"

    def __init__(self, api_key: str, model: str):
        self.model = model
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or None, timeout=60.0, max_retries=2
        )

    async def complete(self, system: str, messages: list[dict], max_tokens: int, lang: Lang) -> str:
        try:
            response = await self._client.beta.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                # If a safety classifier declines, the API retries on Anthropic's recommended
                # fallback model inside the same call.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as e:
            log.error("LLM authentication failed (check LLM_API_KEY)")
            raise LLMUnavailable("auth") from e
        except anthropic.RateLimitError as e:
            log.warning("LLM rate limited")
            raise LLMUnavailable("rate_limited") from e
        except anthropic.APIStatusError as e:
            log.warning("LLM API error %s", e.status_code)
            raise LLMUnavailable(f"status_{e.status_code}") from e
        except anthropic.APIConnectionError as e:
            log.warning("LLM unreachable")
            raise LLMUnavailable("connection") from e

        if response.stop_reason == "refusal":
            category = response.stop_details.category if response.stop_details else None
            log.warning("LLM declined (category=%s)", category)
            raise LLMUnavailable("refusal")
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if not text:
            raise LLMUnavailable("empty")
        return text
