from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    """Only users with role=admin (or superusers) may access this view."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser or getattr(request.user, "role", None) == "admin":
            return view_func(request, *args, **kwargs)
        messages.error(request, "Não tem permissão para aceder a esta área.")
        return redirect("/")
    return wrapper


def recruiter_required(view_func):
    """Viewers (read-only role) are blocked; admins and recruiters may proceed."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        role = getattr(request.user, "role", None)
        if request.user.is_superuser or role in ("admin", "recruiter"):
            return view_func(request, *args, **kwargs)
        messages.error(request, "Não tem permissão para realizar esta acção.")
        return redirect(request.META.get("HTTP_REFERER", "/"))
    return wrapper
