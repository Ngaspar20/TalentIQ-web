from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.db import connection
from .dashboard import dashboard
from ajuda.views import ajuda_view
from .gestao_views import utilizadores_list, utilizador_novo, utilizador_toggle, utilizador_reset_password, minha_senha, utilizador_apagar
from .system_views import sistema_view


def health_check(request):
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False
    status = 200 if db_ok else 503
    return JsonResponse({"status": "ok" if db_ok else "degraded", "db": db_ok}, status=status)


urlpatterns = [
    path("health/", health_check, name="health"),
    path("admin/", admin.site.urls),
    path("gestao/utilizadores/", utilizadores_list, name="utilizadores_list"),
    path("gestao/utilizadores/novo/", utilizador_novo, name="utilizador_novo"),
    path("gestao/utilizadores/minha-senha/", minha_senha, name="minha_senha"),
    path("gestao/utilizadores/<uuid:pk>/toggle/", utilizador_toggle, name="utilizador_toggle"),
    path("gestao/utilizadores/<uuid:pk>/reset-password/", utilizador_reset_password, name="utilizador_reset_password"),
    path("gestao/utilizadores/<uuid:pk>/apagar/", utilizador_apagar, name="utilizador_apagar"),
    path("accounts/", include("accounts.urls")),
    path("vagas/", include("vagas.urls")),
    path("candidatos/", include("candidatos.urls")),
    path("scoring/", include("scoring.urls")),
    path("pipeline/", include("pipeline.urls")),
    path("ajuda/", ajuda_view, name="ajuda"),
    path("sistema/", sistema_view, name="sistema"),
    path("", dashboard, name="dashboard"),
]
