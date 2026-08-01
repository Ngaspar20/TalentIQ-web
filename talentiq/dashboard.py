from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from vagas.models import Vaga, ComiteSession
from candidatos.models import Candidato


def _period_bounds(periodo, now):
    if periodo == "30d":
        start = now - timedelta(days=30)
        prev_start = now - timedelta(days=60)
        prev_end = start
    elif periodo == "1y":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_start = start.replace(year=start.year - 1)
        prev_end = start
    elif periodo == "all":
        return None, None, None
    else:  # 3m default
        start = now - timedelta(days=90)
        prev_start = now - timedelta(days=180)
        prev_end = start
    return start, prev_start, prev_end


def _delta(current, previous, good_when_up=True):
    if previous is None:
        return None
    diff = current - previous
    if diff > 0:
        return {"label": f"↑{diff}", "up": True, "down": False, "good": good_when_up}
    elif diff < 0:
        return {"label": f"↓{abs(diff)}", "up": False, "down": True, "good": not good_when_up}
    return {"label": "=", "up": False, "down": False, "good": True}


def dashboard(request):
    org = getattr(request.user, "organisation", None) if request.user.is_authenticated else None
    if not org:
        return render(request, "dashboard.html", {})

    now = timezone.now()
    modo = request.GET.get("modo", "recrutador")
    periodo = request.GET.get("periodo", "3m")

    start, prev_start, prev_end = _period_bounds(periodo, now)

    all_vagas = Vaga.objects.filter(organisation=org)
    open_vagas = all_vagas.filter(estado="Aberta").prefetch_related(
        "candidatos", "guiao_sessions", "comite_sessions"
    )
    all_cands = Candidato.objects.filter(organisation=org, vaga__isnull=False)

    # ── HERO KPIs ─────────────────────────────────────────────────────────────
    total_vagas = open_vagas.count()
    total_ativos = all_cands.exclude(etapa__in=["Rejeitado", "Contratado"]).count()
    total_contratados = all_cands.filter(etapa="Contratado").count()

    # Tempo médio para contratar: days from vaga created to candidate hired
    tempo_list = []
    for c in all_cands.filter(etapa="Contratado").select_related("vaga"):
        if c.vaga:
            d = (c.updated_at - c.vaga.created_at).days
            if 0 < d < 730:
                tempo_list.append(d)
    tempo_medio = round(sum(tempo_list) / len(tempo_list)) if tempo_list else 0

    total_all = all_vagas.count()
    fechadas = all_vagas.filter(estado="Fechada").count()
    taxa_preenchimento = round(fechadas / total_all * 100) if total_all else 0

    total_cands_all = all_cands.count()
    taxa_conversao = round(total_contratados / total_cands_all * 100) if total_cands_all else 0

    # Period-scoped for deltas
    if start:
        cands_period_count = all_cands.filter(created_at__gte=start).count()
        hired_period = all_cands.filter(etapa="Contratado", updated_at__gte=start).count()

        if prev_start:
            cands_prev_count = all_cands.filter(created_at__gte=prev_start, created_at__lt=prev_end).count()
            hired_prev = all_cands.filter(
                etapa="Contratado", updated_at__gte=prev_start, updated_at__lt=prev_end
            ).count()

            # Tempo médio for period vs prev period
            tempo_period = []
            for c in all_cands.filter(etapa="Contratado", updated_at__gte=start).select_related("vaga"):
                if c.vaga:
                    d = (c.updated_at - c.vaga.created_at).days
                    if 0 < d < 730:
                        tempo_period.append(d)
            tempo_period_avg = round(sum(tempo_period) / len(tempo_period)) if tempo_period else 0

            tempo_prev = []
            for c in all_cands.filter(etapa="Contratado", updated_at__gte=prev_start, updated_at__lt=prev_end).select_related("vaga"):
                if c.vaga:
                    d = (c.updated_at - c.vaga.created_at).days
                    if 0 < d < 730:
                        tempo_prev.append(d)
            tempo_prev_avg = round(sum(tempo_prev) / len(tempo_prev)) if tempo_prev else 0
        else:
            cands_prev_count = None
            hired_prev = None
            tempo_period_avg = tempo_medio
            tempo_prev_avg = None
    else:
        cands_period_count = total_cands_all
        hired_period = total_contratados
        cands_prev_count = None
        hired_prev = None
        tempo_period_avg = tempo_medio
        tempo_prev_avg = None

    delta_candidatos = _delta(cands_period_count, cands_prev_count, good_when_up=True)
    delta_contratados = _delta(hired_period, hired_prev, good_when_up=True)
    delta_tempo = _delta(tempo_period_avg, tempo_prev_avg, good_when_up=False)  # lower is better
    delta_preenchimento = _delta(taxa_preenchimento,
                                  round(fechadas / total_all * 100) if total_all else 0,
                                  good_when_up=True)

    # ── FUNNEL ────────────────────────────────────────────────────────────────
    all_active = all_cands.exclude(etapa="Rejeitado")
    f_cand = all_active.filter(etapa__in=["Candidatura Recebida", "Em Triagem", "Pré-Seleccionado"]).count()
    f_entrev = all_active.filter(etapa="Entrevista").count()
    f_prop = all_active.filter(etapa="Proposta").count()
    f_cont = all_active.filter(etapa="Contratado").count()

    funnel = [
        {
            "etapa": "Candidatura Recebida",
            "count": f_cand,
            "color": "#3b82f6",
            "conv_next": round(f_entrev / f_cand * 100) if f_cand else 0,
        },
        {
            "etapa": "Entrevista",
            "count": f_entrev,
            "color": "#f59e0b",
            "conv_next": round(f_prop / f_entrev * 100) if f_entrev else 0,
        },
        {
            "etapa": "Proposta",
            "count": f_prop,
            "color": "#06b6d4",
            "conv_next": round(f_cont / f_prop * 100) if f_prop else 0,
        },
        {
            "etapa": "Contratado",
            "count": f_cont,
            "color": "#10b981",
            "conv_next": None,
        },
    ]
    funnel_max = max(s["count"] for s in funnel) or 1

    # ── SCORE METRICS ─────────────────────────────────────────────────────────
    shortlist_scores = list(
        all_cands.filter(etapa__in=["Entrevista", "Proposta", "Contratado"], score_fit__isnull=False)
        .values_list("score_fit", flat=True)
    )
    score_medio_shortlist = round(sum(shortlist_scores) / len(shortlist_scores)) if shortlist_scores else None

    hired_scores = list(
        all_cands.filter(etapa="Contratado", score_fit__isnull=False).values_list("score_fit", flat=True)
    )
    score_medio_contratados = round(sum(hired_scores) / len(hired_scores)) if hired_scores else None

    all_scores = list(all_cands.filter(score_fit__isnull=False).values_list("score_fit", flat=True))
    score_dist = [
        {"label": "0–25%",    "count": sum(1 for s in all_scores if s <= 25),           "color": "#ef4444"},
        {"label": "26–50%",   "count": sum(1 for s in all_scores if 26 <= s <= 50),     "color": "#f59e0b"},
        {"label": "51–75%",   "count": sum(1 for s in all_scores if 51 <= s <= 75),     "color": "#3b82f6"},
        {"label": "76–100%",  "count": sum(1 for s in all_scores if s >= 76),           "color": "#10b981"},
    ]
    score_dist_max = max(d["count"] for d in score_dist) or 1

    # ── VAGAS EM RISCO ────────────────────────────────────────────────────────
    vagas_risco = []
    for v in open_vagas:
        days_open = (now - v.created_at).days
        if days_open < 15:
            continue
        has_progress = v.candidatos.filter(etapa__in=["Entrevista", "Proposta", "Contratado"]).exists()
        if has_progress:
            continue
        num_cands = v.candidatos.count()
        nivel = "critico" if days_open >= 30 else "aviso"
        motivo = (
            f"Nenhum candidato registado em {days_open} dias"
            if num_cands == 0
            else f"{num_cands} candidato{'s' if num_cands != 1 else ''} sem avançar para entrevista"
        )
        vagas_risco.append({"vaga": v, "days_open": days_open, "nivel": nivel, "motivo": motivo})
    vagas_risco.sort(key=lambda x: -x["days_open"])
    vagas_criticas_count = sum(1 for v in vagas_risco if v["nivel"] == "critico")
    vagas_aviso_count = sum(1 for v in vagas_risco if v["nivel"] == "aviso")

    # ── PENDING ACTIONS ───────────────────────────────────────────────────────
    acoes = []

    # 1. CVs without AI score
    for c in all_cands.filter(score_fit__isnull=True).select_related("vaga").order_by("created_at")[:8]:
        days = (now - c.created_at).days
        acoes.append({
            "icon": "fa-magnifying-glass",
            "color": "#8b5cf6",
            "titulo": f"CV de {c.nome} não analisado",
            "porque": f"Carregado há {days} dia{'s' if days != 1 else ''} sem scoring de IA",
            "link": f"/candidatos/{c.pk}/",
            "label": "Analisar agora",
            "urgencia": days,
        })

    # 2. ToR analyzed but not approved
    for v in all_vagas.filter(tor_analisado=True, tor_aprovado=False, estado="Aberta")[:5]:
        days = (now - v.updated_at).days
        acoes.append({
            "icon": "fa-file-circle-check",
            "color": "#f59e0b",
            "titulo": f"ToR de \"{v.titulo}\" aguarda aprovação",
            "porque": f"Análise IA concluída há {days} dia{'s' if days != 1 else ''} sem aprovação",
            "link": f"/vagas/{v.pk}/",
            "label": "Aprovar ToR",
            "urgencia": days,
        })

    # 3. Candidates in Entrevista but no guião sent
    for v in open_vagas:
        count_e = v.candidatos.filter(etapa="Entrevista").count()
        if count_e > 0 and not v.guiao_sessions.exists():
            acoes.append({
                "icon": "fa-clipboard-list",
                "color": "#06b6d4",
                "titulo": f"Guião em falta — {v.titulo}",
                "porque": f"{count_e} candidato{'s' if count_e != 1 else ''} em entrevista sem guião enviado ao júri",
                "link": f"/vagas/{v.pk}/",
                "label": "Enviar guião",
                "urgencia": 3,
            })

    # 4. Committee evaluations pending
    vaga_comite = {}
    for cs in ComiteSession.objects.filter(vaga__organisation=org, estado="pendente").select_related("vaga"):
        vk = str(cs.vaga.pk)
        if vk not in vaga_comite:
            total = ComiteSession.objects.filter(vaga=cs.vaga).count()
            vaga_comite[vk] = {"vaga": cs.vaga, "pendentes": 0, "total": total}
        vaga_comite[vk]["pendentes"] += 1

    for vk, info in vaga_comite.items():
        acoes.append({
            "icon": "fa-users",
            "color": "#ef4444",
            "titulo": f"Avaliação em falta — {info['vaga'].titulo}",
            "porque": f"{info['pendentes']} de {info['total']} avaliador{'es' if info['total'] != 1 else ''} ainda não submeteu",
            "link": f"/vagas/{info['vaga'].pk}/",
            "label": "Ver comité",
            "urgencia": 7,
        })

    acoes.sort(key=lambda x: -x["urgencia"])

    # ── PER-VAGA TABLE ────────────────────────────────────────────────────────
    vaga_rows = []
    for v in open_vagas:
        cands = v.candidatos.all()
        scores = [c.score_fit for c in cands if c.score_fit is not None]
        days_open = (now - v.created_at).days
        has_progress = cands.filter(etapa__in=["Entrevista", "Proposta", "Contratado"]).exists()
        if not has_progress and days_open >= 30:
            risco = "critico"
        elif not has_progress and days_open >= 15:
            risco = "aviso"
        else:
            risco = None
        vaga_rows.append({
            "vaga": v,
            "cvs": cands.count(),
            "candidatura": cands.filter(etapa__in=["Candidatura Recebida", "Em Triagem", "Pré-Seleccionado"]).count(),
            "entrevista": cands.filter(etapa="Entrevista").count(),
            "proposta": cands.filter(etapa="Proposta").count(),
            "contratados": cands.filter(etapa="Contratado").count(),
            "numero_vagas": v.numero_vagas,
            "score_medio": round(sum(scores) / len(scores)) if scores else None,
            "days_open": days_open,
            "prazo_data": v.prazo_data,
            "prazo_vencido": v.prazo_data and v.prazo_data < now.date(),
            "risco": risco,
        })
    vaga_rows.sort(key=lambda x: -x["days_open"])

    periodo_options = [
        ("30d", "Últimos 30 dias"),
        ("3m", "Últimos 3 meses"),
        ("1y", "Este ano"),
        ("all", "Todo o período"),
    ]

    return render(request, "dashboard.html", {
        "modo": modo,
        "periodo": periodo,
        "periodo_options": periodo_options,
        # Hero
        "total_vagas": total_vagas,
        "total_ativos": total_ativos,
        "total_contratados": total_contratados,
        "tempo_medio": tempo_medio,
        "taxa_preenchimento": taxa_preenchimento,
        "taxa_conversao": taxa_conversao,
        # Deltas
        "delta_candidatos": delta_candidatos,
        "delta_contratados": delta_contratados,
        "delta_tempo": delta_tempo,
        # Funnel
        "funnel": funnel,
        "funnel_max": funnel_max,
        # Scores
        "score_medio_shortlist": score_medio_shortlist,
        "score_medio_contratados": score_medio_contratados,
        "score_dist": score_dist,
        "score_dist_max": score_dist_max,
        # Risk
        "vagas_risco": vagas_risco,
        "vagas_criticas_count": vagas_criticas_count,
        "vagas_aviso_count": vagas_aviso_count,
        # Pending
        "acoes": acoes,
        "acoes_count": len(acoes),
        # Table
        "vaga_rows": vaga_rows,
    })
