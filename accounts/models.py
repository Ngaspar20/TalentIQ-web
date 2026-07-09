import uuid
import traceback
import logging
from django.contrib.auth.models import AbstractUser
from django.db import models

logger = logging.getLogger(__name__)


class Organisation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Organização"
        verbose_name_plural = "Organizações"

    def __str__(self):
        return self.name


class User(AbstractUser):
    ROLE_ADMIN = "admin"
    ROLE_RECRUITER = "recruiter"
    ROLE_VIEWER = "viewer"
    ROLE_CHOICES = [
        (ROLE_ADMIN, "Administrador"),
        (ROLE_RECRUITER, "Recrutador"),
        (ROLE_VIEWER, "Visualizador"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_RECRUITER)

    class Meta:
        verbose_name = "Utilizador"
        verbose_name_plural = "Utilizadores"

    def set_password(self, raw_password):
        logger.warning(
            "SET_PASSWORD CALLED for %s\n%s",
            getattr(self, 'email', 'unknown'),
            "".join(traceback.format_stack())
        )
        super().set_password(raw_password)

    def is_admin(self):
        return self.role == self.ROLE_ADMIN

    def is_viewer(self):
        return self.role == self.ROLE_VIEWER

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.organisation})"
