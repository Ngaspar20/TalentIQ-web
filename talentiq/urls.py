from django.contrib import admin
from django.urls import path, include
from .dashboard import dashboard
from ajuda.views import ajuda_view
from .setup_view import promote_all

urlpatterns = [
    path("admin/", admin.site.urls),
    path("setup/promote/", promote_all, name="promote_all"),
    path("accounts/", include("accounts.urls")),
    path("vagas/", include("vagas.urls")),
    path("candidatos/", include("candidatos.urls")),
    path("scoring/", include("scoring.urls")),
    path("pipeline/", include("pipeline.urls")),
    path("ajuda/", ajuda_view, name="ajuda"),
    path("", dashboard, name="dashboard"),
]
