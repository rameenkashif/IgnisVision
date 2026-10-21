from app.core.config import get_settings
from app.llm.base import LLMProvider, TemplateProvider

_provider: LLMProvider | None = None


def get_llm() -> LLMProvider:
    global _provider
    if _provider is None:
        s = get_settings()
        if s.llm_provider == "anthropic" and s.llm_api_key:
            from app.llm.anthropic_provider import AnthropicProvider

            _provider = AnthropicProvider(s.llm_api_key, s.llm_model)
        else:
            _provider = TemplateProvider()
    return _provider


def set_llm(provider: LLMProvider | None) -> None:
    """Test hook."""
    global _provider
    _provider = provider
