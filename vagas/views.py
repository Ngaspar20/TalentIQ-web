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

Usa EXACTAMENTE este formato para cada categoria e pergunta (sem adicionar mais texto):

## APRESENTACAO E MOTIVACAO
P: [pergunta completa]
A: [o que avaliar na resposta, em 1 frase]
P: [pergunta completa]
A: [o que avaliar na resposta, em 1 frase]
P: [pergunta completa]
A: [o que avaliar na resposta, em 1 frase]

## EXPERIENCIA E HISTORIAL PROFISSIONAL
P: [pergunta completa]
A: [o que avaliar]
[mais 3 perguntas no mesmo formato]

## COMPETENCIAS TECNICAS
P: [pergunta tecnica especifica ao cargo de {vaga.titulo}]
A: [o que avaliar]
[mais 3 perguntas no mesmo formato]

## COMPETENCIAS COMPORTAMENTAIS
P: [pergunta comportamental]
A: [o que avaliar]
[mais 2 perguntas no mesmo formato]

## SITUACOES HIPOTETICAS
P: [situacao hipotetica]
A: [o que avaliar]
[mais 2 perguntas no mesmo formato]

## QUESTOES DO CANDIDATO
P: Dar espaco ao/a candidato/a para colocar questoes sobre o cargo e a organizacao.
A: Interesse genuino, qualidade e pertinencia das questoes colocadas."""

    system = "Es um especialista em recursos humanos e seleccao de pessoal. Escreve em portugues europeu formal. Segue o formato pedido rigorosamente."
    texto = get_llm_response(prompt, system)

    if not texto:
        comp_perguntas = ""
        if vaga.competencias_requeridas:
            for c in vaga.competencias_requeridas[:3]:
                comp_perguntas += f"P: Descreva a sua experiencia com {c} e como a aplicou em contexto profissional.\nA: Profundidade de conhecimento, exemplos concretos, relevancia para o cargo.\n"
        else:
            comp_perguntas = "P: Quais sao as suas principais competencias tecnicas relevantes para este cargo?\nA: Alinhamento com os requisitos, profundidade de conhecimento.\n"

        texto = f"""## APRESENTACAO E MOTIVACAO
P: Apresente-se brevemente e descreva o seu percurso profissional.
A: Capacidade de sintese, clareza de comunicacao, coerencia do percurso.
P: O que o/a motivou a candidatar-se a este cargo na nossa organizacao?
A: Conhecimento da organizacao, motivacao genuina, alinhamento de valores.
P: Onde se ve profissionalmente daqui a 5 anos?
A: Ambicao realista, alinhamento com a funcao e a organizacao.

## EXPERIENCIA E HISTORIAL PROFISSIONAL
P: Descreva a sua experiencia mais relevante para o cargo de {vaga.titulo}.
A: Alinhamento com os requisitos da vaga, profundidade e qualidade da experiencia.
P: Qual foi o maior desafio profissional que enfrentou e como o resolveu?
A: Capacidade de resolucao de problemas, resiliencia, aprendizagem com a experiencia.
P: Descreva um projecto ou realizacao profissional da qual se orgulha particularmente.
A: Realizacoes concretas, impacto mensuravel, iniciativa propria.
P: Porque saiu ou pretende sair do seu emprego actual?
A: Maturidade profissional, honestidade, ausencia de conflitos desnecessarios.

## COMPETENCIAS TECNICAS
{comp_perguntas}P: Como se mantém actualizado/a nas tendencias e novidades da sua area profissional?
A: Curiosidade intelectual, iniciativa de aprendizagem continua.

## COMPETENCIAS COMPORTAMENTAIS
P: Como gere situacoes de conflito com colegas ou superiores hierarquicos?
A: Inteligencia emocional, comunicacao assertiva, capacidade de mediar.
P: Descreva uma situacao em que teve de trabalhar sob pressao e com prazos apertados.
A: Resistencia ao stress, organizacao, capacidade de priorizar.
P: Como prefere receber feedback sobre o seu trabalho?
A: Abertura a aprendizagem, maturidade profissional, orientacao para a melhoria.

## SITUACOES HIPOTETICAS
P: Se tivesse de gerir varias tarefas urgentes em simultaneo, como procederia?
A: Gestao de prioridades, metodologia de trabalho, pedido de apoio quando necessario.
P: Se discordasse de uma decisao do seu superior hierarquico, como agiria?
A: Assertividade, respeito pela hierarquia, capacidade de argumentar construtivamente.
P: Como se adaptaria rapidamente a uma mudanca inesperada de objectivos ou prioridades?
A: Flexibilidade, adaptabilidade, atitude positiva perante a mudanca.

## QUESTOES DO CANDIDATO
P: Dar espaco ao/a candidato/a para colocar questoes sobre o cargo e a organizacao.
A: Interesse genuino, qualidade e pertinencia das questoes colocadas."""

    request.session[f"perguntas_{pk}"] = texto

    return render(request, "vagas/perguntas_preview.html", {
        "vaga": vaga,
        "texto": texto,
    })


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


def download_perguntas(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    texto = request.POST.get("texto", "") or request.session.get(f"perguntas_{pk}", "")

    if not texto:
        return redirect("vaga_detail", pk=pk)

    from docx import Document as DocxDocument
    from docx.shared import Pt, Inches, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    import io
    from datetime import date

    doc = DocxDocument()
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

    org_name = vaga.organisation.name if vaga.organisation else "Organizacao"

    # Title
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

    # Parse into structured sections
    categorias = _parse_perguntas(texto)

    # Table column widths in cm (total ~17cm for A4 with 1" margins)
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

    if not categorias:
        # Fallback: plain text if parsing found nothing
        for line in texto.split('\n'):
            p = doc.add_paragraph(line if line.strip() else "")
            for r in p.runs:
                r.font.size = Pt(10)
    else:
        for cat_name, rows in categorias:
            # Category header (full-width merged row)
            table = doc.add_table(rows=1, cols=5)
            table.style = 'Table Grid'
            table.autofit = False

            # Set widths
            for i, w in enumerate([COL_NUM, COL_PERG, COL_AVAL, COL_SCORE, COL_NOTAS]):
                table.columns[i].width = w

            # Category header row — merge all cells
            hdr_row = table.rows[0]
            hdr_row.cells[0].merge(hdr_row.cells[4])
            hdr_cell = hdr_row.cells[0]
            set_cell_bg(hdr_cell, '1E3A5F')
            cell_para(hdr_cell, cat_name, bold=True, size=10,
                      align=WD_ALIGN_PARAGRAPH.LEFT,
                      color=RGBColor(0xFF, 0xFF, 0xFF))

            # Column header row
            col_row = table.add_row()
            col_row.cells[0].width = COL_NUM
            labels = ['#', 'Pergunta', 'O que avaliar', '1–5', 'Notas']
            bg = 'D0DCF0'
            for i, label in enumerate(labels):
                set_cell_bg(col_row.cells[i], bg)
                cell_para(col_row.cells[i], label, bold=True, size=8,
                          align=WD_ALIGN_PARAGRAPH.CENTER)

            # Question rows
            for idx, (pergunta, avaliar) in enumerate(rows, 1):
                r = table.add_row()
                cell_para(r.cells[0], str(idx), align=WD_ALIGN_PARAGRAPH.CENTER)
                cell_para(r.cells[1], pergunta)
                cell_para(r.cells[2], avaliar, color=RGBColor(0x44, 0x55, 0x66))
                cell_para(r.cells[3], '', align=WD_ALIGN_PARAGRAPH.CENTER)
                cell_para(r.cells[4], '')
                # Taller notes rows
                for cell in r.cells:
                    for para in cell.paragraphs:
                        para.paragraph_format.space_before = Pt(4)
                        para.paragraph_format.space_after = Pt(4)

            doc.add_paragraph()

    # Footer note
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

