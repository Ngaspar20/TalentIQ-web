import json
import sys
import os
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from accounts.decorators import recruiter_required
from .models import Vaga

# Make sure core/ is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


_ALLOWED_EXTENSIONS = (".pdf", ".docx", ".txt")
_MAGIC_SIGNATURES = {
    b"%PDF": "PDF",
    b"PK\x03\x04": "DOCX/ZIP",
}


def _validate_upload(uploaded_file):
    """Return an error string if the file is not an allowed type, else None."""
    name = uploaded_file.name.lower()
    if not any(name.endswith(ext) for ext in _ALLOWED_EXTENSIONS):
        return f"Tipo de ficheiro não permitido. Use PDF, DOCX ou TXT."
    header = uploaded_file.read(8)
    uploaded_file.seek(0)
    if name.endswith(".pdf") and not header.startswith(b"%PDF"):
        return "O ficheiro não é um PDF válido."
    if name.endswith(".docx") and not header.startswith(b"PK\x03\x04"):
        return "O ficheiro não é um DOCX válido. Ficheiros .doc antigos devem ser guardados como .docx."
    return None


def org_vagas(request):
    return Vaga.objects.filter(organisation=request.user.organisation)


def vaga_list(request):
    from django.utils import timezone
    vagas = org_vagas(request).order_by("-created_at")
    return render(request, "vagas/list.html", {"vagas": vagas, "today": timezone.now().date()})


@recruiter_required
def vaga_create(request):
    if request.method == "POST":
        titulo = request.POST.get("titulo", "").strip()
        if not titulo:
            messages.error(request, "O título da vaga é obrigatório.")
            return render(request, "vagas/create.html")

        competencias_raw = request.POST.get("competencias_input", "")
        competencias = [c.strip().lower() for c in competencias_raw.split(",") if c.strip()]

        responsabilidades_raw = request.POST.get("responsabilidades_input", "")
        responsabilidades = [r.strip().lstrip("•").strip() for r in responsabilidades_raw.splitlines() if r.strip()]

        tor_filename = request.POST.get("tor_filename", "").strip()
        tor_r2_url = request.POST.get("tor_r2_url", "").strip()
        tor_path = tor_r2_url or tor_filename

        vaga = Vaga.objects.create(
            organisation=request.user.organisation,
            titulo=titulo,
            organizacao=request.POST.get("organizacao", "").strip(),
            departamento=request.POST.get("departamento", "Outro"),
            local=request.POST.get("local", "").strip(),
            modalidade=request.POST.get("modalidade", "Presencial"),
            nivel_formacao=request.POST.get("nivel_formacao", "").lower(),
            anos_experiencia_min=int(request.POST.get("anos_experiencia_min", 0) or 0),
            tipo_contrato=request.POST.get("tipo_contrato", "Tempo Inteiro"),
            salario=request.POST.get("salario", "").strip(),
            prazo_candidatura=request.POST.get("prazo_candidatura", "").strip(),
            prazo_data=request.POST.get("prazo_data") or None,
            numero_vagas=int(request.POST.get("numero_vagas", 1) or 1),
            competencias_requeridas=competencias,
            responsabilidades=responsabilidades,
            descricao=request.POST.get("descricao", "").strip(),
            tor_file_path=tor_path,
            tor_aprovado=False,
            origem="ToR" if tor_path else "Manual",
            created_by=request.user,
        )
        messages.success(request, f"Vaga '{vaga.titulo}' criada com sucesso!")
        return redirect("vaga_list")

    return render(request, "vagas/create.html")


def vaga_detail(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    if vaga.modo_rapido:
        return redirect("avaliacao_rapida_detail", pk=pk)
    from candidatos.models import Candidato, AvaliacaoSession
    guiao_session = vaga.guiao_sessions.order_by("-created_at").first()

    todos = list(
        Candidato.objects
        .filter(vaga=vaga)
        .select_related("nota_entrevista")
        .order_by("-score_fit", "nome")
    )

    cands_triagem   = [c for c in todos if c.etapa in ("Candidatura Recebida", "Em Triagem")]
    cands_entrevista = [c for c in todos if c.etapa == "Entrevista"]
    cands_decisao   = [c for c in todos if c.etapa in ("Proposta", "Contratado", "Rejeitado")]

    # Build entrevista list with attached avaliacao_session (avoids underscore attr in templates)
    eval_session_map = {}
    if cands_entrevista:
        ids = [c.pk for c in cands_entrevista]
        for s in AvaliacaoSession.objects.filter(candidato_id__in=ids).order_by("candidato_id", "-created_at"):
            if s.candidato_id not in eval_session_map:
                eval_session_map[s.candidato_id] = s

    cands_entrevista_data = [
        {"candidato": c, "avaliacao_session": eval_session_map.get(c.pk),
         "nota": getattr(c, "nota_entrevista", None)}
        for c in cands_entrevista
    ]

    n_scored = sum(1 for c in todos if c.score_fit is not None)

    from .models import ComiteSession
    comite_sessions = list(vaga.comite_sessions.all())

    return render(request, "vagas/detail.html", {
        "vaga": vaga,
        "guiao_session": guiao_session,
        "cands_triagem": cands_triagem,
        "cands_entrevista_data": cands_entrevista_data,
        "cands_decisao": cands_decisao,
        "total_candidatos": len(todos),
        "n_entrevista": len(cands_entrevista),
        "n_scored": n_scored,
        "comite_sessions": comite_sessions,
    })


@require_POST
def vaga_marcar_notificacoes(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    vaga.notificacoes_enviadas = True
    vaga.save(update_fields=["notificacoes_enviadas"])
    messages.success(request, "Notificações marcadas como enviadas.")
    return redirect("vaga_detail", pk=pk)


@require_POST
def vaga_confirmar_analise(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    vaga.tor_analisado = True
    vaga.save(update_fields=["tor_analisado"])
    messages.success(request, "Análise IA confirmada. Pode agora aprovar os Termos de Referência.")
    if vaga.modo_rapido:
        return redirect("avaliacao_rapida_detail", pk=pk)
    return redirect("vaga_detail", pk=pk)


@require_POST
def vaga_aprovar_tor(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    vaga.tor_aprovado = True
    vaga.save(update_fields=["tor_aprovado"])
    messages.success(request, f"Termos de Referência de '{vaga.titulo}' aprovados.")
    if vaga.modo_rapido:
        return redirect("avaliacao_rapida_detail", pk=pk)
    return redirect("vaga_detail", pk=pk)


@recruiter_required
def vaga_edit(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    if request.method == "POST":
        titulo = request.POST.get("titulo", "").strip()
        if not titulo:
            messages.error(request, "O título da vaga é obrigatório.")
            return render(request, "vagas/edit.html", {"vaga": vaga})

        competencias_raw = request.POST.get("competencias_input", "")
        competencias = [c.strip().lower() for c in competencias_raw.split(",") if c.strip()]

        responsabilidades_raw = request.POST.get("responsabilidades_input", "")
        responsabilidades = [r.strip().lstrip("•").strip() for r in responsabilidades_raw.splitlines() if r.strip()]

        vaga.titulo = titulo
        vaga.organizacao = request.POST.get("organizacao", "").strip()
        vaga.departamento = request.POST.get("departamento", "Outro")
        vaga.local = request.POST.get("local", "").strip()
        vaga.modalidade = request.POST.get("modalidade", "Presencial")
        vaga.estado = request.POST.get("estado", "Aberta")
        vaga.nivel_formacao = request.POST.get("nivel_formacao", "").lower()
        vaga.anos_experiencia_min = int(request.POST.get("anos_experiencia_min", 0) or 0)
        vaga.tipo_contrato = request.POST.get("tipo_contrato", "Tempo Inteiro")
        vaga.salario = request.POST.get("salario", "").strip()
        vaga.prazo_candidatura = request.POST.get("prazo_candidatura", "").strip()
        vaga.prazo_data = request.POST.get("prazo_data") or None
        vaga.numero_vagas = int(request.POST.get("numero_vagas", 1) or 1)
        vaga.competencias_requeridas = competencias
        vaga.responsabilidades = responsabilidades
        vaga.descricao = request.POST.get("descricao", "").strip()
        vaga.save()
        messages.success(request, f"Vaga '{vaga.titulo}' actualizada.")
        return redirect("vaga_detail", pk=vaga.pk)

    return render(request, "vagas/edit.html", {"vaga": vaga})


@recruiter_required
def vaga_delete(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    if request.method == "POST":
        vaga.delete()
        messages.success(request, f"Vaga '{vaga.titulo}' eliminada.")
        return redirect("vaga_list")
    return render(request, "vagas/confirm_delete.html", {"vaga": vaga})


@require_POST
def parse_tor_view(request):
    """
    HTMX endpoint - called when user uploads a ToR file.
    Step 1: extract text and return preview.
    """
    from django.conf import settings
    uploaded = request.FILES.get("tor_file")
    if not uploaded:
        return HttpResponse('<div class="alert-error">Nenhum ficheiro recebido.</div>')

    err = _validate_upload(uploaded)
    if err:
        return HttpResponse(f'<div class="alert-error">{err}</div>')

    try:
        from core.parser import extract_text_from_file
        texto = extract_text_from_file(uploaded)
    except Exception as e:
        return HttpResponse(f'<div class="alert-error">Erro ao extrair texto: {e}</div>')

    if not texto.strip():
        return HttpResponse('<div class="alert-error">Não foi possível extrair texto. O ficheiro pode ser uma imagem digitalizada.</div>')

    from talentiq.storage import upload_to_r2
    r2_url = upload_to_r2(uploaded, "tor", uploaded.name)

    texto_preview = texto[:4000]
    return render(request, "vagas/_tor_preview.html", {
        "texto": texto_preview,
        "texto_completo": texto,
        "r2_url": r2_url,
    })


@require_POST
def analyse_tor_view(request):
    """
    HTMX endpoint — called when user clicks 'Analisar com IA'.
    Sends text to Grok and returns pre-filled form fields.
    """
    from talentiq.ratelimit import check_llm_rate_limit, rate_limited_response
    if not check_llm_rate_limit(request):
        return rate_limited_response()
    from django.conf import settings
    texto = request.POST.get("texto_completo", "")
    if not texto.strip():
        return HttpResponse('<div class="alert-error">Texto não encontrado. Carregue o ficheiro novamente.</div>')

    try:
        os.environ["GROK_API_KEY"] = settings.GROK_API_KEY
        os.environ["LLM_ENGINE"] = settings.LLM_ENGINE

        from core.parser import parse_tor
        extraido = parse_tor(texto)
    except Exception as e:
        return HttpResponse(f'<div class="alert-error">Erro na análise IA: {e}</div>')

    return render(request, "vagas/_form_fields.html", {
        "tor": extraido,
        "metodo": extraido.get("metodo_extracao", "IA"),
    })


def gerar_perguntas_entrevista(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)

    session_key = f"perguntas_{pk}"
    force_refresh = request.GET.get("refresh") == "1"

    if not force_refresh and session_key in request.session:
        texto = request.session[session_key]
        categorias_parsed = _parse_perguntas(texto)
        categorias = [{"nome": nome, "perguntas": rows} for nome, rows in categorias_parsed]
        return render(request, "vagas/perguntas_preview.html", {"vaga": vaga, "texto": texto, "categorias": categorias})

    from talentiq.ratelimit import check_llm_rate_limit, rate_limited_response
    if not check_llm_rate_limit(request):
        return rate_limited_response()

    competencias = ", ".join(vaga.competencias_requeridas) if vaga.competencias_requeridas else "nao especificadas"
    responsabilidades = "; ".join(vaga.responsabilidades) if vaga.responsabilidades else "nao especificadas"
    descricao = vaga.descricao or ""

    from core.llm import get_llm_response

    prompt = f"""Gera um guiao estruturado de perguntas de entrevista em portugues europeu para o cargo de {vaga.titulo}.

Informacao da vaga:
- Cargo: {vaga.titulo}
- Departamento: {vaga.departamento}
- Formacao minima: {vaga.nivel_formacao or 'nao especificada'}
- Experiencia minima: {vaga.anos_experiencia_min} anos
- Competencias requeridas: {competencias}
- Responsabilidades: {responsabilidades}
- Descricao: {descricao[:500] if descricao else 'nao disponivel'}

Usa EXACTAMENTE este formato para cada categoria e pergunta (sem adicionar mais texto):

TOTAL DE PERGUNTAS: exactamente 10, distribuidas assim:

## APRESENTACAO E MOTIVACAO
P: [pergunta completa]
A: [o que avaliar na resposta, em 1 frase]
P: [pergunta completa]
A: [o que avaliar na resposta, em 1 frase]

## EXPERIENCIA E HISTORIAL PROFISSIONAL
P: [pergunta completa]
A: [o que avaliar]
P: [pergunta completa]
A: [o que avaliar]

## COMPETENCIAS TECNICAS
P: [pergunta tecnica especifica ao cargo de {vaga.titulo}]
A: [o que avaliar]
P: [pergunta tecnica especifica ao cargo de {vaga.titulo}]
A: [o que avaliar]
P: [pergunta tecnica especifica ao cargo de {vaga.titulo}]
A: [o que avaliar]

## COMPETENCIAS COMPORTAMENTAIS
P: [pergunta comportamental]
A: [o que avaliar]
P: [pergunta comportamental]
A: [o que avaliar]

## SITUACOES HIPOTETICAS
P: [situacao hipotetica relevante para o cargo]
A: [o que avaliar]

## QUESTOES DO CANDIDATO
P: Dar espaco ao/a candidato/a para colocar questoes sobre o cargo e a organizacao.
A: Interesse genuino, qualidade e pertinencia das questoes colocadas."""

    system = "Es um especialista em recursos humanos e seleccao de pessoal. Escreve em portugues europeu formal. Segue o formato pedido rigorosamente."
    texto = get_llm_response(prompt, system)

    if not texto:
        if vaga.competencias_requeridas:
            c1 = vaga.competencias_requeridas[0]
            c2 = vaga.competencias_requeridas[1] if len(vaga.competencias_requeridas) > 1 else c1
            comp_perguntas = (
                f"P: Descreva a sua experiencia com {c1} e como a aplicou em contexto profissional.\n"
                f"A: Profundidade de conhecimento, exemplos concretos, relevancia para o cargo.\n"
                f"P: Como utilizaria {c2} nas responsabilidades diarias deste cargo?\n"
                f"A: Aplicacao pratica, raciocinio tecnico, alinhamento com a funcao.\n"
                f"P: Como se mantém actualizado/a nas tendencias da sua area profissional?\n"
                f"A: Curiosidade intelectual, iniciativa de aprendizagem continua.\n"
            )
        else:
            comp_perguntas = (
                "P: Quais sao as suas principais competencias tecnicas relevantes para este cargo?\n"
                "A: Alinhamento com os requisitos, profundidade de conhecimento.\n"
                "P: Descreva uma situacao em que teve de aprender rapidamente uma nova ferramenta ou metodologia.\n"
                "A: Capacidade de aprendizagem, adaptacao, proactividade.\n"
                "P: Como garante a qualidade do seu trabalho tecnico?\n"
                "A: Metodo, atencao ao detalhe, orientacao para resultados.\n"
            )

        texto = f"""## APRESENTACAO E MOTIVACAO
P: Apresente-se brevemente e descreva o seu percurso profissional.
A: Capacidade de sintese, clareza de comunicacao, coerencia do percurso.
P: O que o/a motivou a candidatar-se a este cargo na nossa organizacao?
A: Conhecimento da organizacao, motivacao genuina, alinhamento de valores.

## EXPERIENCIA E HISTORIAL PROFISSIONAL
P: Descreva a sua experiencia mais relevante para o cargo de {vaga.titulo}.
A: Alinhamento com os requisitos da vaga, profundidade e qualidade da experiencia.
P: Qual foi o maior desafio profissional que enfrentou e como o resolveu?
A: Capacidade de resolucao de problemas, resiliencia, aprendizagem com a experiencia.

## COMPETENCIAS TECNICAS
{comp_perguntas}
## COMPETENCIAS COMPORTAMENTAIS
P: Como gere situacoes de conflito com colegas ou superiores hierarquicos?
A: Inteligencia emocional, comunicacao assertiva, capacidade de mediar.
P: Descreva uma situacao em que teve de trabalhar sob pressao e com prazos apertados.
A: Resistencia ao stress, organizacao, capacidade de priorizar.

## SITUACOES HIPOTETICAS
P: Se tivesse de gerir varias tarefas urgentes em simultaneo, como procederia?
A: Gestao de prioridades, metodologia de trabalho, pedido de apoio quando necessario.

## QUESTOES DO CANDIDATO
P: Dar espaco ao/a candidato/a para colocar questoes sobre o cargo e a organizacao.
A: Interesse genuino, qualidade e pertinencia das questoes colocadas."""

    request.session[f"perguntas_{pk}"] = texto

    categorias_parsed = _parse_perguntas(texto)
    categorias = [
        {"nome": nome, "perguntas": rows}
        for nome, rows in categorias_parsed
    ]

    return render(request, "vagas/perguntas_preview.html", {
        "vaga": vaga,
        "texto": texto,
        "categorias": categorias,
    })


def enviar_guiao_juri(request, pk):
    """HR generates a tokenized link and sends to committee chair."""
    from talentiq.ratelimit import check_llm_rate_limit, rate_limited_response
    vaga = get_object_or_404(org_vagas(request), pk=pk)

    if request.method != "POST":
        return redirect("vaga_detail", pk=pk)
    if not check_llm_rate_limit(request):
        messages.error(request, "Demasiadas análises em pouco tempo. Aguarde um momento e tente novamente.")
        return redirect("vaga_detail", pk=pk)

    from core.llm import get_llm_response

    competencias = ", ".join(vaga.competencias_requeridas) if vaga.competencias_requeridas else "nao especificadas"
    responsabilidades = "; ".join(vaga.responsabilidades) if vaga.responsabilidades else "nao especificadas"
    descricao = vaga.descricao or ""

    prompt = f"""Gera um guiao estruturado de perguntas de entrevista em portugues europeu para o cargo de {vaga.titulo}.

Informacao da vaga:
- Cargo: {vaga.titulo}
- Departamento: {vaga.departamento}
- Formacao minima: {vaga.nivel_formacao or 'nao especificada'}
- Experiencia minima: {vaga.anos_experiencia_min} anos
- Competencias requeridas: {competencias}
- Responsabilidades: {responsabilidades}
- Descricao: {descricao[:500] if descricao else 'nao disponivel'}

TOTAL DE PERGUNTAS: exactamente 10, distribuidas assim:

## APRESENTACAO E MOTIVACAO
P: [pergunta completa]
A: [o que avaliar na resposta, em 1 frase]
P: [pergunta completa]
A: [o que avaliar na resposta, em 1 frase]

## EXPERIENCIA E HISTORIAL PROFISSIONAL
P: [pergunta completa]
A: [o que avaliar]
P: [pergunta completa]
A: [o que avaliar]

## COMPETENCIAS TECNICAS
P: [pergunta tecnica especifica ao cargo de {vaga.titulo}]
A: [o que avaliar]
P: [pergunta tecnica especifica ao cargo de {vaga.titulo}]
A: [o que avaliar]
P: [pergunta tecnica especifica ao cargo de {vaga.titulo}]
A: [o que avaliar]

## COMPETENCIAS COMPORTAMENTAIS
P: [pergunta comportamental]
A: [o que avaliar]
P: [pergunta comportamental]
A: [o que avaliar]

## SITUACOES HIPOTETICAS
P: [situacao hipotetica relevante para o cargo]
A: [o que avaliar]

## QUESTOES DO CANDIDATO
P: Dar espaco ao/a candidato/a para colocar questoes sobre o cargo e a organizacao.
A: Interesse genuino, qualidade e pertinencia das questoes colocadas."""

    system = "Es um especialista em recursos humanos e seleccao de pessoal. Escreve em portugues europeu formal. Segue o formato pedido rigorosamente."
    texto = get_llm_response(prompt, system) or _fallback_texto(vaga)

    chair_email = request.POST.get("chair_email", "").strip()

    from .models import InterviewGuideSession
    session = InterviewGuideSession.objects.create(
        vaga=vaga,
        texto_gerado=texto,
        chair_email=chair_email,
    )

    link = request.build_absolute_uri(f"/vagas/juri/{session.token}/")
    messages.success(request, f"Link gerado com sucesso.")
    return render(request, "vagas/guiao_link.html", {
        "vaga": vaga,
        "session": session,
        "link": link,
    })


def _fallback_texto(vaga):
    if vaga.competencias_requeridas:
        c1 = vaga.competencias_requeridas[0]
        c2 = vaga.competencias_requeridas[1] if len(vaga.competencias_requeridas) > 1 else c1
        comp = (
            f"P: Descreva a sua experiencia com {c1} e como a aplicou em contexto profissional.\n"
            f"A: Profundidade de conhecimento, exemplos concretos, relevancia para o cargo.\n"
            f"P: Como utilizaria {c2} nas responsabilidades diarias deste cargo?\n"
            f"A: Aplicacao pratica, raciocinio tecnico, alinhamento com a funcao.\n"
            f"P: Como se mantém actualizado/a nas tendencias da sua area profissional?\n"
            f"A: Curiosidade intelectual, iniciativa de aprendizagem continua.\n"
        )
    else:
        comp = (
            "P: Quais sao as suas principais competencias tecnicas relevantes para este cargo?\n"
            "A: Alinhamento com os requisitos, profundidade de conhecimento.\n"
            "P: Descreva uma situacao em que teve de aprender rapidamente uma nova ferramenta.\n"
            "A: Capacidade de aprendizagem, adaptacao, proactividade.\n"
            "P: Como garante a qualidade do seu trabalho tecnico?\n"
            "A: Metodo, atencao ao detalhe, orientacao para resultados.\n"
        )
    return f"""## APRESENTACAO E MOTIVACAO
P: Apresente-se brevemente e descreva o seu percurso profissional.
A: Capacidade de sintese, clareza de comunicacao, coerencia do percurso.
P: O que o/a motivou a candidatar-se a este cargo na nossa organizacao?
A: Conhecimento da organizacao, motivacao genuina, alinhamento de valores.

## EXPERIENCIA E HISTORIAL PROFISSIONAL
P: Descreva a sua experiencia mais relevante para o cargo de {vaga.titulo}.
A: Alinhamento com os requisitos da vaga, profundidade e qualidade da experiencia.
P: Qual foi o maior desafio profissional que enfrentou e como o resolveu?
A: Capacidade de resolucao de problemas, resiliencia, aprendizagem com a experiencia.

## COMPETENCIAS TECNICAS
{comp}
## COMPETENCIAS COMPORTAMENTAIS
P: Como gere situacoes de conflito com colegas ou superiores hierarquicos?
A: Inteligencia emocional, comunicacao assertiva, capacidade de mediar.
P: Descreva uma situacao em que teve de trabalhar sob pressao e com prazos apertados.
A: Resistencia ao stress, organizacao, capacidade de priorizar.

## SITUACOES HIPOTETICAS
P: Se tivesse de gerir varias tarefas urgentes em simultaneo, como procederia?
A: Gestao de prioridades, metodologia de trabalho, pedido de apoio quando necessario.

## QUESTOES DO CANDIDATO
P: Dar espaco ao/a candidato/a para colocar questoes sobre o cargo e a organizacao.
A: Interesse genuino, qualidade e pertinencia das questoes colocadas."""


def guiao_juri_view(request, token):
    """Public view for committee chair — no login required."""
    from .models import InterviewGuideSession
    session = get_object_or_404(InterviewGuideSession, token=token)

    if session.estado == InterviewGuideSession.ESTADO_APROVADO:
        return render(request, "vagas/guiao_juri_fechado.html", {"session": session})

    texto = session.texto_editado or session.texto_gerado
    categorias_parsed = _parse_perguntas(texto)
    categorias = [{"nome": nome, "perguntas": rows} for nome, rows in categorias_parsed]

    if request.method == "POST":
        cat_nomes = request.POST.getlist("cat_nome[]")
        perguntas = request.POST.getlist("pergunta[]")
        avaliar = request.POST.getlist("avaliar[]")
        cat_indices = request.POST.getlist("cat_index[]")

        linhas = []
        for nome in cat_nomes:
            linhas.append(f"## {nome}")
        texto_novo = _reconstruct_texto(cat_nomes, perguntas, avaliar, cat_indices)

        session.texto_editado = texto_novo
        session.estado = InterviewGuideSession.ESTADO_SUBMETIDO
        session.save()

        return render(request, "vagas/guiao_juri_obrigado.html", {"session": session})

    return render(request, "vagas/guiao_juri.html", {
        "session": session,
        "vaga": session.vaga,
        "categorias": categorias,
    })


def _reconstruct_texto(cat_nomes, perguntas, avaliar, cat_indices):
    """Rebuild P:/A: text from form POST data."""
    buckets = {i: [] for i in range(len(cat_nomes))}
    for i, (p, a) in enumerate(zip(perguntas, avaliar)):
        try:
            cat_i = int(cat_indices[i])
        except (IndexError, ValueError):
            cat_i = len(cat_nomes) - 1
        buckets[cat_i].append((p, a))

    lines = []
    for i, nome in enumerate(cat_nomes):
        lines.append(f"## {nome}")
        for p, a in buckets.get(i, []):
            if p.strip():
                lines.append(f"P: {p}")
                lines.append(f"A: {a}")
    return "\n".join(lines)


def guiao_aprovar(request, pk, session_id):
    """HR reviews and approves the chair's submitted guide."""
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    from .models import InterviewGuideSession
    session = get_object_or_404(InterviewGuideSession, pk=session_id, vaga=vaga)

    texto = session.texto_editado or session.texto_gerado
    categorias_parsed = _parse_perguntas(texto)
    categorias = [{"nome": nome, "perguntas": rows} for nome, rows in categorias_parsed]

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "aprovar":
            # Save any HR edits before approving
            cat_nomes = request.POST.getlist("cat_nome[]")
            perguntas_list = request.POST.getlist("pergunta[]")
            avaliar_list = request.POST.getlist("avaliar[]")
            cat_indices = request.POST.getlist("cat_index[]")
            if cat_nomes and perguntas_list:
                session.texto_editado = _reconstruct_texto(cat_nomes, perguntas_list, avaliar_list, cat_indices)
            session.estado = InterviewGuideSession.ESTADO_APROVADO
            session.save()
            messages.success(request, "Guião aprovado. Pode descarregá-lo no passo 7.")
            return redirect("vaga_detail", pk=pk)
        elif action == "devolver":
            session.estado = InterviewGuideSession.ESTADO_PENDENTE
            session.save()
            messages.info(request, "Guião devolvido ao presidente do júri para revisão.")
            return redirect("vaga_detail", pk=pk)

    return render(request, "vagas/guiao_aprovar.html", {
        "vaga": vaga,
        "session": session,
        "categorias": categorias,
    })


def guiao_download(request, pk, session_id):
    """Download approved guide as Word scoring table."""
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    from .models import InterviewGuideSession
    session = get_object_or_404(InterviewGuideSession, pk=session_id, vaga=vaga)

    if session.estado != InterviewGuideSession.ESTADO_APROVADO:
        messages.error(request, "O guião ainda não foi aprovado.")
        return redirect("vaga_detail", pk=pk)

    texto = session.texto_final()
    categorias = _parse_perguntas(texto)
    return _build_word_doc(vaga, categorias)


def _parse_perguntas(texto):
    """Parse structured interview guide text into list of (categoria, [(pergunta, avaliar)])."""
    categorias = []
    current_cat = None
    current_rows = []
    current_p = None

    for line in texto.split('\n'):
        line = line.strip()
        if line.startswith('## '):
            if current_cat is not None:
                if current_p:
                    current_rows.append((current_p, ''))
                    current_p = None
                categorias.append((current_cat, current_rows))
            current_cat = line[3:].strip()
            current_rows = []
            current_p = None
        elif line.startswith('P: ') or line.startswith('P:'):
            if current_p:
                current_rows.append((current_p, ''))
            current_p = line[2:].strip().lstrip(':').strip()
        elif line.startswith('A: ') or line.startswith('A:'):
            avaliar = line[2:].strip().lstrip(':').strip()
            if current_p:
                current_rows.append((current_p, avaliar))
                current_p = None
            else:
                current_rows.append(('', avaliar))

    if current_cat is not None:
        if current_p:
            current_rows.append((current_p, ''))
        categorias.append((current_cat, current_rows))

    return categorias


def _build_word_doc(vaga, categorias):
    from docx import Document as DocxDocument
    from docx.shared import Pt, Inches, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    import io

    doc = DocxDocument()
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

    org_name = vaga.organisation.name if vaga.organisation else "Organizacao"

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"GUIAO DE ENTREVISTA — {vaga.titulo.upper()}")
    run.bold = True
    run.font.size = Pt(13)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = p.add_run(f"{org_name}   |   Data: ___/___/______   |   Candidato/a: _______________________________")
    sub.font.size = Pt(9)
    sub.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    doc.add_paragraph()

    COL_NUM   = Cm(0.8)
    COL_PERG  = Cm(8.5)
    COL_AVAL  = Cm(4.5)
    COL_SCORE = Cm(1.5)
    COL_NOTAS = Cm(2.2)

    def set_cell_bg(cell, hex_color):
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), hex_color)
        tcPr.append(shd)

    def cell_para(cell, text, bold=False, size=9, align=WD_ALIGN_PARAGRAPH.LEFT, color=None):
        cell.text = ''
        p = cell.paragraphs[0]
        p.alignment = align
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(text)
        run.bold = bold
        run.font.size = Pt(size)
        if color:
            run.font.color.rgb = color

    for cat_name, rows in categorias:
        table = doc.add_table(rows=1, cols=5)
        table.style = 'Table Grid'
        table.autofit = False
        for i, w in enumerate([COL_NUM, COL_PERG, COL_AVAL, COL_SCORE, COL_NOTAS]):
            table.columns[i].width = w

        hdr_row = table.rows[0]
        hdr_row.cells[0].merge(hdr_row.cells[4])
        hdr_cell = hdr_row.cells[0]
        set_cell_bg(hdr_cell, '1E3A5F')
        cell_para(hdr_cell, cat_name, bold=True, size=10,
                  align=WD_ALIGN_PARAGRAPH.LEFT, color=RGBColor(0xFF, 0xFF, 0xFF))

        col_row = table.add_row()
        for i, label in enumerate(['#', 'Pergunta', 'O que avaliar', '1–5', 'Notas']):
            set_cell_bg(col_row.cells[i], 'D0DCF0')
            cell_para(col_row.cells[i], label, bold=True, size=8, align=WD_ALIGN_PARAGRAPH.CENTER)

        for idx, (pergunta, av) in enumerate(rows, 1):
            r = table.add_row()
            cell_para(r.cells[0], str(idx), align=WD_ALIGN_PARAGRAPH.CENTER)
            cell_para(r.cells[1], pergunta)
            cell_para(r.cells[2], av, color=RGBColor(0x44, 0x55, 0x66))
            cell_para(r.cells[3], '', align=WD_ALIGN_PARAGRAPH.CENTER)
            cell_para(r.cells[4], '')
            for cell in r.cells:
                for para in cell.paragraphs:
                    para.paragraph_format.space_before = Pt(4)
                    para.paragraph_format.space_after = Pt(4)

        doc.add_paragraph()

    p = doc.add_paragraph()
    run = p.add_run("Pontuação: 1 = Muito fraco   2 = Fraco   3 = Adequado   4 = Bom   5 = Excelente")
    run.font.size = Pt(8)
    run.font.italic = True
    run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    safe_titulo = vaga.titulo.replace(' ', '_')
    filename = f"guiao_entrevista_{safe_titulo}.docx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@require_POST
def comite_adicionar_avaliador(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    from .models import ComiteSession
    nome = request.POST.get("nome", "").strip()
    email = request.POST.get("email", "").strip()
    if not nome:
        messages.error(request, "O nome do avaliador é obrigatório.")
        return redirect("vaga_detail", pk=pk)
    if not email:
        messages.error(request, "O email do avaliador é obrigatório.")
        return redirect("vaga_detail", pk=pk)
    ComiteSession.objects.create(vaga=vaga, avaliador_nome=nome, avaliador_email=email)
    return redirect(f"/vagas/{pk}/?show_comite=1")


@require_POST
def comite_remover_avaliador(request, pk, session_pk):
    from .models import ComiteSession
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    session = get_object_or_404(ComiteSession, pk=session_pk, vaga=vaga)
    session.delete()
    messages.success(request, "Membro removido do comité.")
    return redirect("vaga_detail", pk=pk)


@require_POST
def comite_repor_avaliacao(request, pk, session_pk):
    from .models import ComiteSession, ComiteAvaliacao
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    session = get_object_or_404(ComiteSession, pk=session_pk, vaga=vaga)
    ComiteAvaliacao.objects.filter(session=session).delete()
    session.estado = ComiteSession.ESTADO_PENDENTE
    session.save(update_fields=["estado"])
    messages.success(request, f"Avaliação de {session.avaliador_nome} reposta. O membro pode voltar a preencher com o guião actualizado.")
    return redirect("vaga_detail", pk=pk)


def comite_avaliacao_view(request, token):
    from .models import ComiteSession, ComiteAvaliacao, InterviewGuideSession
    from candidatos.models import Candidato

    session = get_object_or_404(ComiteSession, token=token)
    vaga = session.vaga

    if vaga.avaliacao_encerrada:
        return render(request, "candidatos/avaliacao_fechada.html", {"session": session})

    secoes = []
    perguntas = []
    guiao = (InterviewGuideSession.objects
             .filter(vaga=vaga, estado=InterviewGuideSession.ESTADO_APROVADO)
             .order_by("-created_at").first())
    if guiao:
        import re
        current_secao = {"titulo": "", "perguntas": []}
        current_p = None
        current_criterio = ""
        for line in guiao.texto_final().splitlines():
            heading = re.match(r'^#{1,3}\s*(.+)', line) or re.match(r'^\*{1,2}(.+?)\*{1,2}\s*$', line)
            if heading:
                if current_p:
                    current_secao["perguntas"].append({"texto": current_p, "criterio": current_criterio})
                    perguntas.append(current_p)
                    current_p = None
                    current_criterio = ""
                if current_secao["perguntas"]:
                    secoes.append(current_secao)
                current_secao = {"titulo": heading.group(1).strip().rstrip(':'), "perguntas": []}
                continue
            p_match = re.match(r'^P:\s*(.+)', line)
            a_match = re.match(r'^A:\s*(.+)', line)
            if p_match:
                if current_p:
                    current_secao["perguntas"].append({"texto": current_p, "criterio": current_criterio})
                    perguntas.append(current_p)
                current_p = p_match.group(1).strip()
                current_criterio = ""
            elif a_match and current_p:
                current_criterio = a_match.group(1).strip()
                current_secao["perguntas"].append({"texto": current_p, "criterio": current_criterio})
                perguntas.append(current_p)
                current_p = None
                current_criterio = ""
        if current_p:
            current_secao["perguntas"].append({"texto": current_p, "criterio": current_criterio})
            perguntas.append(current_p)
        if current_secao["perguntas"]:
            secoes.append(current_secao)
        if not secoes and perguntas:
            secoes = [{"titulo": "Perguntas de Entrevista", "perguntas": [{"texto": q, "criterio": ""} for q in perguntas]}]
        # Add flat index so template can name fields c{pk}_resp_{idx}
        flat_idx = 0
        for s in secoes:
            for q_item in s["perguntas"]:
                q_item["idx"] = flat_idx
                flat_idx += 1

    candidatos = Candidato.objects.filter(vaga=vaga, etapa="Entrevista").order_by("nome")

    if request.method == "POST":
        for c in candidatos:
            p = request.POST.get(f"c{c.pk}_pontuacao", "")
            ComiteAvaliacao.objects.update_or_create(
                session=session, candidato=c,
                defaults={
                    "pontuacao": int(p) if p.isdigit() and 1 <= int(p) <= 5 else None,
                    "recomendacao": request.POST.get(f"c{c.pk}_recomendacao", ""),
                    "pontos_fortes": request.POST.get(f"c{c.pk}_pontos_fortes", "").strip(),
                    "pontos_fracos": request.POST.get(f"c{c.pk}_pontos_fracos", "").strip(),
                    "notas": request.POST.get(f"c{c.pk}_notas", "").strip(),
                    "data_entrevista": request.POST.get(f"c{c.pk}_data_entrevista") or None,
                    "respostas_perguntas": [
                        {
                            "pergunta": q,
                            "nota": request.POST.get(f"c{c.pk}_resp_{i}", "").strip(),
                            "score": request.POST.get(f"c{c.pk}_qscore_{i}", ""),
                        }
                        for i, q in enumerate(perguntas)
                    ],
                }
            )
        session.estado = ComiteSession.ESTADO_SUBMETIDO
        session.save(update_fields=["estado"])
        return render(request, "vagas/comite_obrigado.html", {"session": session, "vaga": vaga})

    existing = {a.candidato_id: a for a in ComiteAvaliacao.objects.filter(session=session)}
    return render(request, "vagas/comite_avaliacao.html", {
        "session": session,
        "vaga": vaga,
        "candidatos": candidatos,
        "secoes": secoes,
        "perguntas": perguntas,
        "guiao": guiao,
        "existing": existing,
    })


def comite_resultados(request, pk):
    from .models import ComiteSession, ComiteAvaliacao
    from candidatos.models import Candidato
    from collections import Counter

    vaga = get_object_or_404(org_vagas(request), pk=pk)
    sessions = list(vaga.comite_sessions.prefetch_related("avaliacoes__candidato").order_by("created_at"))
    candidatos = list(Candidato.objects.filter(vaga=vaga, etapa="Entrevista").order_by("nome"))

    matrix = []
    for c in candidatos:
        row = []
        scores = []
        recomendacoes = []
        for s in sessions:
            av = next((a for a in s.avaliacoes.all() if a.candidato_id == c.pk), None)
            row.append({"session": s, "av": av})
            if av:
                if av.pontuacao:
                    scores.append(av.pontuacao)
                if av.recomendacao:
                    recomendacoes.append(av.recomendacao)

        avg_score = round(sum(scores) / len(scores), 1) if scores else None
        rec_count = Counter(recomendacoes)
        consenso = rec_count.most_common(1)[0][0] if rec_count else None

        matrix.append({
            "candidato": c,
            "avaliacoes": row,
            "avg_score": avg_score,
            "rec_count": dict(rec_count),
            "consenso": consenso,
            "n_submetido": len(recomendacoes),
            "n_total": len(sessions),
        })

    return render(request, "vagas/comite_resultados.html", {
        "vaga": vaga,
        "sessions": sessions,
        "matrix": matrix,
    })


@require_POST
def comite_confirmar_decisoes(request, pk):
    from .models import ComiteSession, ComiteAvaliacao
    from candidatos.models import Candidato, NotaEntrevista
    from django.db import transaction
    from collections import defaultdict

    vaga = get_object_or_404(org_vagas(request), pk=pk)
    candidatos = Candidato.objects.filter(vaga=vaga, etapa="Entrevista")

    with transaction.atomic():
        for c in candidatos:
            avaliacoes = ComiteAvaliacao.objects.filter(
                session__vaga=vaga, session__estado=ComiteSession.ESTADO_SUBMETIDO, candidato=c
            )
            if not avaliacoes.exists():
                continue
            pontuacoes = [a.pontuacao for a in avaliacoes if a.pontuacao]
            media = round(sum(pontuacoes) / len(pontuacoes)) if pontuacoes else None
            recomendacoes = [a.recomendacao for a in avaliacoes if a.recomendacao]
            rec_final = max(set(recomendacoes), key=recomendacoes.count) if recomendacoes else ""
            notas_concat = "\n\n".join(
                f"[{a.session.avaliador_nome}]: {a.notas}" for a in avaliacoes if a.notas
            )
            NotaEntrevista.objects.update_or_create(
                candidato=c,
                defaults={"pontuacao": media, "recomendacao": rec_final, "notas": notas_concat}
            )
    Vaga.objects.filter(pk=pk).update(avaliacao_encerrada=True)
    messages.success(request, "Avaliações do comité consolidadas. Confirme agora a decisão final para cada candidato.")
    return redirect("vaga_detail", pk=pk)


@require_POST
def candidato_decisao_final(request, pk, candidato_pk):
    from candidatos.models import Candidato
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    candidato = get_object_or_404(Candidato, pk=candidato_pk, vaga=vaga)
    decisao = request.POST.get("decisao", "")
    etapa_map = {"contratar": "Proposta", "rejeitar": "Rejeitado", "considerar": "Entrevista"}
    nova_etapa = etapa_map.get(decisao)
    if nova_etapa:
        candidato.etapa = nova_etapa
        candidato.save(update_fields=["etapa"])
        messages.success(request, f"Decisão registada para {candidato.nome}.")
    return redirect("vaga_detail", pk=pk)


@require_POST
def enviar_avaliacao_grupo(request, pk):
    import uuid as _uuid
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    from candidatos.models import Candidato, AvaliacaoSession

    # Generate group token if not set
    if not vaga.avaliacao_group_token:
        vaga.avaliacao_group_token = _uuid.uuid4()
        vaga.save(update_fields=["avaliacao_group_token"])

    chair_email = request.POST.get("chair_email", "").strip()

    # Create AvaliacaoSession for every entrevista candidate that doesn't have one
    cands_entrevista = Candidato.objects.filter(
        vaga=vaga, organisation=request.user.organisation, etapa="Entrevista"
    )
    for c in cands_entrevista:
        if not AvaliacaoSession.objects.filter(candidato=c).exists():
            AvaliacaoSession.objects.create(candidato=c, chair_email=chair_email)
        elif chair_email:
            AvaliacaoSession.objects.filter(candidato=c).update(chair_email=chair_email)

    return redirect(f"/vagas/{pk}/?show_av_link=1")


def avaliacao_grupo_juri(request, token):
    from candidatos.models import AvaliacaoSession, Candidato
    from .models import InterviewGuideSession

    vaga = get_object_or_404(Vaga, avaliacao_group_token=token)

    if vaga.avaliacao_encerrada:
        return render(request, "candidatos/avaliacao_fechada.html", {"session": None})

    # Get interview questions from approved guide
    perguntas = []
    guiao = (InterviewGuideSession.objects
             .filter(vaga=vaga, estado=InterviewGuideSession.ESTADO_APROVADO)
             .order_by("-created_at").first())
    if guiao:
        import re
        current_p = None
        current_criterio = ""
        for line in guiao.texto_final().splitlines():
            p_match = re.match(r'^P:\s*(.+)', line.strip())
            a_match = re.match(r'^A:\s*(.+)', line.strip())
            if p_match:
                if current_p:
                    perguntas.append({"pergunta": current_p, "criterio": current_criterio})
                current_p = p_match.group(1).strip()
                current_criterio = ""
            elif a_match and current_p:
                current_criterio = a_match.group(1).strip()
                perguntas.append({"pergunta": current_p, "criterio": current_criterio})
                current_p = None
                current_criterio = ""
        if current_p:
            perguntas.append({"pergunta": current_p, "criterio": current_criterio})

    sessions = (AvaliacaoSession.objects
                .filter(candidato__vaga=vaga)
                .select_related("candidato")
                .order_by("candidato__nome"))

    if request.method == "POST":
        for session in sessions:
            if session.estado == AvaliacaoSession.ESTADO_CONFIRMADA:
                continue
            prefix = f"c{session.candidato.pk}_"
            p = request.POST.get(f"{prefix}pontuacao", "")
            session.pontuacao = int(p) if p.isdigit() and 1 <= int(p) <= 5 else None
            session.recomendacao = request.POST.get(f"{prefix}recomendacao", "")
            session.pontos_fortes = request.POST.get(f"{prefix}pontos_fortes", "").strip()
            session.pontos_fracos = request.POST.get(f"{prefix}pontos_fracos", "").strip()
            session.notas = request.POST.get(f"{prefix}notas", "").strip()
            session.data_entrevista = request.POST.get(f"{prefix}data_entrevista") or None
            respostas = []
            for i, item in enumerate(perguntas):
                nota = request.POST.get(f"{prefix}resp_{i}", "").strip()
                score_raw = request.POST.get(f"{prefix}qscore_{i}", "").strip()
                score = int(score_raw) if score_raw.isdigit() and 1 <= int(score_raw) <= 5 else None
                respostas.append({"pergunta": item["pergunta"], "criterio": item.get("criterio", ""), "score": score, "nota": nota})
            session.respostas_perguntas = respostas
            session.estado = AvaliacaoSession.ESTADO_SUBMETIDA
            session.save()
        return render(request, "candidatos/avaliacao_obrigado.html", {"session": sessions.first()})

    return render(request, "vagas/avaliacao_grupo_juri.html", {
        "vaga": vaga,
        "sessions": sessions,
        "perguntas": perguntas,
    })


@require_POST
def confirmar_avaliacoes_grupo(request, pk):
    from candidatos.models import AvaliacaoSession, Candidato, NotaEntrevista
    from django.db import transaction

    vaga = get_object_or_404(org_vagas(request), pk=pk)
    sessions = AvaliacaoSession.objects.filter(
        candidato__vaga=vaga,
        estado=AvaliacaoSession.ESTADO_SUBMETIDA
    ).select_related("candidato")

    with transaction.atomic():
        for session in sessions:
            candidato = session.candidato
            AvaliacaoSession.objects.filter(pk=session.pk).update(
                estado=AvaliacaoSession.ESTADO_CONFIRMADA
            )
            NotaEntrevista.objects.update_or_create(
                candidato=candidato,
                defaults={
                    "data_entrevista": session.data_entrevista,
                    "pontuacao": session.pontuacao,
                    "recomendacao": session.recomendacao,
                    "pontos_fortes": session.pontos_fortes,
                    "pontos_fracos": session.pontos_fracos,
                    "notas": session.notas,
                }
            )
            rec = session.recomendacao
            nova_etapa = "Proposta" if rec == "recomendado" else ("Rejeitado" if rec == "nao_recomendado" else candidato.etapa)
            Candidato.objects.filter(pk=candidato.pk).update(etapa=nova_etapa)

    Vaga.objects.filter(pk=pk).update(avaliacao_encerrada=True)
    messages.success(request, "Avaliações confirmadas. Os candidatos foram actualizados.")
    return redirect("vaga_detail", pk=pk)


def shortlist(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    from candidatos.models import Candidato
    candidatos_triagem = (
        Candidato.objects
        .filter(vaga=vaga)
        .exclude(etapa__in=["Entrevista", "Proposta", "Contratado", "Rejeitado"])
        .order_by("-score_fit", "nome")
    )
    candidatos_entrevista = (
        Candidato.objects
        .filter(vaga=vaga, etapa="Entrevista")
        .order_by("-score_fit", "nome")
    )
    return render(request, "vagas/shortlist.html", {
        "vaga": vaga,
        "candidatos_triagem": candidatos_triagem,
        "candidatos_entrevista": candidatos_entrevista,
    })


@require_POST
def mover_para_entrevista(request, pk, candidato_pk):
    from candidatos.models import Candidato
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    candidato = get_object_or_404(Candidato, pk=candidato_pk, vaga=vaga, organisation=request.user.organisation)
    if candidato.etapa not in ("Entrevista", "Proposta", "Contratado", "Rejeitado"):
        Candidato.objects.filter(pk=candidato.pk).update(etapa="Entrevista")
        messages.success(request, f"{candidato.nome} movido para Entrevista.")
    return redirect("shortlist", pk=pk)


def relatorio_selecao(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    from candidatos.models import Candidato, NotaEntrevista

    candidatos_avaliados = (
        Candidato.objects
        .filter(vaga=vaga)
        .exclude(etapa="Candidatura Recebida")
        .select_related("nota_entrevista")
        .order_by("-nota_entrevista__pontuacao", "-score_fit", "nome")
    )

    total_candidatos = Candidato.objects.filter(vaga=vaga).count()

    dados_candidatos = []
    candidato_selecionado = None
    for c in candidatos_avaliados:
        nota = getattr(c, "nota_entrevista", None)
        dado = {
            "pk": str(c.pk),
            "nome": c.nome,
            "etapa": c.etapa,
            "score_fit": c.score_fit,
            "pontuacao_entrevista": nota.pontuacao if nota else None,
            "recomendacao": nota.recomendacao if nota else "",
            "pontos_fortes": nota.pontos_fortes if nota else "",
            "pontos_fracos": nota.pontos_fracos if nota else "",
            "notas": nota.notas if nota else "",
            "experiencia_anos": c.experiencia_anos,
            "competencias": c.competencias,
        }
        dados_candidatos.append(dado)
        if c.etapa == "Contratado" and candidato_selecionado is None:
            candidato_selecionado = dado

    comite_sessions = list(vaga.comite_sessions.order_by("created_at"))
    narrativa = _gerar_narrativa_relatorio(vaga, dados_candidatos)

    return render(request, "vagas/relatorio_selecao.html", {
        "vaga": vaga,
        "candidatos": dados_candidatos,
        "narrativa": narrativa,
        "comite_sessions": comite_sessions,
        "candidato_selecionado": candidato_selecionado,
        "total_candidatos": total_candidatos,
    })


def relatorio_selecao_download(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    from candidatos.models import Candidato
    import io
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    candidatos_avaliados = (
        Candidato.objects
        .filter(vaga=vaga)
        .exclude(etapa__in=["Candidatura Recebida", "Em Triagem"])
        .select_related("nota_entrevista")
        .order_by("-nota_entrevista__pontuacao", "-score_fit", "nome")
    )

    dados_candidatos = []
    for c in candidatos_avaliados:
        nota = getattr(c, "nota_entrevista", None)
        dados_candidatos.append({
            "nome": c.nome,
            "etapa": c.etapa,
            "score_fit": c.score_fit,
            "pontuacao_entrevista": nota.pontuacao if nota else None,
            "recomendacao": nota.recomendacao if nota else "",
            "pontos_fortes": nota.pontos_fortes if nota else "",
            "pontos_fracos": nota.pontos_fracos if nota else "",
            "notas": nota.notas if nota else "",
            "experiencia_anos": c.experiencia_anos,
            "competencias": c.competencias,
        })

    narrativa = _gerar_narrativa_relatorio(vaga, dados_candidatos)

    doc = Document()

    # Title
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"Relatório de Seleção — {vaga.titulo}")
    run.bold = True
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(0x1E, 0x3A, 0x5F)

    from datetime import date
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run(f"Elaborado em {date.today().strftime('%d/%m/%Y')}")
    r2.font.size = Pt(10)
    r2.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    doc.add_paragraph()

    # Narrativa IA
    if narrativa:
        h = doc.add_paragraph()
        rh = h.add_run("Análise e Recomendação")
        rh.bold = True
        rh.font.size = Pt(12)
        rh.font.color.rgb = RGBColor(0x1E, 0x3A, 0x5F)
        for line in narrativa.split("\n"):
            if line.strip():
                doc.add_paragraph(line.strip())
        doc.add_paragraph()

    # Candidate summaries
    h2 = doc.add_paragraph()
    rh2 = h2.add_run("Resumo por Candidato")
    rh2.bold = True
    rh2.font.size = Pt(12)
    rh2.font.color.rgb = RGBColor(0x1E, 0x3A, 0x5F)

    REC_LABELS = {
        "recomendado": "Recomendado",
        "a_considerar": "A considerar",
        "nao_recomendado": "Não recomendado",
        "": "Sem avaliação",
    }
    STARS = {1: "★☆☆☆☆", 2: "★★☆☆☆", 3: "★★★☆☆", 4: "★★★★☆", 5: "★★★★★"}

    for idx, c in enumerate(dados_candidatos, 1):
        p_name = doc.add_paragraph()
        r_name = p_name.add_run(f"{idx}. {c['nome']}")
        r_name.bold = True
        r_name.font.size = Pt(11)

        meta_parts = []
        if c["pontuacao_entrevista"]:
            meta_parts.append(f"Entrevista: {STARS.get(c['pontuacao_entrevista'], '')} ({c['pontuacao_entrevista']}/5)")
        if c["score_fit"] is not None:
            meta_parts.append(f"Fit: {c['score_fit']}%")
        meta_parts.append(f"Etapa: {c['etapa']}")
        meta_parts.append(f"Recomendação: {REC_LABELS.get(c['recomendacao'], c['recomendacao'])}")
        doc.add_paragraph(" · ".join(meta_parts)).runs[0].font.size = Pt(9)

        if c["pontos_fortes"]:
            pf = doc.add_paragraph()
            pf.add_run("Pontos fortes: ").bold = True
            pf.add_run(c["pontos_fortes"])
        if c["pontos_fracos"]:
            pp = doc.add_paragraph()
            pp.add_run("Pontos fracos: ").bold = True
            pp.add_run(c["pontos_fracos"])
        if c["notas"]:
            pn = doc.add_paragraph()
            pn.add_run("Notas: ").bold = True
            pn.add_run(c["notas"])

        doc.add_paragraph()

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    safe_titulo = vaga.titulo.replace(" ", "_")
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response["Content-Disposition"] = f'attachment; filename="relatorio_selecao_{safe_titulo}.docx"'
    return response


def _gerar_narrativa_relatorio(vaga, dados_candidatos):
    """Call LLM to generate a selection narrative. Returns text or None."""
    from core.llm import get_llm_response

    if not dados_candidatos:
        return None

    candidatos_text = ""
    REC_PT = {"recomendado": "Recomendado", "a_considerar": "A considerar", "nao_recomendado": "Não recomendado"}
    for c in dados_candidatos:
        rec = REC_PT.get(c["recomendacao"], "Sem avaliação de júri")
        pts = f"Pontuação entrevista: {c['pontuacao_entrevista']}/5. " if c["pontuacao_entrevista"] else ""
        fit = f"Fit com vaga: {c['score_fit']}%. " if c["score_fit"] is not None else ""
        fortes = f"Pontos fortes: {c['pontos_fortes']}. " if c["pontos_fortes"] else ""
        fracos = f"Pontos fracos: {c['pontos_fracos']}. " if c["pontos_fracos"] else ""
        candidatos_text += f"\n- {c['nome']} ({rec}): {pts}{fit}{fortes}{fracos}"

    req_comp = ", ".join(vaga.competencias_requeridas[:8]) if vaga.competencias_requeridas else "não especificadas"

    prompt = f"""Vaga: {vaga.titulo}
Requisitos: {vaga.nivel_formacao or ''}, {vaga.anos_experiencia_min or 0} anos experiência mínima
Competências requeridas: {req_comp}

Candidatos avaliados em entrevista:{candidatos_text}

Escreve um relatório de seleção profissional e conciso em Português europeu com:
1. Sumário executivo (2–3 frases sobre o processo)
2. Comparação dos candidatos (pontos diferenciadores)
3. Recomendação final clara (quem deve ser contratado e porquê)

Tom profissional, directo, sem repetir dados já listados. Máximo 300 palavras."""

    return get_llm_response(prompt, system="És um especialista em recrutamento e seleção de recursos humanos.")


def download_perguntas(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)

    cat_nomes = request.POST.getlist("cat_nome[]")
    perguntas = request.POST.getlist("pergunta[]")
    avaliar_list = request.POST.getlist("avaliar[]")
    cat_indices = request.POST.getlist("cat_index[]")

    if cat_nomes and perguntas:
        texto = _reconstruct_texto(cat_nomes, perguntas, avaliar_list, cat_indices)
        categorias = _parse_perguntas(texto)
    else:
        texto = request.session.get(f"perguntas_{pk}", "")
        if not texto:
            return redirect("vaga_detail", pk=pk)
        categorias = _parse_perguntas(texto)

    if not categorias:
        return redirect("vaga_detail", pk=pk)

    return _build_word_doc(vaga, categorias)



# ---------------------------------------------------------------------------
# Avaliação Rápida
# ---------------------------------------------------------------------------

# Candidates at or above this score advance to the next phase
SCORE_APURADO_MIN = 80


def _apurados(candidatos):
    """Shortlist: at/above the threshold AND no essential criterion failed."""
    return [c for c in candidatos
            if (c.score_fit or 0) >= SCORE_APURADO_MIN
            and not (c.avaliacao_criterios or {}).get("essenciais_falhados")]


def _excluidos_por_essencial(candidatos):
    """Above the threshold on score, but blocked by a failed essential criterion."""
    return [c for c in candidatos
            if (c.score_fit or 0) >= SCORE_APURADO_MIN
            and (c.avaliacao_criterios or {}).get("essenciais_falhados")]


def avaliacao_rapida_list(request):
    from django.utils import timezone
    vagas = org_vagas(request).filter(modo_rapido=True).order_by("-created_at")
    return render(request, "avaliacao_rapida/list.html", {"vagas": vagas, "today": timezone.now().date()})


@recruiter_required
def avaliacao_rapida_create(request):
    if request.method == "POST":
        titulo = request.POST.get("titulo", "").strip()
        if not titulo:
            from django.contrib import messages as _msgs
            _msgs.error(request, "O título é obrigatório.")
            return render(request, "avaliacao_rapida/create.html")
        vaga = Vaga.objects.create(
            organisation=request.user.organisation,
            titulo=titulo,
            organizacao=request.POST.get("organizacao", "").strip(),
            modo_rapido=True,
            created_by=request.user,
        )
        return redirect("avaliacao_rapida_detail", pk=vaga.pk)
    return render(request, "avaliacao_rapida/create.html")


def avaliacao_rapida_detail(request, pk):
    vaga = get_object_or_404(org_vagas(request).filter(modo_rapido=True), pk=pk)
    from candidatos.models import Candidato
    candidatos = Candidato.objects.filter(vaga=vaga).order_by("-score_fit", "nome")
    n_scored = sum(1 for c in candidatos if c.score_fit is not None)
    if not vaga.tor_aprovado:
        step = 1
    elif not candidatos.exists():
        step = 2
    else:
        step = 2 if n_scored < candidatos.count() else 3
    return render(request, "avaliacao_rapida/detail.html", {
        "vaga": vaga,
        "candidatos": candidatos,
        "apurados": _apurados(candidatos),
        "excluidos_essencial": _excluidos_por_essencial(candidatos),
        "score_minimo": SCORE_APURADO_MIN,
        "categorias_criterio": CATEGORIAS_CRITERIO,
        "n_scored": n_scored,
        "step": step,
    })


CATEGORIAS_CRITERIO = [
    ("formacao", "Formação"),
    ("experiencia", "Experiência"),
    ("competencia", "Competência"),
    ("idioma", "Idioma"),
    ("outro", "Outro"),
]


@require_POST
def criterios_rapida(request, pk):
    """Save the recruiter-edited grelha de avaliação, or re-derive it from the ToR."""
    from django.conf import settings
    vaga = get_object_or_404(org_vagas(request).filter(modo_rapido=True), pk=pk)

    if request.POST.get("action") == "reextrair":
        from core.parser import extract_criterios
        os.environ["GROK_API_KEY"] = settings.GROK_API_KEY
        os.environ["LLM_ENGINE"] = settings.LLM_ENGINE
        vaga.criterios = extract_criterios(vaga.tor_texto or "", {
            "nivel_formacao": vaga.nivel_formacao,
            "anos_experiencia_min": vaga.anos_experiencia_min,
            "competencias_requeridas": vaga.competencias_requeridas,
        })
        vaga.save(update_fields=["criterios"])
        messages.success(request, f"Grelha reextraída do ToR ({len(vaga.criterios)} critérios).")
        return redirect("avaliacao_rapida_detail", pk=pk)

    validos = {k for k, _ in CATEGORIAS_CRITERIO}
    criterios = []
    for texto, cat, ess, peso in zip(
        request.POST.getlist("criterio"), request.POST.getlist("categoria"),
        request.POST.getlist("essencial"), request.POST.getlist("peso"),
    ):
        texto = texto.strip()
        if not texto:
            continue
        try:
            peso_int = max(1, min(5, int(peso)))
        except (TypeError, ValueError):
            peso_int = 3
        criterios.append({
            "criterio": texto[:300],
            "categoria": cat if cat in validos else "outro",
            "essencial": ess == "1",
            "peso": peso_int,
        })
    vaga.criterios = criterios[:20]
    vaga.save(update_fields=["criterios"])
    messages.success(
        request,
        f"Grelha de avaliação guardada ({len(vaga.criterios)} critérios). "
        "Use \"Reavaliar candidatos\" para aplicar a nova grelha aos CVs já carregados.",
    )
    return redirect("avaliacao_rapida_detail", pk=pk)


@require_POST
def reavaliar_rapida(request, pk):
    """Re-score every candidate of this vaga against the current grelha."""
    from candidatos.models import Candidato
    from candidatos.views import pontuar_candidato
    vaga = get_object_or_404(org_vagas(request).filter(modo_rapido=True), pk=pk)
    if not vaga.criterios:
        messages.error(request, "Não há grelha de avaliação. Defina os critérios primeiro.")
        return redirect("avaliacao_rapida_detail", pk=pk)
    ok, sem_texto, erros = 0, [], 0
    for c in Candidato.objects.filter(vaga=vaga):
        if not c.cv_texto:
            sem_texto.append(c.nome)
            continue
        try:
            pontuar_candidato(c)
            ok += 1
        except Exception:
            erros += 1
    msg = f"{ok} candidato(s) reavaliado(s) contra a grelha."
    if sem_texto:
        msg += (f" {len(sem_texto)} sem texto de CV guardado (carregados antes desta versão) — "
                f"volte a carregar o CV: {', '.join(sem_texto[:5])}"
                + ("…" if len(sem_texto) > 5 else "") + ".")
    if erros:
        msg += f" {erros} com erro."
    (messages.warning if (sem_texto or erros) else messages.success)(request, msg)
    return redirect("avaliacao_rapida_detail", pk=pk)


@require_POST
def upload_tor_rapida(request, pk):
    """JSON endpoint: upload + parse + auto-approve ToR for a modo_rapido vaga."""
    from django.http import JsonResponse
    from django.conf import settings
    vaga = get_object_or_404(org_vagas(request).filter(modo_rapido=True), pk=pk)
    uploaded = request.FILES.get("tor_file")
    if not uploaded:
        return JsonResponse({"ok": False, "error": "Nenhum ficheiro recebido."})
    allowed = [".pdf", ".docx", ".txt"]
    ext = os.path.splitext(uploaded.name)[1].lower()
    if ext not in allowed:
        return JsonResponse({"ok": False, "error": f"Formato não suportado: {ext}"})
    if uploaded.size > 20 * 1024 * 1024:
        return JsonResponse({"ok": False, "error": "Ficheiro demasiado grande (máx 20 MB)."})
    try:
        from core.parser import extract_text_from_file
        texto = extract_text_from_file(uploaded)
    except Exception as e:
        return JsonResponse({"ok": False, "error": f"Erro ao extrair texto: {e}"})
    texto = texto.replace('\x00', '')
    if not texto.strip():
        return JsonResponse({"ok": False, "error": "Não foi possível extrair texto do ficheiro."})
    from talentiq.storage import upload_to_r2
    r2_url = upload_to_r2(uploaded, "tor", uploaded.name) or ""
    os.environ["GROK_API_KEY"] = settings.GROK_API_KEY
    os.environ["LLM_ENGINE"] = settings.LLM_ENGINE
    try:
        from core.parser import parse_tor
        extraido = parse_tor(texto) or {}
    except Exception:
        extraido = {}
    try:
        from core.parser import extract_criterios
        criterios = extract_criterios(texto, extraido)
    except Exception:
        criterios = []
    update_fields = ["tor_file_path", "tor_texto", "criterios", "tor_analisado", "tor_aprovado"]
    vaga.tor_file_path = r2_url or uploaded.name
    vaga.tor_texto = texto
    vaga.criterios = criterios
    vaga.tor_analisado = True
    vaga.tor_aprovado = True
    if extraido.get("competencias_requeridas"):
        vaga.competencias_requeridas = extraido["competencias_requeridas"]
        update_fields.append("competencias_requeridas")
    if extraido.get("anos_experiencia_min") is not None:
        try:
            vaga.anos_experiencia_min = int(extraido["anos_experiencia_min"])
            update_fields.append("anos_experiencia_min")
        except (TypeError, ValueError):
            pass
    if extraido.get("nivel_formacao"):
        vaga.nivel_formacao = extraido["nivel_formacao"]
        update_fields.append("nivel_formacao")
    if extraido.get("responsabilidades"):
        vaga.responsabilidades = extraido["responsabilidades"]
        update_fields.append("responsabilidades")
    try:
        vaga.save(update_fields=update_fields)
    except Exception as e:
        return JsonResponse({"ok": False, "error": f"Erro ao guardar: {e}"})
    return JsonResponse({"ok": True})


_SNAPSHOT_VAGA_FIELDS = [
    "tor_file_path", "tor_texto", "criterios", "tor_analisado", "tor_aprovado",
    "competencias_requeridas", "responsabilidades", "nivel_formacao", "anos_experiencia_min",
]
_SNAPSHOT_CANDIDATO_FIELDS = [
    "id", "nome", "email", "telefone", "experiencia_anos", "competencias", "formacao",
    "idiomas", "resumo", "etapa", "score_fit", "notas", "motivo_rejeicao", "cv_file_path",
    "cv_texto", "avaliacao_criterios", "perfil_completo", "created_by_id", "created_at",
]


def _titulo_confirmado(request, vaga):
    return request.POST.get("confirm_titulo", "").strip().casefold() == vaga.titulo.strip().casefold()


@require_POST
def reiniciar_avaliacao_rapida(request, pk):
    """Snapshot the whole session, then clear it back to Step 1.

    The snapshot stays on the vaga until the next Reiniciar or a Restaurar,
    so a mistaken reset can be undone. Requires the position title typed
    back as confirmation.
    """
    import json
    from django.core.serializers.json import DjangoJSONEncoder
    from django.db import transaction
    from django.utils import timezone
    from candidatos.models import Candidato, CandidatoNota

    vaga = get_object_or_404(org_vagas(request).filter(modo_rapido=True), pk=pk)
    if not _titulo_confirmado(request, vaga):
        messages.error(request, "Reinício cancelado: o nome da posição não coincide.")
        return redirect("avaliacao_rapida_detail", pk=pk)

    candidatos = list(Candidato.objects.filter(vaga=vaga))
    notas = list(
        CandidatoNota.objects.filter(candidato__in=candidatos)
        .values("candidato_id", "texto", "criado_por_id", "criado_em")
    )
    agora = timezone.localtime()
    snapshot = {
        "criado_em": agora.isoformat(),
        "criado_em_display": agora.strftime("%d/%m/%Y %H:%M"),
        "vaga": {f: getattr(vaga, f) for f in _SNAPSHOT_VAGA_FIELDS},
        "candidatos": [{f: getattr(c, f) for f in _SNAPSHOT_CANDIDATO_FIELDS} for c in candidatos],
        "notas": notas,
    }
    # Round-trip so UUIDs and datetimes become JSON-safe before hitting the JSONField
    snapshot = json.loads(json.dumps(snapshot, cls=DjangoJSONEncoder))

    with transaction.atomic():
        Candidato.objects.filter(vaga=vaga).delete()
        vaga.ultimo_snapshot = snapshot
        vaga.tor_file_path = ""
        vaga.tor_texto = ""
        vaga.criterios = []
        vaga.tor_analisado = False
        vaga.tor_aprovado = False
        vaga.competencias_requeridas = []
        vaga.responsabilidades = []
        vaga.nivel_formacao = ""
        vaga.anos_experiencia_min = 0
        vaga.save(update_fields=_SNAPSHOT_VAGA_FIELDS + ["ultimo_snapshot"])

    messages.success(
        request,
        f"Avaliação reiniciada ({len(candidatos)} candidato(s) removidos). "
        "Se foi engano, use \"Restaurar última avaliação\".",
    )
    return redirect("avaliacao_rapida_detail", pk=pk)


@require_POST
def restaurar_avaliacao_rapida(request, pk):
    """Undo the last Reiniciar: bring back the ToR, grelha, candidates and their notes."""
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from candidatos.models import Candidato, CandidatoNota

    vaga = get_object_or_404(org_vagas(request).filter(modo_rapido=True), pk=pk)
    snap = vaga.ultimo_snapshot or {}
    if not snap:
        messages.error(request, "Não há avaliação anterior para restaurar.")
        return redirect("avaliacao_rapida_detail", pk=pk)

    # Authors may have been deleted since the snapshot; only keep FKs that still resolve.
    wanted = {c.get("created_by_id") for c in snap.get("candidatos", [])}
    wanted |= {n.get("criado_por_id") for n in snap.get("notas", [])}
    wanted.discard(None)
    existentes = {str(u) for u in get_user_model().objects.filter(pk__in=wanted).values_list("pk", flat=True)}

    def uid(v):
        return v if v is not None and str(v) in existentes else None

    restaurados, ja_existiam = 0, 0
    with transaction.atomic():
        for f, v in snap.get("vaga", {}).items():
            if f in _SNAPSHOT_VAGA_FIELDS:
                setattr(vaga, f, v)
        vaga.ultimo_snapshot = {}
        vaga.save(update_fields=_SNAPSHOT_VAGA_FIELDS + ["ultimo_snapshot"])

        skip = {"id", "created_by_id", "created_at"}
        for c in snap.get("candidatos", []):
            if Candidato.objects.filter(pk=c["id"]).exists():
                ja_existiam += 1
                continue
            data = {f: c.get(f) for f in _SNAPSHOT_CANDIDATO_FIELDS if f not in skip}
            obj = Candidato.objects.create(
                id=c["id"], organisation=vaga.organisation, vaga=vaga,
                created_by_id=uid(c.get("created_by_id")), **data,
            )
            if c.get("created_at"):
                Candidato.objects.filter(pk=obj.pk).update(created_at=c["created_at"])
            restaurados += 1

        for n in snap.get("notas", []):
            if not Candidato.objects.filter(pk=n["candidato_id"], vaga=vaga).exists():
                continue
            nota = CandidatoNota.objects.create(
                candidato_id=n["candidato_id"], texto=n["texto"],
                criado_por_id=uid(n.get("criado_por_id")),
            )
            if n.get("criado_em"):
                CandidatoNota.objects.filter(pk=nota.pk).update(criado_em=n["criado_em"])

    msg = f"Avaliação restaurada: ToR, grelha e {restaurados} candidato(s) repostos."
    if ja_existiam:
        msg += f" {ja_existiam} já existia(m) e foi/foram mantido(s)."
    messages.success(request, msg)
    return redirect("avaliacao_rapida_detail", pk=pk)


def avaliacao_rapida_relatorio(request, pk):
    vaga = get_object_or_404(org_vagas(request).filter(modo_rapido=True), pk=pk)
    from candidatos.models import Candidato
    from django.utils import timezone
    from django.conf import settings
    candidatos = list(Candidato.objects.filter(vaga=vaga).order_by("-score_fit", "nome"))
    narrativa = _gerar_narrativa_rapida(vaga, candidatos)
    return render(request, "avaliacao_rapida/relatorio.html", {
        "vaga": vaga,
        "candidatos": candidatos,
        "apurados": _apurados(candidatos),
        "excluidos_essencial": _excluidos_por_essencial(candidatos),
        "score_minimo": SCORE_APURADO_MIN,
        "today": timezone.now().date(),
        "narrativa": narrativa,
    })


def _gerar_narrativa_rapida(vaga, candidatos):
    """Generate a Portuguese narrative assessment report using the LLM, with deterministic fallback."""
    from django.conf import settings
    if not candidatos:
        return ""
    os.environ["GROK_API_KEY"] = settings.GROK_API_KEY
    os.environ["LLM_ENGINE"] = settings.LLM_ENGINE
    tor_excerpt = (vaga.tor_texto or "")[:8000]
    cands_text = ""
    for i, c in enumerate(candidatos[:15], 1):
        score_str = f"{c.score_fit}%" if c.score_fit is not None else "não calculado"
        comps = ", ".join(str(x) for x in (c.competencias or [])[:12]) or "não especificadas"
        form = "; ".join(str(x) for x in (c.formacao or [])) or "não especificada"
        idiomas = ", ".join(str(x) for x in (c.idiomas or [])) or "não especificados"
        cands_text += (
            f"{i}. {c.nome} | Score: {score_str} | "
            f"Experiência: {c.experiencia_anos or 0} anos\n"
            f"   Formação: {form}\n"
            f"   Competências: {comps}\n"
            f"   Idiomas: {idiomas}\n"
        )
        if c.resumo:
            cands_text += f"   Resumo: {c.resumo[:500]}\n"
        av = c.avaliacao_criterios or {}
        if av.get("criterios"):
            cands_text += "   Avaliação por critério (fonte de verdade):\n"
            for lc in av["criterios"]:
                tag = "ESSENCIAL" if lc.get("essencial") else "desejável"
                cands_text += f"     - {lc['criterio']} [{tag}]: {lc['resultado']}"
                if lc.get("evidencia"):
                    cands_text += f' — evidência: "{lc["evidencia"][:160]}"'
                cands_text += "\n"
            if av.get("essenciais_falhados"):
                cands_text += f"   CRITÉRIOS ESSENCIAIS EM FALTA: {'; '.join(av['essenciais_falhados'])}\n"
    prompt = f"""És um especialista em recursos humanos. Analisa os candidatos abaixo face aos Termos de Referência e redige um relatório narrativo em português europeu/moçambicano.

POSIÇÃO: {vaga.titulo}{f' — {vaga.organizacao}' if vaga.organizacao else ''}

TERMOS DE REFERÊNCIA (extracto):
{tor_excerpt if tor_excerpt else 'Ver campos estruturados abaixo.'}

COMPETÊNCIAS REQUERIDAS: {', '.join(vaga.competencias_requeridas or [])}
FORMAÇÃO MÍNIMA: {vaga.nivel_formacao or 'não especificada'}
EXPERIÊNCIA MÍNIMA: {vaga.anos_experiencia_min or 0} anos

CANDIDATOS AVALIADOS:
{cands_text}

CRITÉRIO DE APURAMENTO: são apurados para a fase seguinte os candidatos com score igual ou superior a {SCORE_APURADO_MIN}% E sem nenhum critério essencial em falta. Um candidato com critério essencial em falta não é apurado, independentemente do score.
Quando existe "Avaliação por critério", ela é a fonte de verdade: a narrativa tem de ser consistente com esses resultados e citar a evidência quando relevante.

Redige um relatório narrativo com as seguintes secções (usa headings em Markdown):
## Resumo do Processo
## Análise dos Candidatos
(para cada candidato: 2-3 frases sobre adequação ao ToR, pontos fortes e limitações)
## Candidatos Apurados
(lista apenas os candidatos com score >= {SCORE_APURADO_MIN}%. Se nenhum atingir o mínimo, indica-o explicitamente.)
## Conclusão

Escreve de forma objectiva, profissional e concisa. Não repitas os scores — integra-os na narrativa.

IMPORTANTE: baseia-te apenas nos dados acima. Se um campo estiver marcado como "não especificada"/"não especificados", isso significa que não foi extraído do CV — descreve-o como "não consta do CV" e nunca como uma falha ou lacuna do candidato. Não afirmes que falta informação sobre campos que estão preenchidos."""
    try:
        from core.llm import get_llm_response
        resultado = get_llm_response(prompt)
        if resultado and len(resultado.strip()) > 100:
            return resultado.strip()
    except Exception:
        pass
    # Deterministic fallback
    apurados = _apurados(candidatos)
    linhas = [
        f"## Resumo do Processo\n\nForam avaliados {len(candidatos)} candidato(s) para a posição de **{vaga.titulo}**.",
        f"\n## Análise dos Candidatos\n",
    ]
    for c in candidatos:
        score_str = f"{c.score_fit}%" if c.score_fit is not None else "score não calculado"
        form = "; ".join(str(x) for x in (c.formacao or [])) or "não consta do CV"
        texto = (
            f"**{c.nome}** obteve um score de {score_str}, com {c.experiencia_anos or 0} anos "
            f"de experiência. Formação: {form}."
        )
        av = c.avaliacao_criterios or {}
        if av.get("criterios"):
            n_ok = sum(1 for lc in av["criterios"] if lc["resultado"] == "cumpre")
            texto += f" Cumpre {n_ok} de {len(av['criterios'])} critérios da grelha."
            if av.get("essenciais_falhados"):
                texto += f" Critérios essenciais em falta: {'; '.join(av['essenciais_falhados'])}."
        linhas.append(texto)
    if apurados:
        nomes = ", ".join(f"**{c.nome}** ({c.score_fit}%)" for c in apurados)
        linhas.append(
            f"\n## Candidatos Apurados\n\nCom score igual ou superior a {SCORE_APURADO_MIN}%: {nomes}."
        )
        linhas.append(
            f"\n## Conclusão\n\nRecomenda-se a progressão de {len(apurados)} candidato(s) "
            f"para a fase seguinte do processo de selecção."
        )
    else:
        linhas.append(
            f"\n## Candidatos Apurados\n\nNenhum candidato atingiu o score mínimo de {SCORE_APURADO_MIN}%."
        )
        linhas.append(
            "\n## Conclusão\n\nNão há candidatos apurados para a fase seguinte. "
            "Recomenda-se alargar a pesquisa ou rever os critérios da posição."
        )
    return "\n\n".join(linhas)
