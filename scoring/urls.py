from django.urls import path
from . import views

urlpatterns = [
    path("", views.scoring_view, name="scoring"),
    path("<uuid:vaga_id>/", views.scoring_vaga, name="scoring_vaga"),
    path("calcular/", views.score_calculate, name="score_calculate"),
    path("exportar-excel/", views.exportar_excel, name="exportar_excel"),
    path("exportar-word/", views.exportar_word, name="exportar_word"),
    path("geral/", views.scoring_geral, name="scoring_geral"),
]
