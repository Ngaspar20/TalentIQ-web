from django.http import HttpResponse
from django.contrib.auth import get_user_model


def promote_all(request):
    """One-time URL to promote all users to superuser. Remove after use."""
    User = get_user_model()
    users = User.objects.all()
    if not users.exists():
        return HttpResponse("No users found. Please register first.", status=404)
    for user in users:
        user.is_superuser = True
        user.is_staff = True
        user.save()
    names = ", ".join(u.email for u in users)
    return HttpResponse(f"Done. Promoted: {names}. You can now log in at /admin/")
