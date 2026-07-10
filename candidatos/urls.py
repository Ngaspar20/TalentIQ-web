from django.urls import path
from . import views

urlpatterns = [
    path("", views.candidato_list, name="candidato_list"),
    path("carregar/", views.candidato_create, name="candidato_create"),
    path("<uuid:pk>/", views.candidato_detail, name="candidato_detail"),
    path("<uuid:pk>/editar/", views.candidato_edit, name="candidato_edit"),
    path("<uuid:pk>/eliminar/", views.candidato_delete, name="candidato_delete"),
    path("parse-cv/", views.parse_cv_view, name="parse_cv"),
    path("analyse-cv/", views.analyse_cv_view, name="analyse_cv"),
    path("<uuid:pk>/nota-entrevista/", views.guardar_nota_entrevista, name="guardar_nota_entrevista"),
    path("<uuid:pk>/carta/", views.gerar_carta, name="gerar_carta"),
    path("<uuid:pk>/carta/download/", views.download_carta, name="download_carta"),
]
