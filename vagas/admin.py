from django.contrib import admin
from .models import Vaga, InterviewGuideSession, ComiteSession, ComiteAvaliacao


@admin.register(Vaga)
class VagaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "organizacao", "localizacao", "estado", "created_at")
    list_filter = ("estado", "organizacao")
    search_fields = ("titulo", "organizacao")
    ordering = ("-created_at",)


@admin.register(InterviewGuideSession)
class InterviewGuideSessionAdmin(admin.ModelAdmin):
    list_display = ("vaga", "estado", "created_at")
    list_filter = ("estado",)
    ordering = ("-created_at",)


@admin.register(ComiteSession)
class ComiteSessionAdmin(admin.ModelAdmin):
    list_display = ("avaliador_nome", "avaliador_email", "vaga", "estado", "created_at")
    list_filter = ("estado",)
    search_fields = ("avaliador_nome", "avaliador_email")
    ordering = ("-created_at",)


@admin.register(ComiteAvaliacao)
class ComiteAvaliacaoAdmin(admin.ModelAdmin):
    list_display = ("candidato", "session", "pontuacao", "recomendacao")
    list_filter = ("recomendacao",)
