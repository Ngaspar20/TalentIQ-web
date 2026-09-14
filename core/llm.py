# core/llm.py — Pluggable LLM client for TalentIQ
# Supports: grok | openai | deterministic
# Controlled entirely by config.LLM_ENGINE

import json
import logging
from typing import Optional
try:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import config
except Exception:
    from types import SimpleNamespace
    from django.conf import settings as _s
    config = SimpleNamespace(
        LLM_ENGINE=getattr(_s, "LLM_ENGINE", "deterministic"),
        GROK_API_KEY=getattr(_s, "GROK_API_KEY", ""),
        GROK_BASE_URL="https://api.x.ai/v1",
        GROK_MODEL="grok-3",
        OPENAI_API_KEY="",
        OPENAI_MODEL="gpt-4o",
    )

logger = logging.getLogger(__name__)


def get_llm_response(prompt: str, system: str = "") -> Optional[str]:
    """
    Send a prompt to the configured LLM and return the text response.
    Returns None if the call fails or engine is deterministic.
    """
    engine = config.LLM_ENGINE.lower()

    if engine == "deterministic":
        return None

    if engine == "grok":
        return _call_grok(prompt, system)

    if engine == "openai":
        return _call_openai(prompt, system)

    logger.warning(f"LLM engine desconhecido: {engine}. Usando modo determinístico.")
    return None


# Bulk CV upload fires one call per file back-to-back, which is exactly when
# providers answer 429. Without a retry that silently degrades the candidate
# to the keyword scorer, so retry transient failures with backoff.
_RETRY_ATTEMPTS = 4
_RETRY_BASE_SECONDS = 2.0
_TRANSIENT_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


def _is_transient(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status in _TRANSIENT_STATUS:
        return True
    name = type(exc).__name__
    if name in ("RateLimitError", "APITimeoutError", "APIConnectionError", "InternalServerError"):
        return True
    msg = str(exc).lower()
    return any(t in msg for t in ("rate limit", "too many requests", "timed out", "timeout",
                                  "temporarily", "overloaded", "connection"))


def _retry_after_seconds(exc: Exception, attempt: int) -> float:
    resp = getattr(exc, "response", None)
    headers = getattr(resp, "headers", None) or {}
    try:
        ra = float(headers.get("retry-after") or headers.get("Retry-After"))
        if 0 < ra <= 60:
            return ra
    except (TypeError, ValueError):
        pass
    return _RETRY_BASE_SECONDS * (2 ** attempt)


def _chat_with_retry(client, model: str, messages: list, label: str) -> Optional[str]:
    import time
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            response = client.chat.completions.create(
                model=model, messages=messages, temperature=0.2, timeout=90,
            )
            return response.choices[0].message.content
        except Exception as e:
            ultimo = attempt == _RETRY_ATTEMPTS - 1
            if ultimo or not _is_transient(e):
                logger.error(f"Erro ao chamar {label} (tentativa {attempt + 1}): {e}")
                return None
            espera = _retry_after_seconds(e, attempt)
            logger.warning(f"{label} falhou temporariamente ({e}); nova tentativa em {espera:.0f}s")
            time.sleep(espera)
    return None


def _messages(prompt: str, system: str) -> list:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


def _call_grok(prompt: str, system: str) -> Optional[str]:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.GROK_API_KEY, base_url=config.GROK_BASE_URL)
    except Exception as e:
        logger.error(f"Erro ao criar cliente Grok: {e}")
        return None
    return _chat_with_retry(client, config.GROK_MODEL, _messages(prompt, system), "Grok")


def _call_openai(prompt: str, system: str) -> Optional[str]:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
    except Exception as e:
        logger.error(f"Erro ao criar cliente OpenAI: {e}")
        return None
    return _chat_with_retry(client, config.OPENAI_MODEL, _messages(prompt, system), "OpenAI")


def engine_label() -> str:
    """Return a display label for the active engine."""
    labels = {
        "grok": "Grok (xAI)",
        "openai": "OpenAI GPT-4o",
        "deterministic": "Modo Determinístico",
    }
    return labels.get(config.LLM_ENGINE.lower(), config.LLM_ENGINE)
