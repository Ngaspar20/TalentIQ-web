from django.urls import path
from . import views

urlpatterns = [
    path("", views.vaga_list, name="vaga_list"),
    path("criar/", views.vaga_create, name="vaga_create"),
    path("<uuid:pk>/", views.vaga_detail, name="vaga_detail"),
    path("<uuid:pk>/editar/", views.vaga_edit, name="vaga_edit"),
    path("<uuid:pk>/eliminar/", views.vaga_delete, name="vaga_delete"),
    path("parse-tor/", views.parse_tor_view, name="parse_tor"),
    path("analyse-tor/", views.analyse_tor_view, name="analyse_tor"),
    path("<uuid:pk>/perguntas-entrevista/", views.gerar_perguntas_entrevista, name="gerar_perguntas"),
    path("<uuid:pk>/perguntas-entrevista/download/", views.download_perguntas, name="download_perguntas"),
    path("<uuid:pk>/enviar-juri/", views.enviar_guiao_juri, name="enviar_guiao_juri"),
    path("<uuid:pk>/guiao/<uuid:session_id>/aprovar/", views.guiao_aprovar, name="guiao_aprovar"),
    path("<uuid:pk>/guiao/<uuid:session_id>/download/", views.guiao_download, name="guiao_download"),
    path("juri/<uuid:token>/", views.guiao_juri_view, name="guiao_juri"),
]
