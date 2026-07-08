from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from accounts.models import User, Organisation


def utilizadores_list(request):
    org = getattr(request.user, "organisation", None)
    utilizadores = User.objects.filter(organisation=org).order_by("email") if org else User.objects.none()
    return render(request, "gestao/utilizadores.html", {"utilizadores": utilizadores})


def utilizador_novo(request):
    org = getattr(request.user, "organisation", None)
    error = None
    if request.method == "POST":
        email = request.POST.get("email", "").lower().strip()
        password = request.POST.get("password", "")
        first_name = request.POST.get("first_name", "")
        last_name = request.POST.get("last_name", "")
        if User.objects.filter(email__iexact=email).exists():
            error = "Este email ja esta registado."
        elif len(password) < 8:
            error = "A palavra-passe deve ter pelo menos 8 caracteres."
        else:
            User.objects.create_user(
                username=email, email=email, password=password,
                first_name=first_name, last_name=last_name,
                organisation=org, role=User.ROLE_RECRUITER,
            )
            messages.success(request, f"Utilizador {email} criado com sucesso.")
            return redirect("/gestao/utilizadores/")
    return render(request, "gestao/novo_utilizador.html", {"error": error})


def utilizador_toggle(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == "POST" and user != request.user:
        user.is_active = not user.is_active
        user.save()
        status = "activado" if user.is_active else "bloqueado"
        messages.success(request, f"Utilizador {user.email} {status}.")
    return redirect("/gestao/utilizadores/")


def utilizador_reset_password(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == "POST" and user != request.user:
        new_password = "Demo2024!"
        user.set_password(new_password)
        user.save()
        messages.success(request, f"Senha de {user.email} reposta para: {new_password}")
    return redirect("/gestao/utilizadores/")
