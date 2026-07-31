from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from vagas.models import Vaga
from candidatos.models import Candidato


def relatorios(request):
    org = getattr(request.user, "organisation", None) if request.user.is_authenticated else None
    if not org:
        return render(request, "relatorios.html", {})

    now = timezone.now()
    all_cands = Candidato.objects.filter(organisation=org, vaga__isnull=False)
    open_vagas = Vaga.objects.filter(organisation=org, estado="Aberta").prefetch_related("candidatos")

    # ── VELOCIDADE ────────────────────────────────────────────────────────────
    # Average days candidates have been in each current stage (best proxy without stage history)
    def avg_days_in_stage(etapa):
        cands = all_cands.filter(etapa=etapa)
        if not cands.exists():
            return None
        days = [(now - c.updated_at).days for c in cands]
        return round(sum(days) / len(days))

    vel_triagem = avg_days_in_stage("Em Triagem")
    vel_entrevista = avg_days_in_stage("Entrevista")
    vel_proposta = avg_days_in_stage("Proposta")

    # Time-to-fill for hired candidates: vaga.created_at → candidato.updated_at
    hired = all_cands.filter(etapa="Contratado").select_related("vaga")
    ttf_list = [
        (c.updated_at - c.vaga.created_at).days
        for c in hired
        if c.vaga and c.updated_at > c.vaga.created_at
    ]
    avg_ttf = round(sum(ttf_list) / len(ttf_list)) if ttf_list else None

    # Slowest and fastest stages
    stage_times = {
        "Triagem": vel_triagem,
        "Entrevista": vel_entrevista,
        "Proposta": vel_proposta,
    }
    filled_stages = {k: v for k, v in stage_times.items() if v is not None}
    slowest = max(filled_stages, key=filled_stages.get) if filled_stages else None
    fastest = min(filled_stages, key=filled_stages.get) if filled_stages else None

    velocidade = {
        "triagem": vel_triagem,
        "entrevista": vel_entrevista,
        "proposta": vel_proposta,
        "avg_ttf": avg_ttf,
        "slowest": slowest,
        "slowest_days": filled_stages.get(slowest),
        "fastest": fastest,
        "fastest_days": filled_stages.get(fastest),
    }

    # Max days for bar width scaling
    max_vel = max((v for v in [vel_triagem, vel_entrevista, vel_proposta] if v), default=1)

    # ── CONVERSÃO POR VAGA ────────────────────────────────────────────────────
    conv_rows = []
    for v in open_vagas:
        cands = v.candidatos.all()
        total = cands.count()
        if total == 0:
            continue
        reached_triagem = cands.filter(etapa__in=["Em Triagem", "Entrevista", "Proposta", "Contratado"]).count()
        reached_entrevista = cands.filter(etapa__in=["Entrevista", "Proposta", "Contratado"]).count()
        reached_proposta = cands.filter(etapa__in=["Proposta", "Contratado"]).count()

        def pct(num, den):
            return round(num / den * 100) if den else None

        conv_rows.append({
            "vaga": v,
            "total": total,
            "cv_triagem": pct(reached_triagem, total),
            "triagem_entrevista": pct(reached_entrevista, reached_triagem) if reached_triagem else None,
            "entrevista_proposta": pct(reached_proposta, reached_entrevista) if reached_entrevista else None,
        })

    conv_rows.sort(key=lambda x: (x["cv_triagem"] or 0), reverse=True)

    return render(request, "relatorios.html", {
        "velocidade": velocidade,
        "max_vel": max_vel,
        "conv_rows": conv_rows,
    })
