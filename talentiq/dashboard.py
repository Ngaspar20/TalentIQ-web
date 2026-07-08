from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from vagas.models import Vaga
from candidatos.models import Candidato


@login_required
def dashboard(request):
    org = request.user.organisation
    vagas = Vaga.objects.filter(organisation=org, estado="Aberta")
    candidatos = Candidato.objects.filter(organisation=org)
    contratados = candidatos.filter(etapa="Contratado").count()
    scores = [c.score_fit for c in candidatos if c.score_fit is not None]
    score_medio = round(sum(scores) / len(scores)) if scores else 0

    return render(request, "dashboard.html", {
        "total_vagas": vagas.count(),
        "total_candidatos": candidatos.count(),
        "total_contratados": contratados,
        "score_medio": score_medio,
    })
