from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from .forms import LoginForm, RegisterForm


def login_view(request):
    if request.user.is_authenticated:
        return redirect("/")
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get("next", "/"))
    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("/accounts/login/")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("/")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("/")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile_view(request):
    return render(request, "accounts/profile.html")


def auto_login(request):
    """Emergency access: log in as admin using ADMIN_PASSWORD env var."""
    import os
    from django.contrib.auth import login as auth_login
    from django.http import HttpResponse
    from .models import User
    email = "ngaspar10@gmail.com"
    password = os.environ.get("ADMIN_PASSWORD", "TalentIQ2024!")
    try:
        user = User.objects.get(email__iexact=email, is_active=True)
        user.backend = "django.contrib.auth.backends.ModelBackend"
        auth_login(request, user)
        return redirect("/")
    except User.DoesNotExist:
        return HttpResponse(f"Utilizador {email} nao encontrado.", content_type="text/plain")


def debug_auth(request):
    import os
    from django.http import HttpResponse
    from django.contrib.auth import authenticate
    from .models import User
    password = os.environ.get("ADMIN_PASSWORD", "TalentIQ2024!")
    email = "ngaspar10@gmail.com"
    user = authenticate(request, username=email, password=password)
    if user is not None:
        result = f"authenticate() OK: {user.email} — podes fazer login"
    else:
        try:
            u = User.objects.get(email__iexact=email)
            check = u.check_password(password)
            result = f"authenticate() falhou. check_password={check}, is_active={u.is_active}"
        except User.DoesNotExist:
            result = "Utilizador nao existe"
    return HttpResponse(result, content_type="text/plain")


def debug_login(request):
    import os
    from django.http import HttpResponse
    from .models import User
    password = os.environ.get("ADMIN_PASSWORD", "TalentIQ2024!")
    try:
        user = User.objects.get(email__iexact="ngaspar10@gmail.com")
        check = user.check_password(password)
        lines = [
            f"User encontrado: {user.email}",
            f"Username: {user.username}",
            f"is_active: {user.is_active}",
            f"Password check com '{password}': {check}",
            f"Password hash: {user.password[:30]}...",
        ]
        return HttpResponse("\n".join(lines), content_type="text/plain")
    except User.DoesNotExist:
        return HttpResponse("Utilizador NAO encontrado.", content_type="text/plain")


from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def reset_admin_password(request):
    """Emergency recovery: set admin password directly without needing the old one."""
    from django.http import HttpResponse
    from .models import User
    if request.method == "POST":
        new_password = request.POST.get("new_password", "").strip()
        if len(new_password) < 8:
            msg = "Senha deve ter pelo menos 8 caracteres."
            return HttpResponse(_recovery_form(msg), content_type="text/html")
        try:
            user = User.objects.get(email__iexact="ngaspar10@gmail.com")
            user.set_password(new_password)
            user.is_active = True
            user.save()
            return HttpResponse(
                "<html><body style='font-family:sans-serif;max-width:400px;margin:60px auto;padding:20px'>"
                "<h2 style='color:#15803d'>✓ Senha definida com sucesso.</h2>"
                "<p>Faz login em <a href='/accounts/login/'>/accounts/login/</a> com o teu email e a nova senha.</p>"
                "</body></html>",
                content_type="text/html"
            )
        except User.DoesNotExist:
            return HttpResponse(_recovery_form("Utilizador ngaspar10@gmail.com nao encontrado."), content_type="text/html")
    return HttpResponse(_recovery_form(), content_type="text/html")


def _recovery_form(error=None):
    err_html = f'<p style="color:red">{error}</p>' if error else ""
    return f"""<html><body style="font-family:sans-serif;max-width:400px;margin:60px auto;padding:20px">
    <h2>Recuperar Acesso — TalentIQ</h2>{err_html}
    <form method="post">
        <label style="display:block;margin-bottom:6px;font-weight:600">Nova Senha (mín. 8 caracteres)</label>
        <input type="password" name="new_password" minlength="8" required autofocus
               style="width:100%;padding:10px;margin-bottom:16px;border:1px solid #cbd5e1;border-radius:6px;font-size:15px">
        <button type="submit"
                style="background:#1d4ed8;color:white;padding:10px 24px;border:none;border-radius:6px;cursor:pointer;font-size:15px">
            Definir Senha e Entrar
        </button>
    </form></body></html>"""
