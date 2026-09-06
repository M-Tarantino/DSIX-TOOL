import os

from .base import ExtractionProvider, EXTRACTION_SYSTEM_PROMPT


def get_provider() -> ExtractionProvider:
    """Return the Stage 2 extraction provider selected via LLM_PROVIDER.

    LLM_PROVIDER=gemini      (default) -- precise extraction/scoring, requires GOOGLE_API_KEY
    LLM_PROVIDER=groq        -- FREE, unlimited, top-tier speed, requires GROQ_API_KEY
                                 (used as the Stage 1 gatekeeper by default -- see
                                 src/filters/groq_filter.py -- but selectable here too)
    LLM_PROVIDER=anthropic   -- paid, requires ANTHROPIC_API_KEY
    LLM_PROVIDER=openai      -- paid, requires OPENAI_API_KEY
    LLM_PROVIDER=ollama      -- local/on-premise, no API key needed
    """
    backend = os.environ.get("LLM_PROVIDER", "gemini").lower()
    if backend == "groq":
        from .groq_provider import GroqProvider

        return GroqProvider()
    if backend == "openai":
        from .openai_provider import OpenAIProvider

        return OpenAIProvider()
    if backend == "ollama":
        from .ollama_provider import OllamaProvider

        return OllamaProvider()
    if backend == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    # default to gemini (precise Stage 2 extraction, per architecture)
    from .gemini_provider import GeminiProvider

    return GeminiProvider()
