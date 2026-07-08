from django.http import HttpResponse
from django.contrib.auth import get_user_model
from accounts.models import Organisation


def promote_all(request):
    """One-time setup URL — promotes all users to superuser and resets passwords."""
    User = get_user_model()

    # If no users exist at all, create org + admin from scratch
    if not User.objects.exists():
        if not Organisation.objects.exists():
            org = Organisation.objects.create(name="TalentIQ Demo", slug="talentiq-demo")
        else:
            org = Organisation.objects.first()
        user = User.objects.create_superuser(
            username="admin@talentiq.app",
            email="admin@talentiq.app",
            password="TalentIQ2024!",
            organisation=org,
            role=User.ROLE_ADMIN,
        )
        return HttpResponse(
            "Created admin user.<br><br>"
            "<strong>Email:</strong> admin@talentiq.app<br>"
            "<strong>Password:</strong> TalentIQ2024!<br><br>"
            "Go to <a href='/accounts/login/'>Login</a>"
        )

    # Promote all existing users and reset their passwords
    new_password = "TalentIQ2024!"
    lines = []
    for user in User.objects.all():
        user.is_superuser = True
        user.is_staff = True
        user.set_password(new_password)
        user.save()
        lines.append(f"<li>{user.email} &rarr; password reset to <strong>{new_password}</strong></li>")

    html = (
        "<h2>Done!</h2><ul>" + "".join(lines) + "</ul>"
        "<br>Go to <a href='/accounts/login/'>Login</a> or "
        "<a href='/admin/'>Admin</a>"
    )
    return HttpResponse(html)
