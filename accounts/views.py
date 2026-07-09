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


def reset_admin_password(request):
    from django.http import HttpResponse
    from .models import User
    try:
        user = User.objects.get(email__iexact="ngaspar10@gmail.com")
        user.set_password("TalentIQ2024!")
        user.is_active = True
        user.save()
        return HttpResponse("Password reposta para TalentIQ2024! — Faz login agora.", content_type="text/plain")
    except User.DoesNotExist:
        return HttpResponse("Utilizador nao encontrado.", content_type="text/plain")
