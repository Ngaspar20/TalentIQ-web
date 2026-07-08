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
]
