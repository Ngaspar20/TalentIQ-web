import os
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from vagas.models import Vaga
from candidatos.models import Candidato


def scoring_view(request):
    vagas = Vaga.objects.filter(organisation=request.user.organisation).order_by("-created_at")
    vaga_sel = None
    candidatos = []

    vaga_id = request.GET.get("vaga")
    if vaga_id:
        try:
            vaga_sel = Vaga.objects.get(pk=vaga_id, organisation=request.user.organisation)
            candidatos = Candidato.objects.filter(vaga=vaga_sel).order_by("-score_fit")
        except Vaga.DoesNotExist:
            pass

    sem_vaga_count = Candidato.objects.filter(
        organisation=request.user.organisation, vaga__isnull=True
    ).count()

    return render(request, "scoring/scoring.html", {
        "vagas": vagas,
        "vaga_sel": vaga_sel,
        "candidatos": candidatos,
        "sem_vaga_count": sem_vaga_count,
    })


def scoring_vaga(request, vaga_id):
    vaga = get_object_or_404(Vaga, pk=vaga_id, organisation=request.user.organisation)
    candidatos = Candidato.objects.filter(vaga=vaga).order_by("-score_fit")
    return redirect(f"/scoring/?vaga={vaga_id}")


@require_POST
def score_calculate(request):
    """Calculate fit score for one or all candidates of a vaga."""
    from django.conf import settings
    vaga_id = request.POST.get("vaga_id")
    candidato_id = request.POST.get("candidato_id")

    try:
        vaga = get_object_or_404(Vaga, pk=vaga_id, organisation=request.user.organisation)
    except Exception:
        return HttpResponse('<div class="alert-error">Vaga nao encontrada.</div>')

    os.environ["GROK_API_KEY"] = settings.GROK_API_KEY
    os.environ["LLM_ENGINE"] = settings.LLM_ENGINE

    from core.scorer import calcular_fit

    vaga_dict = {
        "titulo": vaga.titulo,
        "competencias_requeridas": vaga.competencias_requeridas or [],
        "anos_experiencia_min": vaga.anos_experiencia_min,
        "nivel_formacao": vaga.nivel_formacao,
        "responsabilidades": vaga.responsabilidades or [],
    }

    if candidato_id:
        qs = Candidato.objects.filter(pk=candidato_id, organisation=request.user.organisation)
    else:
        qs = Candidato.objects.filter(vaga=vaga, organisation=request.user.organisation)

    import logging
    log = logging.getLogger(__name__)
    from core.scorer import _score_deterministic

    for candidato in qs:
        cand_dict = {
            "nome": candidato.nome,
            "competencias": candidato.competencias or [],
            "experiencia_anos": candidato.experiencia_anos or 0,
            "formacao": candidato.formacao or [],
            "idiomas": candidato.idiomas or [],
            "resumo": candidato.resumo or "",
        }
        try:
            resultado = _score_deterministic(cand_dict, vaga_dict)
            resultado["metodo"] = "Deterministico"
            candidato.score_fit = resultado.get("score_total", 0)
            candidato.perfil_completo = resultado
            candidato.save(update_fields=["score_fit", "perfil_completo"])
        except Exception as e:
            log.error(f"Score error for {candidato.nome}: {e}", exc_info=True)

    return redirect(f"/scoring/?vaga={vaga_id}")


def exportar_excel(request):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    vaga_id = request.GET.get("vaga")
    vaga = get_object_or_404(Vaga, pk=vaga_id, organisation=request.user.organisation)
    candidatos = Candidato.objects.filter(vaga=vaga).order_by("-score_fit")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ranking de Candidatos"

    # Styles
    header_fill = PatternFill("solid", fgColor="1D4ED8")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    title_font = Font(bold=True, size=14, color="1D4ED8")
    bold = Font(bold=True)
    center = Alignment(horizontal="center", vertical="center")
    thin = Side(style="thin", color="E2E8F0")
    border = Border(top=thin, bottom=thin, left=thin, right=thin)

    # Title block
    ws.merge_cells("A1:H1")
    ws["A1"] = f"Ranking de Candidatos - {vaga.titulo}"
    ws["A1"].font = title_font
    ws["A2"] = f"Organizacao: {vaga.organizacao or '-'}   |   Local: {vaga.local or '-'}   |   Candidatos: {candidatos.count()}"
    ws["A2"].font = Font(size=10, color="64748B")
    ws.append([])

    # Headers
    headers = ["#", "Nome", "Email", "Experiencia (anos)", "Score Total", "Competencias /50", "Experiencia /30", "Formacao /20", "Alinhamento", "Etapa Pipeline"]
    ws.append(headers)
    header_row = ws.max_row
    for col, _ in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        cell.border = border

    # Data rows
    alt_fill = PatternFill("solid", fgColor="F8FAFC")
    green_fill = PatternFill("solid", fgColor="F0FDF4")
    for i, c in enumerate(candidatos, 1):
        det = c.perfil_completo or {}
        pts = det.get("pontuacao_detalhada") or {}
        row = [
            i,
            c.nome,
            c.email or "",
            c.experiencia_anos or 0,
            c.score_fit if c.score_fit is not None else "",
            pts.get("competencias", ""),
            pts.get("experiencia", ""),
            pts.get("formacao", ""),
            det.get("nivel_alinhamento", ""),
            c.etapa,
        ]
        ws.append(row)
        data_row = ws.max_row
        row_fill = green_fill if i == 1 else (alt_fill if i % 2 == 0 else None)
        for col in range(1, len(row) + 1):
            cell = ws.cell(row=data_row, column=col)
            cell.border = border
            cell.alignment = Alignment(vertical="center")
            if row_fill:
                cell.fill = row_fill
            if col == 5 and c.score_fit is not None:
                if c.score_fit >= 75:
                    cell.font = Font(bold=True, color="15803D")
                elif c.score_fit >= 50:
                    cell.font = Font(bold=True, color="92400E")
                else:
                    cell.font = Font(bold=True, color="DC2626")

    # Column widths
    widths = [5, 30, 30, 20, 14, 18, 18, 14, 18, 22]
    for col, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = w

    ws.row_dimensions[header_row].height = 20

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="ranking_{vaga.titulo[:30]}.xlsx"'
    wb.save(response)
    return response


def exportar_word(request):
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    import datetime

    vaga_id = request.GET.get("vaga")
    vaga = get_object_or_404(Vaga, pk=vaga_id, organisation=request.user.organisation)
    candidatos = list(Candidato.objects.filter(vaga=vaga).order_by("-score_fit"))

    doc = Document()

    # Page margins
    for section in doc.sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(3)
        section.right_margin = Cm(2.5)

    def set_color(run, hex_color):
        run.font.color.rgb = RGBColor(
            int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        )

    def add_heading(text, level=1, color="1D4ED8"):
        p = doc.add_heading(text, level=level)
        for run in p.runs:
            run.font.color.rgb = RGBColor(
                int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
            )
        return p

    def add_hr(doc):
        p = doc.add_paragraph()
        pPr = p._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), "CBD5E1")
        pBdr.append(bottom)
        pPr.append(pBdr)
        p.paragraph_format.space_after = Pt(6)

    # â"€â"€ Cover / Title â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    title = doc.add_heading("", 0)
    title_run = title.add_run("Relatorio de Selecao de Candidatos")
    title_run.font.size = Pt(20)
    title_run.font.bold = True
    set_color(title_run, "1D4ED8")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run(f"{vaga.titulo}")
    r.font.size = Pt(14)
    r.font.bold = True

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta_text = f"Data: {datetime.date.today().strftime('%d/%m/%Y')}   |   Candidatos avaliados: {len(candidatos)}"
    if vaga.organizacao:
        meta_text = f"{vaga.organizacao}   |   " + meta_text
    r2 = meta.add_run(meta_text)
    r2.font.size = Pt(10)
    set_color(r2, "64748B")

    add_hr(doc)

    # 1. Sumario Executivo
    add_heading("1. Sumario Executivo", level=1)
    scored = [c for c in candidatos if c.score_fit is not None]
    alto = [c for c in scored if c.score_fit >= 75]
    medio = [c for c in scored if 50 <= c.score_fit < 75]
    baixo = [c for c in scored if c.score_fit < 50]

    if scored:
        top = scored[0]
        p = doc.add_paragraph()
        p.add_run(f"Foram avaliados {len(candidatos)} candidato(s) para a vaga de ").font.size = Pt(11)
        b = p.add_run(f"{vaga.titulo}")
        b.bold = True; b.font.size = Pt(11)
        p.add_run(f". {len(alto)} candidato(s) apresentam alinhamento Alto (>=75), {len(medio)} Medio (50-74) e {len(baixo)} Baixo (<50).").font.size = Pt(11)

        p2 = doc.add_paragraph()
        p2.add_run("Candidato mais recomendado: ").font.size = Pt(11)
        b2 = p2.add_run(f"{top.nome} (Score: {top.score_fit}/100)")
        b2.bold = True; b2.font.size = Pt(11)
        det_top = top.perfil_completo or {}
        if det_top.get("explicacao"):
            p2.add_run(f" - {det_top['explicacao'][0] if det_top['explicacao'] else ''}").font.size = Pt(11)
    else:
        doc.add_paragraph("Nenhum candidato foi avaliado com score de fit. Execute o calculo de scores antes de exportar o relatorio.").font.size = Pt(11)

    add_hr(doc)

    # 2. Perfil da Vaga
    add_heading("2. Perfil da Vaga", level=1)
    table_vaga = doc.add_table(rows=0, cols=2)
    table_vaga.style = "Table Grid"

    def add_vaga_row(label, value):
        if not value:
            return
        row = table_vaga.add_row()
        row.cells[0].text = label
        row.cells[0].paragraphs[0].runs[0].bold = True
        row.cells[0].paragraphs[0].runs[0].font.size = Pt(10)
        row.cells[1].text = str(value)
        row.cells[1].paragraphs[0].runs[0].font.size = Pt(10)
        row.cells[0].width = Cm(5)

    add_vaga_row("Titulo", vaga.titulo)
    add_vaga_row("Organizacao", vaga.organizacao)
    add_vaga_row("Localizacao", vaga.local)
    add_vaga_row("Departamento", vaga.departamento)
    add_vaga_row("Modalidade", vaga.modalidade)
    add_vaga_row("Tipo de Contrato", vaga.tipo_contrato)
    add_vaga_row("Formacao Minima", vaga.nivel_formacao)
    add_vaga_row("Experiencia Minima", f"{vaga.anos_experiencia_min} anos" if vaga.anos_experiencia_min else None)
    add_vaga_row("Prazo", vaga.prazo_candidatura)
    if vaga.competencias_requeridas:
        add_vaga_row("Competencias Requeridas", ", ".join(vaga.competencias_requeridas))

    add_hr(doc)

    # 3. Ranking Geral
    add_heading("3. Ranking Geral de Candidatos", level=1)

    if candidatos:
        t = doc.add_table(rows=1, cols=6)
        t.style = "Table Grid"
        headers = ["#", "Nome", "Score", "Competencias", "Experiencia", "Formacao"]
        for i, h in enumerate(headers):
            cell = t.rows[0].cells[i]
            cell.text = h
            run = cell.paragraphs[0].runs[0]
            run.bold = True
            run.font.size = Pt(10)
            set_color(run, "FFFFFF")
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), "1D4ED8")
            tcPr.append(shd)

        for i, c in enumerate(candidatos, 1):
            det = c.perfil_completo or {}
            pts = det.get("pontuacao_detalhada") or {}
            row = t.add_row()
            vals = [
                str(i),
                c.nome,
                f"{c.score_fit}/100" if c.score_fit is not None else "-",
                f"{pts.get('competencias', '-')}/50",
                f"{pts.get('experiencia', '-')}/30",
                f"{pts.get('formacao', '-')}/20",
            ]
            for j, v in enumerate(vals):
                row.cells[j].text = v
                run = row.cells[j].paragraphs[0].runs[0]
                run.font.size = Pt(10)
                if j == 2 and c.score_fit is not None:
                    run.bold = True
                    if c.score_fit >= 75:
                        set_color(run, "15803D")
                    elif c.score_fit >= 50:
                        set_color(run, "92400E")
                    else:
                        set_color(run, "DC2626")
    else:
        doc.add_paragraph("Sem candidatos avaliados.")

    add_hr(doc)

    # 4. Analise Individual
    add_heading("4. Analise Individual por Candidato", level=1)

    for i, c in enumerate(candidatos, 1):
        det = c.perfil_completo or {}
        pts = det.get("pontuacao_detalhada") or {}

        p_name = doc.add_heading("", level=2)
        r_rank = p_name.add_run(f"{i}. {c.nome}")
        r_rank.font.size = Pt(13)
        set_color(r_rank, "1E293B")

        score_p = doc.add_paragraph()
        score_p.paragraph_format.space_after = Pt(4)
        if c.score_fit is not None:
            r_score = score_p.add_run(f"Score Fit: {c.score_fit}/100")
            r_score.bold = True
            r_score.font.size = Pt(11)
            color = "15803D" if c.score_fit >= 75 else ("92400E" if c.score_fit >= 50 else "DC2626")
            set_color(r_score, color)
            nivel = det.get("nivel_alinhamento", "")
            if nivel:
                r_niv = score_p.add_run(f"   [{nivel}]")
                r_niv.font.size = Pt(10)
                set_color(r_niv, color)
        else:
            score_p.add_run("Score Fit: Nao calculado").font.size = Pt(11)

        if pts:
            breakdown = doc.add_paragraph()
            breakdown.paragraph_format.space_after = Pt(2)
            b_run = breakdown.add_run(
                f"Competencias: {pts.get('competencias','-')}/50   |   "
                f"Experiencia: {pts.get('experiencia','-')}/30   |   "
                f"Formacao: {pts.get('formacao','-')}/20"
            )
            b_run.font.size = Pt(10)
            set_color(b_run, "475569")

        info_parts = []
        if c.email:
            info_parts.append(f"Email: {c.email}")
        if c.telefone:
            info_parts.append(f"Tel: {c.telefone}")
        if c.experiencia_anos:
            info_parts.append(f"Experiencia: {c.experiencia_anos} anos")
        if c.etapa:
            info_parts.append(f"Pipeline: {c.etapa}")
        if info_parts:
            info_p = doc.add_paragraph("   |   ".join(info_parts))
            info_p.runs[0].font.size = Pt(10)
            set_color(info_p.runs[0], "64748B")

        if c.competencias:
            skill_p = doc.add_paragraph()
            skill_r = skill_p.add_run("Competencias: ")
            skill_r.bold = True
            skill_r.font.size = Pt(10)
            skill_p.add_run(", ".join(c.competencias)).font.size = Pt(10)

        if c.formacao:
            form_p = doc.add_paragraph()
            form_r = form_p.add_run("Formacao: ")
            form_r.bold = True
            form_r.font.size = Pt(10)
            form_p.add_run(" / ".join(c.formacao)).font.size = Pt(10)

        if c.resumo:
            sum_p = doc.add_paragraph()
            sum_r = sum_p.add_run("Resumo Profissional: ")
            sum_r.bold = True
            sum_r.font.size = Pt(10)
            sum_p.add_run(c.resumo[:600]).font.size = Pt(10)

        explicacao = det.get("explicacao") or []
        if explicacao:
            expl_head = doc.add_paragraph()
            expl_r = expl_head.add_run("Analise de Alinhamento:")
            expl_r.bold = True
            expl_r.font.size = Pt(10)
            set_color(expl_r, "1D4ED8")
            for note in explicacao:
                p_note = doc.add_paragraph(style="List Bullet")
                p_note.add_run(note).font.size = Pt(10)
                p_note.paragraph_format.space_after = Pt(1)

        rec_p = doc.add_paragraph()
        rec_r = rec_p.add_run("Recomendacao: ")
        rec_r.bold = True
        rec_r.font.size = Pt(10)
        if c.score_fit is not None:
            if c.score_fit >= 75:
                rec_text = "Candidato altamente recomendado para avancar no processo de selecao. O perfil demonstra forte alinhamento com os requisitos da vaga."
            elif c.score_fit >= 50:
                rec_text = "Candidato com alinhamento moderado. Recomenda-se entrevista para verificar competencias especificas nao confirmadas pelo CV."
            else:
                rec_text = "Candidato com baixo alinhamento com os requisitos da vaga. Considerar apenas se houver escassez de outros candidatos."
        else:
            rec_text = "Score nao calculado. Execute a analise para obter uma recomendacao fundamentada."
        rec_p.add_run(rec_text).font.size = Pt(10)

        if i < len(candidatos):
            doc.add_paragraph()
            add_hr(doc)

    add_hr(doc)

    # 5. Conclusao e Proximos Passos
    add_heading("5. Conclusao e Proximos Passos", level=1)
    conc = doc.add_paragraph()
    conc.add_run(
        f"Com base na analise de {len(candidatos)} candidato(s) para a vaga de {vaga.titulo}, "
    ).font.size = Pt(11)
    if alto:
        b3 = conc.add_run(f"recomenda-se avancar com {', '.join([c.nome for c in alto[:3]])} ")
        b3.bold = True; b3.font.size = Pt(11)
        conc.add_run("para a fase de entrevistas.").font.size = Pt(11)
    else:
        conc.add_run("nenhum candidato atingiu o limiar de alta recomendacao (75+). Considere alargar o processo de recrutamento.").font.size = Pt(11)

    steps = doc.add_paragraph()
    steps.add_run("Passos sugeridos:").bold = True
    steps.runs[0].font.size = Pt(11)
    for step in [
        "Agendar entrevistas com candidatos de score Alto (>=75)",
        "Rever candidatos de score Medio (50-74) apos entrevistas iniciais",
        "Actualizar o pipeline no TalentIQ apos cada fase de selecao",
        "Documentar feedback das entrevistas nas notas de cada candidato",
    ]:
        p_s = doc.add_paragraph(style="List Bullet")
        p_s.add_run(step).font.size = Pt(10)
        p_s.paragraph_format.space_after = Pt(2)

    footer_p = doc.add_paragraph()
    footer_p.paragraph_format.space_before = Pt(24)
    fr = footer_p.add_run(f"Relatorio gerado pelo TalentIQ - {datetime.date.today().strftime('%d/%m/%Y')}")
    fr.font.size = Pt(9)
    set_color(fr, "94A3B8")
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    import io
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    filename = f"relatorio_{vaga.titulo[:30].replace(' ', '_')}.docx"
    response = HttpResponse(
        buffer.read(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def scoring_geral(request):
    candidatos = Candidato.objects.filter(
        organisation=request.user.organisation,
    ).select_related("vaga").order_by("-score_fit")
    return render(request, "scoring/geral.html", {"candidatos": candidatos})

