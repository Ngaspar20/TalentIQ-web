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


def _call_grok(prompt: str, system: str) -> Optional[str]:
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=config.GROK_API_KEY,
            base_url=config.GROK_BASE_URL,
        )
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=config.GROK_MODEL,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Erro ao chamar Grok: {e}")
        return None


def _call_openai(prompt: str, system: str) -> Optional[str]:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Erro ao chamar OpenAI: {e}")
        return None


def engine_label() -> str:
    """Return a display label for the active engine."""
    labels = {
        "grok": "Grok (xAI)",
        "openai": "OpenAI GPT-4o",
        "deterministic": "Modo Determinístico",
    }
    return labels.get(config.LLM_ENGINE.lower(), config.LLM_ENGINE)
