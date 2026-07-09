from django.contrib.auth import get_user_model, login


class AutoLoginMiddleware:
    """Auto-login the first active user — no authentication required during demo phase."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            User = get_user_model()
            user = User.objects.filter(is_active=True).first()
            if user:
                user.backend = "django.contrib.auth.backends.ModelBackend"
                login(request, user)
        return self.get_response(request)
