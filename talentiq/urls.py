from django.contrib import admin
from django.urls import path, include
from .dashboard import dashboard
from ajuda.views import ajuda_view
from .gestao_views import utilizadores_list, utilizador_novo, utilizador_toggle, utilizador_reset_password, minha_senha

urlpatterns = [
    path("admin/", admin.site.urls),
    path("gestao/utilizadores/", utilizadores_list, name="utilizadores_list"),
    path("gestao/utilizadores/novo/", utilizador_novo, name="utilizador_novo"),
    path("gestao/utilizadores/minha-senha/", minha_senha, name="minha_senha"),
    path("gestao/utilizadores/<uuid:pk>/toggle/", utilizador_toggle, name="utilizador_toggle"),
    path("gestao/utilizadores/<uuid:pk>/reset-password/", utilizador_reset_password, name="utilizador_reset_password"),
    path("accounts/", include("accounts.urls")),
    path("vagas/", include("vagas.urls")),
    path("candidatos/", include("candidatos.urls")),
    path("scoring/", include("scoring.urls")),
    path("pipeline/", include("pipeline.urls")),
    path("ajuda/", ajuda_view, name="ajuda"),
    path("", dashboard, name="dashboard"),
]
