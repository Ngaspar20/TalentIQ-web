import uuid
from django.db import models
from django.conf import settings
from accounts.models import Organisation
from vagas.models import Vaga


class Candidato(models.Model):
    ETAPA_CHOICES = [
        ("Candidatura Recebida", "Candidatura Recebida"),
        ("Em Triagem", "Em Triagem"),
        ("Entrevista", "Entrevista"),
        ("Proposta", "Proposta"),
        ("Contratado", "Contratado"),
        ("Rejeitado", "Rejeitado"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="candidatos")
    vaga = models.ForeignKey(Vaga, on_delete=models.SET_NULL, null=True, blank=True, related_name="candidatos")
    nome = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=50, blank=True)
    experiencia_anos = models.PositiveIntegerField(default=0)
    competencias = models.JSONField(default=list)
    formacao = models.JSONField(default=list)
    idiomas = models.JSONField(default=list)
    resumo = models.TextField(blank=True)
    etapa = models.CharField(max_length=100, choices=ETAPA_CHOICES, default="Candidatura Recebida")
    score_fit = models.PositiveIntegerField(null=True, blank=True)
    notas = models.TextField(blank=True)
    cv_file_path = models.CharField(max_length=500, blank=True)
    perfil_completo = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="candidatos_criados"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Candidato"
        verbose_name_plural = "Candidatos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.nome} — {self.vaga.titulo if self.vaga else 'Sem vaga'}"

    def short_id(self):
        return str(self.id)[:8]

    def score_label(self):
        if self.score_fit is None:
            return None
        if self.score_fit >= 75:
            return "alto"
        if self.score_fit >= 50:
            return "medio"
        return "baixo"


class AvaliacaoSession(models.Model):
    ESTADO_PENDENTE = "pendente"
    ESTADO_SUBMETIDA = "submetida"
    ESTADO_CONFIRMADA = "confirmada"
    ESTADO_CHOICES = [
        (ESTADO_PENDENTE, "Pendente"),
        (ESTADO_SUBMETIDA, "Submetida pelo Júri"),
        (ESTADO_CONFIRMADA, "Confirmada por HR"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    candidato = models.ForeignKey("Candidato", on_delete=models.CASCADE, related_name="avaliacao_sessions")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDENTE)
    pontuacao = models.PositiveSmallIntegerField(null=True, blank=True)
    recomendacao = models.CharField(max_length=20, blank=True)
    notas = models.TextField(blank=True)
    pontos_fortes = models.TextField(blank=True)
    pontos_fracos = models.TextField(blank=True)
    respostas_perguntas = models.JSONField(default=list)
    data_entrevista = models.DateField(null=True, blank=True)
    chair_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Avaliação {self.candidato.nome} — {self.get_estado_display()}"


class NotaEntrevista(models.Model):
    RECOMENDACAO_CHOICES = [
        ("recomendado", "Recomendado"),
        ("a_considerar", "A considerar"),
        ("nao_recomendado", "Não recomendado"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidato = models.OneToOneField(Candidato, on_delete=models.CASCADE, related_name="nota_entrevista")
    data_entrevista = models.DateField(null=True, blank=True)
    pontuacao = models.PositiveSmallIntegerField(null=True, blank=True, help_text="1–5")
    recomendacao = models.CharField(max_length=20, choices=RECOMENDACAO_CHOICES, blank=True)
    notas = models.TextField(blank=True)
    pontos_fortes = models.TextField(blank=True)
    pontos_fracos = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Entrevista — {self.candidato.nome}"
