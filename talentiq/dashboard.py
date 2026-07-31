from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from vagas.models import Vaga
from candidatos.models import Candidato


def dashboard(request):
    org = getattr(request.user, "organisation", None) if request.user.is_authenticated else None
    if not org:
        return render(request, "dashboard.html", {})

    now = timezone.now()
    open_vagas = Vaga.objects.filter(organisation=org, estado="Aberta").prefetch_related("candidatos")
    all_cands = Candidato.objects.filter(organisation=org, vaga__isnull=False)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total_vagas = open_vagas.count()
    total_candidatos = all_cands.count()
    contratados = all_cands.filter(etapa="Contratado").count()
    taxa_conversao = round(contratados / total_candidatos * 100) if total_candidatos else 0

    dias_list = [(now - v.created_at).days for v in open_vagas]
    media_dias = round(sum(dias_list) / len(dias_list)) if dias_list else 0

    # ── FUNNEL (current stage counts, excluding Rejeitado) ────────────────────
    active_cands = all_cands.exclude(etapa="Rejeitado")
    funnel = {
        "cvs": total_candidatos,
        "triagem": active_cands.filter(etapa="Em Triagem").count(),
        "entrevista": active_cands.filter(etapa="Entrevista").count(),
        "proposta": active_cands.filter(etapa="Proposta").count(),
        "contratado": contratados,
    }

    # ── ATTENTION ITEMS ───────────────────────────────────────────────────────
    atencao = []

    # Vagas paralidas: aberta > 20 dias, nenhum candidato em Entrevista/Proposta/Contratado
    for v in open_vagas:
        days_open = (now - v.created_at).days
        if days_open <= 20:
            continue
        advanced = v.candidatos.filter(etapa__in=["Entrevista", "Proposta", "Contratado"]).exists()
        if advanced:
            continue
        in_triagem = v.candidatos.filter(etapa="Em Triagem").count()
        if in_triagem == 0:
            continue
        atencao.append({
            "tipo": "red",
            "titulo": f"{v.titulo} — paralizada há {days_open} dias",
            "sub": f"{in_triagem} candidato{'s' if in_triagem != 1 else ''} em triagem sem nenhuma entrevista marcada",
            "link": f"/vagas/{v.pk}/",
            "link_label": "Ver candidatos",
            "age": f"{days_open}d aberta",
        })

    atencao.sort(key=lambda x: x["tipo"])  # red first

    # Propostas sem resposta > 7 dias
    for c in all_cands.filter(etapa="Proposta", updated_at__lt=now - timedelta(days=7)).select_related("vaga")[:3]:
        days = (now - c.updated_at).days
        atencao.append({
            "tipo": "amber",
            "titulo": f"{c.vaga.titulo if c.vaga else 'Vaga'} — proposta sem resposta",
            "sub": f"Proposta enviada a {c.nome} há {days} dias sem resposta registada",
            "link": f"/candidatos/{c.pk}/",
            "link_label": "Registar resposta",
            "age": f"{days}d",
        })

    # Candidatos em Entrevista > 14 dias sem progressão
    stalled_interviews = all_cands.filter(etapa="Entrevista", updated_at__lt=now - timedelta(days=14))
    count_stalled = stalled_interviews.count()
    if count_stalled > 0:
        oldest = stalled_interviews.order_by("updated_at").first()
        oldest_days = (now - oldest.updated_at).days
        atencao.append({
            "tipo": "amber",
            "titulo": f"{count_stalled} candidato{'s' if count_stalled != 1 else ''} aguarda{'m' if count_stalled != 1 else ''} decisão há mais de 14 dias",
            "sub": f"Em etapa de Entrevista sem progressão — o mais antigo há {oldest_days} dias",
            "link": "/pipeline/",
            "link_label": "Ver no pipeline",
            "age": f"{oldest_days}d",
        })

    # ── PER-VAGA TABLE ────────────────────────────────────────────────────────
    vaga_rows = []
    for v in open_vagas:
        cands = v.candidatos.all()
        scores = [c.score_fit for c in cands if c.score_fit is not None]
        vaga_rows.append({
            "vaga": v,
            "cvs": cands.count(),
            "triagem": cands.filter(etapa="Em Triagem").count(),
            "entrevista": cands.filter(etapa="Entrevista").count(),
            "proposta": cands.filter(etapa="Proposta").count(),
            "score_medio": round(sum(scores) / len(scores)) if scores else None,
            "days_open": (now - v.created_at).days,
        })
    vaga_rows.sort(key=lambda x: -x["days_open"])

    return render(request, "dashboard.html", {
        "total_vagas": total_vagas,
        "total_candidatos": total_candidatos,
        "taxa_conversao": taxa_conversao,
        "media_dias": media_dias,
        "funnel": funnel,
        "atencao": atencao,
        "vaga_rows": vaga_rows,
    })
