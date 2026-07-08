from django.http import HttpResponse
from django.contrib.auth import get_user_model
from accounts.models import Organisation


def promote_all(request):
    User = get_user_model()
    new_password = "TalentIQ2024!"
    email = "ngaspar10@gmail.com"

    # Ensure org exists
    if not Organisation.objects.exists():
        org = Organisation.objects.create(name="TalentIQ Demo", slug="talentiq-demo")
    else:
        org = Organisation.objects.first()

    # Get or create the user
    user, created = User.objects.get_or_create(
        email__iexact=email,
        defaults={
            "username": email,
            "email": email,
            "organisation": org,
            "role": User.ROLE_ADMIN,
            "is_superuser": True,
            "is_staff": True,
            "is_active": True,
        }
    )

    if not created:
        user.is_active = True
        user.is_superuser = True
        user.is_staff = True

    user.set_password(new_password)
    user.save()

    return HttpResponse(
        f"<h2>Done!</h2>"
        f"<p><strong>Email:</strong> {email}</p>"
        f"<p><strong>Password:</strong> {new_password}</p>"
        f"<br><a href='/accounts/login/'>Go to Login</a>"
    )
