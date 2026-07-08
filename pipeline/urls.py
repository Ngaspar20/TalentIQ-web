from django.urls import path
from . import views

urlpatterns = [
    path("", views.pipeline_view, name="pipeline"),
    path("<uuid:vaga_id>/", views.pipeline_vaga, name="pipeline_vaga"),
    path("mover/", views.mover_etapa, name="mover_etapa"),
    path("exportar/", views.pipeline_export, name="pipeline_export"),
]
