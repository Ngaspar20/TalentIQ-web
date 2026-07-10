from django.contrib import admin
from .models import Candidato, NotaEntrevista, AvaliacaoSession


@admin.register(Candidato)
class CandidatoAdmin(admin.ModelAdmin):
    list_display = ("nome", "email", "vaga", "etapa", "score_fit", "created_at")
    list_filter = ("etapa", "vaga")
    search_fields = ("nome", "email")
    ordering = ("-created_at",)


@admin.register(NotaEntrevista)
class NotaEntrevistaAdmin(admin.ModelAdmin):
    list_display = ("candidato", "pontuacao", "recomendacao")
    list_filter = ("recomendacao",)


@admin.register(AvaliacaoSession)
class AvaliacaoSessionAdmin(admin.ModelAdmin):
    list_display = ("candidato", "estado", "created_at")
    list_filter = ("estado",)
    ordering = ("-created_at",)
