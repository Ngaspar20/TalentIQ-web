import uuid
from django.db import models
from django.conf import settings
from accounts.models import Organisation


class Vaga(models.Model):
    ESTADO_ABERTA = "Aberta"
    ESTADO_FECHADA = "Fechada"
    ESTADO_SUSPENSA = "Suspensa"
    ESTADO_CHOICES = [
        (ESTADO_ABERTA, "Aberta"),
        (ESTADO_FECHADA, "Fechada"),
        (ESTADO_SUSPENSA, "Suspensa"),
    ]

    MODALIDADE_CHOICES = [
        ("Presencial", "Presencial"),
        ("Remoto", "Remoto"),
        ("Híbrido", "Híbrido"),
    ]

    CONTRATO_CHOICES = [
        ("Tempo Inteiro", "Tempo Inteiro"),
        ("Tempo Parcial", "Tempo Parcial"),
        ("Consultoria", "Consultoria"),
        ("Estágio", "Estágio"),
    ]

    DEPARTAMENTO_CHOICES = [
        ("Recursos Humanos", "Recursos Humanos"),
        ("Tecnologia de Informação", "Tecnologia de Informação"),
        ("Finanças", "Finanças"),
        ("Operações", "Operações"),
        ("Saúde Pública", "Saúde Pública"),
        ("Marketing", "Marketing"),
        ("Vendas", "Vendas"),
        ("Outro", "Outro"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="vagas")
    titulo = models.CharField(max_length=255)
    organizacao = models.CharField(max_length=255, blank=True)
    departamento = models.CharField(max_length=100, choices=DEPARTAMENTO_CHOICES, default="Outro")
    local = models.CharField(max_length=255, blank=True)
    modalidade = models.CharField(max_length=50, choices=MODALIDADE_CHOICES, default="Presencial")
    nivel_formacao = models.CharField(max_length=100, blank=True)
    anos_experiencia_min = models.PositiveIntegerField(default=0)
    tipo_contrato = models.CharField(max_length=100, choices=CONTRATO_CHOICES, default="Tempo Inteiro")
    salario = models.CharField(max_length=100, blank=True)
    prazo_candidatura = models.CharField(max_length=100, blank=True)
    competencias_requeridas = models.JSONField(default=list)
    responsabilidades = models.JSONField(default=list)
    descricao = models.TextField(blank=True)
    estado = models.CharField(max_length=50, choices=ESTADO_CHOICES, default=ESTADO_ABERTA)
    tor_file_path = models.CharField(max_length=500, blank=True)
    origem = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="vagas_criadas"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Vaga"
        verbose_name_plural = "Vagas"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.titulo} ({self.organisation})"

    def short_id(self):
        return str(self.id)[:8]


class InterviewGuideSession(models.Model):
    ESTADO_PENDENTE = "pendente"
    ESTADO_SUBMETIDO = "submetido"
    ESTADO_APROVADO = "aprovado"
    ESTADO_CHOICES = [
        (ESTADO_PENDENTE, "Pendente"),
        (ESTADO_SUBMETIDO, "Submetido pelo Júri"),
        (ESTADO_APROVADO, "Aprovado"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    vaga = models.ForeignKey(Vaga, on_delete=models.CASCADE, related_name="guiao_sessions")
    texto_gerado = models.TextField()
    texto_editado = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDENTE)
    chair_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Guião {self.vaga.titulo} — {self.get_estado_display()}"

    def texto_final(self):
        return self.texto_editado or self.texto_gerado
