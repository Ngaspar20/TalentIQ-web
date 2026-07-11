import sys
import django
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.utils import timezone
from datetime import timedelta

from accounts.models import User, Organisation
from vagas.models import Vaga
from candidatos.models import Candidato


@login_required
def sistema_view(request):
    if not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    # DB health
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False

    now = timezone.now()
    ultimas_24h = now - timedelta(hours=24)
    ultimos_7d = now - timedelta(days=7)

    # Counts
    total_utilizadores = User.objects.count()
    total_vagas = Vaga.objects.count()
    vagas_abertas = Vaga.objects.filter(estado="Aberta").count()
    total_candidatos = Candidato.objects.count()
    candidatos_com_score = Candidato.objects.filter(score_fit__isnull=False).count()
    score_medio = None
    if candidatos_com_score:
        from django.db.models import Avg
        score_medio = Candidato.objects.filter(score_fit__isnull=False).aggregate(Avg("score_fit"))["score_fit__avg"]
        score_medio = round(score_medio, 1)

    # Recent logins
    ultimos_logins = User.objects.filter(
        last_login__isnull=False
    ).order_by("-last_login")[:8]

    # New users last 7 days
    novos_utilizadores = User.objects.filter(date_joined__gte=ultimos_7d).count()

    # New candidates last 7 days
    novos_candidatos = Candidato.objects.filter(created_at__gte=ultimos_7d).count()

    # System info
    python_version = sys.version.split(" ")[0]
    django_version = django.__version__

    ctx = {
        "db_ok": db_ok,
        "total_utilizadores": total_utilizadores,
        "total_vagas": total_vagas,
        "vagas_abertas": vagas_abertas,
        "total_candidatos": total_candidatos,
        "candidatos_com_score": candidatos_com_score,
        "score_medio": score_medio,
        "ultimos_logins": ultimos_logins,
        "novos_utilizadores": novos_utilizadores,
        "novos_candidatos": novos_candidatos,
        "python_version": python_version,
        "django_version": django_version,
        "now": now,
    }
    return render(request, "sistema/sistema.html", ctx)
