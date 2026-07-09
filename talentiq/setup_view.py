from django.http import HttpResponse
from django.contrib.auth import get_user_model
from accounts.models import Organisation


def promote_all(request):
    User = get_user_model()
    email = "ngaspar10@gmail.com"
    password = "TalentIQ2024!"

    if not Organisation.objects.exists():
        org = Organisation.objects.create(name="TalentIQ Demo", slug="talentiq-demo")
    else:
        org = Organisation.objects.first()

    # Delete any existing user with this email (any username variant)
    User.objects.filter(email__iexact=email).delete()

    # Create fresh
    user = User.objects.create_superuser(
        username=email,
        email=email,
        password=password,
        organisation=org,
        role=User.ROLE_ADMIN,
    )

    all_users = User.objects.all().values("username", "email", "is_active", "is_superuser")
    lines = "".join(f"<li>{u}</li>" for u in all_users)

    return HttpResponse(
        f"<h2>Feito!</h2>"
        f"<p>Utilizador criado de raiz:</p>"
        f"<p><strong>Email:</strong> {email}</p>"
        f"<p><strong>Password:</strong> {password}</p>"
        f"<h3>Todos os utilizadores na BD:</h3><ul>{lines}</ul>"
        f"<br><a href='/accounts/login/'>Ir para Login</a>"
    )
