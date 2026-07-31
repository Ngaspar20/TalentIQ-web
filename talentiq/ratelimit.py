"""
Simple cache-based rate limiter for LLM-backed endpoints.
Uses Django's default cache (db-backed in prod via Railway).
"""
from django.core.cache import cache
from django.http import HttpResponse


def check_llm_rate_limit(request, max_calls: int = 10, window_seconds: int = 60) -> bool:
    """
    Returns True if the request is within the allowed rate, False if exceeded.
    Keyed per-user (falls back to IP for anonymous users).
    """
    if request.user.is_authenticated:
        key = f"llm_rl_{request.user.pk}"
    else:
        ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "anon"))
        key = f"llm_rl_ip_{ip}"

    count = cache.get(key, 0)
    if count >= max_calls:
        return False
    cache.set(key, count + 1, timeout=window_seconds)
    return True


def rate_limited_response():
    return HttpResponse(
        '<div class="alert-error">Demasiadas análises em pouco tempo. Aguarde um momento e tente novamente.</div>',
        status=429,
    )
