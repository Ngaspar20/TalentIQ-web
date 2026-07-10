import os
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import Candidato


def org_candidatos(request):
    return Candidato.objects.filter(organisation=request.user.organisation)


def candidato_list(request):
    candidatos = org_candidatos(request).select_related("vaga").order_by("-created_at")
    return render(request, "candidatos/list.html", {"candidatos": candidatos})


def candidato_create(request):
    from vagas.models import Vaga
    if request.method == "POST":
        vaga_id = request.POST.get("vaga_id", "").strip()
        nome = request.POST.get("nome", "").strip()
        if not nome:
            messages.error(request, "O nome do candidato Ã© obrigatÃ³rio.")
            vagas = Vaga.objects.filter(organisation=request.user.organisation, estado="Aberta")
            return render(request, "candidatos/create.html", {"vagas": vagas})

        import json
        competencias_raw = request.POST.get("competencias_input", "")
        competencias = [c.strip().lower() for c in competencias_raw.split(",") if c.strip()]

        formacao_raw = request.POST.get("formacao_input", "")
        formacao = [f.strip() for f in formacao_raw.splitlines() if f.strip()]

        idiomas_raw = request.POST.get("idiomas_input", "")
        idiomas = [i.strip() for i in idiomas_raw.split(",") if i.strip()]

        vaga = None
        if vaga_id:
            try:
                vaga = Vaga.objects.get(pk=vaga_id, organisation=request.user.organisation)
            except Vaga.DoesNotExist:
                pass

        candidato = Candidato.objects.create(
            organisation=request.user.organisation,
            vaga=vaga,
            nome=nome,
            email=request.POST.get("email", "").strip(),
            telefone=request.POST.get("telefone", "").strip(),
            experiencia_anos=int(request.POST.get("experiencia_anos", 0) or 0),
            competencias=competencias,
            formacao=formacao,
            idiomas=idiomas,
            resumo=request.POST.get("resumo", "").strip(),
            notas=request.POST.get("notas", "").strip(),
            created_by=request.user,
        )
        messages.success(request, f"Candidato '{candidato.nome}' adicionado com sucesso!")
        return redirect("candidato_list")

    vagas = Vaga.objects.filter(organisation=request.user.organisation, estado="Aberta")
    return render(request, "candidatos/create.html", {"vagas": vagas})


def candidato_detail(request, pk):
    candidato = get_object_or_404(org_candidatos(request), pk=pk)
    return render(request, "candidatos/detail.html", {"candidato": candidato})


def candidato_edit(request, pk):
    from vagas.models import Vaga
    candidato = get_object_or_404(org_candidatos(request), pk=pk)
    vagas = Vaga.objects.filter(organisation=request.user.organisation).order_by("titulo")
    if request.method == "POST":
        nome = request.POST.get("nome", "").strip()
        if not nome:
            messages.error(request, "O nome do candidato Ã© obrigatÃ³rio.")
            return render(request, "candidatos/edit.html", {"candidato": candidato, "vagas": vagas})

        competencias_raw = request.POST.get("competencias_input", "")
        competencias = [c.strip().lower() for c in competencias_raw.split(",") if c.strip()]

        formacao_raw = request.POST.get("formacao_input", "")
        formacao = [f.strip() for f in formacao_raw.splitlines() if f.strip()]

        idiomas_raw = request.POST.get("idiomas_input", "")
        idiomas = [i.strip() for i in idiomas_raw.split(",") if i.strip()]

        vaga_id = request.POST.get("vaga_id", "").strip()
        if vaga_id:
            try:
                candidato.vaga = Vaga.objects.get(pk=vaga_id, organisation=request.user.organisation)
            except Vaga.DoesNotExist:
                candidato.vaga = None
        else:
            candidato.vaga = None

        candidato.nome = nome
        candidato.email = request.POST.get("email", "").strip()
        candidato.telefone = request.POST.get("telefone", "").strip()
        candidato.experiencia_anos = int(request.POST.get("experiencia_anos", 0) or 0)
        candidato.etapa = request.POST.get("etapa", "Candidatura Recebida")
        candidato.competencias = competencias
        candidato.formacao = formacao
        candidato.idiomas = idiomas
        candidato.resumo = request.POST.get("resumo", "").strip()
        candidato.notas = request.POST.get("notas", "").strip()
        candidato.save()
        messages.success(request, f"Candidato '{candidato.nome}' actualizado.")
        return redirect("candidato_detail", pk=candidato.pk)

    return render(request, "candidatos/edit.html", {"candidato": candidato, "vagas": vagas})


def candidato_delete(request, pk):
    candidato = get_object_or_404(org_candidatos(request), pk=pk)
    if request.method == "POST":
        candidato.delete()
        messages.success(request, f"Candidato '{candidato.nome}' eliminado.")
        return redirect("candidato_list")
    return render(request, "candidatos/confirm_delete.html", {"candidato": candidato})


CARTA_TIPOS = {
    "triagem_exclusao": "Screening Exclusion Letter",
    "pre_selecao": "Pre-Selection Letter",
    "pos_entrevista_rejeicao": "Post-Interview Rejection Letter",
    "oferta": "Offer Letter",
}


def _gerar_texto_carta(tipo, nome, vaga, org):
    from core.llm import get_llm_response

    prompts = {
        "triagem_exclusao": f"Write a professional, warm screening exclusion letter for {nome} who applied for the position of {vaga} at {org}. They were not selected for interview. Be respectful, appreciative, and concise (3 paragraphs). Write only the letter body starting with 'Dear {nome},'.",
        "pre_selecao": f"Write a professional pre-selection letter inviting {nome} for an interview for the position of {vaga} at {org}. Congratulate them, mention HR will follow up with interview details. Be warm and concise (2-3 paragraphs). Write only the letter body starting with 'Dear {nome},'.",
        "pos_entrevista_rejeicao": f"Write a professional post-interview rejection letter for {nome} who was interviewed for {vaga} at {org}. Thank them for attending, acknowledge their effort, inform them another candidate was selected. Be warm and respectful (3 paragraphs). Write only the letter body starting with 'Dear {nome},'.",
        "oferta": f"Write a professional offer letter for {nome} for the position of {vaga} at {org}. Congratulate them on being selected, mention HR will follow with full details. Be warm and formal (2-3 paragraphs). Write only the letter body starting with 'Dear {nome},'.",
    }
    system = "You are an HR professional writing formal employment letters. Be professional, warm and concise."
    texto = get_llm_response(prompts[tipo], system)
    if texto:
        return texto

    fallbacks = {
        "triagem_exclusao": f"Dear {nome},\n\nThank you for your application for the position of {vaga} at {org}. We appreciate the time and effort you invested in your application.\n\nAfter careful review of all applications received, we regret to inform you that you have not been selected to proceed to the interview stage. This was a difficult decision given the high number of qualified candidates who applied.\n\nWe wish you every success in your job search and hope you will consider applying for future opportunities with us.\n\nYours sincerely,\n\nHuman Resources\n{org}",
        "pre_selecao": f"Dear {nome},\n\nWe are pleased to inform you that following the review of applications for the position of {vaga} at {org}, you have been selected to proceed to the interview stage.\n\nOur HR team will contact you shortly with the interview details including date, time and format. We look forward to learning more about your experience and qualifications.\n\nThank you for your interest in joining {org}.\n\nYours sincerely,\n\nHuman Resources\n{org}",
        "pos_entrevista_rejeicao": f"Dear {nome},\n\nThank you for attending the interview for the position of {vaga} at {org}. We greatly appreciate the time and effort you invested in the selection process.\n\nAfter careful deliberation, we have decided to proceed with another candidate whose profile more closely matched the specific requirements of the role. This was a difficult decision given the strong candidates we had the pleasure of interviewing.\n\nWe encourage you to apply for future opportunities with {org} and wish you every success in your career.\n\nYours sincerely,\n\nHuman Resources\n{org}",
        "oferta": f"Dear {nome},\n\nOn behalf of {org}, it is our great pleasure to offer you the position of {vaga}. Following a thorough selection process, the selection committee agreed that your profile and experience make you the ideal candidate for this role.\n\nOur HR team will be in touch shortly with the full details of the offer including terms, conditions and start date.\n\nWe look forward to welcoming you to the team.\n\nYours sincerely,\n\nHuman Resources\n{org}",
    }
    return fallbacks[tipo]


def gerar_carta(request, pk):
    candidato = get_object_or_404(org_candidatos(request), pk=pk)
    tipo = request.GET.get("tipo", "")
    if tipo not in CARTA_TIPOS:
        return redirect("candidato_detail", pk=pk)

    nome = candidato.nome
    vaga = candidato.vaga.titulo if candidato.vaga else "the advertised position"
    org = candidato.organisation.name if hasattr(candidato, 'organisation') and candidato.organisation else "our organisation"

    texto = _gerar_texto_carta(tipo, nome, vaga, org)
    request.session[f"carta_{tipo}_{pk}"] = texto

    return render(request, "candidatos/carta_preview.html", {
        "candidato": candidato,
        "tipo": tipo,
        "tipo_label": CARTA_TIPOS[tipo],
        "texto": texto,
    })


def download_carta(request, pk):
    candidato = get_object_or_404(org_candidatos(request), pk=pk)
    tipo = request.GET.get("tipo", "")
    texto = request.POST.get("texto", "") or request.session.get(f"carta_{tipo}_{pk}", "")

    if not texto or tipo not in CARTA_TIPOS:
        return redirect("candidato_detail", pk=pk)

    from docx import Document as DocxDocument
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    import io
    from datetime import date

    doc = DocxDocument()
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1.2)
    section.right_margin = Inches(1.2)

    org_name = candidato.organisation.name if candidato.organisation else "Organisation"

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run(org_name)
    run.bold = True
    run.font.size = Pt(12)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.add_run(date.today().strftime("%d %B %Y")).font.size = Pt(11)

    doc.add_paragraph()

    vaga_titulo = candidato.vaga.titulo if candidato.vaga else "Position"
    p = doc.add_paragraph()
    run = p.add_run(f"Re: {vaga_titulo}")
    run.bold = True
    run.font.size = Pt(11)

    doc.add_paragraph()

    for line in texto.split('\n'):
        p = doc.add_paragraph(line if line.strip() else "")
        p.paragraph_format.space_after = Pt(4)
        for run in p.runs:
            run.font.size = Pt(11)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    safe_name = candidato.nome.replace(' ', '_')
    filename = f"{tipo}_{safe_name}.docx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@require_POST
def parse_cv_view(request):
    """HTMX â€” extracts text from uploaded CV file and returns preview."""
    uploaded = request.FILES.get("cv_file")
    if not uploaded:
        return HttpResponse('<div class="alert-error">Nenhum ficheiro recebido.</div>')

    try:
        from core.parser import extract_text_from_file
        texto = extract_text_from_file(uploaded)
    except Exception as e:
        return HttpResponse(f'<div class="alert-error">Erro ao extrair texto: {e}</div>')

    if not texto.strip():
        return HttpResponse('<div class="alert-error">NÃ£o foi possÃ­vel extrair texto. O ficheiro pode ser uma imagem digitalizada.</div>')

    return render(request, "candidatos/_cv_preview.html", {
        "texto": texto[:4000],
        "texto_completo": texto,
    })


@require_POST
def analyse_cv_view(request):
    """HTMX â€” sends CV text to Grok and returns pre-filled candidate form."""
    from django.conf import settings
    texto = request.POST.get("texto_completo", "")
    if not texto.strip():
        return HttpResponse('<div class="alert-error">Texto nÃ£o encontrado. Carregue o CV novamente.</div>')

    try:
        os.environ["GROK_API_KEY"] = settings.GROK_API_KEY
        os.environ["LLM_ENGINE"] = settings.LLM_ENGINE

        from core.parser import parse_cv
        extraido = parse_cv(texto)
    except Exception as e:
        return HttpResponse(f'<div class="alert-error">Erro na anÃ¡lise IA: {e}</div>')

    return render(request, "candidatos/_cv_form_fields.html", {
        "cv": extraido,
        "metodo": extraido.get("metodo_extracao", "IA"),
    })

