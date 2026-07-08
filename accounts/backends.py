from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class EmailBackend(ModelBackend):
    """Authenticate using email (case-insensitive) instead of username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        if not username:
            return None
        try:
            user = User.objects.get(email__iexact=username.strip())
        except User.DoesNotExist:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
