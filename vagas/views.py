import json
import sys
import os
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import Vaga

# Make sure core/ is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def org_vagas(request):
    return Vaga.objects.filter(organisation=request.user.organisation)


def vaga_list(request):
    vagas = org_vagas(request).order_by("-created_at")
    return render(request, "vagas/list.html", {"vagas": vagas})


def vaga_create(request):
    if request.method == "POST":
        titulo = request.POST.get("titulo", "").strip()
        if not titulo:
            messages.error(request, "O tÃ­tulo da vaga Ã© obrigatÃ³rio.")
            return render(request, "vagas/create.html")

        competencias_raw = request.POST.get("competencias_input", "")
        competencias = [c.strip().lower() for c in competencias_raw.split(",") if c.strip()]

        responsabilidades_raw = request.POST.get("responsabilidades_input", "")
        responsabilidades = [r.strip().lstrip("â€¢").strip() for r in responsabilidades_raw.splitlines() if r.strip()]

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
            competencias_requeridas=competencias,
            responsabilidades=responsabilidades,
            descricao=request.POST.get("descricao", "").strip(),
            origem="Manual",
            created_by=request.user,
        )
        messages.success(request, f"Vaga '{vaga.titulo}' criada com sucesso!")
        return redirect("vaga_list")

    return render(request, "vagas/create.html")


def vaga_detail(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    return render(request, "vagas/detail.html", {"vaga": vaga})


def vaga_edit(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    if request.method == "POST":
        titulo = request.POST.get("titulo", "").strip()
        if not titulo:
            messages.error(request, "O tÃ­tulo da vaga Ã© obrigatÃ³rio.")
            return render(request, "vagas/edit.html", {"vaga": vaga})

        competencias_raw = request.POST.get("competencias_input", "")
        competencias = [c.strip().lower() for c in competencias_raw.split(",") if c.strip()]

        responsabilidades_raw = request.POST.get("responsabilidades_input", "")
        responsabilidades = [r.strip().lstrip("â€¢").strip() for r in responsabilidades_raw.splitlines() if r.strip()]

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
        vaga.competencias_requeridas = competencias
        vaga.responsabilidades = responsabilidades
        vaga.descricao = request.POST.get("descricao", "").strip()
        vaga.save()
        messages.success(request, f"Vaga '{vaga.titulo}' actualizada.")
        return redirect("vaga_detail", pk=vaga.pk)

    return render(request, "vagas/edit.html", {"vaga": vaga})


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
    HTMX endpoint â€” called when user uploads a ToR file.
    Step 1: extract text and return preview.
    """
    from django.conf import settings
    uploaded = request.FILES.get("tor_file")
    if not uploaded:
        return HttpResponse('<div class="alert-error">Nenhum ficheiro recebido.</div>')

    try:
        from core.parser import extract_text_from_file
        texto = extract_text_from_file(uploaded)
    except Exception as e:
        return HttpResponse(f'<div class="alert-error">Erro ao extrair texto: {e}</div>')

    if not texto.strip():
        return HttpResponse('<div class="alert-error">NÃ£o foi possÃ­vel extrair texto. O ficheiro pode ser uma imagem digitalizada.</div>')

    # Return the text preview + hidden field + AI analysis button
    texto_preview = texto[:4000]
    return render(request, "vagas/_tor_preview.html", {
        "texto": texto_preview,
        "texto_completo": texto,
    })


@require_POST
def analyse_tor_view(request):
    """
    HTMX endpoint â€” called when user clicks 'Analisar com IA'.
    Sends text to Grok and returns pre-filled form fields.
    """
    from django.conf import settings
    texto = request.POST.get("texto_completo", "")
    if not texto.strip():
        return HttpResponse('<div class="alert-error">Texto nÃ£o encontrado. Carregue o ficheiro novamente.</div>')

    try:
        os.environ["GROK_API_KEY"] = settings.GROK_API_KEY
        os.environ["LLM_ENGINE"] = settings.LLM_ENGINE

        from core.parser import parse_tor
        extraido = parse_tor(texto)
    except Exception as e:
        return HttpResponse(f'<div class="alert-error">Erro na anÃ¡lise IA: {e}</div>')

    return render(request, "vagas/_form_fields.html", {
        "tor": extraido,
        "metodo": extraido.get("metodo_extracao", "IA"),
    })


def gerar_perguntas_entrevista(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)

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

Organiza as perguntas nas seguintes categorias:
1. Apresentacao e motivacao (3 perguntas)
2. Experiencia e historial profissional (4 perguntas)
3. Competencias tecnicas especificas ao cargo (4 perguntas)
4. Competencias comportamentais e trabalho em equipa (3 perguntas)
5. Situacoes hipoteticas e resolucao de problemas (3 perguntas)
6. Questoes finais do candidato (mencionar que o candidato pode fazer perguntas)

Para cada pergunta inclui uma nota breve sobre o que avaliar na resposta.
Usa um formato claro e profissional adequado para imprimir e usar na sala de entrevista."""

    system = "Es um especialista em recursos humanos e seleccao de pessoal. Escreve em portugues europeu formal."
    texto = get_llm_response(prompt, system)

    if not texto:
        linhas_comp = "\n".join([f"- Demonstre conhecimento em {c}" for c in vaga.competencias_requeridas[:4]]) if vaga.competencias_requeridas else "- Competencias relevantes para o cargo"
        texto = f"""GUIAO DE PERGUNTAS DE ENTREVISTA
Cargo: {vaga.titulo}
Departamento: {vaga.departamento}

1. APRESENTACAO E MOTIVACAO
   a) Apresente-se brevemente e descreva o seu percurso profissional.
      (Avaliar: capacidade de sintese, clareza de comunicacao)
   b) O que o/a motivou a candidatar-se a este cargo na nossa organizacao?
      (Avaliar: conhecimento da organizacao, motivacao genuina)
   c) Onde se ve profissionalmente daqui a 5 anos?
      (Avaliar: ambicao, alinhamento com a organizacao)

2. EXPERIENCIA E HISTORIAL PROFISSIONAL
   a) Descreva a sua experiencia mais relevante para este cargo.
      (Avaliar: alinhamento com os requisitos da vaga)
   b) Qual foi o maior desafio profissional que enfrentou e como o resolveu?
      (Avaliar: capacidade de resolucao de problemas)
   c) Descreva um projecto do qual se orgulha particularmente.
      (Avaliar: realizacoes concretas, impacto)
   d) Porque saiu ou pretende sair do seu emprego actual?
      (Avaliar: maturidade profissional, honestidade)

3. COMPETENCIAS TECNICAS
{linhas_comp}
   a) Como avalia o seu nivel de competencia nas areas requeridas para este cargo?
      (Avaliar: auto-consciencia, honestidade)
   b) Que ferramentas e metodologias utiliza regularmente no seu trabalho?
      (Avaliar: conhecimento pratico)

4. COMPETENCIAS COMPORTAMENTAIS
   a) Como gere situacoes de conflito com colegas ou superiores?
      (Avaliar: inteligencia emocional, comunicacao)
   b) Descreva uma situacao em que teve de trabalhar sob pressao.
      (Avaliar: resistencia ao stress, organizacao)
   c) Como prefere receber feedback sobre o seu trabalho?
      (Avaliar: abertura a aprendizagem)

5. SITUACOES HIPOTETICAS
   a) Se tivesse de gerir varias tarefas urgentes em simultaneo, como procederia?
      (Avaliar: gestao de prioridades)
   b) Se discordasse de uma decisao do seu superior, como agiria?
      (Avaliar: assertividade, respeito hierarquico)
   c) Como se adaptaria rapidamente a uma mudanca inesperada de objectivos?
      (Avaliar: flexibilidade, adaptabilidade)

6. QUESTOES DO CANDIDATO
   Dar espaco ao candidato para colocar questoes sobre o cargo, a organizacao e as condicoes de trabalho.
   (Avaliar: interesse genuino, qualidade das questoes)

---
Entrevistadores: ______________________
Data: ______________________
Candidato/a: {vaga.titulo}"""

    request.session[f"perguntas_{pk}"] = texto

    return render(request, "vagas/perguntas_preview.html", {
        "vaga": vaga,
        "texto": texto,
    })


def download_perguntas(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    texto = request.POST.get("texto", "") or request.session.get(f"perguntas_{pk}", "")

    if not texto:
        return redirect("vaga_detail", pk=pk)

    from docx import Document as DocxDocument
    from docx.shared import Pt, Inches
    import io
    from datetime import date

    doc = DocxDocument()
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1.2)
    section.right_margin = Inches(1.2)

    org_name = vaga.organisation.name if vaga.organisation else "Organizacao"

    p = doc.add_paragraph()
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"GUIAO DE ENTREVISTA — {vaga.titulo.upper()}")
    run.bold = True
    run.font.size = Pt(13)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(f"{org_name} | {date.today().strftime('%d/%m/%Y')}").font.size = Pt(10)

    doc.add_paragraph()

    for line in texto.split('\n'):
        p = doc.add_paragraph(line if line.strip() else "")
        p.paragraph_format.space_after = Pt(3)
        for run in p.runs:
            run.font.size = Pt(10)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    safe_titulo = vaga.titulo.replace(' ', '_')
    filename = f"perguntas_entrevista_{safe_titulo}.docx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

